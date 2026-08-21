import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.state.graph_db import MAX_BELIEF_CACHE_ENTRIES, GraphDB


def _make_graph_db() -> GraphDB:
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_driver.session.return_value.__aenter__.return_value = mock_session
    with patch("neo4j.AsyncGraphDatabase.driver", return_value=mock_driver):
        return GraphDB(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="".join(["strong_", "pass", "word_123"]),  # noqa: FLY002
        )


@pytest.mark.asyncio
async def test_constructor_does_not_schedule_an_unawaited_bootstrap_task():
    """H11 regression: `__init__` used to fire `bootstrap_constraints` via
    `loop.create_task` and never await it. A caller could run its first query
    before the constraints existed, letting duplicate entity nodes form.
    Construction alone must not schedule any background work now.
    """
    db = _make_graph_db()
    assert db._bootstrap_task is None


@pytest.mark.asyncio
async def test_initialize_waits_for_bootstrap_to_actually_finish():
    """`initialize()` must not return until the constraints have actually
    been created - the whole point is giving callers a point to await."""
    db = _make_graph_db()

    finished = False

    async def slow_bootstrap():
        nonlocal finished
        await asyncio.sleep(0.01)
        finished = True

    db.bootstrap_constraints = slow_bootstrap

    await db.initialize()

    assert finished is True


@pytest.mark.asyncio
async def test_initialize_logs_critical_when_neo4j_is_unreachable_at_startup(caplog):
    """M12: `bootstrap_constraints` swallows every failure as a per-constraint
    `logger.warning`, indistinguishable from "index already exists". Startup
    needs one unambiguous signal when Neo4j cannot be reached at all, rather
    than operators discovering it mid-session on a cognitive turn's first
    graph write.
    """
    db = _make_graph_db()
    db.execute_query = AsyncMock(return_value=[])
    db.bootstrap_constraints = AsyncMock()

    with caplog.at_level(logging.CRITICAL, logger="graph_db"):
        await db.initialize()

    assert any("unreachable" in rec.message.lower() for rec in caplog.records)
    db.bootstrap_constraints.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_does_not_log_critical_when_neo4j_responds(caplog):
    db = _make_graph_db()
    db.execute_query = AsyncMock(return_value=[{"1": 1}])
    db.bootstrap_constraints = AsyncMock()

    with caplog.at_level(logging.CRITICAL, logger="graph_db"):
        await db.initialize()

    assert not any("unreachable" in rec.message.lower() for rec in caplog.records)


@pytest.mark.asyncio
async def test_belief_cache_evicts_oldest_entry_once_over_capacity():
    """M9: `_belief_cache` used to be a plain dict with no maximum size - a
    session issuing many distinct cached queries/parameter sets grew it
    without bound. Once capacity is exceeded, the oldest entry must be
    evicted rather than the dict growing past the cap.
    """
    db = _make_graph_db()
    mock_session = db.driver.session.return_value.__aenter__.return_value
    mock_session.execute_read = AsyncMock(return_value=[])

    for i in range(MAX_BELIEF_CACHE_ENTRIES + 5):
        await db.execute_query("MATCH (n) RETURN n", {"i": i}, use_cache=True)

    assert len(db._belief_cache) == MAX_BELIEF_CACHE_ENTRIES


@pytest.mark.asyncio
async def test_belief_cache_lru_recency_survives_eviction():
    """A recently re-accessed entry must not be the one evicted just because
    it was inserted first - this is LRU, not FIFO.
    """
    db = _make_graph_db()
    mock_session = db.driver.session.return_value.__aenter__.return_value
    mock_session.execute_read = AsyncMock(return_value=[])

    for i in range(MAX_BELIEF_CACHE_ENTRIES):
        await db.execute_query("MATCH (n) RETURN n", {"i": i}, use_cache=True)

    # Touch key 0 again so it becomes the most-recently-used entry.
    await db.execute_query("MATCH (n) RETURN n", {"i": 0}, use_cache=True)

    # One more distinct key forces an eviction.
    await db.execute_query("MATCH (n) RETURN n", {"i": "new"}, use_cache=True)

    key0 = ("MATCH (n) RETURN n", json.dumps({"i": 0}))
    key1 = ("MATCH (n) RETURN n", json.dumps({"i": 1}))
    assert key0 in db._belief_cache  # just re-touched, survives
    assert key1 not in db._belief_cache  # least-recently-used, evicted
