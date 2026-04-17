import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

@pytest.fixture
def mock_llm_service():
    """Mock for OllamaClient"""
    client = MagicMock()
    client.generate = AsyncMock(return_value='{"intent": "CHAT", "goal": "ENGAGE"}')
    client.generate_stream = MagicMock()
    
    async def mock_stream(prompt, system=None):
        yield "Hello "
        yield "there!"
    
    client.generate_stream.side_effect = mock_stream
    return client

@pytest.fixture
def mock_graph_db():
    """Mock for Neo4j GraphDB"""
    db = MagicMock()
    db.execute_query = AsyncMock(return_value=[])
    db.create_relationship = AsyncMock(return_value=None)
    return db

@pytest.fixture
def mock_memory_store():
    """Mock for PGVector MemoryStore"""
    store = MagicMock()
    store.search_memories = AsyncMock(return_value=[])
    store.add_memory = AsyncMock(return_value=None)
    return store
