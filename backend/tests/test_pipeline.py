from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.appraisal import AppraisalVector
from app.cognitive.decision import ActionPlan
from app.cognitive.pipeline import CognitivePipeline


@pytest.fixture
def mock_components():
    state = MagicMock()
    state.update_from_appraisal = AsyncMock()
    state.update_theory_of_mind = AsyncMock()
    state.get_context_snapshot = MagicMock()
    state.get_behavioral_directive = MagicMock()

    decision = MagicMock()
    decision.decide = AsyncMock()
    decision.is_speculative_stop_confirmed = MagicMock()

    action = MagicMock()
    # execute is an async generator, so side_effect should be a function returning one.

    identity = MagicMock()
    identity.validate_response = AsyncMock()

    return {
        "perception": AsyncMock(),
        "appraisal": MagicMock(),
        "state": state,
        "decision": decision,
        "action": action,
        "learning": AsyncMock(),
        "identity": identity,
    }


@pytest.fixture
def pipeline(mock_components):
    return CognitivePipeline(**mock_components)


@pytest.mark.asyncio
async def test_pipeline_execution_flow(pipeline, mock_components):
    mock_components["state"].last_speculative_intent = None
    mock_components["perception"].perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="hello",
        intent="CHAT",
        event_id="evt-1",
        metadata={},
    )

    mock_components["appraisal"].appraise.return_value = AppraisalVector(
        relevance=1.0,
        novelty=0.5,
        goal_congruence=0.2,
        agency=0.8,
        norm_alignment=1.0,
        relationship_impact=0.1,
    )

    mock_components["state"].get_context_snapshot.return_value = {"mood": 0.0}
    mock_components["state"].get_behavioral_directive.return_value = "be friendly"

    mock_components["decision"].decide.return_value = ActionPlan(
        action_type="RESPOND_CHAT", goal="GREET", payload={"message": "hi"}
    )

    async def mock_execute(plan):
        yield {"type": "content", "data": "Hi there!"}
        yield {"type": "done", "data": ""}

    mock_components["action"].execute.side_effect = mock_execute
    mock_components["identity"].validate_response.return_value = (True, "")
    mock_components["identity"].get_persona_prompt.return_value = "System prompt"

    # Execute
    results = []
    async for chunk in pipeline.execute({"type": "USER_MESSAGE", "content": "hello"}):
        results.append(chunk)

    print(f"DEBUG RESULTS: {results}")
    assert results, "Pipeline yielded no results"
    # Verify
    assert any(r["type"] == "content" and r["data"] == "Hi there!" for r in results)
    assert any(r["type"] == "reflection_needed" for r in results)

    mock_components["perception"].perceive.assert_awaited_once()
    mock_components["appraisal"].appraise.assert_called_once()
    mock_components["state"].update_from_appraisal.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_carries_visual_context_into_the_plan_payload(
    pipeline, mock_components
):
    """P1-9/vision-grounding: `raw_event["metadata"]["visuals"]` (written by
    brain_agent from vision.frames/vision.description) has to survive the
    perception -> decision -> action-prep handoff and land in
    plan.payload["visual_context"], or action.py's `_build_visual_context`
    has nothing to render regardless of how correctly it's written."""
    mock_components["state"].last_speculative_intent = None
    mock_components["perception"].perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="what am I holding?",
        intent="CHAT",
        event_id="evt-2",
        metadata={"visuals": "I am seeing the user's camera."},
    )
    mock_components["appraisal"].appraise.return_value = AppraisalVector(
        relevance=1.0,
        novelty=0.5,
        goal_congruence=0.2,
        agency=0.8,
        norm_alignment=1.0,
        relationship_impact=0.1,
    )
    mock_components["state"].get_context_snapshot.return_value = {"mood": 0.0}
    mock_components["state"].get_behavioral_directive.return_value = "be friendly"
    mock_components["decision"].decide.return_value = ActionPlan(
        action_type="RESPOND_CHAT", goal="ANSWER", payload={"message": "hi"}
    )
    mock_components["identity"].validate_response.return_value = (True, "")
    mock_components["identity"].get_persona_prompt.return_value = "System prompt"

    seen_payloads = []

    async def mock_execute(plan):
        seen_payloads.append(plan.payload)
        yield {"type": "content", "data": "You're holding a mug."}
        yield {"type": "done", "data": ""}

    mock_components["action"].execute.side_effect = mock_execute

    async for _ in pipeline.execute(
        {"type": "USER_MESSAGE", "content": "what am I holding?"}
    ):
        pass

    assert seen_payloads, "action.execute was never called"
    assert seen_payloads[0]["visual_context"] == "I am seeing the user's camera."


@pytest.mark.asyncio
async def test_pipeline_sources_appraisal_boundaries_from_immutable_core(
    pipeline, mock_components
):
    """`identity.personality` (the raw personality.json dict) has no top-level
    "boundaries" key, so appraisal used to always score norm_alignment against
    an empty list regardless of what the persona actually forbids. If this
    regresses to reading `identity.personality.get("boundaries", ...)` again,
    a real boundary like "no hate" silently stops affecting appraisal."""
    mock_components["state"].last_speculative_intent = None
    mock_components["perception"].perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="hello",
        intent="CHAT",
        event_id="evt-3",
        metadata={},
    )
    mock_components["appraisal"].appraise.return_value = AppraisalVector(
        relevance=1.0,
        novelty=0.5,
        goal_congruence=0.2,
        agency=0.8,
        norm_alignment=1.0,
        relationship_impact=0.1,
    )
    mock_components["state"].get_context_snapshot.return_value = {"mood": 0.0}
    mock_components["state"].get_behavioral_directive.return_value = "be friendly"
    mock_components["decision"].decide.return_value = ActionPlan(
        action_type="RESPOND_CHAT", goal="GREET", payload={"message": "hi"}
    )
    mock_components["identity"].validate_response.return_value = (True, "")
    mock_components["identity"].get_persona_prompt.return_value = "System prompt"
    mock_components["identity"].personality = {}
    mock_components["identity"].immutable_core = {
        "values": ["Honesty", "Privacy"],
        "boundaries": ["Will never share user data", "Will not adopt toxic behavior"],
    }

    async def mock_execute(plan):
        yield {"type": "content", "data": "Hi there!"}
        yield {"type": "done", "data": ""}

    mock_components["action"].execute.side_effect = mock_execute

    async for _ in pipeline.execute({"type": "USER_MESSAGE", "content": "hello"}):
        pass

    _, kwargs = mock_components["appraisal"].appraise.call_args
    assert kwargs["identity_boundaries"] == [
        "Will never share user data",
        "Will not adopt toxic behavior",
    ]


@pytest.mark.asyncio
async def test_pipeline_interruption_confirmed(pipeline, mock_components):
    # Setup Interruption
    mock_components["state"].last_speculative_intent = {
        "text": "stop",
        "keywords": ["stop"],
        "utterance_id": "utt-1",
    }
    mock_components["decision"].is_speculative_stop_confirmed.return_value = True

    # Execute
    results = []
    async for chunk in pipeline.execute({"type": "USER_MESSAGE", "content": "stop!"}):
        results.append(chunk)

    # Verify
    assert len(results) == 2
    assert results[0]["type"] == "mesh_signal"
    assert results[0]["subject"] == "audio.stop"
    assert results[0]["data"]["reason"] == "confirmed_command"
    assert results[1]["type"] == "pipeline_telemetry"

    # Ensure rest of pipeline didn't run
    mock_components["perception"].perceive.assert_not_awaited()
