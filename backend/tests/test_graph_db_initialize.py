import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.state.graph_db import MAX_BELIEF_CACHE_ENTRIES, GraphDB


def _make_graph_db() -> GraphDB:
    mock_driver = MagicMock()
    mock_driver.close = AsyncMock()
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


@pytest.mark.asyncio
async def test_close_waits_for_an_in_flight_query_before_closing_the_driver():
    """L7: `close()` used to cancel the bootstrap task and immediately call
    `driver.close()`, with no regard for a concurrent `execute_query()` call
    still in flight (e.g. a background reflection/decay task) - that call
    would then raise an unhandled connection error instead of finishing or
    failing on its own terms.
    """
    db = _make_graph_db()
    db.bootstrap_constraints = AsyncMock()
    query_started = asyncio.Event()
    release_query = asyncio.Event()

    async def slow_session_read(tx_func):
        query_started.set()
        await release_query.wait()
        return []

    mock_session = db.driver.session.return_value.__aenter__.return_value
    mock_session.execute_read = slow_session_read

    query_task = asyncio.create_task(db.execute_query("MATCH (n) RETURN n"))
    await query_started.wait()

    close_task = asyncio.create_task(db.close())
    await asyncio.sleep(0.01)
    assert not close_task.done()  # must still be waiting on the query
    assert db.driver.close.await_count == 0

    release_query.set()
    await query_task
    await close_task

    assert db.driver.close.await_count == 1


@pytest.mark.asyncio
async def test_close_does_not_hang_forever_on_a_stuck_query(monkeypatch):
    """A query that never finishes must not block shutdown indefinitely -
    close() should time out and proceed anyway, loudly."""
    import app.state.graph_db as graph_db_module

    monkeypatch.setattr(graph_db_module, "GRAPHDB_CLOSE_DRAIN_TIMEOUT_SECONDS", 0.05)

    db = _make_graph_db()
    db.bootstrap_constraints = AsyncMock()

    async def hung_session_read(tx_func):
        await asyncio.sleep(999)
        return []

    mock_session = db.driver.session.return_value.__aenter__.return_value
    mock_session.execute_read = hung_session_read

    query_task = asyncio.create_task(db.execute_query("MATCH (n) RETURN n"))
    await asyncio.sleep(0.01)

    await db.close()

    assert db.driver.close.await_count == 1
    query_task.cancel()
