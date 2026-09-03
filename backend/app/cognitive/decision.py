"""
Decision Layer — MAUT + Intent Persistence (psychological_layer.md §3).

Intent selection uses Multi-Attribute Utility Theory (Keeney & Raiffa, 1976):
    U(Intent) = w₁·GoalAlignment + w₂·EmotionalFit + w₃·IdentityAlignment + w₄·ContextRelevance

Intent persistence uses temporal smoothing (§3.2):
    Intent_t = (1 − ρ) · Intent_{t−1} + ρ · Intent_new
    With context gating: if ContextShift > θ → hard reset
"""

import logging
from dataclasses import dataclass
from typing import Any

from ..config import Config
from ..state.adaptive_weights_store import AdaptiveWeightsStore
from .behavior_contracts import BehaviorDecision, CommunicativeIntent
from .bt import Action, Condition, NodeStatus, Selector, Sequence
from .intent_classifier import get_intent_classifier
from .json_extract import extract_first_json_value
from .perception import CognitiveEvent

logger = logging.getLogger(__name__)

# Available goals for MAUT scoring
GOALS = ["ENGAGE", "COMFORT", "INFORM", "TEASE", "PROTECT"]

_WEIGHT_KEY = "goal_utilities"


@dataclass
class ActionPlan:
    action_type: str  # e.g., "RESPOND_CHAT", "STORE_MEMORY", "BACKGROUND_CONSOLIDATION"
    payload: dict[str, Any]
    goal: str
    priority: int = 1
    # 1B: typed sibling of goal/payload -- what this turn is trying to do and
    # what it may/may not claim, before persona/policy.py's precheck
    # (pipeline.py stage 7) and action.py's realization see it. Defaulted so
    # every existing keyword/short-positional ActionPlan(...) call keeps
    # working unchanged.
    behavior_decision: BehaviorDecision | None = None


# Ordered coarsest -> warmest; _bucket_relational_stance clamps into this.
_RELATIONAL_STANCES: tuple[str, ...] = ("distant", "guarded", "neutral", "warm", "close")

# Urgency at/above this maps a turn's interruption_policy to "reflex" --
# naming, for conversational turns, the same class of "high-arousal signal
# competes for the workspace immediately" judgment
# `is_facial_reflex_interruption_worthy` already makes for vision's `startle`
# reflex, rather than reintroducing a second threshold with different logic.
_REFLEX_URGENCY_THRESHOLD = 0.75


def _bucket_relational_stance(trust: float, attachment: float, mood: float) -> str:
    """Clamp+bucket trust/attachment/mood into a named stance -- the same
    clamp-then-map shape `persona/compiler.py::_infer_temperament` uses for
    turning continuous dimension scores into bounded fields, applied here to
    pick one of `_RELATIONAL_STANCES` instead of a numeric field."""
    trust = max(0.0, min(1.0, trust))
    attachment = max(0.0, min(1.0, attachment))
    mood_unit = max(0.0, min(1.0, (mood + 1.0) / 2.0))
    score = (trust + attachment + mood_unit) / 3.0
    index = min(int(score * len(_RELATIONAL_STANCES)), len(_RELATIONAL_STANCES) - 1)
    return _RELATIONAL_STANCES[index]


def _build_communicative_intent(
    event: CognitiveEvent, blackboard: dict[str, Any]
) -> CommunicativeIntent:
    """Stage 6: derive what this turn is trying to do from the event and the
    state snapshot already on the blackboard -- no new state reads."""
    state = blackboard.get("state") or {}
    metadata = event.metadata or {}
    tom = metadata.get("tom_inferences") or {}
    urgency = max(0.0, min(1.0, float(tom.get("inferred_arousal", 0.5))))
    stance = _bucket_relational_stance(
        trust=float(state.get("trust", 0.5)),
        attachment=float(state.get("attachment", 0.1)),
        mood=float(state.get("mood", 0.0)),
    )
    return CommunicativeIntent(
        act=event.intent or "CHAT",
        goal=metadata.get("suggested_goal", "ENGAGE"),
        urgency=urgency,
        relational_stance=stance,
        interruption_policy=(
            "reflex" if urgency >= _REFLEX_URGENCY_THRESHOLD else "deliberative"
        ),
    )


class DecisionService:
    """
    The Decision Layer.
    Uses LLM-based Intent Classification, MAUT goal scoring, and a Behavior Tree for routing.
    """

    def __init__(
        self,
        llm_service=None,
        memory_store=None,
        agent_name: str = "my friend",
        weights_store: AdaptiveWeightsStore | None = None,
    ):
        self.llm = llm_service
        self.memory = memory_store
        self.root = self._build_bt()

        # MAUT Weights (§3.1)
        self.w_goal = Config.MAUT_W_GOAL
        self.w_emotion = Config.MAUT_W_EMOTION
        self.w_identity = Config.MAUT_W_IDENTITY
        self.w_context = Config.MAUT_W_CONTEXT

        # ACT-R Goal Utility Reinforcement Learning
        self.goal_utilities = {g: 1.0 for g in GOALS}
        self.alpha_rl = 0.1  # TD learning rate

        # #118 / H7: `goal_utilities` used to reset to 1.0 for every goal on
        # every process restart, discarding whatever reinforcement learning had
        # accumulated. `hydrate()` restores it; `decide()` persists it whenever
        # `_score_goals_maut` updates a utility.
        self.agent_name = agent_name
        self._weights_store = weights_store or AdaptiveWeightsStore()

        # Intent Persistence (§3.2)
        self.persistence_rate = Config.INTENT_PERSISTENCE_RATE  # ρ
        self.shift_threshold = Config.CONTEXT_SHIFT_THRESHOLD  # θ_shift
        self._previous_goal: str | None = None
        self._goal_scores: dict[str, float] = {g: 0.0 for g in GOALS}
        self.intent_classifier = get_intent_classifier(self)

    async def hydrate(self) -> None:
        """Restore previously-learned goal utilities, if this agent has any.

        Only known goals are applied, so a row from an older `GOALS` list (a
        renamed or retired goal) cannot inject an untracked key that
        `_score_goals_maut` never reads back out.
        """
        saved = await self._weights_store.load(self.agent_name, _WEIGHT_KEY)
        if not saved:
            return
        for goal in GOALS:
            if goal in saved:
                try:
                    self.goal_utilities[goal] = float(saved[goal])
                except (TypeError, ValueError):
                    continue
        logger.info(
            "[Decision] Hydrated learned goal utilities for %r: %s",
            self.agent_name,
            self.goal_utilities,
        )

    def _build_bt(self):
        """Constructs the Behavior Tree."""
        return Selector(
            "RootDecision",
            [
                Sequence(
                    "SystemTasks",
                    [
                        Condition(
                            "IsSystemTick", lambda b: b["event"].intent == "REFLECT"
                        ),
                        Action("PlanReflection", self._plan_reflection),
                    ],
                ),
                Sequence(
                    "MemoryCommands",
                    [
                        Condition(
                            "IsRememberIntent",
                            lambda b: b["event"].intent == "REMEMBER",
                        ),
                        Action("PlanStorage", self._plan_storage),
                    ],
                ),
                Sequence(
                    "SocialReasoning",
                    [
                        Condition(
                            "IsChatIntent", lambda b: b["event"].intent == "CHAT"
                        ),
                        Action("DetermineGoalAndResponse", self._plan_social_response),
                    ],
                ),
            ],
        )

    async def decide(
        self, event: CognitiveEvent, state_snapshot: dict[str, Any]
    ) -> ActionPlan:
        """Main decision loop with MAUT scoring and intent persistence."""
        # 1. Hybrid Routing: Fast Path for Greetings
        if self._is_simple_greeting(event.raw_content):
            event.intent = "CHAT"
            event.metadata["suggested_goal"] = "ENGAGE"
            event.metadata["preferred_model"] = Config.LLM_FAST_MODEL
        elif event.event_type == "USER_MESSAGE":
            await self.intent_classifier.classify(event, state_snapshot)

        # 2. MAUT Goal Scoring (§3.1) — replaces raw keyword goal
        appraisal = event.metadata.get("appraisal", {})
        if appraisal and event.intent == "CHAT":
            maut_goal = self._score_goals_maut(
                appraisal, state_snapshot, event.metadata
            )
            event.metadata["suggested_goal"] = maut_goal
            # #118 / H7: `_score_goals_maut` just updated one entry of
            # `goal_utilities` via TD learning (unless this was the very first
            # turn, when `_previous_goal` was still None). Persisting here
            # rather than inside that method keeps it a pure scoring function.
            await self._weights_store.save(
                self.agent_name, _WEIGHT_KEY, self.goal_utilities.copy()
            )

        # 3. Tick BT
        blackboard: dict[str, Any] = {
            "event": event,
            "state": state_snapshot,
            "plan": None,
        }
        status = await self.root.tick(blackboard)

        if status == NodeStatus.SUCCESS and blackboard["plan"]:
            return blackboard["plan"]

        fallback_goal = event.metadata.get("suggested_goal", "ENGAGE")
        return ActionPlan(
            "RESPOND_CHAT",
            {
                "message": event.raw_content,
                "surfaced_memories": event.metadata.get("surfaced_memories", []),
            },
            fallback_goal,
        )

    def _score_goals_maut(
        self,
        appraisal: dict[str, float],
        state: dict[str, Any],
        event_metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Multi-Attribute Utility Theory (§3.1).
        Scores each goal and applies temporal persistence (§3.2).
        Includes dynamic ACT-R Goal Utility Reinforcement Learning updates.
        """
        V = state.get("mood", 0.0)
        Ar = state.get("energy", 0.5)
        T = state.get("trust", 0.5)
        R = appraisal.get("relevance", 0.5)
        G = appraisal.get("goal_congruence", 0.0)
        N = appraisal.get("novelty", 0.3)
        NA = appraisal.get("norm_alignment", 1.0)

        # 1. Update utility of previous goal if it exists (TD learning: U_g(t) = U_g(t-1) + alpha * [Reward - U_g(t-1)])
        V_user = state.get("inferred_valence", 0.0)
        if not V_user and "user_mental_model" in state:
            V_user = state["user_mental_model"].get("inferred_valence", 0.0)

        gaze = 0.5
        if event_metadata:
            gaze = event_metadata.get(
                "gaze",
                event_metadata.get(
                    "gaze_duration", event_metadata.get("user_gaze", 0.5)
                ),
            )

        norm_valence = (V_user + 1.0) / 2.0
        reward = 0.7 * norm_valence + 0.3 * gaze

        if self._previous_goal in self.goal_utilities:
            prev_u = self.goal_utilities[self._previous_goal]
            self.goal_utilities[self._previous_goal] = prev_u + self.alpha_rl * (
                reward - prev_u
            )

        scores: dict[str, float] = {}

        # ENGAGE: Best for neutral/positive states, high energy, novel topics
        scores["ENGAGE"] = (
            self.w_goal * max(0, G + 0.5)
            + self.w_emotion * (0.5 + V * 0.3 + Ar * 0.2)
            + self.w_identity * NA
            + self.w_context * R
            + self.goal_utilities["ENGAGE"]
        )

        # COMFORT: Best when user seems distressed — favored at low arousal (calm tone)
        scores["COMFORT"] = (
            self.w_goal * max(0, -G + 0.5)
            + self.w_emotion * max(0, -V + 0.5) * (1.2 - Ar * 0.4)
            + self.w_identity * NA
            + self.w_context * R * 0.8
            + self.goal_utilities["COMFORT"]
        )

        # INFORM: Best for high relevance, novel content — arousal-neutral
        scores["INFORM"] = (
            self.w_goal * max(0, G * 0.5 + 0.3)
            + self.w_emotion * (0.4 + Ar * 0.2)
            + self.w_identity * NA
            + self.w_context * R * N
            + self.goal_utilities["INFORM"]
        )

        # TEASE: Only when trust is high, mood positive, and energy high
        scores["TEASE"] = (
            self.w_goal * max(0, G * 0.3)
            + self.w_emotion * max(0, V * 0.3 + Ar * 0.2)
            + self.w_identity * NA * T
            + self.w_context * (1 - R) * 0.3
            + self.goal_utilities["TEASE"]
        )

        # PROTECT: When norm alignment is low — arousal-neutral (boundary enforcement)
        scores["PROTECT"] = (
            self.w_goal * 0.2
            + self.w_emotion * (0.2 + Ar * 0.1)
            + self.w_identity * max(0, 1.0 - NA)
            + self.w_context * R * 0.5
            + self.goal_utilities["PROTECT"]
        )

        # §3.2: Intent Persistence with Context Gating
        new_goal = max(scores, key=lambda g: scores[g])
        context_shift = N  # Novelty serves as a proxy for context shift

        if self._previous_goal is not None and context_shift < self.shift_threshold:
            # Apply temporal smoothing: blend previous goal scores
            rho = self.persistence_rate
            for g in GOALS:
                prev_score = self._goal_scores.get(g, 0.0)
                scores[g] = (1 - rho) * prev_score + rho * scores[g]
            new_goal = max(scores, key=lambda g: scores[g])
            logger.debug(
                "[Decision] Persistence applied (shift=%.2f < θ=%.2f): %s → %s",
                context_shift,
                self.shift_threshold,
                self._previous_goal,
                new_goal,
            )
        else:
            if self._previous_goal:
                logger.debug(
                    "[Decision] Context shift detected (%.2f ≥ θ=%.2f): hard reset to %s",
                    context_shift,
                    self.shift_threshold,
                    new_goal,
                )

        self._previous_goal = new_goal
        self._goal_scores = scores

        logger.info(
            "[Decision] MAUT scores: %s → selected: %s",
            {g: f"{s:.3f}" for g, s in scores.items()},
            new_goal,
        )
        return new_goal

    def _is_simple_greeting(self, text: str) -> bool:
        greetings = {"hi", "hello", "hey", "hola", "namaste", "yo"}
        clean_text = text.lower().strip().strip("!").strip(".")
        return clean_text in greetings

    def _apply_heuristic_intent_and_goal(self, event: CognitiveEvent):
        """Cheap intent defaults to avoid unnecessary LLM calls on every turn."""
        text = (event.raw_content or "").lower().strip()

        # Only classify as REMEMBER if it contains remember/memorize and is NOT a question
        is_question = text.endswith("?") or any(
            text.startswith(w)
            for w in [
                "what",
                "where",
                "how",
                "why",
                "who",
                "when",
                "did",
                "is",
                "can",
                "do you",
                "do",
                "are",
                "have you",
                "has",
            ]
        )

        if ("remember" in text or "memorize" in text) and not is_question:
            event.intent = "REMEMBER"
            event.metadata.setdefault("suggested_goal", "RECALL")
            event.metadata.setdefault("preferred_model", Config.LLM_FAST_MODEL)
            return

        event.intent = "CHAT"
        event.metadata.setdefault("suggested_goal", "ENGAGE")
        event.metadata.setdefault("preferred_model", Config.LLM_CHAT_MODEL)

    async def _classify_intent_and_goal(
        self, event: CognitiveEvent, state: dict[str, Any]
    ):
        """Uses LLM to classify intent and suggested goal, enriching with Theory of Mind inferences."""
        prompt = f"""
        Analyze user input and current agent state.
        Input: "{event.raw_content}"
        Mood: {state["emotion"]} (Valence: {state["mood"]})

        Classify into:
        - intent: REMEMBER, CHAT, COMMAND
          * REMEMBER: ONLY when the user explicitly instructs you to memorize or store a new fact (e.g., "remember that my cat's name is Lily").
          * CHAT: When the user is conversing, sharing, or asking a question (e.g., "do you remember my hometown?", "is my favorite dessert sweet?", "hey there").
          * COMMAND: Explicit control instructions.
        - goal: COMFORT, INFORM, ENGAGE, TEASE, PROTECT

        Also infer Theory of Mind (ToM) details:
        - inferred_valence: float between -1.0 and 1.0 (mood valence of the user)
        - inferred_arousal: float between 0.0 and 1.0 (arousal level of the user)
        - implied_goals: up to 2 implied immediate user goals (list of strings like "seek_reassurance", "express_frustration", "learn_concept", "chat_socially")

        First, output a brief chain-of-thought analysis enclosed in <thought>...</thought> (maximum 45 tokens) analyzing the input, intent, and ToM.
        Then, output the JSON block:
        {{
          "intent": "...",
          "goal": "...",
          "inferred_valence": 0.0,
          "inferred_arousal": 0.5,
          "implied_goals": ["..."]
        }}
        """.strip()

        try:
            response = await self.llm.generate(
                prompt,
                model=Config.LLM_FAST_MODEL,
                options_override={"num_predict": 256},
            )

            json_str = response
            if "</thought>" in response:
                json_str = response.split("</thought>")[-1].strip()
            elif "</think>" in response:
                json_str = response.split("</think>")[-1].strip()

            data = extract_first_json_value(json_str, brackets="{")
            if data is not None:
                # Sanitize/normalize intent: must be CHAT, REMEMBER, or COMMAND
                raw_intent = data.get("intent", "").upper().strip()
                if raw_intent in ["CHAT", "REMEMBER", "COMMAND"]:
                    event.intent = raw_intent
                else:
                    # If it's a goal or invalid value, fall back to CHAT
                    event.intent = "CHAT"

                event.metadata["suggested_goal"] = data.get("goal", "ENGAGE")
                event.metadata["preferred_model"] = (
                    Config.LLM_CHAT_MODEL
                    if event.intent == "CHAT"
                    else Config.LLM_FAST_MODEL
                )

                # Normalize implied_goals to avoid splitting strings into character arrays
                val = data.get("implied_goals", None)
                if val is None:
                    implied_goals = []
                elif isinstance(val, str):
                    implied_goals = [val]
                elif isinstance(val, (list, tuple)):
                    implied_goals = list(val)
                else:
                    implied_goals = []
                    logger.warning(
                        f"[Decision] Unexpected type for implied_goals: {type(val)}. Falling back to empty list."
                    )

                tom_inferences = {
                    "inferred_valence": float(data.get("inferred_valence", 0.0)),
                    "inferred_arousal": float(data.get("inferred_arousal", 0.5)),
                    "implied_goals": implied_goals,
                }
                event.metadata["tom_inferences"] = tom_inferences

                logger.info(f"[Decision] Fast Classified with ToM: {data}")
            else:
                logger.warning(
                    f"[Decision] Failed to find JSON block in LLM response for intent classification. Raw response: {response!r}"
                )
        except Exception as e:
            logger.error(f"Intent and ToM classification failed: {e}")

    # --- BT Actions ---

    def is_speculative_stop_confirmed(
        self, backbone_text: str, perception_keywords: list[str] | None = None
    ) -> bool:
        """
        Hardened Semantic Conflict Resolver for AI Friend.
        Logic: Distinguish between Agent Commands and Conversational Context.
        """
        if not backbone_text:
            return False

        if perception_keywords is None:
            perception_keywords = [
                "stop",
                "wait",
                "hold",
                "listen",
                "sunno",
                "ruko",
                "quiet",
            ]

        clean_text = backbone_text.lower().strip()
        raw_words = clean_text.split()
        words = [w.strip("!.,?;:") for w in raw_words]

        conversational_connectors = [
            "i agree",
            "i think",
            "i actually",
            "i just",
            "i am",
            "but",
            "though",
            "it is",
            "raining",
            "singing",
            "working",
            "playing",
            "for",
            "to",
            "be",
        ]
        call_signs = ["hey", "friend", "listen"]

        for kw in perception_keywords:
            kw = kw.lower()
            if kw in words:
                idx = words.index(kw)

                if idx + 1 < len(words):
                    next_words = " ".join(words[idx + 1 : idx + 3])
                    if any(conn in next_words for conn in conversational_connectors):
                        logger.debug(
                            f"[ConflictResolver] Rejected '{kw}' - Conversational context: '{next_words}'"
                        )
                        continue

                is_pivot = (idx == 0) or all(words[w] in call_signs for w in range(idx))

                if not is_pivot:
                    logger.debug(
                        f"[ConflictResolver] Rejected '{kw}' - Buried intent in: '{clean_text}'"
                    )
                    continue

                if len(words) <= 4:
                    logger.info(
                        f"[ConflictResolver] Stop CONFIRMED (Concise Command): '{kw}' in '{clean_text}'"
                    )
                    return True

                if idx == 0:
                    logger.info(
                        f"[ConflictResolver] Stop CONFIRMED (Pivot Match): '{kw}' in '{clean_text}'"
                    )
                    return True

        logger.warning(
            f"[ConflictResolver] Speculative stop REJECTED. Backbone text '{clean_text}' contradicts early perception."
        )
        return False

    def is_facial_reflex_interruption_worthy(self, reflex_name: str) -> bool:
        """Only `startle` -- the compound, highest-arousal reflex signal
        (`app/vision/reflex.py`) -- is salient enough to compete for the
        workspace and interrupt an in-flight turn. `smile`/`brow_furrow`
        stay background-only: an agent that stopped talking because the
        user smiled would be wrong, not attentive.
        """
        return reflex_name == "startle"

    async def _plan_social_response(self, blackboard: dict[str, Any]) -> bool:
        event = blackboard["event"]
        goal = event.metadata.get("suggested_goal", "ENGAGE")
        intent = _build_communicative_intent(event, blackboard)

        blackboard["plan"] = ActionPlan(
            action_type="RESPOND_CHAT",
            goal=goal,
            payload={
                "message": event.raw_content,
                "emotion_state": blackboard["state"]["emotion"],
                "model": event.metadata.get("preferred_model"),
                "surfaced_memories": event.metadata.get("surfaced_memories", []),
            },
            priority=1,
            behavior_decision=BehaviorDecision(intent=intent),
        )
        return True

    async def _plan_reflection(self, blackboard: dict[str, Any]) -> bool:
        event = blackboard["event"]
        intent = _build_communicative_intent(event, blackboard)
        blackboard["plan"] = ActionPlan(
            "BACKGROUND_CONSOLIDATION",
            {},
            "REFLECT",
            0,
            behavior_decision=BehaviorDecision(intent=intent),
        )
        return True

    async def _plan_storage(self, blackboard: dict[str, Any]) -> bool:
        event = blackboard["event"]
        intent = _build_communicative_intent(event, blackboard)
        blackboard["plan"] = ActionPlan(
            "STORE_MEMORY",
            {"content": event.raw_content},
            "RECALL",
            2,
            behavior_decision=BehaviorDecision(intent=intent),
        )
        return True
