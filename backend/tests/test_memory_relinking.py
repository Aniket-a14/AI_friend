"""Bucket 12's re-linking half of rest-phase replay.

`_prelink_memory_entities` only ever runs once, at `add_memory` time, against
whichever entities existed in the graph *then*. `_compute_candidate_entities`
(the graph-boost/PPR path `search_memories` uses) prefers a memory's stored
`metadata["entities"]` over a live regex scan whenever that list is
non-empty -- a real performance win, but it means a memory whose precomputed
list is merely *incomplete*, not empty, is stuck with it forever: nothing
ever re-scans it. These tests pin the fix -- `get_recent_high_importance_
memories_for_relinking` + `relink_memory_entities` -- against a real
full-schema SQLite database, not the global asyncpg mock (which has no
`memories` table at all; see `test_eriksonian_cognitive_alignment.py` for
why that mock can't be used here).
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.state.memory_store import MemoryStore
from app.state.sqlite_fallback import SQLitePool


@pytest.fixture
def temp_store():
    pool = SQLitePool(":memory:")
    mock_graph = MagicMock()
    # Mutable so a test can add/replace "what the graph currently knows"
    # between writing a memory and running the re-link sweep.
    known_entities = []

    async def mock_execute_query(query, *args, **kwargs):
        if "MATCH (e:Entity)" in query:
            return [{"name": name} for name in known_entities]
        return []

    mock_graph.execute_query = mock_execute_query
    store = MemoryStore(pool, mock_graph)
    store.qdrant_store.client = None
    return store, known_entities


def _fetch_metadata(store, content: str) -> dict:
    """Read a row's raw metadata straight from SQLite, bypassing the search
    path entirely so the assertion checks what was actually written, not
    what a separate retrieval path chooses to surface."""

    async def _fetch():
        async with store.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT metadata FROM memories WHERE content = ?", content
            )
            return rows[0]["metadata"]

    import orjson

    raw = asyncio.run(_fetch())
    return orjson.loads(raw) if isinstance(raw, str) else (raw or {})


def test_relink_picks_up_an_entity_created_after_the_memory_was_written(temp_store):
    """The whole point of the bucket: an entity that didn't exist yet at
    write time must still be findable via graph-boost once it does."""
    store, known_entities = temp_store
    content = "I told Priya about my day."

    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        assert asyncio.run(store.add_memory(content=content)) is True

    assert _fetch_metadata(store, content).get("entities") == []

    known_entities.append("Priya")

    candidates = asyncio.run(
        store.get_recent_high_importance_memories_for_relinking()
    )
    relinked = asyncio.run(store.relink_memory_entities(candidates))

    assert relinked == 1
    assert _fetch_metadata(store, content)["entities"] == ["Priya"]


def test_relink_does_not_rewrite_a_row_already_fully_linked(temp_store):
    """No wasted writes on a candidate whose entities are already current --
    a mutation that drops the 'only write if it grew' guard would make this
    return 1 instead of 0."""
    store, known_entities = temp_store
    known_entities.append("Priya")
    content = "I told Priya about my day."

    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        assert asyncio.run(store.add_memory(content=content)) is True

    assert _fetch_metadata(store, content)["entities"] == ["Priya"]

    candidates = asyncio.run(
        store.get_recent_high_importance_memories_for_relinking()
    )
    relinked = asyncio.run(store.relink_memory_entities(candidates))

    assert relinked == 0


def test_relink_unions_with_existing_entities_rather_than_replacing_them(temp_store):
    """An entity found at write time but no longer returned by a live graph
    scan (renamed, or a mocked-out reorganisation) must not be dropped --
    re-linking only ever adds associations, per this bucket's own design."""
    store, known_entities = temp_store
    known_entities.append("OldEntity")
    content = "OldEntity and NewEntity had lunch together."

    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        assert asyncio.run(store.add_memory(content=content)) is True

    assert _fetch_metadata(store, content)["entities"] == ["OldEntity"]

    # The graph now only reports NewEntity -- OldEntity is gone from it, but
    # must survive in the memory's own stored metadata regardless.
    known_entities.clear()
    known_entities.append("NewEntity")

    candidates = asyncio.run(
        store.get_recent_high_importance_memories_for_relinking()
    )
    relinked = asyncio.run(store.relink_memory_entities(candidates))

    assert relinked == 1
    assert _fetch_metadata(store, content)["entities"] == ["NewEntity", "OldEntity"]


def test_relink_preserves_unrelated_metadata_fields(temp_store):
    """A read-modify-write over the whole metadata blob must not clobber
    fields re-linking has no business touching."""
    store, known_entities = temp_store
    content = "Priya came over for coffee."

    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        assert asyncio.run(
            store.add_memory(content=content, metadata={"custom_flag": "keep_me"})
        ) is True

    known_entities.append("Priya")

    candidates = asyncio.run(
        store.get_recent_high_importance_memories_for_relinking()
    )
    asyncio.run(store.relink_memory_entities(candidates))

    updated = _fetch_metadata(store, content)
    assert updated["entities"] == ["Priya"]
    assert updated["custom_flag"] == "keep_me"


def test_relink_handles_an_empty_candidate_list():
    """The rest-phase sweep calls this every idle cycle; a night with no
    qualifying memories must be a no-op, not an exception."""
    store = MemoryStore(SQLitePool(":memory:"), MagicMock())
    assert asyncio.run(store.relink_memory_entities([])) == 0
