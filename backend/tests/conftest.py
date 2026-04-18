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
    """Mock for OllamaClient (Hardened for CVS-1.0)"""
    client = MagicMock()
    # Support **kwargs in async mock
    client.generate = AsyncMock(return_value='{"intent": "CHAT", "goal": "ENGAGE", "confidence": 0.9}')
    client.generate_stream = MagicMock()
    
    async def mock_stream(prompt, system=None, **kwargs):
        """Streaming mock that accepts Resilient parameters (model, num_thread, etc.)"""
        yield "Hello "
        yield "there!"
    
    client.generate_stream.side_effect = mock_stream
    return client

@pytest.fixture
def mock_graph_db():
    """Mock for Neo4j GraphDB (Async-Mesh Migration)"""
    db = MagicMock()
    # All methods MUST be async to match AsyncGraphDatabase driver
    db.execute_query = AsyncMock(return_value=[])
    db.create_relationship = AsyncMock(return_value=None)
    db.create_entity = AsyncMock(return_value=None)
    db.close = AsyncMock(return_value=None)
    return db

@pytest.fixture
def mock_memory_store():
    """Mock for PGVector MemoryStore"""
    store = MagicMock()
    store.search_memories = AsyncMock(return_value=[])
    store.add_memory = AsyncMock(return_value=None)
    return store
