import sqlite3
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore
from app.state.sqlite_fallback import SQLiteConnection


@pytest.fixture
async def memory_store():
    """Provide an isolated SQLite memory store with one known entity."""
    conversation = ConversationHistoryStore()
    conversation.dsn = "sqlite:///:memory:"
    await conversation.initialize()

    graph = MagicMock()
    graph.execute_query = AsyncMock(return_value=[{"name": "coffee"}])
    store = MemoryStore(pool=conversation.pool, graph_db=graph)
    store.qdrant_store.client = None
    store.get_embedding = AsyncMock(return_value=[0.1] * 768)

    yield store, conversation

    await store.close()
    await conversation.close()


@pytest.mark.asyncio
async def test_speaker_and_record_type_round_trip_through_sqlite(memory_store):
    store, conversation = memory_store

    assert await store.add_memory(
        "The user owns a red bicycle",
        speaker="user-17",
        record_type="fact",
        valid_from=datetime(2026, 9, 3, tzinfo=UTC),
        embedding=[0.1] * 768,
    )

    async with conversation.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT speaker, record_type FROM memories WHERE content = ?",
            "The user owns a red bicycle",
        )

    assert row == {"speaker": "user-17", "record_type": "fact"}


@pytest.mark.asyncio
async def test_find_contradiction_links_new_record_without_overwriting_prior(memory_store):
    store, conversation = memory_store

    assert await store.add_memory(
        "I like coffee",
        speaker="user-17",
        record_type="fact",
        valence=0.8,
        embedding=[0.1] * 768,
    )
    async with conversation.pool.acquire() as conn:
        first = await conn.fetchrow(
            "SELECT id, contradicts_id FROM memories WHERE content = ?", "I like coffee"
        )

    contradiction = await store.find_contradiction("I hate coffee", "coffee", -0.8)
    assert contradiction is not None
    assert contradiction["id"] == first["id"]

    assert await store.add_memory(
        "I hate coffee",
        speaker="user-17",
        record_type="fact",
        valence=-0.8,
        embedding=[0.2] * 768,
    )
    async with conversation.pool.acquire() as conn:
        linked = await conn.fetchrow(
            "SELECT contradicts_id FROM memories WHERE content = ?", "I hate coffee"
        )
        prior = await conn.fetchrow(
            "SELECT contradicts_id FROM memories WHERE id = ?", first["id"]
        )

    assert linked["contradicts_id"] == first["id"]
    assert prior["contradicts_id"] is None


def test_sqlite_provenance_migration_is_idempotent_when_columns_exist(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    legacy = sqlite3.connect(db_path)
    legacy.execute(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY, content TEXT, raw_content TEXT, wing TEXT,
            room TEXT, embedding TEXT, importance_score REAL,
            emotional_weight REAL, valence REAL, certainty REAL, source TEXT,
            recall_count INTEGER, last_recalled_at TIMESTAMP,
            created_at TIMESTAMP, metadata TEXT
        )
        """
    )
    legacy.execute("CREATE TABLE archived_memories AS SELECT * FROM memories")
    legacy.execute(
        "INSERT INTO memories (id, content, metadata) VALUES (?, ?, ?)",
        ("legacy-1", "legacy memory", "{}"),
    )
    legacy.commit()
    legacy.close()

    first = SQLiteConnection(str(db_path))
    first.conn.close()
    second = SQLiteConnection(str(db_path))
    try:
        columns = {
            row[1] for row in second.conn.execute("PRAGMA table_info(memories)")
        }
        assert {
            "speaker",
            "record_type",
            "valid_from",
            "valid_until",
            "contradicts_id",
        } <= columns
        assert second.conn.execute(
            "SELECT record_type FROM memories WHERE id = ?", ("legacy-1",)
        ).fetchone()[0] == "episode"
    finally:
        second.conn.close()
