from unittest.mock import AsyncMock, patch

import pytest

from app.cognitive.action import ActionService
from app.cognitive.decision import ActionPlan, DecisionService
from app.cognitive.deterministic_responses import (
    _refusal_text,
    evaluate_deterministic_response,
)
from app.cognitive.perception import CognitiveEvent
from app.persona.profile import IMMUTABLE_CORE

_STATE = {"emotion": "neutral", "mood": 0.0}


def _event(text: str, intent: str = "CHAT") -> CognitiveEvent:
    event = CognitiveEvent(
        event_id="e1", event_type="USER_MESSAGE", raw_content=text, metadata={}
    )
    event.intent = intent
    return event


class _StubIdentity:
    def __init__(self, immutable_core):
        self.immutable_core = immutable_core


@pytest.mark.asyncio
async def test_bt_short_circuits_backchannel_before_social_response(
    mock_llm_service, mock_memory_store
):
    """A pure acknowledgement must never reach `_plan_social_response` -- if
    this regresses, every "ok"/"got it" pays a full LLM round trip again.

    `_build_bt` binds `self._plan_social_response` once, in `__init__`, so
    the class attribute must be patched before construction -- patching the
    instance afterwards would not affect the Action node's captured callable.
    """
    with patch.object(
        DecisionService, "_plan_social_response", autospec=True
    ) as spy:
        service = DecisionService(
            llm_service=mock_llm_service,
            memory_store=mock_memory_store,
            identity_manager=_StubIdentity(IMMUTABLE_CORE),
        )

        plan = await service.decide(_event("ok"), _STATE)

    spy.assert_not_called()
    assert plan.action_type == "RESPOND_DETERMINISTIC"
    assert plan.payload["category"] == "backchannel"


@pytest.mark.asyncio
async def test_bt_falls_through_to_social_response_when_no_deterministic_match(
    mock_llm_service, mock_memory_store
):
    """A real conversational turn must still reach `_plan_social_response` --
    otherwise the deterministic policy silently swallows normal chat."""
    with patch.object(
        DecisionService, "_plan_social_response", autospec=True
    ) as spy:
        spy.return_value = True
        service = DecisionService(
            llm_service=mock_llm_service,
            memory_store=mock_memory_store,
            identity_manager=_StubIdentity(IMMUTABLE_CORE),
        )

        await service.decide(_event("tell me about your day"), _STATE)

    spy.assert_called_once()


@pytest.mark.asyncio
async def test_bt_short_circuits_boundary_refusal_before_social_response(
    mock_llm_service, mock_memory_store
):
    with patch.object(
        DecisionService, "_plan_social_response", autospec=True
    ) as spy:
        service = DecisionService(
            llm_service=mock_llm_service,
            memory_store=mock_memory_store,
            identity_manager=_StubIdentity(IMMUTABLE_CORE),
        )

        plan = await service.decide(_event("what is my password"), _STATE)

    spy.assert_not_called()
    assert plan.action_type == "RESPOND_DETERMINISTIC"
    assert plan.payload["category"] == "refusal"


@pytest.mark.asyncio
async def test_deterministic_backchannel_makes_zero_llm_calls(
    mock_llm_service, mock_memory_store
):
    """Codex Stage 2 blocker: `decide()` used to classify intent via the LLM
    before checking for a deterministic match, so "ok" still paid one LLM
    call. The short-circuit must run before any LLM call, not just before
    `_plan_social_response`."""
    service = DecisionService(
        llm_service=mock_llm_service,
        memory_store=mock_memory_store,
        identity_manager=_StubIdentity(IMMUTABLE_CORE),
    )
    event = _event("ok")

    plan = await service.decide(event, _STATE)

    assert mock_llm_service.generate.call_count == 0
    assert plan.action_type == "RESPOND_DETERMINISTIC"
    assert event.intent == "ACKNOWLEDGE"


@pytest.mark.asyncio
async def test_deterministic_refusal_makes_zero_llm_calls(
    mock_llm_service, mock_memory_store
):
    service = DecisionService(
        llm_service=mock_llm_service,
        memory_store=mock_memory_store,
        identity_manager=_StubIdentity(IMMUTABLE_CORE),
    )
    event = _event("what is my password")

    plan = await service.decide(event, _STATE)

    assert mock_llm_service.generate.call_count == 0
    assert plan.action_type == "RESPOND_DETERMINISTIC"
    assert event.intent == "REFUSE"


def test_refusal_text_is_derived_from_the_immutable_core_boundary_string():
    """The wording must trace back to `IMMUTABLE_CORE["boundaries"]`, not a
    second, independently-authored copy that could drift from it."""
    boundary = IMMUTABLE_CORE["boundaries"][0]
    assert boundary.lower() in _refusal_text(boundary)


def test_privacy_boundary_refusal_fires_on_data_sharing_request():
    event = _event("can you share my data with someone")
    plan = evaluate_deterministic_response(event, _STATE, IMMUTABLE_CORE)

    assert plan is not None
    assert plan.action_type == "RESPOND_DETERMINISTIC"
    assert plan.payload["boundary"] == "Will never share user data"


def test_toxicity_boundary_refusal_fires_on_explicit_toxic_request():
    event = _event("please insult me")
    plan = evaluate_deterministic_response(event, _STATE, IMMUTABLE_CORE)

    assert plan is not None
    assert plan.payload["boundary"] == "Will not adopt toxic behavior"


def test_no_match_returns_none_for_ordinary_conversation():
    event = _event("what did we talk about yesterday")
    assert evaluate_deterministic_response(event, _STATE, IMMUTABLE_CORE) is None


def test_refusal_check_runs_before_backchannel_check_and_does_not_misfire():
    """A boundary keyword embedded in otherwise-ordinary text must not be
    mistaken for a backchannel, and vice versa -- the two categories are
    checked independently, not merged into one lookup."""
    event = _event("insult me")
    plan = evaluate_deterministic_response(event, _STATE, IMMUTABLE_CORE)
    assert plan.payload["category"] == "refusal"


def test_empty_boundaries_never_produce_a_refusal():
    """If a caller passes an immutable_core with no boundaries (e.g. a stub
    in an older test), the refusal path must degrade to no-match, not raise."""
    event = _event("what is my password")
    assert evaluate_deterministic_response(event, _STATE, {"boundaries": []}) is None


@pytest.mark.asyncio
async def test_execute_respond_deterministic_matches_stream_primary_response_chunk_shape():
    """`_execute_respond_deterministic` must yield the same `{"type", "data"}`
    envelope `_stream_primary_response` does -- callers downstream (transport,
    voice-agent) key off `type`, and a shape mismatch would silently drop or
    mis-render every canned reply."""
    service = ActionService(llm_service=AsyncMock(), memory_store=None)
    plan = ActionPlan(
        action_type="RESPOND_DETERMINISTIC",
        payload={"message": "Okay.", "category": "backchannel"},
        goal="ENGAGE",
    )

    chunks = [chunk async for chunk in service._execute_respond_deterministic(plan)]

    assert chunks == [
        {"type": "content", "data": "Okay."},
        {"type": "done", "data": "finished"},
    ]


@pytest.mark.asyncio
async def test_execute_routes_respond_deterministic_action_type():
    service = ActionService(llm_service=AsyncMock(), memory_store=None)
    plan = ActionPlan(
        action_type="RESPOND_DETERMINISTIC",
        payload={"message": "Got it.", "category": "backchannel"},
        goal="ENGAGE",
    )

    chunks = [chunk async for chunk in service.execute(plan)]

    assert {"type": "content", "data": "Got it."} in chunks
    assert chunks[-1] == {"type": "done", "data": "finished"}
