from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.decision import DecisionService
from app.cognitive.intent_classifier import (
    HeuristicIntentClassifier,
    LLMIntentClassifier,
    get_intent_classifier,
)
from app.cognitive.perception import CognitiveEvent
from app.config import Config


def _event(content="Remember my birthday"):
    return CognitiveEvent(
        event_id="intent-test",
        event_type="USER_MESSAGE",
        raw_content=content,
        metadata={},
    )


@pytest.mark.asyncio
async def test_default_backend_matches_legacy_classification_output(monkeypatch):
    monkeypatch.setattr(Config, "INTENT_CLASSIFIER_BACKEND", "llm", raising=False)
    response = '{"intent": "REMEMBER", "goal": "RECALL"}'

    legacy_service = DecisionService(llm_service=MagicMock())
    legacy_service.llm.generate = AsyncMock(return_value=response)
    legacy_event = _event()
    legacy_service._apply_heuristic_intent_and_goal(legacy_event)
    legacy_event.metadata["heuristic_intent"] = legacy_event.intent
    await legacy_service._classify_intent_and_goal(
        legacy_event, {"emotion": "neutral", "mood": 0.0}
    )

    service = DecisionService(llm_service=MagicMock())
    service.llm.generate = AsyncMock(return_value=response)
    event = _event()
    result = await get_intent_classifier(service).classify(
        event, {"emotion": "neutral", "mood": 0.0}
    )

    assert result == (legacy_event.intent, legacy_event.metadata)
    assert event.intent == legacy_event.intent
    assert event.metadata == legacy_event.metadata


@pytest.mark.asyncio
async def test_heuristic_backend_uses_existing_fast_path(monkeypatch):
    monkeypatch.setattr(Config, "INTENT_CLASSIFIER_BACKEND", "heuristic", raising=False)
    service = DecisionService(llm_service=MagicMock())
    event = _event("do you remember my birthday?")

    result = await get_intent_classifier(service).classify(event, {})

    assert isinstance(get_intent_classifier(service), HeuristicIntentClassifier)
    assert result[0] == "CHAT"
    assert result[1]["heuristic_intent"] == "CHAT"
    service.llm.generate.assert_not_called()


def test_default_factory_returns_llm_classifier(monkeypatch):
    monkeypatch.setattr(Config, "INTENT_CLASSIFIER_BACKEND", "llm", raising=False)

    classifier = get_intent_classifier(DecisionService(llm_service=MagicMock()))

    assert isinstance(classifier, LLMIntentClassifier)
