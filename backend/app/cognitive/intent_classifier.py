from __future__ import annotations

from typing import Any, Protocol

from ..config import Config
from .perception import CognitiveEvent


class IntentClassifier(Protocol):
    async def classify(
        self, event: CognitiveEvent, state: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]: ...


class LLMIntentClassifier:
    def __init__(self, decision_service: Any):
        self._decision_service = decision_service

    async def classify(
        self, event: CognitiveEvent, state: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        self._decision_service._apply_heuristic_intent_and_goal(event)
        event.metadata["heuristic_intent"] = event.intent
        if Config.LLM_INTENT_CLASSIFICATION_ENABLED:
            await self._decision_service._classify_intent_and_goal(event, state)
        return event.intent, event.metadata


class HeuristicIntentClassifier:
    def __init__(self, decision_service: Any):
        self._decision_service = decision_service

    async def classify(
        self, event: CognitiveEvent, state: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        del state
        self._decision_service._apply_heuristic_intent_and_goal(event)
        event.metadata["heuristic_intent"] = event.intent
        return event.intent, event.metadata


def get_intent_classifier(decision_service: Any) -> IntentClassifier:
    if Config.INTENT_CLASSIFIER_BACKEND == "heuristic":
        return HeuristicIntentClassifier(decision_service)
    return LLMIntentClassifier(decision_service)
