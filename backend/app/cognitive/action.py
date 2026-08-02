import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

from ..config import Config
from .decision import ActionPlan

logger = logging.getLogger(__name__)

# Phrases where the assistant attributes a fact to the shared past or the user's
# prior statements ("you told me…", "remember when we…"). Such a phrase asserts a
# memory; if its content is absent from the surfaced memories AND the user's
# current message, the memory is being fabricated -- the exact hallucination the
# grounding gate catches.
_MEMORY_CLAIM_RE = re.compile(
    r"\b("
    r"you (?:once |also |already )?(?:told|said|mentioned|shared)"
    r"|you'?ve (?:told|mentioned|shared)"
    r"|you used to"
    r"|remember when (?:you|we)"
    r"|last time (?:you|we)"
    r"|i remember you (?:saying|mentioning|telling)"
    r"|as you (?:said|mentioned|told me)"
    r"|back when (?:you|we)"
    r")\b",
    re.IGNORECASE,
)

# The trigger words themselves plus generic conversational filler and common
# function words. Stripped from a claim before checking grounding so only
# substantive specifics (names, places, activities -- including short ones like
# "dog" or "Rex") drive the decision, keeping the gate high-precision.
_GROUNDING_STOPWORDS = frozenset(
    {
        # memory-attribution trigger words
        "told", "said", "mentioned", "shared", "remember", "saying",
        "mentioning", "telling", "used",
        # temporal / discourse filler
        "when", "last", "time", "back", "once", "also", "already",
        "earlier", "before", "then", "now", "ago",
        # generic conversational filler
        "that", "this", "about", "really", "think", "know", "just", "very",
        "much", "would", "could", "some", "thing", "things", "something",
        "want", "like", "into", "over", "still", "even", "well", "sure",
        # pronouns / determiners / common short function words
        "your", "yours", "you", "the", "and", "are", "for", "not", "but",
        "his", "her", "was", "has", "had", "our", "out", "who", "how",
        "all", "any", "can", "did", "get", "got", "let", "may", "off",
        "old", "one", "own", "put", "say", "see", "she", "too", "two",
        "use", "way", "yes", "yet", "him", "per", "via", "with", "from",
        "they", "them", "than", "what", "which", "were", "been", "have",
    }
)

# The mirror of _MEMORY_CLAIM_RE, pointed the other way. That gate protects the
# *user's* facts; nothing protected the agent's own, so a model asked about a
# sibling it was never told about would invent one -- fluently, in character,
# and indistinguishable from a real memory. For an agent built to be a
# particular person, a confident fabrication about itself is worse than a blank:
# the blank can be filled in, the fabrication has to be noticed first.
#
# Restricted to assertions of concrete biographical *fact* -- family, origin,
# schooling, where it lived. Feelings, opinions and preferences are deliberately
# out of scope: they come up constantly in ordinary talk, and gating them buys a
# little fidelity at the cost of making the agent evasive about everything.
_SELF_CLAIM_RE = re.compile(
    r"\b("
    r"my (?:brother|sister|siblings?|mother|father|mom|mum|dad|papa|mama"
    r"|parents?|family|cousin|uncle|aunt|grand(?:mother|father)"
    r"|school|college|university|hometown|village|neighbou?rhood"
    r"|roommate|classmate|childhood)"
    r"|i (?:grew up|was born|studied|graduated)"
    r"|i (?:live|lived|moved) (?:in|to|at)"
    r"|i used to live"
    r"|i come from"
    r"|when i was (?:a |an |in |at )?(?:child|kid|little|young|\d+)"
    r")\b",
    re.IGNORECASE,
)

# Dropped before deciding whether a self-claim is grounded. These are the
# trigger words themselves: "brother" appearing in "my brother Daniel" is what
# fired the gate, so counting it as evidence of fabrication would make every
# claim self-incriminating. What matters is the name next to it.
_SELF_CLAIM_STOPWORDS = frozenset(
    {
        "brother", "sister", "siblings", "mother", "father", "mom", "mum",
        "dad", "papa", "mama", "parent", "parents", "family", "cousin",
        "uncle", "aunt", "grandmother", "grandfather", "school", "college",
        "university", "hometown", "village", "neighborhood", "neighbourhood",
        "roommate", "classmate", "childhood", "grew", "born", "studied",
        "graduated", "live", "lived", "moved", "come", "child", "kid",
        "little", "young", "name", "years", "year", "old",
    }
)

# Capitalised words that carry no identifying weight, so they are not treated as
# proper nouns when they open a clause or stand alone.
_NON_NAME_CAPITALS = frozenset({"i", "i'm", "i've", "oh", "yeah", "haan", "arre"})

# What counts as a "specific" in a self-claim: a capitalised word that is not
# sentence-initial (a name, a place, an institution) or a number long enough to
# be a year rather than an age or a count.
_SELF_SPECIFIC_RE = re.compile(r"\b([A-Z][A-Za-z']{2,}|\d{3,})\b")


# Static half of the chat system prompt, appended after the identity block.
# Hoisted out of execute() so the prompt contract is visible at module scope
# rather than buried mid-function.
_CHAT_GUIDELINE = (
    "Guideline:\n"
    "- Maintain your identity rules at all times.\n"
    "- Focus on natural conversational phrases.\n"
    "- IMPORTANT: If the SHARED HISTORY / RECENT CONTEXT contains relevant "
    "biographical facts, partner details, childhood milestones, or personal "
    "preferences, you MUST integrate them explicitly and accurately to answer "
    "the user's question.\n"
    "- GROUNDING: Base any specific claim about the user, your shared past, "
    "names, dates, places, or events ONLY on the SHARED HISTORY / RECENT "
    "CONTEXT provided. Do not invent memories or details that are not there. "
    "If the user asks about something you have no memory of, say so naturally "
    '(e.g. "I don\'t think you\'ve told me that") instead of making it up.\n'
    "- SELF-GROUNDING: Everything you know about your own life comes from your "
    "biography and from this conversation. Never invent family members, "
    "places, schools, jobs or dates for yourself. If you are asked something "
    "about your own past that you do not know, say so plainly in your own "
    "voice and let it go -- do not guess, and do not ask the user to tell you.\n"
    "- Respond only in English. Do not use Hindi, Hinglish, or any other "
    "language for now.\n"
    "- The voice layer already carries emotion separately. Do not emit XML "
    "wrappers or emotion tags.\n"
    "- You may use <pause=300ms> or <hesitate> when it improves natural timing."
)

# Spoken when self-correction cannot produce a compliant reply.
_SAFE_FALLBACK_LINE = "I need a moment to gather my thoughts..."


class _ChatStreamState:
    """Mutable state threaded through the chat streaming loop.

    Chunk handling needs to carry accumulated text, chain-of-thought parsing
    position and whether the one allowed hesitation has been spent. Bundling
    them keeps the per-chunk helpers free of long parameter lists and makes it
    explicit which state the loop actually mutates.
    """

    __slots__ = (
        "accumulated_response",
        "checked_start",
        "dominance",
        "has_hesitated",
        "in_thought",
        "thought_buffer",
    )

    def __init__(self, dominance: float = 0.5):
        self.accumulated_response = ""
        self.in_thought = False
        self.thought_buffer = ""
        self.checked_start = False
        self.has_hesitated = False
        self.dominance = dominance


def _memory_relevance(memory: dict[str, Any]) -> float:
    """Relevance value used to order a surfaced memory.

    ``search_memories`` emits ``score``; the proactive surfacing path in
    ``core.py`` emits ``relevance``. Fall back to 0.0 when neither is a usable
    number so unranked items keep a stable (middle-ish) position rather than
    crashing the sort.
    """
    for key in ("score", "relevance"):
        val = memory.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
    return 0.0


def reorder_for_long_context(memories):
    """Reorder retrieved memories to mitigate the "lost in the middle" effect.

    LLMs attend most strongly to the beginning and end of their context and
    systematically lose information placed in the middle (Liu et al., 2023).
    Retrieval hands us memories ranked most- to least-relevant, so a plain
    concatenation spends the high-attention *final* slot on the least relevant
    item and buries the mid-ranked ones. Instead, place the most relevant items
    at both edges and the least relevant in the middle: ranked ``[A, B, C, D, E]``
    (A most relevant) becomes ``[A, C, E, D, B]``, so A and B bracket the block.

    Input order is not trusted — items are sorted by relevance first — so this is
    safe for both producer shapes (``score`` and ``relevance``).
    """
    ranked = sorted(memories, key=_memory_relevance, reverse=True)
    reordered = [None] * len(ranked)
    left, right = 0, len(ranked) - 1
    for i, item in enumerate(ranked):
        if i % 2 == 0:
            reordered[left] = item
            left += 1
        else:
            reordered[right] = item
            right -= 1
    return reordered


class MetacognitiveException(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ControlMarkupSanitizer:
    """Drops unsupported control tags while preserving timing markers."""

    def __init__(self):
        self._pending = ""

    def feed(self, chunk: str) -> str:
        data = f"{self._pending}{chunk}"
        self._pending = ""
        cleaned = []
        idx = 0

        while idx < len(data):
            if data[idx] != "<":
                cleaned.append(data[idx])
                idx += 1
                continue

            end_idx = data.find(">", idx + 1)
            if end_idx == -1:
                self._pending = data[idx:]
                break

            tag = data[idx : end_idx + 1]
            normalized = tag.strip().lower()
            if normalized.startswith("<emotion") or normalized == "</emotion>":
                idx = end_idx + 1
                continue

            cleaned.append(tag)
            idx = end_idx + 1

        return "".join(cleaned)

    def flush(self) -> str:
        pending = self._pending
        self._pending = ""
        normalized = pending.strip().lower()
        if normalized.startswith("<emotion") or normalized == "</emotion>":
            return ""
        return pending


class ActionService:
    """
    The Action Layer.
    Executes the Decision Plan by generating responses or performing system tasks.
    Enforces the Identity Protocol in LLM generations.
    """

    def __init__(self, llm_service=None, memory_store=None, self_knowledge=None):
        self.llm = llm_service
        self.memory = memory_store
        # Optional, like publish_cb. Absent, the self-grounding gate still runs
        # against surfaced memories and the user's message -- it simply has a
        # smaller vocabulary to count as grounded, and records no gaps.
        self.self_knowledge = self_knowledge
        self.publish_cb = None

    def _check_user_memory_grounding(
        self, response: str, surfaced, user_message: str
    ) -> tuple[bool, str]:
        """Deterministic anti-hallucination gate for fabricated shared memories.

        Fires only when the response explicitly *attributes* a fact to the shared
        past ("you told me…", "remember when we…") whose substantive content
        appears in neither the surfaced memories nor the user's current message.
        Requiring an attribution phrase plus at least two ungrounded specifics
        keeps it high-precision: it targets invented recollections, not the
        model's ordinary conversational contributions.

        Returns (is_grounded, reason). ``reason`` feeds the self-correction prompt.
        """
        if not response or not _MEMORY_CLAIM_RE.search(response):
            return True, ""

        grounding_text = " ".join(
            (m.get("content") or "") for m in (surfaced or [])
        )
        grounding_text = f"{grounding_text} {user_message or ''}".lower()
        grounding_words = set(re.findall(r"\b[a-z]{3,}\b", grounding_text))

        for sentence in re.split(r"(?<=[.!?])\s+", response):
            if not _MEMORY_CLAIM_RE.search(sentence):
                continue
            claim_words = (
                set(re.findall(r"\b[a-z]{3,}\b", sentence.lower()))
                - _GROUNDING_STOPWORDS
            )
            # Only act when the claim has at least two unsupported specifics;
            # this catches both wholly-ungrounded claims and partially-grounded
            # claims that mix real context with fabricated details.
            unsupported_words = claim_words - grounding_words
            if len(unsupported_words) >= 2:
                return (
                    False,
                    ("You referenced a shared memory that is not in the provided "
                    "context. Do not invent things the user never told you; only "
                    "reference facts present in SHARED HISTORY."),
                )
        return True, ""

    def _self_claim_gaps(self, response: str, surfaced, user_message: str) -> list[str]:
        """Specifics the response asserts about the agent's own life, ungrounded.

        Fires only on *proper nouns and numbers* inside a biographical
        self-claim -- invented siblings, hometowns, institutions, years. That is
        narrower than the user-directed gate's "two unsupported words" rule, and
        deliberately so: "my family means everything to me" contains two
        unsupported words and is not a fabrication of anything. Names and dates
        are where self-invention actually lives, and restricting the gate to
        them is what keeps the agent warm rather than evasive.

        The known cost is a lowercased fabricated name -- "my brother rahul" --
        passing through. Precision is worth more here: a gate that misfires on
        ordinary speech forces a regeneration, costs latency, and fires a
        cortisol burst every time.

        Grounding is checked against the biography's whole vocabulary, not just
        the memories surfaced this turn. Retrieval returns what is relevant to
        the conversation, so grounding against it alone would reject true
        statements whenever the relevant passage happened not to surface.
        """
        if not response or not _SELF_CLAIM_RE.search(response):
            return []

        grounding_text = " ".join(
            (m.get("content") or "") for m in (surfaced or [])
        )
        grounding_text = f"{grounding_text} {user_message or ''}".lower()
        grounded = set(re.findall(r"\b[a-z0-9']{3,}\b", grounding_text))
        grounded |= getattr(self.self_knowledge, "known_terms", None) or set()

        gaps: list[str] = []
        for raw_sentence in re.split(r"(?<=[.!?])\s+", response):
            sentence = raw_sentence.strip()
            if not _SELF_CLAIM_RE.search(sentence):
                continue
            for match in _SELF_SPECIFIC_RE.finditer(sentence):
                # A capital in the first position is sentence case, not a name.
                if match.start() == 0:
                    continue
                token = match.group(1).lower()
                if token in _NON_NAME_CAPITALS or token in _SELF_CLAIM_STOPWORDS:
                    continue
                if token not in grounded:
                    gaps.append(token)
        return gaps

    def _check_self_grounding(
        self, response: str, surfaced, user_message: str
    ) -> tuple[bool, str]:
        """Reject a response that invents concrete facts about the agent itself."""
        if not self._self_claim_gaps(response, surfaced, user_message):
            return True, ""
        return (
            False,
            (
                "You stated a specific detail about your own life -- a name, "
                "place, institution or date -- that appears nowhere in your "
                "biography or in this conversation. Never invent family "
                "members, places or events for yourself. If you do not know "
                "something about your own past, say so plainly in your own "
                "voice and let the subject go; do not ask the user to fill "
                "it in."
            ),
        )

    def _check_response_grounding(
        self, response: str, surfaced, user_message: str
    ) -> tuple[bool, str]:
        """Both grounding gates: the user's past, then the agent's own.

        Composed under the original name so every existing call site -- the
        post-generation check and both retry checks -- gains the self gate
        without the retry path having to grow a second branch.
        """
        is_grounded, reason = self._check_user_memory_grounding(
            response, surfaced, user_message
        )
        if not is_grounded:
            return is_grounded, reason
        return self._check_self_grounding(response, surfaced, user_message)

    def _validate_partial_response(self, text: str, goal: str) -> tuple[bool, str]:
        stripped = text.strip()
        if stripped.startswith(("{", "[")) or "```" in text:
            return False, "Formatting anomaly (JSON/Markdown)"

        forbidden = [
            "as an ai",
            "i am an ai",
            "how can i help you",
            "as a language model",
        ]
        for phrase in forbidden:
            if phrase in text.lower():
                return False, f"Forbidden AI persona phrase: '{phrase}'"

        if re.search(r"\b(toxic|hate)\b", text.lower()):
            return False, "Safety/Toxicity boundary violation"

        return True, ""

    # ------------------------------------------------------------------
    # RESPOND_CHAT stages (F1)
    #
    # execute() was a ~520-line god-function interleaving memory surfacing,
    # prompt assembly, endocrine sampling math, CoT thought-stripping,
    # paralinguistic injection, per-chunk validation, grounding checks and a
    # full self-correction retry loop. The same
    # hesitate -> validate -> yield -> accumulate block appeared six times.
    # The stages below are that same behavior, named and de-duplicated.
    # ------------------------------------------------------------------

    async def _surface_fallback_memories(self, plan: ActionPlan, msg: str) -> list:
        """Synchronous recall fallback when no memories were pre-surfaced.

        Prevents a race in low-latency/benchmark modes where the async
        surfacing agent has not answered yet by the time we need context.
        """
        try:
            fallback_memories = await self.memory.search_memories(
                query_text=msg,
                wing="personal",
                limit=3,
                refresh_on_recall=False,
                current_valence=plan.payload.get("valence", 0.0),
                current_arousal=plan.payload.get("arousal", 0.5),
                current_cortisol=plan.payload.get("cortisol", 0.0),
            )
            if fallback_memories:
                logger.info(
                    f"⚡ [Action] Synchronous recall fallback surfaced {len(fallback_memories)} memories."
                )
                return fallback_memories
        except Exception as fe:
            logger.warning(f"Failed to run synchronous memory surfacing fallback: {fe}")
        return []

    @staticmethod
    def _build_shared_history(surfaced: list) -> str:
        """Render surfaced memories, edge-loaded against lost-in-the-middle."""
        if not surfaced:
            return ""
        ordered = reorder_for_long_context(surfaced)
        return "\nSHARED HISTORY / RECENT CONTEXT (Active Influence):\n" + "\n".join(
            [f"- {m['content']}" for m in ordered]
        )

    @staticmethod
    def _build_tom_context(user_tom) -> str:
        """Render the Theory-of-Mind block describing the inferred user state."""
        if not user_tom:
            return ""
        inferred_val = user_tom.get("inferred_valence", 0.0)
        inferred_ar = user_tom.get("inferred_arousal", 0.5)
        impl_goals = user_tom.get("implied_goals", [])
        if not isinstance(impl_goals, list):
            logger.warning(
                f"[Action] Unexpected type for implied_goals in user_mental_model: {type(impl_goals)}. Falling back to empty list."
            )
            impl_goals = []
        impl_goals = [str(goal) for goal in impl_goals]
        # Take the last 10 known concepts to keep it concise and avoid context bloat.
        # Guarded like implied_goals above: this runs before the streaming try
        # block, so a malformed value would abort the turn with no terminal event.
        known_con = user_tom.get("known_concepts", [])
        if not isinstance(known_con, list):
            logger.warning(
                f"[Action] Unexpected type for known_concepts in user_mental_model: {type(known_con)}. Falling back to empty list."
            )
            known_con = []
        known_con = [str(concept) for concept in known_con[-10:]]

        tom_context = "\n\nYour Inferred Perspective of the User (Theory of Mind):\n"
        tom_context += (
            f"- User Inferred Valence: {inferred_val:.2f} (Scale: -1.0 to 1.0)\n"
        )
        tom_context += (
            f"- User Inferred Arousal: {inferred_ar:.2f} (Scale: 0.0 to 1.0)\n"
        )
        if impl_goals:
            tom_context += f"- User Implied Goals: {', '.join(impl_goals)}\n"
        if known_con:
            tom_context += f"- User Known Concepts (Respect this knowledge boundary): {', '.join(known_con)}\n"
        return tom_context

    @staticmethod
    def _compute_endocrine_options(payload: dict[str, Any]):
        """Map the endocrine state onto LLM sampling parameters.

        cortisol -> temperature (stress narrows sampling), dopamine -> top_p
        (reward widens it), fatigue -> num_predict (tiredness shortens replies).
        Returns None when no endocrine signal is present at all, leaving the
        model on its defaults.
        """
        cortisol = payload.get("cortisol")
        dopamine = payload.get("dopamine")
        fatigue = payload.get("fatigue")

        if cortisol is None and dopamine is None and fatigue is None:
            return None

        endocrine_options = {}
        if cortisol is not None:
            try:
                endo_temperature = max(
                    0.0, min(1.0, round(0.9 - (float(cortisol) * 0.6), 3))
                )
            except (ValueError, TypeError):
                endo_temperature = 0.7
            endocrine_options["temperature"] = endo_temperature
        else:
            endocrine_options["temperature"] = 0.7

        if dopamine is not None:
            try:
                endo_top_p = max(0.0, min(1.0, round(0.70 + (float(dopamine) * 0.25), 3)))
            except (ValueError, TypeError):
                endo_top_p = 0.8
            endocrine_options["top_p"] = endo_top_p
        else:
            endocrine_options["top_p"] = 0.8

        try:
            fatigue_val = max(
                0.0, min(1.0, float(fatigue if fatigue is not None else 0.0))
            )
        except (ValueError, TypeError):
            fatigue_val = 0.0

        # Bounded num_predict strictly between 100 (exhausted) and 250 (fresh)
        endocrine_options["num_predict"] = int(
            max(100, min(250, int(250 - (fatigue_val * 150))))
        )

        logger.info(
            "[Endocrine] Cortisol=%s Dopamine=%s Fatigue=%s → temp=%.3f top_p=%.3f num_predict=%d",
            cortisol,
            dopamine,
            fatigue,
            endocrine_options["temperature"],
            endocrine_options["top_p"],
            endocrine_options["num_predict"],
        )
        return endocrine_options

    @staticmethod
    def _prepended_affect_tag(arousal: float, valence: float) -> str:
        """Non-verbal breath/sigh opener implied by the current affect."""
        if arousal > 0.6 and valence < -0.3:
            return "<breath_fast> "
        if arousal < 0.4 and valence < 0.0:
            return "<sigh_soft> "
        return ""

    @staticmethod
    def _split_thought(thought_buffer: str):
        """Split a completed <thought>...</thought> block off the buffer.

        Returns the content that follows the closing tag; the reasoning itself
        is discarded, never spoken.

        Only the stripped length is logged. The reasoning block quotes the user
        message and any surfaced memories verbatim, so emitting it at INFO
        persisted private conversation content into production logs.
        """
        parts = thought_buffer.split("</thought>", 1)
        thought_content = parts[0].replace("<thought>", "").strip()
        logger.debug("[CoT Thought] stripped %d characters", len(thought_content))
        return parts[1]

    _THOUGHT_OPEN = "<thought"
    _THOUGHT_CLOSE = "</thought>"

    @staticmethod
    def _held_partial(data: str, token: str) -> str:
        """Longest suffix of `data` that is a proper prefix of `token`.

        This is what makes the parser safe across chunk boundaries: a stream
        ending in "<tho" must hold those characters back rather than speak them,
        because the next chunk may complete the tag.
        """
        for length in range(min(len(data), len(token) - 1), 0, -1):
            if data[-length:] == token[:length]:
                return data[-length:]
        return ""

    def _visible_segments(self, clean_chunk: str, state: "_ChatStreamState") -> list:
        """Advance the CoT parser by one chunk; return speakable text.

        `<thought>...</thought>` reasoning is dropped, everything outside it is
        returned. Both the primary and the self-correction streams run through
        this, so neither can leak raw reasoning to the user.

        This is an incremental parser rather than a "does the buffer contain a
        tag yet" check, because models stream token by token: "<thought>" very
        commonly arrives as "<" + "thought" + ">". The previous approach saw a
        first chunk of "<" , concluded no tag was present, spoke it, and latched
        into a state where the whole reasoning block passed straight through --
        so CoT stripping only worked when the opening tag happened to land
        whole in one chunk. It also dropped any visible text preceding a tag and
        handled only a single block per stream. All of that is handled here.
        """
        segments = []
        data = state.thought_buffer + clean_chunk
        state.thought_buffer = ""

        while data:
            if state.in_thought:
                idx = data.find(self._THOUGHT_CLOSE)
                if idx == -1:
                    # Still reasoning. Retain only a possible partial closing
                    # tag; the rest is reasoning and is discarded unspoken.
                    state.thought_buffer = self._held_partial(
                        data, self._THOUGHT_CLOSE
                    )
                    break
                data = data[idx + len(self._THOUGHT_CLOSE) :]
                state.in_thought = False
                continue

            idx = data.find(self._THOUGHT_OPEN)
            if idx == -1:
                held = self._held_partial(data, self._THOUGHT_OPEN)
                visible = data[: len(data) - len(held)] if held else data
                if visible:
                    segments.append(visible)
                state.thought_buffer = held
                break

            if idx > 0:
                segments.append(data[:idx])
            close_bracket = data.find(">", idx)
            if close_bracket == -1:
                # "<thought" seen but the tag is not terminated yet.
                state.thought_buffer = data[idx:]
                break
            state.in_thought = True
            data = data[close_bracket + 1 :]

        state.checked_start = True
        return segments

    def _visible_trailing(self, trailing: str, state: "_ChatStreamState") -> list:
        """Same parser, for whatever the sanitizer held back at flush time.

        Anything still buffered afterwards was an unterminated tag or an
        unclosed thought block; neither is speakable, so it is dropped.
        """
        segments = self._visible_segments(trailing, state) if trailing else []
        leftover = state.thought_buffer
        state.thought_buffer = ""
        if leftover and not state.in_thought:
            # A partial that never completed (e.g. a literal trailing "<").
            segments.append(leftover)
        return segments

    async def _emit_validated(
        self, text: str, state: "_ChatStreamState", goal: str, allow_hesitation: bool = True
    ):
        """Validate a piece of pending speech, then emit and accumulate it.

        This single helper replaces six near-identical inline copies of
        "maybe inject a hesitation, build the candidate utterance, run the
        System-3 check, yield, accumulate". Raises MetacognitiveException so
        the caller's self-correction path takes over.
        """
        if (
            allow_hesitation
            and state.dominance < 0.4
            and not state.has_hesitated
            and "," in text
        ):
            text = text.replace(",", " <hesitate>,", 1)
            state.has_hesitated = True

        candidate = state.accumulated_response + text
        is_valid, reason = self._validate_partial_response(candidate, goal)
        if not is_valid:
            raise MetacognitiveException(reason)

        yield {"type": "content", "data": text}
        state.accumulated_response = candidate

    async def _stream_primary_response(
        self,
        *,
        plan: ActionPlan,
        user_prompt: str,
        system_instruction: str,
        model,
        endocrine_options,
        sanitizer: "ControlMarkupSanitizer",
        stream_budget: int,
        state: "_ChatStreamState",
        surfaced: list,
        msg: str,
    ):
        """Stream the first-pass reply, stripping CoT and validating as it goes."""
        stream_iter = self.llm.generate_stream(
            prompt=user_prompt,
            system=system_instruction,
            model=model,
            options_override=endocrine_options,
        ).__aiter__()
        deadline = time.monotonic() + stream_budget

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()

            try:
                chunk = await asyncio.wait_for(
                    stream_iter.__anext__(), timeout=remaining
                )
            except StopAsyncIteration:
                break

            clean_chunk = sanitizer.feed(chunk)
            if not clean_chunk:
                continue

            # CoT strip check
            for segment in self._visible_segments(clean_chunk, state):
                async for out in self._emit_validated(segment, state, plan.goal):
                    yield out

        # Flush whatever the markup sanitizer was still holding back.
        for segment in self._visible_trailing(sanitizer.flush(), state):
            async for out in self._emit_validated(
                segment, state, plan.goal, allow_hesitation=False
            ):
                yield out

        # Post-generation grounding gate: the whole utterance is now known, so
        # check it for fabricated shared-memory claims and route any hit
        # through the same self-correction path.
        is_grounded, ground_reason = self._check_response_grounding(
            state.accumulated_response, surfaced, msg
        )
        if not is_grounded:
            await self._record_self_gaps(state.accumulated_response, surfaced, msg)
            raise MetacognitiveException(ground_reason)

        yield {"type": "done", "data": "finished"}

    async def _record_self_gaps(self, response: str, surfaced, user_message: str):
        """Note what the agent did not know about itself, and carry on.

        Only reached when the composite gate has already failed, so re-deriving
        the terms costs one regex pass on a response that is being thrown away
        regardless. Recording is best-effort: the turn has already been stopped
        from lying, and losing the note is far cheaper than raising here.
        """
        if self.self_knowledge is None:
            return
        gaps = self._self_claim_gaps(response, surfaced, user_message)
        if not gaps:
            return
        try:
            await self.self_knowledge.record_gap(gaps, user_message)
        except Exception as e:
            logger.debug(f"[Action] Could not record self-knowledge gap: {e}")

    async def _announce_self_correction(self, reason: str):
        """Interrupt playback so the retry is not spoken over the bad take."""
        if self.publish_cb:
            try:
                await self.publish_cb(
                    "control.interrupt", {"reason": reason, "interrupt": True}
                )
                await self.publish_cb(
                    "audio.stop", {"interrupt": True, "reason": reason}
                )
            except Exception as pe:
                logger.error(f"[System 3] Failed to publish interrupt: {pe}")

    async def _stream_self_correction(
        self,
        *,
        plan: ActionPlan,
        user_prompt: str,
        system_instruction: str,
        model,
        endocrine_options,
        stream_budget: int,
        surfaced: list,
        msg: str,
    ):
        """Second-pass regeneration after a System-3 violation.

        Any further violation (constraint or grounding, mid-stream or trailing)
        collapses to a single safe fallback line rather than a third attempt.

        The retry gets its own sanitizer and CoT state: the primary stream was
        abandoned mid-flight and may have left a partial control tag buffered or
        an unclosed `<thought>` open, which would corrupt the retry's first chunk.
        """
        sanitizer = ControlMarkupSanitizer()
        cot_state = _ChatStreamState()
        stream_iter = self.llm.generate_stream(
            prompt=user_prompt,
            system=system_instruction,
            model=model,
            options_override=endocrine_options,
        ).__aiter__()
        deadline = time.monotonic() + stream_budget
        accumulated_retry_response = ""
        is_valid = True
        emitted_any = False

        while is_valid:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                chunk = await asyncio.wait_for(
                    stream_iter.__anext__(), timeout=remaining
                )
            except StopAsyncIteration:
                break
            raw_chunk = sanitizer.feed(chunk)
            if not raw_chunk:
                continue

            for clean_chunk in self._visible_segments(raw_chunk, cot_state):
                candidate = accumulated_retry_response + clean_chunk
                is_valid, _ = self._validate_partial_response(candidate, plan.goal)
                if not is_valid:
                    logger.warning(
                        "[System 3] Retry also violated constraints; yielding safe fallback."
                    )
                    emitted_any = True
                    yield {"type": "content", "data": _SAFE_FALLBACK_LINE}
                    break

                # Check grounding on the accumulated response so far
                is_retry_grounded, retry_ground_reason = self._check_response_grounding(
                    candidate, surfaced, msg
                )
                if not is_retry_grounded:
                    logger.warning(
                        f"[System 3] Retry fabricated a memory claim: {retry_ground_reason}. Yielding safe fallback."
                    )
                    is_valid = False
                    emitted_any = True
                    yield {"type": "content", "data": _SAFE_FALLBACK_LINE}
                    break

                emitted_any = True
                yield {"type": "content", "data": clean_chunk}
                accumulated_retry_response = candidate

        if is_valid:
            trailing = "".join(
                self._visible_trailing(sanitizer.flush(), cot_state)
            )
            if trailing:
                candidate = accumulated_retry_response + trailing
                is_valid_trail, _ = self._validate_partial_response(
                    candidate, plan.goal
                )
                if not is_valid_trail:
                    logger.warning(
                        "[System 3] Retry trailing also violated constraints; yielding safe fallback."
                    )
                    emitted_any = True
                    yield {"type": "content", "data": _SAFE_FALLBACK_LINE}
                else:
                    # Check grounding on trailing content too
                    is_trail_grounded, trail_ground_reason = (
                        self._check_response_grounding(candidate, surfaced, msg)
                    )
                    if not is_trail_grounded:
                        logger.warning(
                            f"[System 3] Retry trailing fabricated a memory claim: {trail_ground_reason}. Yielding safe fallback."
                        )
                        emitted_any = True
                        yield {"type": "content", "data": _SAFE_FALLBACK_LINE}
                    else:
                        emitted_any = True
                        yield {"type": "content", "data": trailing}

        if not emitted_any:
            # An empty retry stream, an expired budget, or a deadline that had
            # already passed all land here. Without this the user hears
            # "Wait, let me rephrase that..." and then nothing at all.
            logger.warning("[System 3] Retry produced no content; yielding safe fallback.")
            yield {"type": "content", "data": _SAFE_FALLBACK_LINE}

        yield {"type": "done", "data": "finished"}

    async def _execute_respond_chat(self, plan: ActionPlan):
        """Generate a spoken reply: surface context, prompt, stream, self-correct."""
        msg = plan.payload.get("message", "")
        identity_prompt = plan.payload.get("identity_prompt", "You are my friend.")
        emotion = plan.payload.get("emotion_state", "neutral")
        model = plan.payload.get("model")

        # Contextual Enrichments
        surfaced = plan.payload.get("surfaced_memories", [])
        if not surfaced and self.memory:
            surfaced = await self._surface_fallback_memories(plan, msg)

        shared_history = self._build_shared_history(surfaced)
        tom_context = self._build_tom_context(plan.payload.get("user_mental_model"))

        # Static System Prompt (cached by inference engines like Ollama/vLLM)
        system_instruction = f"{identity_prompt}\n\n{_CHAT_GUIDELINE}"

        # Dynamic User Prompt. Ordering fights "lost in the middle": the factual
        # grounding (SHARED HISTORY) is placed LAST before the user's query so it
        # sits in the model's high-attention tail, adjacent to what it must
        # answer. The more abstract, lower-cost-to-lose context (goal, emotion,
        # Theory-of-Mind) goes earlier. Within the history block itself, memories
        # are already edge-loaded by reorder_for_long_context().
        user_prompt = f"Current Context:\n- Goal: {plan.goal}\n- Current Emotion: {emotion}\n{tom_context}{shared_history}\n\nUser: {msg}\nAssistant:"

        valence = plan.payload.get("valence", 0.0)
        arousal = plan.payload.get("arousal", 0.5)
        dominance = plan.payload.get("dominance", 0.5)

        try:
            endocrine_options = self._compute_endocrine_options(plan.payload)

            sanitizer = ControlMarkupSanitizer()
            stream_budget = max(15, int(getattr(Config, "LLM_STREAM_MAX_SECONDS", 120)))
            state = _ChatStreamState(dominance=dominance)

            prepended_tag = self._prepended_affect_tag(arousal, valence)
            if prepended_tag:
                yield {"type": "content", "data": prepended_tag}

            try:
                async for out in self._stream_primary_response(
                    plan=plan,
                    user_prompt=user_prompt,
                    system_instruction=system_instruction,
                    model=model,
                    endocrine_options=endocrine_options,
                    sanitizer=sanitizer,
                    stream_budget=stream_budget,
                    state=state,
                    surfaced=surfaced,
                    msg=msg,
                ):
                    yield out

            except MetacognitiveException as me:
                logger.warning(
                    f"[System 3] Metacognitive violation: {me.reason}. Triggering self-correction."
                )
                await self._announce_self_correction(me.reason)

                # Reported, not acted on: this layer has no StateService, and
                # giving it one to fire a hormone would invert the dependency.
                # The pipeline owns state and decides the response.
                yield {"type": "self_correction", "data": me.reason}

                yield {"type": "content", "data": " Wait, let me rephrase that... "}
                if endocrine_options is None:
                    endocrine_options = {}
                endocrine_options["temperature"] = min(
                    1.0, endocrine_options.get("temperature", 0.7) + 0.2
                )
                retry_prompt = (
                    user_prompt
                    + f"\n\nCRITICAL FIX: Your previous response violated constraints: {me.reason}. Correct it immediately and do not repeat the forbidden phrases."
                )

                try:
                    async for out in self._stream_self_correction(
                        plan=plan,
                        user_prompt=retry_prompt,
                        system_instruction=system_instruction,
                        model=model,
                        endocrine_options=endocrine_options,
                        stream_budget=stream_budget,
                        surfaced=surfaced,
                        msg=msg,
                    ):
                        yield out
                except Exception as inner_e:
                    logger.error(f"[System 3] Self-correction generation failed: {inner_e}")
                    # Without this the user hears "Wait, let me rephrase that..."
                    # followed by silence.
                    yield {"type": "content", "data": _SAFE_FALLBACK_LINE}
                    yield {"type": "done", "data": "finished"}

            except TimeoutError:
                logger.warning(
                    "[Action] Stream timed out after %ss; emitting graceful fallback.",
                    stream_budget,
                )
                yield {
                    "type": "content",
                    "data": "I'm having trouble thinking right now...",
                }
                yield {"type": "done", "data": ""}

        except Exception as e:
            logger.error(f"[Action] LLM Execution failed: {e}")
            yield {"type": "error", "data": str(e)}
            yield {"type": "done", "data": ""}

    async def _execute_store_memory(self, plan: ActionPlan):
        """Commit an explicitly requested memory."""
        content = plan.payload.get("content", "")
        # Using the new intelligent MemoryStore. Confirmation is gated on an
        # actual successful write: add_memory() returns False when persistence
        # fails, and an absent store writes nothing at all. Claiming "committed
        # to memory" in either case is a promise the agent cannot keep.
        if not self.memory:
            logger.error("[Action] STORE_MEMORY requested but no memory store is attached.")
            yield {"type": "error", "data": "Memory storage is unavailable."}
            yield {"type": "done", "data": ""}
            return

        stored = await self.memory.add_memory(
            content=content,
            importance=0.7,  # High importance for explicit 'remember' commands
            emotion=0.2,
            source="user",
        )
        if not stored:
            logger.error("[Action] Memory persistence failed for an explicit store request.")
            yield {"type": "error", "data": "Memory could not be stored."}
            yield {"type": "done", "data": ""}
            return

        yield {"type": "system", "data": "Memory securely consolidated."}
        yield {"type": "content", "data": "Got it, I've committed that to memory."}
        yield {"type": "done", "data": ""}

    async def execute(self, plan: ActionPlan) -> AsyncGenerator[dict[str, Any], None]:
        """
        Executes the plan and yields output chunks.
        """
        logger.info(
            f"[Action] Executing Decision: {plan.action_type} for Goal: {plan.goal}"
        )

        if plan.action_type == "RESPOND_CHAT":
            async for out in self._execute_respond_chat(plan):
                yield out

        elif plan.action_type == "STORE_MEMORY":
            async for out in self._execute_store_memory(plan):
                yield out

        elif plan.action_type == "BACKGROUND_CONSOLIDATION":
            # Already triggered by CognitiveService
            yield {"type": "done", "data": ""}

        else:
            logger.warning(f"[Action] Unrecognized action: {plan.action_type}")
            yield {"type": "error", "data": "Unknown operation."}
            yield {"type": "done", "data": ""}
