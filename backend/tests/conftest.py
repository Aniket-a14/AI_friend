import sys
import os
import types
import pytest
import asyncio
import sqlite3
import re
from unittest.mock import MagicMock, AsyncMock

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# =====================================================================
# 📦 HIGH-FIDELITY IN-MEMORY NATS SIMULATOR
# =====================================================================

class MockJSM:
    async def add_stream(self, name, subjects):
        return None
    async def stream_info(self, name):
        # Return a mock object with config.subjects
        class MockConfig:
            def __init__(self):
                self.subjects = []
        class MockInfo:
            def __init__(self):
                self.config = MockConfig()
        return MockInfo()
    async def update_stream(self, config):
        return None

class MockMessage:
    def __init__(self, subject, data, headers=None):
        self.subject = subject
        self.data = data
        self.headers = headers
    async def ack(self):
        pass
    async def nak(self):
        pass

class MockJetStream:
    def __init__(self, connection):
        self.connection = connection
        
    async def publish(self, subject, data, headers=None):
        self.connection._trigger(subject, data, headers)
        await self.connection.drain()
        return None
        
    async def subscribe(self, subject, cb, durable=None, **kwargs):
        self.connection._subscribe(subject, cb)
        return None

class MockNATSConnection:
    def __init__(self):
        self.subscribers = {}
        self._js = MockJetStream(self)
        self.pending_tasks = set()
        
    def jetstream(self):
        return self._js
        
    def jsm(self):
        return MockJSM()
        
    def _subscribe(self, subject, cb):
        self.subscribers.setdefault(subject, []).append(cb)
        
    def _trigger(self, subject, data, headers=None):
        async def run_callback(cb, msg):
            try:
                await cb(msg)
            except Exception as e:
                import logging
                logging.getLogger("MockNATS").error(f"Subscriber callback failed: {e}", exc_info=True)
                raise
        
        msg = MockMessage(subject, data, headers)
        for sub_subj, callbacks in self.subscribers.items():
            matched = False
            if sub_subj == subject:
                matched = True
            elif sub_subj.endswith(".>") and subject.startswith(sub_subj[:-1]):
                matched = True
            elif sub_subj.endswith(".*") and subject.split(".")[:-1] == sub_subj.split(".")[:-1]:
                matched = True
            elif sub_subj == ">":
                matched = True
                
            if matched:
                for cb in callbacks:
                    task = asyncio.create_task(run_callback(cb, msg))
                    self.pending_tasks.add(task)
                    task.add_done_callback(self.pending_tasks.discard)
                    
    async def drain(self):
        if self.pending_tasks:
            # Gather all pending subscriber tasks to ensure deterministic completion
            await asyncio.gather(*list(self.pending_tasks), return_exceptions=True)

    async def close(self):
        await self.drain()

# Create mock module objects for nats and its submodules
nats_module = types.ModuleType("nats")
async def mock_connect(nats_url, **kwargs):
    return MockNATSConnection()
nats_module.connect = mock_connect

nats_errors_module = types.ModuleType("nats.errors")
class NoRespondersError(Exception):
    pass
class TimeoutError(Exception):
    pass
nats_errors_module.NoRespondersError = NoRespondersError
nats_errors_module.TimeoutError = TimeoutError

nats_js_module = types.ModuleType("nats.js")

nats_js_errors_module = types.ModuleType("nats.js.errors")
class BadRequestError(Exception):
    pass
class ServiceUnavailableError(Exception):
    pass
class NotFoundError(Exception):
    pass
nats_js_errors_module.BadRequestError = BadRequestError
nats_js_errors_module.ServiceUnavailableError = ServiceUnavailableError
nats_js_errors_module.NotFoundError = NotFoundError

nats_js_api_module = types.ModuleType("nats.js.api")
class DeliverPolicy:
    ALL = "all"
    LAST = "last"
    NEW = "new"
nats_js_api_module.DeliverPolicy = DeliverPolicy

# Register them in sys.modules to satisfy python's package import system
sys.modules["nats"] = nats_module
sys.modules["nats.errors"] = nats_errors_module
sys.modules["nats.js"] = nats_js_module
sys.modules["nats.js.errors"] = nats_js_errors_module
sys.modules["nats.js.api"] = nats_js_api_module


# =====================================================================
# 🗄️ IN-MEMORY SQLITE-BACKED ASYNCPG MOCK
# =====================================================================

class SQLiteConnection:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                consolidated INTEGER DEFAULT 0,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_configs (
                id INTEGER PRIMARY KEY,
                personality TEXT,
                background_history TEXT,
                evolved_learnings TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _translate_query(self, query: str):
        # 1. Translate PostgreSQL $1, $2 placeholders to SQLite ?
        translated = re.sub(r'\$\d+', '?', query)
        # 2. Replace NOW() with CURRENT_TIMESTAMP
        translated = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', translated, flags=re.IGNORECASE)
        # 3. Translate PostgreSQL ON CONFLICT DO UPDATE to SQLite INSERT OR REPLACE INTO generically
        if "ON CONFLICT" in translated.upper():
            # Strip everything starting from ON CONFLICT
            parts = re.split(r'\bON\s+CONFLICT\b', translated, flags=re.IGNORECASE)
            base_query = parts[0].strip()
            # Replace INSERT INTO with INSERT OR REPLACE INTO
            translated = re.sub(r'\bINSERT\s+INTO\b', 'INSERT OR REPLACE INTO', base_query, flags=re.IGNORECASE)
        return translated

    async def execute(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, 'hex') else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        self.conn.commit()
        return None

    async def fetch(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, 'hex') else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetchrow(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, 'hex') else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        row = cursor.fetchone()
        return dict(row) if row else None

    async def fetchval(self, query, *args):
        translated = self._translate_query(query)
        cleaned_args = [str(arg) if hasattr(arg, 'hex') else arg for arg in args]
        cursor = self.conn.cursor()
        cursor.execute(translated, cleaned_args)
        row = cursor.fetchone()
        return row[0] if row else None

class MockPoolAcquisition:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class MockPGPool:
    def __init__(self):
        self.connection = SQLiteConnection()

    def acquire(self):
        return MockPoolAcquisition(self.connection)

    async def close(self):
        pass

# Intercept and stub asyncpg library
class MockAsyncPG:
    Pool = MockPGPool
    async def create_pool(self, dsn=None, **kwargs):
        return MockPGPool()

sys.modules["asyncpg"] = MockAsyncPG()


# =====================================================================
# 🛠️ STANDARD PYTEST CONFIGURATION & FIXTURES
# =====================================================================

def pytest_configure(config):
    """Dynamically enable benchmark-autosave if pytest-benchmark is installed.
    This prevents CI/CD failures on environments that do not have pytest-benchmark,
    while ensuring local runs are always saved for visualization.
    """
    if config.pluginmanager.hasplugin("benchmark"):
        config.option.benchmark_autosave = True


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
    db.create_triplet = AsyncMock(return_value=None)
    db.create_entity = AsyncMock(return_value=None)
    db.invalidate_cache = AsyncMock(return_value=None)
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
