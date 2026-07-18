"""
A5 regression: MemoryStore.is_sqlite must key off what the pool's connection
actually is (a real sqlite3.Connection), not a hardcoded set of class-name
strings that silently misclassifies any pool it doesn't recognize.
"""

from unittest.mock import MagicMock

from app.state.memory_store import MemoryStore
from app.state.sqlite_fallback import SQLitePool


def _make_store(pool):
    store = MemoryStore(pool, MagicMock())
    store.qdrant_store.client = None
    return store


def test_is_sqlite_true_for_real_sqlite_pool():
    store = _make_store(SQLitePool(":memory:"))
    assert store.is_sqlite is True


def test_is_sqlite_false_for_generic_pool_mock():
    # A bare MagicMock auto-vivifies any attribute access (including
    # .connection.conn), so the old name-based check needed to special-case
    # "MagicMock"/"AsyncMock"/"Mock" explicitly. The structural check doesn't.
    store = _make_store(MagicMock())
    assert store.is_sqlite is False


def test_is_sqlite_false_for_pool_with_no_connection_attribute():
    class BarePool:
        async def close(self):
            pass

    store = _make_store(BarePool())
    assert store.is_sqlite is False


def test_is_sqlite_true_for_renamed_sqlite_pool_subclass():
    # A5's core complaint: a renamed/subclassed SQLite pool used to be silently
    # misdetected because the check matched on type(pool).__name__.
    class CustomSQLitePool(SQLitePool):
        pass

    store = _make_store(CustomSQLitePool(":memory:"))
    assert store.is_sqlite is True
