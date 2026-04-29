"""
Memory Store Tests — ACT-R Retrieval Scoring (Phase 2).

Tests validate that the ACT-R activation equation correctly ranks memories
based on frequency, recency, cosine similarity, and emotional alignment.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from app.state.memory_store import MemoryStore


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.fixture
def memory_store(mock_pool):
    pool, _ = mock_pool
    return MemoryStore(pool)


def _make_row(content, similarity, hours_ago=0, recall_count=1, valence=0.0,
              importance=0.5, emotion=0.0):
    """Helper to build a mock DB row with all ACT-R fields."""
    now = datetime.now(timezone.utc)
    return {
        "content": content,
        "importance_score": importance,
        "emotional_weight": emotion,
        "valence": valence,
        "recall_count": recall_count,
        "last_recalled_at": now - timedelta(hours=hours_ago),
        "created_at": now - timedelta(hours=hours_ago),
        "metadata": "{}",
        "similarity": similarity,
    }


def test_calculate_utility_no_emotion(memory_store, mock_pool):
    """Basic ACT-R retrieval: single memory should pass threshold."""
    pool, conn = mock_pool
    rows = [_make_row("Old memory", similarity=1.0, hours_ago=10, recall_count=3)]
    conn.fetch.return_value = rows

    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        results = asyncio.run(memory_store.search_memories("test query", threshold=0.1))
        assert len(results) == 1
        assert results[0]["content"] == "Old memory"
        assert results[0]["score"] > 0.1


def test_emotional_boost(memory_store, mock_pool):
    """Mood-congruent recall: emotionally aligned memory should rank higher."""
    pool, conn = mock_pool
    rows = [
        _make_row("Mundane Fact", similarity=0.7, valence=0.0),
        _make_row("Emotional Memory", similarity=0.6, valence=0.5, emotion=0.8),
    ]
    conn.fetch.return_value = rows

    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        # With current_valence=0.5, emotional memory should align better
        results = asyncio.run(memory_store.search_memories(
            "test query", threshold=0.1, limit=1, current_valence=0.5
        ))
        assert results[0]["content"] == "Emotional Memory"


def test_time_decay_ranking(memory_store, mock_pool):
    """ACT-R base-level activation: recent memories should outrank stale ones."""
    pool, conn = mock_pool
    rows = [
        _make_row("Recent memory", similarity=0.7, hours_ago=0, recall_count=2),
        _make_row("Ancient memory", similarity=0.9, hours_ago=2400, recall_count=1),
    ]
    conn.fetch.return_value = rows

    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        results = asyncio.run(memory_store.search_memories("test query", threshold=-5.0, limit=1))
        # Recent memory has higher base-level activation despite lower similarity
        assert results[0]["content"] == "Recent memory"


def test_recall_frequency_boost(memory_store, mock_pool):
    """ACT-R: frequently recalled memories should have higher activation."""
    pool, conn = mock_pool
    rows = [
        _make_row("Rarely recalled", similarity=0.8, recall_count=1),
        _make_row("Frequently recalled", similarity=0.7, recall_count=50),
    ]
    conn.fetch.return_value = rows

    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        results = asyncio.run(memory_store.search_memories("test query", threshold=-5.0, limit=1))
        # ln(50) >> ln(1), so frequent recall should win despite lower similarity
        assert results[0]["content"] == "Frequently recalled"
