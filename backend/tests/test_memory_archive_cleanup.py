"""
Permanent archive-cleanup tests for apply_actr_decay.

A pruned memory is copied to archived_memories and later permanently deleted
once it ages past a biological-timeline cutoff. Two fidelity requirements:

  * A memory that was archived but NEVER recalled has last_recalled_at = NULL.
    `NULL < cutoff` is NULL (never true) in SQL, so without COALESCE such rows
    become immortal in the archive. They must instead age out by created_at --
    a never-recalled memory is the most forgettable, not the least.

  * The SQLite fallback stores timestamps as text; comparisons must be robust
    to ISO format/precision differences, so the cleanup normalises through
    datetime().
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

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

# Minimal archived_memories: apply_actr_decay's cleanup only reads
# importance_score, last_recalled_at and created_at. The memory kept in
# `memories` is fresh, so the archive-INSERT (to_delete) path never fires here.
_ARCHIVE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS archived_memories (
        id TEXT PRIMARY KEY,
        content TEXT,
        importance_score REAL,
        last_recalled_at TIMESTAMP,
        created_at TIMESTAMP
    )
"""


@pytest.fixture
async def store_with_archive():
    store = ConversationHistoryStore()
    await store.initialize()
    async with store.pool.acquire() as conn:
        await conn.execute(_MEMORIES_SCHEMA)
        await conn.execute(_ARCHIVE_SCHEMA)
        await conn.execute("DELETE FROM memories;")
        await conn.execute("DELETE FROM archived_memories;")
        # A live, fresh memory so apply_actr_decay has a row to process and
        # proceeds to the cleanup stage (it returns early on no matches).
        await conn.execute(
            "INSERT INTO memories (id, content, recall_count, importance_score, "
            "created_at, last_recalled_at) VALUES "
            "('live', 'anchor memory', 1, 0.6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )

    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    mem = MemoryStore(pool=store.pool, graph_db=mock_graph)
    mem.qdrant_store.client = None
    mem.get_embedding = AsyncMock(return_value=[0.1] * 768)
    yield store, mem
    await store.close()
    await mem.close()


# SQLite (and CURRENT_TIMESTAMP) store naive, space-separated timestamps. Match
# that format so the stored values read back cleanly and reflect reality.
def _ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt is not None else None


async def _insert_archived(store, id_, importance, created_at, last_recalled_at):
    async with store.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO archived_memories (id, content, importance_score, "
            "last_recalled_at, created_at) VALUES (?, ?, ?, ?, ?)",
            id_,
            id_,
            importance,
            _ts(last_recalled_at),
            _ts(created_at),
        )


async def _surviving_ids(store):
    async with store.pool.acquire() as conn:
        rows = await conn.fetch("SELECT id FROM archived_memories")
    return {r["id"] for r in rows}


class TestArchiveNullCleanup:
    @pytest.mark.asyncio
    async def test_old_never_recalled_row_is_purged(self, store_with_archive):
        store, mem = store_with_archive
        now = datetime(2026, 7, 18)
        # Distractor (importance < 0.5), never recalled, created 400 days ago:
        # well past the 30-day distractor cutoff -> must be purged via created_at.
        await _insert_archived(
            store,
            "old_null",
            0.3,
            now - timedelta(days=400),
            None,
        )

        await mem.apply_actr_decay(["anchor memory"], current_time=now)

        assert "old_null" not in await _surviving_ids(store)

    @pytest.mark.asyncio
    async def test_recent_never_recalled_row_survives(self, store_with_archive):
        store, mem = store_with_archive
        now = datetime(2026, 7, 18)
        # Never recalled but created only 5 days ago: inside the 30-day cutoff,
        # so COALESCE(created_at) keeps it -- recency, not NULL, decides.
        await _insert_archived(
            store,
            "recent_null",
            0.3,
            now - timedelta(days=5),
            None,
        )

        await mem.apply_actr_decay(["anchor memory"], current_time=now)

        assert "recent_null" in await _surviving_ids(store)

    @pytest.mark.asyncio
    async def test_recalled_row_respects_last_recalled_at(self, store_with_archive):
        store, mem = store_with_archive
        now = datetime(2026, 7, 18)
        # Created long ago but recalled recently: last_recalled_at (5 days ago)
        # takes precedence over created_at, so it must survive.
        await _insert_archived(
            store,
            "old_but_recalled",
            0.3,
            now - timedelta(days=400),
            now - timedelta(days=5),
        )
        # And an old, long-unrecalled distractor that should be purged.
        await _insert_archived(
            store,
            "old_and_stale",
            0.3,
            now - timedelta(days=400),
            now - timedelta(days=90),
        )

        await mem.apply_actr_decay(["anchor memory"], current_time=now)

        survivors = await _surviving_ids(store)
        assert "old_but_recalled" in survivors
        assert "old_and_stale" not in survivors
