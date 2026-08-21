import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CognitiveEvent:
    event_id: str
    event_type: str  # e.g. "USER_MESSAGE", "AUDIO_INPUT", "SYSTEM_TICK"
    raw_content: str
    metadata: dict[str, Any]
    intent: str | None = None  # e.g., "CHAT", "REFLECT", "REMEMBER"


class PerceptionService:
    """
    The Perception Layer.
    Converts raw I/O events (like a NATS message) into structured CognitiveEvents.
    Responsible for early filtering, intent classification, and formatting.
    """

    def __init__(self, llm_service=None):
        """
        Dependency injection for any models we might need for early perception
        (e.g., Llama 3.2 for simple lightweight intent classification).
        """
        self.llm = llm_service

    async def perceive(self, raw_event: dict[str, Any]) -> CognitiveEvent:
        """
        Takes raw dictionary (e.g. from NATS) and produces a CognitiveEvent.
        """
        # 1. Parse base fields
        event_id = raw_event.get("id", "unknown")
        event_type = raw_event.get("type", "USER_MESSAGE")
        content = raw_event.get("content", "")
        metadata = raw_event.get("metadata", {})

        # 2. Extract Intent
        # H9: USER_MESSAGE intent classification (REMEMBER vs CHAT, including the
        # question-negation guard for phrasing like "do you remember...?") lives
        # solely in DecisionService._apply_heuristic_intent_and_goal, which runs
        # unconditionally later in the pipeline and overwrites whatever is set
        # here. A second keyword heuristic in this method used to disagree with
        # it (e.g. classifying "do you remember my hometown?" as REMEMBER, which
        # DecisionService correctly treats as CHAT) without ever being able to
        # win, since Appraisal never reads `event.intent` either. SYSTEM_TICK is
        # the one case Perception's intent is load-bearing: DecisionService's
        # heuristic only applies to USER_MESSAGE, so REFLECT reaches the BT's
        # IsSystemTick condition untouched.
        intent = "CHAT"  # Default fallback

        if event_type == "SYSTEM_TICK":
            intent = "REFLECT"  # Idle reflection trigger

        logger.debug("[Perception] Extracted intent '%s' from %s", intent, event_type)

        return CognitiveEvent(
            event_id=event_id,
            event_type=event_type,
            raw_content=content,
            metadata=metadata,
            intent=intent,
        )
