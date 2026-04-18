import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from app.memory_store import MemoryStore

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

def test_calculate_utility_no_emotion(memory_store, mock_pool):
    pool, conn = mock_pool
    
    # Mock row data
    now = datetime.now()
    rows = [{
        "content": "Old memory",
        "importance_score": 0.5,
        "emotional_weight": 0.0,
        "last_recalled_at": now - timedelta(hours=10),
        "similarity": 1.0
    }]
    conn.fetch.return_value = rows
    
    # Mock embedding
    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        results = asyncio.run(memory_store.search_memories("test query", threshold=0.1))
        assert len(results) == 1
        assert results[0]["content"] == "Old memory"
        assert results[0]["score"] > 0.1
        
        # Manually calculate expected utility
        # decay = exp(-0.001 * 10) = 0.99
        # utility = 1.0 * (0.5 * 0.99) = 0.495
        # Since 0.495 > 0.1, it should be returned.

def test_emotional_boost(memory_store, mock_pool):
    pool, conn = mock_pool
    now = datetime.now()
    
    # One mundance memory vs one emotional memory
    # Mundane higher similarity but emotional should win
    rows = [
        {
            "content": "Mundane Fact",
            "importance_score": 0.5,
            "emotional_weight": 0.0,
            "last_recalled_at": now,
            "similarity": 0.7
        },
        {
            "content": "Emotional Memory",
            "importance_score": 0.5,
            "emotional_weight": 0.8,
            "last_recalled_at": now,
            "similarity": 0.6
        }
    ]
    conn.fetch.return_value = rows
    
    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        # Mundane utility = 0.7 * (0.5 * 1.0) = 0.35
        # Emotional utility = 0.6 * (0.5 * 1.0) * (1 + 0.5 * 0.8) = 0.3 * 1.4 = 0.42
        results = asyncio.run(memory_store.search_memories("test query", threshold=0.1, limit=1))
        assert results[0]["content"] == "Emotional Memory"

def test_time_decay_ranking(memory_store, mock_pool):
    pool, conn = mock_pool
    now = datetime.now()
    
    # New memory vs very old memory
    rows = [
        {
            "content": "Recent memory",
            "importance_score": 0.5,
            "emotional_weight": 0.0,
            "last_recalled_at": now,
            "similarity": 0.7
        },
        {
            "content": "Ancient memory",
            "importance_score": 0.5,
            "emotional_weight": 0.0,
            "last_recalled_at": now - timedelta(days=100),
            "similarity": 0.9
        }
    ]
    conn.fetch.return_value = rows
    
    with patch.object(memory_store, 'get_embedding', return_value=[0.1]*768):
        results = asyncio.run(memory_store.search_memories("test query", threshold=0.1, limit=1))
        # Ancient utility = 0.9 * (0.5 * exp(-0.001 * 2400)) = 0.45 * 0.09 = 0.04 (Below threshold)
        assert results[0]["content"] == "Recent memory"
