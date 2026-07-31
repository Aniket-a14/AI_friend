"""
Reinforce-on-repeat dedup tests for MemoryStore.add_memory.

Human memory consolidates a repeated statement into the existing trace rather
than storing a fresh copy each time. add_memory must therefore detect an
identical content+wing memory and strengthen it (recall_count, recency,
importance) instead of minting a duplicate row that would inflate retrieval and
distort ACT-R frequency.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore

_MEMORIES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        content TEXT,
        raw_content TEXT,
        wing TEXT,
        room TEXT,
        embedding TEXT,
        importance_score REAL,
        emotional_weight REAL,
        valence REAL,
        certainty REAL,
        source TEXT,
        metadata TEXT,
        recall_count INTEGER,
        last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        lifespan_stage TEXT,
        crisis TEXT,
        virtue TEXT,
        relations TEXT,
        relation_circles TEXT,
        modality TEXT
    )
"""


@pytest.fixture
async def sqlite_store():
    store = ConversationHistoryStore()
    await store.initialize()
    async with store.pool.acquire() as conn:
        await conn.execute(_MEMORIES_SCHEMA)
        await conn.execute("DELETE FROM memories;")

    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    mem = MemoryStore(pool=store.pool, graph_db=mock_graph)
    mem.qdrant_store.client = None
    mem.get_embedding = AsyncMock(return_value=[0.1] * 768)
    yield mem
    await store.close()
    await mem.close()


async def _row_count(store, content, wing="personal"):
    async with store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, recall_count, importance_score FROM memories "
            "WHERE content = ? AND wing = ?",
            content,
            wing,
        )
    return rows


class TestReinforceOnRepeat:
    @pytest.mark.asyncio
    async def test_repeat_does_not_duplicate(self, sqlite_store):
        content = "I have a dog named Rex"
        assert await sqlite_store.add_memory(content, importance=0.5) is True
        assert await sqlite_store.add_memory(content, importance=0.5) is True

        rows = await _row_count(sqlite_store, content)
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_repeat_bumps_recall_count(self, sqlite_store):
        content = "My favourite colour is teal"
        await sqlite_store.add_memory(content, importance=0.5)
        await sqlite_store.add_memory(content, importance=0.5)
        await sqlite_store.add_memory(content, importance=0.5)

        rows = await _row_count(sqlite_store, content)
        assert len(rows) == 1
        assert rows[0]["recall_count"] == 3

    @pytest.mark.asyncio
    async def test_repeat_raises_importance_to_max(self, sqlite_store):
        content = "I am learning the cello"
        await sqlite_store.add_memory(content, importance=0.4)
        await sqlite_store.add_memory(content, importance=0.9)

        rows = await _row_count(sqlite_store, content)
        assert rows[0]["importance_score"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_lower_importance_restatement_never_demotes(self, sqlite_store):
        content = "My sister's wedding is in June"
        await sqlite_store.add_memory(content, importance=0.9)
        await sqlite_store.add_memory(content, importance=0.2)

        rows = await _row_count(sqlite_store, content)
        assert rows[0]["importance_score"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_repeat_skips_embedding(self, sqlite_store):
        content = "I drink chamomile tea at night"
        await sqlite_store.add_memory(content, importance=0.5)
        sqlite_store.get_embedding.reset_mock()

        await sqlite_store.add_memory(content, importance=0.5)
        # A reinforced repeat must not recompute the embedding.
        sqlite_store.get_embedding.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_different_wing_is_not_a_duplicate(self, sqlite_store):
        content = "The meeting is at noon"
        await sqlite_store.add_memory(content, wing="personal", importance=0.5)
        await sqlite_store.add_memory(content, wing="work", importance=0.5)

        personal = await _row_count(sqlite_store, content, wing="personal")
        work = await _row_count(sqlite_store, content, wing="work")
        assert len(personal) == 1
        assert len(work) == 1

    @pytest.mark.asyncio
    async def test_distinct_content_is_not_a_duplicate(self, sqlite_store):
        await sqlite_store.add_memory("fact one", importance=0.5)
        await sqlite_store.add_memory("fact two", importance=0.5)

        async with sqlite_store.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id FROM memories")
        assert len(rows) == 2


class TestFindExistingMemoryGuard:
    @pytest.mark.asyncio
    async def test_asyncmock_fetch_not_treated_as_hit(self):
        # PG unit-test path: conn.fetch is an AsyncMock returning a MagicMock,
        # which is truthy. The isinstance(rows, list) guard must reject it so a
        # fresh add is never misread as a duplicate.
        pool = MagicMock()  # not MockPGPool -> is_sqlite False -> PG branch
        store = MemoryStore(pool, MagicMock())
        store.qdrant_store.client = None

        conn = AsyncMock()  # fetch returns a MagicMock, not a list
        result = await store._find_existing_memory(conn, "anything", "personal")
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_error_falls_through_to_insert(self):
        pool = MagicMock()
        store = MemoryStore(pool, MagicMock())
        store.qdrant_store.client = None

        conn = AsyncMock()
        conn.fetch.side_effect = RuntimeError("db down")
        result = await store._find_existing_memory(conn, "anything", "personal")
        assert result is None
