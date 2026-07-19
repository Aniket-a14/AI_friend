"""
Starting your friend over from the file you wrote.

`config/persona.toml` and `config/biography.md` are read once, on the first
boot, and then never again — the friend owns their own values from that point
on. That is the right default, and it leaves one thing unanswered: what if you
got the description wrong, or want to try a different person entirely?

This is that escape hatch, and it is deliberately not something a text editor
can trigger. Editing a config file and restarting is how you tune a service.
Erasing who someone is should take a decision.

**What it clears:** the persona row in `agent_configs`, and every memory tagged
as seeded rather than lived (`biography`, `seed_history`).

**What it keeps:** everything said in an actual conversation. Those memories
were not seeded from a file, so re-seeding has nothing to say about them, and
destroying months of real history to correct a typo in a temperament setting
would be a wildly disproportionate trade. The friend goes back to their
original nature but still remembers you.

The persona row is *deleted* rather than rewritten, because
`ConversationHistoryStore._ensure_config_exists` already knows how to seed a
missing row from the shipped JSON defaults. Re-implementing that here would
create a second definition of "a fresh agent" that could drift from the real
one. Deleting the row makes the next boot a genuine first boot, which is
exactly what re-seeding means.
"""

import logging
from typing import Any, Dict, List, Sequence

from .biography import BIOGRAPHY_SOURCE
from .history_migration import HISTORY_SOURCE

logger = logging.getLogger(__name__)

# The sources that came from a file rather than from the user. Anything not in
# this list is something the agent was actually told, and survives a reset.
SEEDED_SOURCES: Sequence[str] = (BIOGRAPHY_SOURCE, HISTORY_SOURCE)

# Both tiers. A seeded memory that decayed out of the active set still exists in
# the archive and can be promoted back, so clearing only `memories` would leave
# the old persona able to resurface weeks later — the most confusing possible
# outcome of a reset that appeared to succeed.
_MEMORY_TABLES = ("memories", "archived_memories")


async def _seeded_ids(conn: Any, table: str, is_sqlite: bool) -> List[str]:
    """Ids of file-seeded rows in one memory table."""
    if is_sqlite:
        placeholders = ",".join("?" for _ in SEEDED_SOURCES)
        query = f"SELECT id FROM {table} WHERE source IN ({placeholders})"
    else:
        placeholders = ",".join(f"${i + 1}" for i in range(len(SEEDED_SOURCES)))
        query = f"SELECT id FROM {table} WHERE source IN ({placeholders})"

    rows = await conn.fetch(query, *SEEDED_SOURCES)
    return [str(dict(row)["id"]) for row in rows or ()]


async def _drop_from_qdrant(memory_store: Any, ids: Sequence[str]) -> None:
    """Remove the vectors for deleted memories.

    Not optional cleanup. Retrieval fuses Qdrant hits with SQL rows, so a vector
    left behind after its row is gone means the old persona keeps being *found*
    — the search returns a candidate that no longer exists, and depending on the
    branch that is either a crash or a silently resurrected memory.
    """
    if not ids:
        return

    store = getattr(memory_store, "qdrant_store", None)
    if not store or not getattr(store, "client", None):
        return

    try:
        import asyncio

        from qdrant_client.http import models

        await asyncio.to_thread(
            store.client.delete,
            collection_name=store.collection_name,
            points_selector=models.PointIdsList(points=list(ids)),
        )
    except Exception as exc:
        # Logged rather than raised: the SQL delete is the authoritative one and
        # has already happened. Aborting here would leave the caller believing
        # nothing was reset when in fact most of it was.
        logger.error("[Reset] Could not delete %d vector(s) from Qdrant: %s", len(ids), exc)


async def clear_seeded_memories(memory_store: Any) -> int:
    """Delete every file-seeded memory, from both tiers and from Qdrant."""
    if memory_store is None or getattr(memory_store, "pool", None) is None:
        return 0

    is_sqlite = bool(getattr(memory_store, "is_sqlite", False))
    removed = 0

    async with memory_store.pool.acquire() as conn:
        for table in _MEMORY_TABLES:
            try:
                ids = await _seeded_ids(conn, table, is_sqlite)
            except Exception as exc:
                # `archived_memories` may not exist on a partially migrated
                # install. Missing a table is not a reason to abandon the rest.
                logger.warning("[Reset] Could not scan %s (%s); skipping.", table, exc)
                continue

            if not ids:
                continue

            if is_sqlite:
                marks = ",".join("?" for _ in ids)
            else:
                marks = ",".join(f"${i + 1}" for i in range(len(ids)))

            await conn.execute(f"DELETE FROM {table} WHERE id IN ({marks})", *ids)
            await _drop_from_qdrant(memory_store, ids)
            removed += len(ids)
            logger.info("[Reset] Removed %d seeded memory/memories from %s.", len(ids), table)

    return removed


async def clear_persona_row(config_store: Any) -> bool:
    """Delete the stored persona so the next boot seeds from the files again."""
    if config_store is None or getattr(config_store, "pool", None) is None:
        return False

    try:
        async with config_store.pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_configs WHERE id = 1")
        logger.info("[Reset] Cleared the stored persona.")
        return True
    except Exception as exc:
        logger.error("[Reset] Could not clear the stored persona: %s", exc)
        return False


async def reset_persona(config_store: Any, memory_store: Any) -> Dict[str, Any]:
    """Reset the friend to whatever `config/` currently describes.

    Memories go first. If the process dies between the two steps, the surviving
    order is "seeded memories gone, persona intact" — a friend missing some
    backstory, which the next boot re-seeds from the file. The reverse order
    would leave a cleared persona alongside the *old* biography still in memory:
    a new temperament fused with someone else's history, and nothing to indicate
    the reset was incomplete.
    """
    memories_removed = await clear_seeded_memories(memory_store)
    persona_cleared = await clear_persona_row(config_store)

    return {
        "memories_removed": memories_removed,
        "persona_cleared": persona_cleared,
    }
