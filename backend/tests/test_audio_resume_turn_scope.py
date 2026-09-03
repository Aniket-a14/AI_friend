"""Phase 2D (§15 item 8, remaining half): turn-scoped `audio.resume`.

`AudioStop` was already turn-scoped (Rust checks `stop.turn_id` against the
turn currently speaking before honouring a stop). `AudioResume` was the one
gap -- a resume delayed in the mesh could restore volume for a turn that had
since genuinely stopped, because nothing on the wire let the Rust side tell
the two apart. This mirrors `AudioStop`'s existing pattern symmetrically.

The Rust-side enforcement (`mesh_signal_applies_to_active_turn`,
`crates/voice-agent/src/main.rs`) has its own `cargo test` coverage in that
crate's `mod tests` -- this file covers the Python-side wire contract and
the pipeline publisher that stamps `turn_id` onto the `audio.resume` signal.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.appraisal import AppraisalVector
from app.cognitive.decision import ActionPlan
from app.cognitive.pipeline import CognitivePipeline
from app.contracts import AudioResume


def test_audio_resume_defaults_turn_id_to_none():
    """A publisher that predates Phase 2D still validates -- additive field,
    default None, matching `AudioStop.turn_id`'s own default."""
    resume = AudioResume()
    assert resume.turn_id is None


def test_audio_resume_carries_turn_id_when_supplied():
    resume = AudioResume(turn_id="turn-1")
    assert resume.turn_id == "turn-1"


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
async def test_rejected_interruption_stamps_turn_id_on_audio_resume(
    pipeline, mock_components
):
    """The failure this guards: a resume delayed in the mesh restoring
    volume for a turn that has since actually stopped, because nothing on
    the wire let the Rust side tell them apart.

    A rejected interruption doesn't stop the pipeline (only a *confirmed*
    one does, per `_resolve_turn_conflict`'s `result["stop"]`) -- the rest of
    the turn still has to run, so this needs the same full mock setup as
    `test_pipeline.py::test_pipeline_execution_flow`.
    """
    mock_components["state"].last_speculative_intent = {
        "text": "actually never mind",
        "keywords": ["stop"],
        "utterance_id": "utt-1",
    }
    mock_components["decision"].is_speculative_stop_confirmed.return_value = False

    mock_components["perception"].perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="actually never mind",
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
        action_type="RESPOND_CHAT", goal="GREET", payload={"message": "ok"}
    )

    async def mock_execute(plan):
        yield {"type": "content", "data": "ok"}
        yield {"type": "done", "data": ""}

    mock_components["action"].execute.side_effect = mock_execute
    mock_components["identity"].validate_response.return_value = (True, "")
    mock_components["identity"].get_persona_prompt.return_value = "System prompt"

    results = []
    async for chunk in pipeline.execute(
        {
            "type": "USER_MESSAGE",
            "content": "actually never mind",
            "metadata": {"turn_id": "turn-42"},
        }
    ):
        results.append(chunk)

    resume_signals = [r for r in results if r.get("subject") == "audio.resume"]
    assert len(resume_signals) == 1
    assert resume_signals[0]["data"]["turn_id"] == "turn-42"


@pytest.mark.asyncio
async def test_rejected_interruption_with_no_turn_id_stamps_none(
    pipeline, mock_components
):
    """An event carrying no `metadata.turn_id` (e.g. STT paths that can't
    always name the turn they're interrupting) must still publish, unscoped
    -- `None` on the wire, which the Rust side treats as "always applies"."""
    mock_components["state"].last_speculative_intent = {
        "text": "stop please",
        "keywords": ["stop"],
        "utterance_id": "utt-1",
    }
    mock_components["decision"].is_speculative_stop_confirmed.return_value = False

    mock_components["perception"].perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="stop please",
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
        action_type="RESPOND_CHAT", goal="GREET", payload={"message": "ok"}
    )

    async def mock_execute(plan):
        yield {"type": "content", "data": "ok"}
        yield {"type": "done", "data": ""}

    mock_components["action"].execute.side_effect = mock_execute
    mock_components["identity"].validate_response.return_value = (True, "")
    mock_components["identity"].get_persona_prompt.return_value = "System prompt"

    results = []
    async for chunk in pipeline.execute(
        {"type": "USER_MESSAGE", "content": "stop please"}
    ):
        results.append(chunk)

    resume_signals = [r for r in results if r.get("subject") == "audio.resume"]
    assert len(resume_signals) == 1
    assert resume_signals[0]["data"]["turn_id"] is None
