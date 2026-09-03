"""CommunicativeIntent / BehaviorDecision / InternalState (Phase 1B, §15
item 4) -- the typed decision stage 6 hands stage 8, separate from the
`decision.py` glue that builds one (covered in test_decision.py)."""

import pytest
from pydantic import ValidationError

from app.cognitive.behavior_contracts import (
    BehaviorDecision,
    CommunicativeIntent,
    InternalState,
)


def test_internal_state_from_snapshot_reads_known_keys():
    snapshot = {
        "mood": 0.4,
        "energy": 0.6,
        "dominance": 0.55,
        "trust": 0.7,
        "attachment": 0.3,
        "unrelated_key": "ignored",
    }
    state = InternalState.from_snapshot(snapshot)
    assert state.mood == 0.4
    assert state.trust == 0.7
    assert state.attachment == 0.3


def test_internal_state_from_snapshot_defaults_on_missing_keys():
    """A snapshot from a stub or an older caller may not carry every key --
    from_snapshot must not raise, and must fall back to the schema's own
    defaults rather than None."""
    state = InternalState.from_snapshot({})
    assert state.mood == 0.0
    assert state.trust == 0.5
    assert state.attachment == 0.1


def test_internal_state_from_snapshot_handles_none():
    state = InternalState.from_snapshot(None)
    assert state.mood == 0.0


def test_communicative_intent_rejects_urgency_out_of_bounds():
    with pytest.raises(ValidationError):
        CommunicativeIntent(act="CHAT", goal="ENGAGE", urgency=1.5)
    with pytest.raises(ValidationError):
        CommunicativeIntent(act="CHAT", goal="ENGAGE", urgency=-0.1)


def test_communicative_intent_rejects_unknown_relational_stance():
    with pytest.raises(ValidationError):
        CommunicativeIntent(act="CHAT", goal="ENGAGE", relational_stance="obsessed")


def test_behavior_decision_defaults_to_empty_claim_lists():
    decision = BehaviorDecision(intent=CommunicativeIntent(act="CHAT", goal="ENGAGE"))
    assert decision.allowed_claims == []
    assert decision.forbidden_claims == []
