"""`StateUpdate` is the single definition of the `state.update` affect broadcast.

It used to be an orphan: the model existed in `contracts.py` while the payload
it described lived as an 11-field dict literal duplicated across both publish
sites in `CognitivePipeline`. Two definitions of one wire contract, free to
drift — add a field to the broadcast and the model silently no longer matches
what `SurfacingAgent` reads to drive mood-congruent recall and vocal modulation.

These tests pin the wiring that removed the duplication: the pipeline builds the
broadcast *through* the model, and the model is the sole owner of the field set
and its defaults.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.cognitive.appraisal import AppraisalVector
from app.cognitive.decision import ActionPlan
from app.cognitive.pipeline import CognitivePipeline
from app.contracts import StateUpdate


# ---------------------------------------------------------------- from_snapshot


def test_from_snapshot_maps_every_modelled_field():
    """A value the snapshot supplies must reach the wire. Dropping one silently
    flattens that dimension of affect for every downstream consumer."""
    snapshot = {
        "mood": 0.4,
        "energy": 0.7,
        "dominance": 0.6,
        "trust": 0.8,
        "attachment": 0.3,
        "emotion": "happy",
        "interaction_count": 5,
        "cortisol": 0.2,
        "dopamine": 0.5,
        "fatigue": 0.1,
        "user_mental_model": {"guess": "curious"},
    }
    dumped = StateUpdate.from_snapshot(snapshot).model_dump()
    assert dumped == snapshot


def test_a_missing_key_falls_back_to_the_model_default_not_a_literal():
    """The whole point of the rewrite: defaults live on the model and nowhere
    else. A snapshot taken before a field exists must still produce the model's
    default for it, so the broadcast shape is stable across a partial state."""
    dumped = StateUpdate.from_snapshot({"mood": 0.9}).model_dump()

    assert dumped["mood"] == 0.9  # supplied value wins
    # Every other field present, at the model's declared default.
    assert dumped["energy"] == 0.5
    assert dumped["emotion"] == "neutral"
    assert dumped["interaction_count"] == 0
    assert dumped["user_mental_model"] is None
    assert set(dumped) == set(StateUpdate.model_fields)


def test_snapshot_keys_outside_the_schema_are_dropped():
    """`get_context_snapshot` also carries `valence`/`arousal`, which the
    broadcast never included. Leaking them would change the wire payload and
    hand consumers fields the contract does not promise."""
    dumped = StateUpdate.from_snapshot(
        {"mood": 0.1, "valence": 0.1, "arousal": 0.9, "junk": object()}
    ).model_dump()
    assert "valence" not in dumped
    assert "arousal" not in dumped
    assert "junk" not in dumped


# ---------------------------------------------------------------- on the wire


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

    identity = MagicMock()
    identity.validate_response = AsyncMock()

    return {
        "perception": AsyncMock(),
        "appraisal": MagicMock(),
        "state": state,
        "decision": decision,
        "action": MagicMock(),
        "learning": AsyncMock(),
        "identity": identity,
    }


@pytest.mark.asyncio
async def test_the_pipeline_broadcasts_the_state_update_through_the_model(
    mock_components,
):
    """End to end: the `state.update` the pipeline emits must be exactly what
    `StateUpdate.from_snapshot` produces — the proof the model is load-bearing
    rather than a shadow of a hand-written dict.

    The snapshot here is deliberately partial (`mood` only), which is why this
    catches a regression a fuller snapshot would not: it forces the model's
    defaults to fill the other ten fields, so a broadcast built from a stray
    literal with different defaults, or missing a field, would diverge here.
    """
    pipeline = CognitivePipeline(**mock_components)
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
    snapshot = {"mood": 0.33, "cortisol": 0.7}
    mock_components["state"].get_context_snapshot.return_value = snapshot
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

    broadcasts = [
        chunk
        async for chunk in pipeline.execute(
            {"type": "USER_MESSAGE", "content": "hello"}
        )
        if chunk.get("subject") == "state.update"
    ]

    assert broadcasts, "pipeline emitted no state.update"
    expected = StateUpdate.from_snapshot(snapshot).model_dump()
    for chunk in broadcasts:
        assert chunk["data"] == expected
        # The supplied values survived; the rest are model defaults.
        assert chunk["data"]["mood"] == 0.33
        assert chunk["data"]["cortisol"] == 0.7
        assert chunk["data"]["energy"] == 0.5
        assert set(chunk["data"]) == set(StateUpdate.model_fields)
