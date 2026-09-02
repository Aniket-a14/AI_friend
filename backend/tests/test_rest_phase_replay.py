"""
Rest-phase-gated memory replay (Bucket 12, voice remediation Phase 3, items 2-3).

`_run_consolidation_pass` already re-scores and prunes memories via the
existing, independently-tested `apply_actr_decay` pipeline -- but only ever
on memories tied to whatever dialogue this tick's own 300s-silence gate just
consolidated, and that gate has no notion of night or fatigue at all. This
adds a second, orthogonal sweep gated on `is_rest_phase` (idle AND (night OR
fatigue > 0.8) -- the same "asleep or exhausted" condition dreaming already
keys off of) over a broader sample of recent high-importance memories.

These tests deliberately do not re-prove `apply_actr_decay`'s own pruning
math (see `test_eriksonian_cognitive_alignment.py` and
`test_memory_archive_cleanup.py` for that) -- only that this bucket's new
code (the gate, and the wiring into that existing pipeline) is correct.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.subconscious_agent import SubconsciousAgent, is_rest_phase
from app.state.memory_store import MemoryStore
from app.state.sqlite_fallback import SQLitePool

NOON = datetime(2026, 9, 2, 12, 0, 0).timestamp()  # a daytime timestamp
LATE_NIGHT = datetime(2026, 9, 2, 23, 0, 0).timestamp()  # 23:00, inside the night window
EARLY_MORNING = datetime(2026, 9, 2, 3, 0, 0).timestamp()  # 03:00, inside the night window


# --------------------------------------------------------------------------
# is_rest_phase: idle AND (night OR fatigue > 0.8)
# --------------------------------------------------------------------------


def test_not_idle_is_never_a_rest_phase_regardless_of_night_or_fatigue():
    """Idleness gates everything else -- an active conversation at 3am with
    high fatigue must not trigger a DB-writing sweep mid-turn."""
    last_interaction = EARLY_MORNING - 5.0  # only 5s idle
    assert not is_rest_phase(EARLY_MORNING, last_interaction, fatigue=0.95)


def test_idle_and_night_is_a_rest_phase_even_at_low_fatigue():
    last_interaction = EARLY_MORNING - 60.0
    assert is_rest_phase(EARLY_MORNING, last_interaction, fatigue=0.1)


def test_idle_and_high_fatigue_is_a_rest_phase_even_at_noon():
    """Reuses the dream sequence's own fatigue > 0.8 threshold -- a genuinely
    exhausted agent gets a rest phase without waiting for the clock."""
    last_interaction = NOON - 60.0
    assert is_rest_phase(NOON, last_interaction, fatigue=0.85)


def test_idle_daytime_low_fatigue_is_not_a_rest_phase():
    last_interaction = NOON - 60.0
    assert not is_rest_phase(NOON, last_interaction, fatigue=0.3)


def test_fatigue_exactly_at_the_threshold_is_not_yet_a_rest_phase():
    """`> 0.8`, not `>= 0.8` -- matches the dream gate's own strict
    inequality exactly, so the two conditions agree at the boundary."""
    last_interaction = NOON - 60.0
    assert not is_rest_phase(NOON, last_interaction, fatigue=0.8)


def test_idle_threshold_is_configurable_and_defaults_to_30_seconds():
    """Uses a high-fatigue context so the idle check is the only variable --
    otherwise NOON's daytime/low-fatigue combination would fail the night-or-
    fatigue condition regardless of idle time, masking what this test means
    to isolate."""
    last_interaction = NOON - 29.0
    assert not is_rest_phase(NOON, last_interaction, fatigue=0.9)
    assert is_rest_phase(NOON, last_interaction, fatigue=0.9, idle_threshold_s=20.0)


@pytest.mark.parametrize("hour", [22, 23, 0, 3, 5])
def test_every_hour_in_the_night_window_counts_as_night(hour):
    ts = datetime(2026, 9, 2, hour, 0, 0).timestamp()
    assert is_rest_phase(ts, ts - 60.0, fatigue=0.0)


@pytest.mark.parametrize("hour", [6, 12, 18, 21])
def test_every_hour_outside_the_night_window_does_not_count_as_night(hour):
    ts = datetime(2026, 9, 2, hour, 0, 0).timestamp()
    assert not is_rest_phase(ts, ts - 60.0, fatigue=0.0)


# --------------------------------------------------------------------------
# _run_rest_phase_replay: wiring into the existing apply_actr_decay pipeline
# --------------------------------------------------------------------------


def _agent(mock_graph_db):
    mock_memory_store = MagicMock()
    mock_memory_store.get_recent_high_importance_memory_contents = AsyncMock(
        return_value=[]
    )
    mock_memory_store.apply_actr_decay = AsyncMock()
    agent = SubconsciousAgent(
        memory_store=mock_memory_store,
        reflection_service=MagicMock(),
        graph_db=mock_graph_db,
    )
    return agent


@pytest.mark.asyncio
async def test_replay_fetches_candidates_using_the_configured_parameters(
    mock_graph_db,
):
    from app.config import Config

    agent = _agent(mock_graph_db)
    await agent._run_rest_phase_replay()

    agent.memory_store.get_recent_high_importance_memory_contents.assert_awaited_once_with(
        limit=Config.REST_PHASE_REPLAY_LIMIT,
        min_importance=Config.REST_PHASE_REPLAY_MIN_IMPORTANCE,
        lookback_hours=Config.REST_PHASE_REPLAY_LOOKBACK_HOURS,
    )


@pytest.mark.asyncio
async def test_replay_passes_the_fetched_contents_straight_to_actr_decay(
    mock_graph_db,
):
    """The whole point of reusing `apply_actr_decay` rather than writing a
    new pruning path: whatever this sweep samples must reach the exact same
    re-scoring/archiving pipeline the event-triggered consolidation uses."""
    agent = _agent(mock_graph_db)
    agent.memory_store.get_recent_high_importance_memory_contents = AsyncMock(
        return_value=["an old but important memory", "another one"]
    )

    await agent._run_rest_phase_replay()

    agent.memory_store.apply_actr_decay.assert_awaited_once_with(
        ["an old but important memory", "another one"]
    )


@pytest.mark.asyncio
async def test_replay_does_not_call_actr_decay_with_no_candidates(mock_graph_db):
    """An empty result must not turn into `apply_actr_decay([])` -- a
    no-op call that would still acquire a connection and run a query with an
    empty IN-list for nothing."""
    agent = _agent(mock_graph_db)  # default: no candidates

    await agent._run_rest_phase_replay()

    agent.memory_store.apply_actr_decay.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_fetch_failure_does_not_crash_the_subconscious_loop(mock_graph_db):
    """Mirrors every other method in this file's broad-except reasoning:
    memory maintenance failing must never take down the loop that also runs
    dreaming and proactive thought."""
    agent = _agent(mock_graph_db)
    agent.memory_store.get_recent_high_importance_memory_contents = AsyncMock(
        side_effect=RuntimeError("db unavailable")
    )

    await agent._run_rest_phase_replay()  # must not raise

    agent.memory_store.apply_actr_decay.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_decay_failure_does_not_crash_the_subconscious_loop(mock_graph_db):
    agent = _agent(mock_graph_db)
    agent.memory_store.get_recent_high_importance_memory_contents = AsyncMock(
        return_value=["something"]
    )
    agent.memory_store.apply_actr_decay = AsyncMock(
        side_effect=RuntimeError("archive write failed")
    )

    await agent._run_rest_phase_replay()  # must not raise


# --------------------------------------------------------------------------
# get_recent_high_importance_memory_contents: the new query, against a real
# in-memory SQLite MemoryStore (not a mock) -- the actual SQL is what has no
# prior coverage.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recent_high_importance_memory_contents_filters_correctly(
    mock_graph_db,
):
    pool = SQLitePool(":memory:")
    mem_store = MemoryStore(pool, mock_graph_db)
    mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)

    now = datetime.now(UTC)
    await mem_store.add_memory(
        "high importance, recent", importance=0.9, current_time=now
    )
    await mem_store.add_memory(
        "low importance, recent", importance=0.2, current_time=now
    )
    await mem_store.add_memory(
        "high importance, but outside the lookback window",
        importance=0.9,
        current_time=now - timedelta(days=30),
    )

    contents = await mem_store.get_recent_high_importance_memory_contents(
        limit=10, min_importance=0.5, lookback_hours=168
    )

    assert "high importance, recent" in contents
    assert "low importance, recent" not in contents
    assert "high importance, but outside the lookback window" not in contents


@pytest.mark.asyncio
async def test_get_recent_high_importance_memory_contents_respects_the_limit(
    mock_graph_db,
):
    pool = SQLitePool(":memory:")
    mem_store = MemoryStore(pool, mock_graph_db)
    mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)

    now = datetime.now(UTC)
    for i in range(5):
        await mem_store.add_memory(
            f"important memory {i}", importance=0.8, current_time=now
        )

    contents = await mem_store.get_recent_high_importance_memory_contents(
        limit=2, min_importance=0.5, lookback_hours=168
    )
    assert len(contents) == 2


@pytest.mark.asyncio
async def test_get_recent_high_importance_memory_contents_survives_a_db_failure(
    mock_graph_db,
):
    """A broken pool must degrade to an empty candidate list, not crash the
    rest-phase sweep that calls it -- the same defensive posture
    `get_recent_unconsolidated_episodes` already has."""
    pool = SQLitePool(":memory:")
    mem_store = MemoryStore(pool, mock_graph_db)
    pool.connection.conn.close()  # the pool object survives; the DB underneath does not

    contents = await mem_store.get_recent_high_importance_memory_contents()
    assert contents == []
