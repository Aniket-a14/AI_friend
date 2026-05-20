"""
Decision Layer — MAUT + Intent Persistence (psychological_layer.md §3).

Intent selection uses Multi-Attribute Utility Theory (Keeney & Raiffa, 1976):
    U(Intent) = w₁·GoalAlignment + w₂·EmotionalFit + w₃·IdentityAlignment + w₄·ContextRelevance

Intent persistence uses temporal smoothing (§3.2):
    Intent_t = (1 − ρ) · Intent_{t−1} + ρ · Intent_new
    With context gating: if ContextShift > θ → hard reset
"""

import logging
import json
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .perception import CognitiveEvent
from .bt import Selector, Sequence, Action, Condition, NodeStatus
from ..config import Config

logger = logging.getLogger(__name__)

# Available goals for MAUT scoring
GOALS = ["ENGAGE", "COMFORT", "INFORM", "TEASE", "PROTECT"]


@dataclass
class ActionPlan:
    action_type: str  # e.g., "RESPOND_CHAT", "STORE_MEMORY", "BACKGROUND_CONSOLIDATION"
    payload: Dict[str, Any]
    goal: str
    priority: int = 1


class DecisionService:
    """
    The Decision Layer.
    Uses LLM-based Intent Classification, MAUT goal scoring, and a Behavior Tree for routing.
    """

    def __init__(self, llm_service=None, memory_store=None):
        self.llm = llm_service
        self.memory = memory_store
        self.root = self._build_bt()

        # MAUT Weights (§3.1)
        self.w_goal = Config.MAUT_W_GOAL
        self.w_emotion = Config.MAUT_W_EMOTION
        self.w_identity = Config.MAUT_W_IDENTITY
        self.w_context = Config.MAUT_W_CONTEXT

        # Intent Persistence (§3.2)
        self.persistence_rate = Config.INTENT_PERSISTENCE_RATE  # ρ
        self.shift_threshold = Config.CONTEXT_SHIFT_THRESHOLD  # θ_shift
        self._previous_goal: Optional[str] = None
        self._goal_scores: Dict[str, float] = {g: 0.0 for g in GOALS}

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
        self, event: CognitiveEvent, state_snapshot: Dict[str, Any]
    ) -> ActionPlan:
        """Main decision loop with MAUT scoring and intent persistence."""
        # 1. Hybrid Routing: Fast Path for Greetings
        if self._is_simple_greeting(event.raw_content):
            event.intent = "CHAT"
            event.metadata["suggested_goal"] = "ENGAGE"
            event.metadata["preferred_model"] = Config.LLM_FAST_MODEL
        elif event.event_type == "USER_MESSAGE":
            self._apply_heuristic_intent_and_goal(event)
            if Config.LLM_INTENT_CLASSIFICATION_ENABLED:
                await self._classify_intent_and_goal(event, state_snapshot)

        # 2. MAUT Goal Scoring (§3.1) — replaces raw keyword goal
        appraisal = event.metadata.get("appraisal", {})
        if appraisal and event.intent == "CHAT":
            maut_goal = self._score_goals_maut(appraisal, state_snapshot)
            event.metadata["suggested_goal"] = maut_goal

        # 3. Tick BT
        blackboard = {"event": event, "state": state_snapshot, "plan": None}
        status = await self.root.tick(blackboard)

        if status == NodeStatus.SUCCESS and blackboard["plan"]:
            return blackboard["plan"]

        fallback_goal = event.metadata.get("suggested_goal", "ENGAGE")
        return ActionPlan("RESPOND_CHAT", {"message": event.raw_content}, fallback_goal)

    def _score_goals_maut(
        self, appraisal: Dict[str, float], state: Dict[str, Any]
    ) -> str:
        """
        Multi-Attribute Utility Theory (§3.1).
        Scores each goal and applies temporal persistence (§3.2).
        """
        V = state.get("mood", 0.0)
        Ar = state.get("energy", 0.5)
        T = state.get("trust", 0.5)
        R = appraisal.get("relevance", 0.5)
        G = appraisal.get("goal_congruence", 0.0)
        N = appraisal.get("novelty", 0.3)
        NA = appraisal.get("norm_alignment", 1.0)

        scores = {}

        # ENGAGE: Best for neutral/positive states, high energy, novel topics
        scores["ENGAGE"] = (
            self.w_goal * max(0, G + 0.5)
            + self.w_emotion * (0.5 + V * 0.3 + Ar * 0.2)
            + self.w_identity * NA
            + self.w_context * R
        )

        # COMFORT: Best when user seems distressed — favored at low arousal (calm tone)
        scores["COMFORT"] = (
            self.w_goal * max(0, -G + 0.5)
            + self.w_emotion * max(0, -V + 0.5) * (1.2 - Ar * 0.4)
            + self.w_identity * NA
            + self.w_context * R * 0.8
        )

        # INFORM: Best for high relevance, novel content — arousal-neutral
        scores["INFORM"] = (
            self.w_goal * max(0, G * 0.5 + 0.3)
            + self.w_emotion * (0.4 + Ar * 0.2)
            + self.w_identity * NA
            + self.w_context * R * N
        )

        # TEASE: Only when trust is high, mood positive, and energy high
        scores["TEASE"] = (
            self.w_goal * max(0, G * 0.3)
            + self.w_emotion * max(0, V * 0.3 + Ar * 0.2)
            + self.w_identity * NA * T
            + self.w_context * (1 - R) * 0.3
        )

        # PROTECT: When norm alignment is low — arousal-neutral (boundary enforcement)
        scores["PROTECT"] = (
            self.w_goal * 0.2
            + self.w_emotion * (0.2 + Ar * 0.1)
            + self.w_identity * max(0, 1.0 - NA)
            + self.w_context * R * 0.5
        )

        # §3.2: Intent Persistence with Context Gating
        new_goal = max(scores, key=scores.get)
        context_shift = N  # Novelty serves as a proxy for context shift

        if self._previous_goal is not None and context_shift < self.shift_threshold:
            # Apply temporal smoothing: blend previous goal scores
            rho = self.persistence_rate
            for g in GOALS:
                prev_score = self._goal_scores.get(g, 0.0)
                scores[g] = (1 - rho) * prev_score + rho * scores[g]
            new_goal = max(scores, key=scores.get)
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
        text = (event.raw_content or "").lower()

        if "remember" in text or "memorize" in text:
            event.intent = "REMEMBER"
            event.metadata.setdefault("suggested_goal", "RECALL")
            event.metadata.setdefault("preferred_model", Config.LLM_FAST_MODEL)
            return

        event.intent = "CHAT"
        event.metadata.setdefault("suggested_goal", "ENGAGE")
        event.metadata.setdefault("preferred_model", Config.LLM_CHAT_MODEL)

    async def _classify_intent_and_goal(
        self, event: CognitiveEvent, state: Dict[str, Any]
    ):
        """Uses LLM to classify intent and suggested goal, enriching with Theory of Mind inferences."""
        prompt = f"""
        Analyze user input and current agent state.
        Input: "{event.raw_content}"
        Mood: {state["emotion"]} (Valence: {state["mood"]})
        
        Classify into:
        - intent: REMEMBER, CHAT, COMMAND
        - goal: COMFORT, INFORM, ENGAGE, TEASE, PROTECT
        
        Also infer Theory of Mind (ToM) details:
        - inferred_valence: float between -1.0 and 1.0 (mood valence of the user)
        - inferred_arousal: float between 0.0 and 1.0 (arousal level of the user)
        - implied_goals: up to 2 implied immediate user goals (list of strings like "seek_reassurance", "express_frustration", "learn_concept", "chat_socially")
        
        Output JSON ONLY:
        {{
          "intent": "...",
          "goal": "...",
          "inferred_valence": 0.0,
          "inferred_arousal": 0.5,
          "implied_goals": ["..."]
        }}
        """.strip()

        try:
            response = await self.llm.generate(prompt, model=Config.LLM_FAST_MODEL)

            json_str = response
            if "<think>" in response:
                json_str = response.split("</think>")[-1].strip()

            match = re.search(r"\{.*\}", json_str, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                event.intent = data.get("intent", event.intent)
                event.metadata["suggested_goal"] = data.get("goal", "ENGAGE")
                event.metadata["preferred_model"] = (
                    Config.LLM_CHAT_MODEL
                    if event.intent == "CHAT"
                    else Config.LLM_FAST_MODEL
                )
                
                # Extract and store ToM inferences in metadata
                tom_inferences = {
                    "inferred_valence": float(data.get("inferred_valence", 0.0)),
                    "inferred_arousal": float(data.get("inferred_arousal", 0.5)),
                    "implied_goals": list(data.get("implied_goals", []))
                }
                event.metadata["tom_inferences"] = tom_inferences
                
                logger.info(f"[Decision] Fast Classified with ToM: {data}")
        except Exception as e:
            logger.error(f"Intent and ToM classification failed: {e}")

    # --- BT Actions ---

    def is_speculative_stop_confirmed(
        self, backbone_text: str, perception_keywords: list[str] = None
    ) -> bool:
        """
        Hardened Semantic Conflict Resolver for CVS-1.0.
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

    async def _plan_social_response(self, blackboard: Dict[str, Any]) -> bool:
        event = blackboard["event"]
        goal = event.metadata.get("suggested_goal", "ENGAGE")

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
        )
        return True

    async def _plan_reflection(self, blackboard: Dict[str, Any]) -> bool:
        blackboard["plan"] = ActionPlan("BACKGROUND_CONSOLIDATION", {}, "REFLECT", 0)
        return True

    async def _plan_storage(self, blackboard: Dict[str, Any]) -> bool:
        blackboard["plan"] = ActionPlan(
            "STORE_MEMORY", {"content": blackboard["event"].raw_content}, "RECALL", 2
        )
        return True
