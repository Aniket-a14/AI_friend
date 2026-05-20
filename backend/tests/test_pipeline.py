import pytest
from unittest.mock import AsyncMock, MagicMock
from app.cognitive.pipeline import CognitivePipeline
from app.cognitive.decision import ActionPlan
from app.cognitive.appraisal import AppraisalVector


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
    assert len(results) == 1
    assert results[0]["type"] == "mesh_signal"
    assert results[0]["subject"] == "audio.stop"
    assert results[0]["data"]["reason"] == "confirmed_command"

    # Ensure rest of pipeline didn't run
    mock_components["perception"].perceive.assert_not_awaited()
