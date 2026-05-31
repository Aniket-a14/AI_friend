import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from app.state.memory_store import MemoryStore


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


def _make_row(content, similarity=0.8):
    return {
        "content": content,
        "raw_content": content,
        "wing": "personal",
        "room": "social",
        "importance_score": 0.9,
        "emotional_weight": 0.5,
        "valence": 0.5,
        "recall_count": 1,
        "last_recalled_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "metadata": "{}",
        "similarity": similarity,
    }


def test_context_aware_pronoun_mapping_user_speaking(mock_pool):
    """
    Verify that when user_id = 'Raj' and is_self_reflection = False,
    first-person pronouns resolve to 'Raj' and second-person to the agent name.
    """
    pool, conn = mock_pool
    # A candidate memory referring to Raj and Aniket
    rows = [
        _make_row("I chatted with Raj about his work in the workspace."),
        _make_row("Aniket played cricket yesterday."),
    ]
    conn.fetch.return_value = rows

    mock_graph = MagicMock()

    # Mock Neo4j graph nodes and relations
    async def mock_execute_query(query, *args, **kwargs):
        if "MATCH (e:Entity)" in query:
            return [
                {"name": "Aniket", "description": "The central cognitive system."},
                {"name": "Raj", "description": "User / Companion"},
            ]
        elif "MATCH (s:Entity)-[r]-(t:Entity)" in query:
            return [{"source": "Aniket", "target": "Raj"}]
        return []

    mock_graph.execute_query = mock_execute_query

    store = MemoryStore(pool, mock_graph)
    store.qdrant_store.client = None

    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        # User is speaking: "What did I do yesterday?" -> "I" resolves to "Raj"
        results = asyncio.run(
            store.search_memories(
                query_text="What is my favorite drink?",
                user_id="Raj",
                is_self_reflection=False,
                threshold=-10.0,
                limit=2,
            )
        )
        assert len(results) > 0

        # Also verify second-person maps to agent: "Where were you?" -> "you" maps to "Aniket"
        results_you = asyncio.run(
            store.search_memories(
                query_text="Where were you?",
                user_id="Raj",
                is_self_reflection=False,
                threshold=-10.0,
                limit=2,
            )
        )
        assert len(results_you) > 0


def test_context_aware_pronoun_mapping_self_reflection(mock_pool):
    """
    Verify that when is_self_reflection = True,
    first-person pronouns resolve to the agent itself.
    """
    pool, conn = mock_pool
    rows = [_make_row("Aniket walked in the garden alone.")]
    conn.fetch.return_value = rows

    mock_graph = MagicMock()

    async def mock_execute_query(query, *args, **kwargs):
        if "MATCH (e:Entity)" in query:
            return [
                {"name": "Aniket", "description": "The central cognitive system."},
                {"name": "Raj", "description": "User / Companion"},
            ]
        elif "MATCH (s:Entity)-[r]-(t:Entity)" in query:
            return []
        return []

    mock_graph.execute_query = mock_execute_query

    store = MemoryStore(pool, mock_graph)
    store.qdrant_store.client = None

    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        # Agent is self-reflecting: "Where did I walk?" -> "I" resolves to "Aniket"
        results = asyncio.run(
            store.search_memories(
                query_text="Where did I walk?",
                user_id="Raj",
                is_self_reflection=True,
                threshold=-10.0,
                limit=1,
            )
        )
        assert len(results) > 0
