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
        intent = "CHAT"  # Default fallback

        if event_type == "SYSTEM_TICK":
            intent = "REFLECT"  # Idle reflection trigger

        elif event_type == "USER_MESSAGE" and self.llm:
            # Here we might use a quick zero-shot local LLM call to classify intent
            # e.g., "classify this as CHAT or REMEMBER: {content}"
            # For now, we mock the logic or do basic keyword routing:
            if "remember" in content.lower() or "memorize" in content.lower():
                intent = "REMEMBER"
            else:
                intent = "CHAT"

        logger.debug(f"[Perception] Extracted intent '{intent}' from {event_type}")

        return CognitiveEvent(
            event_id=event_id,
            event_type=event_type,
            raw_content=content,
            metadata=metadata,
            intent=intent,
        )
