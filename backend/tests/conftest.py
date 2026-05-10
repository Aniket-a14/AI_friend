import sys
import os
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Some local test environments cannot import asyncpg native bindings.
# Provide a tiny stub so tests that don't hit real DB I/O can import modules safely.
sys.modules.setdefault("asyncpg", SimpleNamespace(Pool=object))


@pytest.fixture
def mock_llm_service():
    """Mock for OllamaClient (Hardened for CVS-1.0)"""
    client = MagicMock()
    # Support **kwargs in async mock
    client.generate = AsyncMock(
        return_value='{"intent": "CHAT", "goal": "ENGAGE", "confidence": 0.9}'
    )
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


@pytest.fixture(autouse=True)
def enforce_test_config():
    """CVS-1.0: Ensure deterministic configuration for cognitive tests."""
    from app.config import Config

    original_classifier = Config.LLM_INTENT_CLASSIFICATION_ENABLED
    original_interval = Config.REFLECTION_MIN_INTERVAL_SECONDS
    original_enabled = Config.REFLECTION_ENABLED

    Config.LLM_INTENT_CLASSIFICATION_ENABLED = True
    Config.REFLECTION_MIN_INTERVAL_SECONDS = 0
    Config.REFLECTION_ENABLED = True

    yield

    Config.LLM_INTENT_CLASSIFICATION_ENABLED = original_classifier
    Config.REFLECTION_MIN_INTERVAL_SECONDS = original_interval
    Config.REFLECTION_ENABLED = original_enabled
