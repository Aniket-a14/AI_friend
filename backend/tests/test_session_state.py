"""Phase 2B: `SessionState` and its `WorkingMemoryStore`-backed persistence."""

import pytest

from app.state.session_state import (
    SessionState,
    load_session_state,
    persist_session_state,
)
from app.state.working_memory_store import WorkingMemoryStore


def _make_store(db_path: str) -> WorkingMemoryStore:
    """A store with no reachable Redis, forced onto the SQLite fallback --
    same pattern `test_working_memory_store.py` uses."""
    return WorkingMemoryStore(
        redis_host="127.0.0.1",
        redis_port=1,  # nothing listens here; connect fails fast
        db_path=db_path,
        max_turns=8,
    )


def test_start_turn_generates_a_turn_id_when_none_supplied():
    """Every turn gets an identity, not just the ones some future producer
    remembers to stamp -- the failure this guards is a `SessionState` whose
    `turn_id` silently reads as None downstream."""
    session_state = SessionState.start_turn()
    assert session_state.turn_id
    assert isinstance(session_state.turn_id, str)

    # Two turns never collide.
    other = SessionState.start_turn()
    assert other.turn_id != session_state.turn_id


def test_start_turn_uses_the_supplied_turn_id_when_given():
    session_state = SessionState.start_turn(turn_id="turn-abc")
    assert session_state.turn_id == "turn-abc"


def test_start_turn_defaults():
    session_state = SessionState.start_turn(turn_id="t1")
    assert session_state.utterance_id is None
    assert session_state.speculative is False
    assert session_state.active_interruption == "none"


def test_to_dict_round_trips_into_the_dataclass():
    session_state = SessionState.start_turn(
        turn_id="t1", utterance_id="u1", speculative=True
    )
    rehydrated = SessionState(**session_state.to_dict())
    assert rehydrated == session_state


@pytest.mark.asyncio
async def test_persist_and_load_round_trip_via_working_memory_store(tmp_path):
    store = _make_store(str(tmp_path / "working.db"))
    session_state = SessionState.start_turn(
        turn_id="t1", utterance_id="u1", speculative=True
    )
    session_state.active_interruption = "stop"

    await persist_session_state(store, session_state)
    loaded = await load_session_state(store)

    assert loaded == session_state


@pytest.mark.asyncio
async def test_persist_and_load_are_no_ops_with_no_store():
    """A `CognitivePipeline` built without a `session_store` (most unit
    tests, and any deployment that hasn't wired one) must not error."""
    session_state = SessionState.start_turn(turn_id="t1")
    await persist_session_state(None, session_state)  # must not raise
    assert await load_session_state(None) is None


@pytest.mark.asyncio
async def test_load_session_state_returns_none_when_nothing_was_persisted(tmp_path):
    store = _make_store(str(tmp_path / "working.db"))
    assert await load_session_state(store) is None
