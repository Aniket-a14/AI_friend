"""
P3-1: salience-gated visual episodic memory.

Covers the write/prune surface on MemoryStore (add_visual_screen_trace,
prune_expired_visual_screen_traces) and the three-signal gate in
SubconsciousAgent._on_vision_description (novelty, description presence,
affective significance) plus its wiring into the periodic consolidation
pass.
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.subconscious_agent import SubconsciousAgent
from app.config import Config
from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore


@pytest.fixture
async def real_memory_store(mock_graph_db):
    """A MemoryStore backed by a real (in-memory) SQLite pool, so schema
    and query correctness are exercised for real rather than through a mock
    that would happily accept a query against a table that doesn't exist.

    `conftest.py`'s fake-asyncpg SQLite shim only creates the tables
    `ConversationHistoryStore` itself manages (sessions/messages/
    agent_configs); every other production table is created inline per-test
    -- the same convention `test_subconscious_consolidation.py` already
    follows for `memories`.
    """
    store = ConversationHistoryStore()
    await store.initialize()
    async with store.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS visual_screen_traces (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                valence REAL DEFAULT 0.0,
                arousal REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph_db)
    mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)
    yield mem_store
    await mem_store.close()
    await store.close()


# --------------------------------------------------------------------------
# MemoryStore.add_visual_screen_trace / prune_expired_visual_screen_traces
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_visual_screen_trace_persists_a_row(real_memory_store):
    await real_memory_store.add_visual_screen_trace(
        description="The user has a spreadsheet open.", valence=0.2, arousal=0.6
    )

    async with real_memory_store.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM visual_screen_traces")

    assert len(rows) == 1
    assert rows[0]["description"] == "The user has a spreadsheet open."
    assert rows[0]["valence"] == 0.2
    assert rows[0]["arousal"] == 0.6


@pytest.mark.asyncio
async def test_prune_expired_visual_screen_traces_removes_only_stale_rows(
    real_memory_store,
):
    """The privacy guarantee this exists for: a screen trace must not
    outlive its TTL, but a fresh one must survive an unrelated prune."""
    import uuid

    now = datetime.now(UTC)
    stale_created_at = (now - timedelta(hours=48)).isoformat()
    fresh_created_at = now.isoformat()

    async with real_memory_store.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO visual_screen_traces (id, description, valence, arousal, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            str(uuid.uuid4()),
            "stale trace",
            0.0,
            0.5,
            stale_created_at,
        )
        await conn.execute(
            "INSERT INTO visual_screen_traces (id, description, valence, arousal, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            str(uuid.uuid4()),
            "fresh trace",
            0.0,
            0.5,
            fresh_created_at,
        )

    await real_memory_store.prune_expired_visual_screen_traces(
        ttl_hours=24.0, current_time=now
    )

    async with real_memory_store.pool.acquire() as conn:
        rows = await conn.fetch("SELECT description FROM visual_screen_traces")

    descriptions = {r["description"] for r in rows}
    assert descriptions == {"fresh trace"}


@pytest.mark.asyncio
async def test_prune_expired_visual_screen_traces_defaults_to_config_ttl(
    real_memory_store,
):
    """No explicit ttl_hours must fall back to Config.VISUAL_SCREEN_TRACE_TTL_H,
    not silently no-op."""
    import uuid

    now = datetime.now(UTC)
    past_ttl = now - timedelta(hours=Config.VISUAL_SCREEN_TRACE_TTL_H + 1)

    async with real_memory_store.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO visual_screen_traces (id, description, valence, arousal, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            str(uuid.uuid4()),
            "past the default TTL",
            0.0,
            0.5,
            past_ttl.isoformat(),
        )

    await real_memory_store.prune_expired_visual_screen_traces(current_time=now)

    async with real_memory_store.pool.acquire() as conn:
        rows = await conn.fetch("SELECT description FROM visual_screen_traces")

    assert rows == []


# --------------------------------------------------------------------------
# SubconsciousAgent._on_vision_description -- the three-signal gate
# --------------------------------------------------------------------------


def _agent(memory_store=None, valence=0.0, arousal=0.5):
    state_service = MagicMock()
    state_service.current_state.valence = valence
    state_service.current_state.arousal = arousal
    agent = SubconsciousAgent(
        state_service=state_service,
        graph_db=MagicMock(),
        memory_store=memory_store or MagicMock(),
    )
    agent.memory_store.add_memory = AsyncMock(return_value=True)
    agent.memory_store.add_visual_screen_trace = AsyncMock(return_value=None)
    return agent


@pytest.mark.asyncio
async def test_not_novel_frame_is_never_stored():
    agent = _agent(arousal=0.9)  # affect clears the bar easily
    await agent._on_vision_description(
        {"description": "A cup of tea.", "source": "camera", "is_novel": False}
    )
    agent.memory_store.add_memory.assert_not_awaited()
    agent.memory_store.add_visual_screen_trace.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_description_is_never_stored():
    agent = _agent(arousal=0.9)
    await agent._on_vision_description(
        {"description": "", "source": "camera", "is_novel": True}
    )
    agent.memory_store.add_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_affectively_neutral_moment_is_never_stored():
    """Both thresholds must fail to trigger the skip -- a genuinely neutral
    baseline (valence=0.0, arousal=0.5) must not mint a memory every tick,
    or salience gating provides no gating at all."""
    agent = _agent(valence=0.0, arousal=0.5)
    await agent._on_vision_description(
        {"description": "An empty desk.", "source": "camera", "is_novel": True}
    )
    agent.memory_store.add_memory.assert_not_awaited()
    agent.memory_store.add_visual_screen_trace.assert_not_awaited()


@pytest.mark.asyncio
async def test_high_arousal_camera_frame_is_stored_via_add_memory():
    agent = _agent(valence=0.0, arousal=0.8)
    await agent._on_vision_description(
        {"description": "The user is laughing.", "source": "camera", "is_novel": True}
    )
    agent.memory_store.add_memory.assert_awaited_once()
    kwargs = agent.memory_store.add_memory.await_args.kwargs
    assert kwargs["content"] == "The user is laughing."
    assert kwargs["modality"] == "visual"
    assert kwargs["source"] == "vision_camera"
    agent.memory_store.add_visual_screen_trace.assert_not_awaited()


@pytest.mark.asyncio
async def test_high_valence_screen_frame_is_stored_via_screen_trace():
    """|valence| alone must be sufficient -- arousal need not also clear
    its own threshold."""
    agent = _agent(valence=-0.4, arousal=0.5)
    await agent._on_vision_description(
        {
            "description": "An error dialog is on screen.",
            "source": "screen",
            "is_novel": True,
        }
    )
    agent.memory_store.add_visual_screen_trace.assert_awaited_once()
    kwargs = agent.memory_store.add_visual_screen_trace.await_args.kwargs
    assert kwargs["description"] == "An error dialog is on screen."
    agent.memory_store.add_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_is_novel_field_defaults_to_stored():
    """A producer that predates this field (or a schema-validated message
    with the field simply omitted) must not silently suppress storage --
    matches the contract's own `is_novel: bool = True` default."""
    agent = _agent(arousal=0.9)
    await agent._on_vision_description(
        {"description": "A birthday cake.", "source": "camera"}
    )
    agent.memory_store.add_memory.assert_awaited_once()


# --------------------------------------------------------------------------
# Wiring into the existing periodic consolidation pass
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidation_pass_prunes_visual_screen_traces_unconditionally(
    mock_graph_db,
):
    """The TTL prune must run every consolidation pass regardless of whether
    there were any unconsolidated chat episodes -- it has nothing to do
    with chat consolidation and must not be gated behind it."""
    mock_memory_store = MagicMock()
    mock_memory_store.get_recent_unconsolidated_episodes = AsyncMock(return_value=[])
    mock_memory_store.prune_expired_visual_screen_traces = AsyncMock(
        return_value=None
    )

    agent = SubconsciousAgent(
        memory_store=mock_memory_store,
        reflection_service=MagicMock(),
        graph_db=mock_graph_db,
    )
    agent.state_service.current_state.last_user_interaction = time.time() - 301
    agent.engine.evaluate_and_think = AsyncMock(return_value=None)

    await agent._on_system_tick({"uptime": 100})
    await agent._consolidation_task

    mock_memory_store.prune_expired_visual_screen_traces.assert_awaited_once()
