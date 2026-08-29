"""Tests for MemoryStore.get_embeddings (P4-12, roadmap leftovers Item 1).

M5-P3 MEASURED: nomic-embed-text, 768-dim, per-item cost ~19ms at batch 1
(warm) vs 8.0ms at batch 32 -- 2.4x cheaper. These tests cover the batching
contract itself: order-preserving, length-preserving on partial failure,
chunked at Config.EMBEDDING_BATCH_SIZE, and falling back to the existing
sequential get_embedding() path on a 404 from the batch endpoint. A separate
test confirms add_memory(embedding=...) skips the internal fetch entirely,
which is what lets the four loop call sites actually batch.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import Config
from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore

pytestmark = pytest.mark.asyncio


def _make_transport(handler):
    return httpx.MockTransport(handler)


def _store_with_transport(handler):
    """A MemoryStore whose HTTP client is wired to a synchronous handler,
    so tests can assert exactly what was requested without a live Ollama."""
    store = MemoryStore(pool=None, graph_db=None)
    store._http_client = httpx.AsyncClient(transport=_make_transport(handler))
    return store


class TestBatchPreservesOrderAndLength:
    async def test_batch_of_three_returns_three_vectors_in_input_order(self):
        """A misaligned batch response would silently attach the wrong
        vector to the wrong memory -- worse than no embedding at all."""
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = request.read()
            import json

            payload = json.loads(body)
            calls.append(payload["input"])
            return httpx.Response(
                200,
                json={
                    "embeddings": [[float(i)] * 4 for i in range(len(payload["input"]))]
                },
            )

        store = _store_with_transport(handler)
        result = await store.get_embeddings(["alpha", "beta", "gamma"])

        assert len(calls) == 1, "expected exactly one HTTP call, not one per item"
        assert calls[0] == ["alpha", "beta", "gamma"]
        assert result == [[0.0] * 4, [1.0] * 4, [2.0] * 4]

    async def test_empty_input_returns_empty_list_with_no_http_call(self):
        called = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal called
            called = True
            return httpx.Response(200, json={"embeddings": []})

        store = _store_with_transport(handler)
        result = await store.get_embeddings([])

        assert result == []
        assert called is False


class TestPartialFailureDoesNotShiftTheList:
    async def test_a_response_shorter_than_the_request_falls_back_per_item(self):
        """A batch response with fewer vectors than inputs must not be
        zipped positionally against the input list -- that silently
        reassigns every vector after the missing one to the wrong text."""
        embed_calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            # /api/embed always returns a short (broken) batch; the
            # per-item sequential fallback for /api/embed also 404s here so
            # the fallback exercises /api/embeddings, matching get_embedding's
            # own two-endpoint shape.
            if "input" in payload:
                embed_calls.append(payload["input"])
                return httpx.Response(200, json={"embeddings": [[9.0] * 4]})
            return httpx.Response(404)

        store = _store_with_transport(handler)
        # Force the per-item fallback path for a deterministic per-text result:
        # patch get_embedding directly to prove get_embeddings() calls it,
        # without depending on a second real HTTP round trip's exact shape.
        store.get_embedding = AsyncMock(side_effect=[[1.0] * 4, [2.0] * 4, [3.0] * 4])

        result = await store.get_embeddings(["a", "b", "c"])

        assert len(result) == 3
        assert result == [[1.0] * 4, [2.0] * 4, [3.0] * 4]
        assert store.get_embedding.await_count == 3

    async def test_a_single_null_vector_in_the_batch_response_yields_none_in_place(
        self,
    ):
        """Ollama can return a null entry for one input without failing the
        whole request; that must surface as None at the same index, not be
        dropped (which would shift every later item left by one)."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"embeddings": [[1.0] * 4, None, [3.0] * 4]},
            )

        store = _store_with_transport(handler)
        result = await store.get_embeddings(["a", "b", "c"])

        assert result == [[1.0] * 4, None, [3.0] * 4]
        assert len(result) == 3


class TestChunking:
    async def test_a_batch_larger_than_the_configured_size_is_chunked(
        self, monkeypatch
    ):
        """Config.EMBEDDING_BATCH_SIZE bounds each HTTP request; a caller
        embedding 70 items at the default 32 must see 3 requests, and the
        final combined result must still be one aligned list of 70."""
        monkeypatch.setattr(Config, "EMBEDDING_BATCH_SIZE", 32)
        request_sizes = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            n = len(payload["input"])
            request_sizes.append(n)
            return httpx.Response(
                200, json={"embeddings": [[1.0] * 4 for _ in range(n)]}
            )

        store = _store_with_transport(handler)
        texts = [f"item-{i}" for i in range(70)]
        result = await store.get_embeddings(texts)

        assert request_sizes == [32, 32, 6]
        assert len(result) == 70
        assert all(vec == [1.0] * 4 for vec in result)

    async def test_batch_size_of_one_still_returns_one_vector_per_call(
        self, monkeypatch
    ):
        monkeypatch.setattr(Config, "EMBEDDING_BATCH_SIZE", 1)
        request_sizes = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.read())
            n = len(payload["input"])
            request_sizes.append(n)
            return httpx.Response(
                200, json={"embeddings": [[2.0] * 4 for _ in range(n)]}
            )

        store = _store_with_transport(handler)
        result = await store.get_embeddings(["x", "y", "z"])

        assert request_sizes == [1, 1, 1]
        assert len(result) == 3


class TestBatchEndpoint404FallsBackToSequential:
    async def test_a_404_from_api_embed_falls_back_to_get_embedding_per_item(self):
        """/api/embeddings (the legacy endpoint get_embedding falls back to)
        is single-input only and cannot serve a batch request, so a 404 on
        the batch path must degrade to calling get_embedding() once per
        text -- preserving the existing two-endpoint fallback shape rather
        than inventing a second one."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        store = _store_with_transport(handler)
        store.get_embedding = AsyncMock(side_effect=[[5.0] * 4, [6.0] * 4])

        result = await store.get_embeddings(["p", "q"])

        assert result == [[5.0] * 4, [6.0] * 4]
        assert store.get_embedding.await_count == 2
        assert store.get_embedding.await_args_list[0].args == ("p",)
        assert store.get_embedding.await_args_list[1].args == ("q",)


class TestMockLlmFallback:
    async def test_mock_llm_text_returns_n_vectors_not_one(self, monkeypatch):
        """The MOCK_LLM_TEXT escape hatch in get_embedding returns one
        random unit vector; get_embeddings must return one per input, not a
        single vector reused or a shortened list."""
        monkeypatch.setattr(Config, "MOCK_LLM_TEXT", True)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no Ollama in this test")

        store = _store_with_transport(handler)
        result = await store.get_embeddings(["one", "two", "three"])

        assert len(result) == 3
        assert all(vec is not None and len(vec) == 768 for vec in result)


class TestAddMemorySkipsInternalFetchWhenEmbeddingProvided:
    async def test_add_memory_with_embedding_never_calls_get_embedding(self):
        """The four batched call sites (archive promotion, biography
        seeding, history migration, eval indexing) depend on add_memory
        skipping its own embedding fetch when handed a precomputed vector --
        otherwise batching upstream buys nothing."""
        conv_store = ConversationHistoryStore()
        await conv_store.initialize()
        async with conv_store.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY, content TEXT, raw_content TEXT,
                    wing TEXT, room TEXT, embedding TEXT,
                    importance_score REAL, emotional_weight REAL, valence REAL,
                    certainty REAL, source TEXT, metadata TEXT,
                    recall_count INTEGER,
                    last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    lifespan_stage TEXT, crisis TEXT, virtue TEXT,
                    relations TEXT, relation_circles TEXT, modality TEXT
                )
                """
            )

        mock_graph = MagicMock()
        mock_graph.execute_query = AsyncMock(return_value=[])
        store = MemoryStore(pool=conv_store.pool, graph_db=mock_graph)
        store.qdrant_store.client = None
        store.get_embedding = AsyncMock(
            side_effect=AssertionError(
                "get_embedding should not be called when embedding= is provided"
            )
        )

        ok = await store.add_memory(
            content="precomputed-vector memory",
            embedding=[0.5] * 768,
        )

        assert ok is True
        store.get_embedding.assert_not_awaited()

    async def test_add_memory_without_embedding_still_calls_get_embedding(self):
        """The default (embedding=None) must preserve every existing
        caller's behavior byte-for-byte."""
        conv_store = ConversationHistoryStore()
        await conv_store.initialize()
        async with conv_store.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY, content TEXT, raw_content TEXT,
                    wing TEXT, room TEXT, embedding TEXT,
                    importance_score REAL, emotional_weight REAL, valence REAL,
                    certainty REAL, source TEXT, metadata TEXT,
                    recall_count INTEGER,
                    last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    lifespan_stage TEXT, crisis TEXT, virtue TEXT,
                    relations TEXT, relation_circles TEXT, modality TEXT
                )
                """
            )

        mock_graph = MagicMock()
        mock_graph.execute_query = AsyncMock(return_value=[])
        store = MemoryStore(pool=conv_store.pool, graph_db=mock_graph)
        store.qdrant_store.client = None
        store.get_embedding = AsyncMock(return_value=[0.1] * 768)

        ok = await store.add_memory(content="default-path memory")

        assert ok is True
        store.get_embedding.assert_awaited_once_with("default-path memory")
