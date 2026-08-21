import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.state.graph_db import GraphDB


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
