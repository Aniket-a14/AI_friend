import sqlite3
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore


async def _memory_store(graph_result=None):
    conversation = ConversationHistoryStore()
    conversation.dsn = "sqlite:///:memory:"
    await conversation.initialize()
    graph = MagicMock()
    graph.execute_query = AsyncMock(return_value=graph_result or [])
    memory = MemoryStore(pool=conversation.pool, graph_db=graph)
    memory.qdrant_store.client = None
    memory.get_embedding = AsyncMock(return_value=[0.1] * 768)
    return conversation, memory


@pytest.mark.asyncio
async def test_sqlite_schema_contains_memory_provenance_columns():
    conversation, memory = await _memory_store()
    try:
        async with conversation.pool.acquire() as conn:
            rows = await conn.fetch("PRAGMA table_info(memories)")
        columns = {row["name"] for row in rows}
        assert {
            "speaker",
            "record_type",
            "valid_from",
            "valid_until",
            "contradicts_id",
        } <= columns
    finally:
        await memory.close()
        await conversation.close()


@pytest.mark.asyncio
async def test_add_memory_persists_event_speaker_and_fact_provenance():
    conversation, memory = await _memory_store()
    valid_from = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    try:
        assert await memory.add_memory(
            "The user owns a red bicycle",
            record_type="fact",
            valid_from=valid_from,
            raw_event={"user_id": "user-17"},
            embedding=[0.1] * 768,
        )
        async with conversation.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT speaker, record_type, valid_from, valid_until, contradicts_id "
                "FROM memories WHERE content = ?",
                "The user owns a red bicycle",
            )
        assert row["speaker"] == "user-17"
        assert row["record_type"] == "fact"
        assert str(row["valid_from"]).startswith("2026-09-03 12:00:00")
        assert row["valid_until"] is None
        assert row["contradicts_id"] is None
    finally:
        await memory.close()
        await conversation.close()


@pytest.mark.asyncio
async def test_conflicting_same_entity_memory_links_without_overwriting():
    conversation, memory = await _memory_store([{"name": "coffee"}])
    try:
        assert await memory.add_memory(
            "I like coffee",
            valence=0.8,
            speaker="user-17",
            record_type="fact",
            embedding=[0.1] * 768,
        )
        async with conversation.pool.acquire() as conn:
            first = await conn.fetchrow(
                "SELECT id FROM memories WHERE content = ?", "I like coffee"
            )

        assert await memory.add_memory(
            "I hate coffee",
            valence=-0.8,
            speaker="user-17",
            record_type="fact",
            embedding=[0.2] * 768,
        )
        async with conversation.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT content, contradicts_id FROM memories "
                "WHERE content IN (?, ?) ORDER BY content",
                "I like coffee",
                "I hate coffee",
            )
        assert len(rows) == 2
        linked = next(row for row in rows if row["content"] == "I hate coffee")
        assert linked["contradicts_id"] == first["id"]
        assert next(row for row in rows if row["content"] == "I like coffee")[
            "contradicts_id"
        ] is None
    finally:
        await memory.close()
        await conversation.close()


@pytest.mark.asyncio
async def test_archive_preserves_memory_provenance():
    conversation, memory = await _memory_store()
    try:
        assert await memory.add_memory(
            "A provenance-preserving memory",
            speaker="user-17",
            record_type="fact",
            valid_from=datetime(2026, 9, 1, tzinfo=UTC),
            valid_until=datetime(2026, 9, 2, tzinfo=UTC),
            contradicts_id="prior-memory",
            embedding=[0.1] * 768,
        )
        async with conversation.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM memories WHERE content = ?",
                "A provenance-preserving memory",
            )
            await memory._archive_and_delete_decayed_memories(conn, [row["id"]])
            archived = await conn.fetchrow(
                "SELECT speaker, record_type, valid_from, valid_until, contradicts_id "
                "FROM archived_memories WHERE id = ?",
                row["id"],
            )
        assert archived["speaker"] == "user-17"
        assert archived["record_type"] == "fact"
        assert archived["contradicts_id"] == "prior-memory"

        archived_row = await conn.fetchrow(
            "SELECT * FROM archived_memories WHERE id = ?", row["id"]
        )
        await memory._write_promoted_memory(
            row["id"],
            archived_row["content"],
            archived_row,
            [0.1] * 768,
            archived_row["recall_count"],
            datetime.now(UTC),
            payload_meta={},
            sql_meta={},
        )
        promoted = await conn.fetchrow(
            "SELECT speaker, record_type, valid_from, valid_until, contradicts_id "
            "FROM memories WHERE id = ?",
            row["id"],
        )
        assert promoted["speaker"] == "user-17"
        assert promoted["record_type"] == "fact"
        assert promoted["contradicts_id"] == "prior-memory"
        assert await conn.fetchrow(
            "SELECT id FROM archived_memories WHERE id = ?", row["id"]
        ) is None
    finally:
        await memory.close()
        await conversation.close()


def test_sqlite_provenance_migration_is_idempotent(tmp_path):
    from app.state.sqlite_fallback import SQLiteConnection

    db_path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(db_path)
    legacy_columns = """
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
        recall_count INTEGER,
        last_recalled_at TIMESTAMP,
        created_at TIMESTAMP,
        metadata TEXT
    """
    connection.execute(f"CREATE TABLE memories ({legacy_columns})")
    connection.execute(f"CREATE TABLE archived_memories ({legacy_columns})")
    connection.execute(
        "INSERT INTO memories (id, content, metadata) VALUES (?, ?, ?)",
        ("legacy-1", "legacy memory", "{}"),
    )
    connection.commit()
    connection.close()

    first = SQLiteConnection(str(db_path))
    first.conn.close()
    second = SQLiteConnection(str(db_path))
    try:
        columns = {
            row[1]
            for row in second.conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        assert {
            "speaker",
            "record_type",
            "valid_from",
            "valid_until",
            "contradicts_id",
        } <= columns
        migrated = second.conn.execute(
            "SELECT record_type FROM memories WHERE id = ?", ("legacy-1",)
        ).fetchone()
        assert migrated[0] == "episode"
    finally:
        second.conn.close()
