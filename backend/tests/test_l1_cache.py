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

import asyncio
import time
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


class TestL1AffectQuantization:
    """P3-9: valence/arousal/cortisol drift continuously (StateService blends
    them in small increments every tick), so a raw-float cache key was a
    near-guaranteed miss on every call during a live conversation."""

    def test_quantize_rounds_to_the_nearest_bucket(self):
        from app.state.memory_store import L1_CACHE_AFFECT_BUCKET, _quantize

        assert _quantize(0.301, L1_CACHE_AFFECT_BUCKET) == pytest.approx(0.30)
        assert _quantize(0.324, L1_CACHE_AFFECT_BUCKET) == pytest.approx(0.30)
        assert _quantize(0.326, L1_CACHE_AFFECT_BUCKET) == pytest.approx(0.35)

    @pytest.mark.asyncio
    async def test_near_identical_affect_hits_the_same_cache_entry(self, store):
        s, conn = store
        s.get_embedding = AsyncMock(return_value=[0.1] * 768)
        conn.fetch.return_value = []

        await s.search_memories(
            "hello", current_valence=0.301, current_arousal=0.5, current_cortisol=0.1
        )
        await s.search_memories(
            "hello", current_valence=0.304, current_arousal=0.5, current_cortisol=0.1
        )

        # Two calls within the same quantization bucket must share a cache
        # entry -- get_embedding (the expensive step the cache exists to
        # skip) must run only once.
        assert s.get_embedding.await_count == 1

    @pytest.mark.asyncio
    async def test_affect_outside_the_bucket_is_a_genuine_cache_miss(self, store):
        s, conn = store
        s.get_embedding = AsyncMock(return_value=[0.1] * 768)
        conn.fetch.return_value = []

        await s.search_memories(
            "hello", current_valence=0.1, current_arousal=0.5, current_cortisol=0.1
        )
        await s.search_memories(
            "hello", current_valence=0.9, current_arousal=0.5, current_cortisol=0.1
        )

        assert s.get_embedding.await_count == 2


class TestSearchFailureVisibility:
    """P3-6: search_memories's outer except returns [] on any failure -- the
    same shape a genuine "nothing relevant" result has. last_search_error /
    last_search_error_at let a caller distinguish them without changing the
    hot-path return contract."""

    @pytest.mark.asyncio
    async def test_failure_is_recorded_alongside_the_empty_return(self, store):
        s, _conn = store
        s.get_embedding = AsyncMock(side_effect=RuntimeError("embedding service down"))

        assert s.last_search_error is None
        results = await s.search_memories("hello")

        assert results == []
        assert s.last_search_error == "embedding service down"
        assert s.last_search_error_at is not None

    @pytest.mark.asyncio
    async def test_empty_embedding_is_recorded_as_a_failure(self, store):
        s, _conn = store
        s.get_embedding = AsyncMock(return_value=None)

        assert await s.search_memories("hello") == []
        assert s.last_search_error == "embedding service returned no vector"
        assert s.last_search_error_at is not None

    @pytest.mark.asyncio
    async def test_close_cancels_retained_refresh_tasks(self, store):
        s, _conn = store
        task = asyncio.create_task(asyncio.sleep(60))
        s._background_tasks.add(task)

        await s.close()

        assert task.cancelled()
        assert not s._background_tasks

    @pytest.mark.asyncio
    async def test_a_later_successful_search_clears_the_stale_failure(self, store):
        s, conn = store
        s.get_embedding = AsyncMock(side_effect=RuntimeError("embedding service down"))
        await s.search_memories("hello")
        assert s.last_search_error is not None

        s.get_embedding = AsyncMock(return_value=[0.1] * 768)
        conn.fetch.return_value = []
        await s.search_memories("hello")

        assert s.last_search_error is None
        assert s.last_search_error_at is None


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


class TestAddMemoryQdrantUpsertOffTheLoop:
    """P3-13a: the other three add_vector_memory call sites in this file all
    wrap the Qdrant client's synchronous network I/O in asyncio.to_thread;
    add_memory's own call didn't, pinning the event loop for the duration of
    every memory write."""

    @pytest.mark.asyncio
    async def test_a_slow_qdrant_upsert_does_not_block_the_loop(self, store):
        s, _conn = store
        s.get_embedding = AsyncMock(return_value=[0.1] * 768)
        s.qdrant_store.client = object()

        ticks = 0
        ticks_when_upsert_finished = []

        def slow_upsert(**_kwargs):
            time.sleep(0.2)
            # Sampled at the moment the blocking work ends. Off the loop, the
            # heartbeat below has been running throughout and this is
            # non-zero; inline, the loop was pinned and it has not ticked
            # once. Asserting only on the final tick count would pass either
            # way -- gather() waits for both regardless of overlap -- so it
            # measures completion, not concurrency.
            ticks_when_upsert_finished.append(ticks)

        s.qdrant_store.add_vector_memory = slow_upsert

        async def heartbeat():
            nonlocal ticks
            for _ in range(10):
                await asyncio.sleep(0.01)
                ticks += 1

        await asyncio.gather(s.add_memory("a slow write", wing="personal"), heartbeat())

        assert ticks_when_upsert_finished, "the qdrant upsert never ran"
        assert ticks_when_upsert_finished[0] > 0, (
            "the event loop made no progress while the qdrant upsert ran, "
            "so the upsert is back on the loop"
        )
