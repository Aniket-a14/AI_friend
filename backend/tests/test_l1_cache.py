"""
L1 activation-cache coherence & bounded-growth tests.

The L1 cache short-circuits repeated recalls within a TTL window. Two
properties it must uphold:

  * Bounded growth — keys are full query signatures, so a long session's
    working set is unbounded; the cache must evict LRU entries past a cap
    instead of leaking.
  * Write coherence — a memory write (add or prune) can change what an
    already-cached query should return, so those mutations must invalidate the
    cache rather than let a stale result set be served for up to the TTL.
"""

from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.state.memory_store import MemoryStore


@pytest.fixture
def store():
    pool = MagicMock()
    pool.acquire = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    s = MemoryStore(pool, mock_graph)
    s.qdrant_store.client = None
    return s, conn


class TestL1BoundedEviction:
    def test_cache_is_ordered_dict(self, store):
        s, _ = store
        assert isinstance(s._l1_cache, OrderedDict)

    def test_put_evicts_least_recently_used(self, store):
        s, _ = store
        s._l1_cache_max = 3
        for i in range(3):
            s._l1_cache_put(f"k{i}", (0.0, [i]))
        assert list(s._l1_cache.keys()) == ["k0", "k1", "k2"]

        # Fourth insert overflows the cap; the oldest (k0) is dropped.
        s._l1_cache_put("k3", (0.0, [3]))
        assert "k0" not in s._l1_cache
        assert list(s._l1_cache.keys()) == ["k1", "k2", "k3"]
        assert len(s._l1_cache) == 3

    def test_reinsert_refreshes_recency(self, store):
        s, _ = store
        s._l1_cache_max = 3
        for i in range(3):
            s._l1_cache_put(f"k{i}", (0.0, [i]))

        # Touch k0 so it is now most-recently-used.
        s._l1_cache_put("k0", (1.0, [99]))
        assert list(s._l1_cache.keys()) == ["k1", "k2", "k0"]

        # Next overflow evicts k1, not k0.
        s._l1_cache_put("k3", (0.0, [3]))
        assert "k1" not in s._l1_cache
        assert "k0" in s._l1_cache

    def test_never_exceeds_max(self, store):
        s, _ = store
        s._l1_cache_max = 8
        for i in range(200):
            s._l1_cache_put(f"k{i}", (0.0, [i]))
        assert len(s._l1_cache) == 8


class TestL1Invalidation:
    def test_invalidate_clears_all(self, store):
        s, _ = store
        for i in range(5):
            s._l1_cache_put(f"k{i}", (0.0, [i]))
        s._invalidate_l1_cache()
        assert len(s._l1_cache) == 0

    @pytest.mark.asyncio
    async def test_add_memory_invalidates_cache(self, store):
        s, _ = store
        s._l1_cache_put("stale", (0.0, ["old"]))

        # Force the write to reach the success path deterministically: a valid
        # embedding and no graph pre-linking. The PG (AsyncMock) branch runs
        # INSERTs against the AsyncMock conn (no-ops) and returns True.
        s.get_embedding = AsyncMock(return_value=[0.0] * 768)
        s.graph_db = None

        ok = await s.add_memory("a brand new fact", wing="personal")
        assert ok is True
        assert len(s._l1_cache) == 0

    @pytest.mark.asyncio
    async def test_add_memory_failure_does_not_invalidate(self, store):
        s, _ = store
        s._l1_cache_put("keep", (0.0, ["old"]))

        # get_embedding returning None makes add_memory drop the memory and
        # return False; a failed write must not touch the cache.
        s.get_embedding = AsyncMock(return_value=None)
        s.graph_db = None

        ok = await s.add_memory("dropped fact", wing="personal")
        assert ok is False
        assert "keep" in s._l1_cache
