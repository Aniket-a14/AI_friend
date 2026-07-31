"""
Unit Tests for Subconscious Memory Consolidation & ACT-R Offline Fallbacks.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.subconscious_agent import SubconsciousAgent
from app.cognitive.learning import ReflectionService
from app.config import Config
from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore


@pytest.mark.asyncio
async def test_sqlite_in_memory_persistence(mock_llm_service, mock_graph_db):
    """Verify that asyncpg/sqlite mock pool can write and fetch conversations completely offline."""
    store = ConversationHistoryStore()

    # Initialize the database (this will trigger schema creation inside our in-memory SQLite connection)
    await store.initialize()

    # 1. Start a session
    session_id = await store.start_session()
    assert session_id is not None

    # 2. Log messages
    await store.log_message("user", "Hello! Tell me about cognitive architectures.")
    await store.log_message(
        "assistant", "ACT-R structures short-term and long-term memory elements."
    )

    # 3. Retrieve recent unconsolidated messages via MemoryStore
    mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph_db)
    mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)

    episodes = await mem_store.get_recent_unconsolidated_episodes(limit=5)
    assert len(episodes) == 2
    roles = {ep["role"] for ep in episodes}
    assert "user" in roles
    assert "assistant" in roles

    await store.close()
    await mem_store.close()


@pytest.mark.asyncio
async def test_sqlite_cosine_similarity_fallback(mock_llm_service):
    """Verify that Python-backed SQLite Cosine Similarity fallback yields correct scores."""
    store = ConversationHistoryStore()
    await store.initialize()

    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph)
    mem_store.qdrant_store.client = None

    # Seed embeddings manually
    # Memory 1: Vector aligned with query
    # Memory 2: Vector orthogonal to query
    query_vector = [1.0, 0.0, 0.0] + [0.0] * 765
    aligned_vector = [0.9, 0.1, 0.0] + [0.0] * 765
    orthogonal_vector = [0.0, 1.0, 0.0] + [0.0] * 765

    async def mock_get_embedding(text):
        if "query" in text:
            return query_vector
        if "aligned" in text:
            return aligned_vector
        return orthogonal_vector

    mem_store.get_embedding = mock_get_embedding

    # Add memories manually to bypass pgvector schema inserts
    async with store.pool.acquire() as conn:
        # We need to create memories table since it is part of pgvector
        await conn.execute("""
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
        """)
        await conn.execute("DELETE FROM memories;")

    # Store memories
    res1 = await mem_store.add_memory(
        "aligned memory",
        raw_content="aligned raw",
        wing="personal",
        importance=0.8,
        valence=0.5,
    )
    res2 = await mem_store.add_memory(
        "orthogonal memory",
        raw_content="orthogonal raw",
        wing="personal",
        importance=0.3,
        valence=-0.5,
    )

    assert res1 is True
    assert res2 is True

    # Search memories
    results = await mem_store.search_memories(
        "query text", wing="personal", threshold=-5.0, limit=2
    )
    assert len(results) == 2

    # Aligned memory should have higher similarity and score
    assert results[0]["content"] == "aligned memory"

    await store.close()
    await mem_store.close()


@pytest.mark.asyncio
async def test_memory_decay_loop(mock_llm_service):
    """Verify that ACT-R memory decay successfully scales down base importance scores."""
    store = ConversationHistoryStore()
    await store.initialize()

    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph)
    mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)

    # Create the memories table
    async with store.pool.acquire() as conn:
        await conn.execute("""
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
        """)

    await mem_store.add_memory("Test memory to decay", importance=0.6)

    # Decay the memory
    await mem_store.apply_actr_decay(["Test memory to decay"])

    # Verify importance score is decayed
    async with store.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT importance_score FROM memories WHERE content = 'Test memory to decay'"
        )
        assert abs(row["importance_score"] - 0.48) < 1e-5

    await store.close()
    await mem_store.close()


@pytest.mark.asyncio
async def test_subconscious_consolidation_pipeline(mock_llm_service, mock_graph_db):
    """Verify that the SubconsciousAgent runs a full fact-extraction & consolidation pass."""
    orig_bypass = getattr(Config, "TESTING_CONSOLIDATION_BYPASS_SILENCE", False)

    store = ConversationHistoryStore()
    mem_store = None
    try:
        await store.initialize()

        # Create memories and config tables
        async with store.pool.acquire() as conn:
            await conn.execute("""
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
            """)

        mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph_db)
        mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)

        # Seed a conversation episode
        await store.start_session()
        await store.log_message(
            "user", "My favorite programming language is Python because it feels clean."
        )

        # Initialize reflection service with mocked LLM and GraphDB
        mock_llm_service.generate.return_value = '[{"subject": "User", "relation": "LIKES", "object": "Python", "type": "Preference", "confidence": 0.9, "reason": "Explicitly stated favorite language"}]'

        ref_service = ReflectionService(
            llm_service=mock_llm_service, graph_store=mock_graph_db, pg_vector=mem_store
        )

        agent = SubconsciousAgent(
            memory_store=mem_store,
            reflection_service=ref_service,
            graph_db=mock_graph_db,
        )
        agent.state_service.current_state.last_user_interaction = time.time() - 301

        # Simulate a system.tick event manually
        await agent._on_system_tick({"uptime": 100})

        # Verify graph write was attempted
        mock_graph_db.create_triplet.assert_called_once()
        args, _kwargs = mock_graph_db.create_triplet.call_args
        assert args[0] == "User"
        assert args[1] == "LIKES"
        assert args[2] == "Python"
    finally:
        if mem_store is not None:
            await mem_store.close()
        await store.close()
        Config.TESTING_CONSOLIDATION_BYPASS_SILENCE = orig_bypass
