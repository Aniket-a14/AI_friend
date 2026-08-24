"""
Draining `history["memories"]` into the store that can actually recall it.

`evolve_persona` appends to `history["memories"]` whenever reflection decides
something is worth keeping. Nothing ever read it back: `get_persona_prompt`
builds from the profile and `history["relationship"]`, and no other caller
touches the list. So the agent has been deciding what to remember, writing it
down, and never once consulting it — the memories existed only as a growing
field in a JSON blob.

This module turns that list into a staging buffer for the real episodic store.
Anything sitting in it is written to `MemoryStore` with a source tag, after
which the ordinary retrieval path can surface it like any other memory.

Idempotence is per-entry by fingerprint, the same shape `biography.py` uses and
for the same reason: the list is appended to over time, so a single "migrated"
flag would force a choice between re-importing everything and never importing
what arrived after the flag was set.

Entries are **not** removed from the list once migrated. Dropping them would
make the JSON the only place a failed migration could be noticed, and the
fingerprint ledger already prevents duplicates. The list stays as a record of
what reflection thought; the memory store becomes where it lives.
"""

import hashlib
import logging
from collections.abc import Iterable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

# Lower than a biography passage. Biography is foundational — who this person
# is — while these are incidental things noticed during conversation. Still
# above an ordinary turn, because reflection already judged them worth keeping.
HISTORY_IMPORTANCE = 0.6

# Distinguishes them from `biography` and from lived conversation, so a persona
# reset can clear seeded material without touching what the user actually said.
HISTORY_SOURCE = "seed_history"


def entry_text(entry: Any) -> str:
    """Normalise one `history["memories"]` item to its text.

    The list has never had an enforced shape. `evolve_persona` appends whatever
    the reflection LLM put in `new_memory`, which is usually a string but has no
    schema forbidding a dict, and the older seeded files used bare strings. A
    migration that assumed one shape would silently drop the other, so both are
    accepted and anything else is skipped rather than stringified — `"{'a': 1}"`
    as a memory is worse than no memory.
    """
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for key in ("content", "text", "memory"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def fingerprint(text: str) -> str:
    """Identity of one migrated memory.

    Over the text alone. Unlike a biography paragraph there is no heading to
    disambiguate, and the same sentence recorded twice genuinely is the same
    memory — reflection re-noticing something is not a second fact.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pending_entries(memories: Sequence[Any], already_seeded: Iterable[str]) -> list[str]:
    """The memory texts not yet written to the store, de-duplicated."""
    seen: set[str] = set(already_seeded or ())
    pending: list[str] = []

    for entry in memories or ():
        text = entry_text(entry)
        if not text:
            continue
        mark = fingerprint(text)
        if mark in seen:
            continue
        # Added as we go, so a list containing the same sentence twice imports
        # it once rather than racing itself within a single run.
        seen.add(mark)
        pending.append(text)

    return pending


async def migrate_history_memories(
    memories: Sequence[Any],
    memory_store: Any,
    already_seeded: Iterable[str] = (),
) -> list[str]:
    """Write pending history memories into the episodic store.

    Returns the fingerprints actually stored, for the caller to persist. One
    failure is logged and skipped rather than aborting the rest: a partial
    migration is strictly better than none, and the next boot retries only what
    is still missing.
    """
    if memory_store is None:
        return []

    pending = pending_entries(memories, already_seeded)
    if not pending:
        return []

    logger.info(
        "[History] Migrating %d memory/memories into the episodic store.",
        len(pending),
    )

    # P4-12 (roadmap leftovers Item 1): one batched embedding call for all
    # pending entries instead of one per entry. Defensive against a
    # get_embeddings that doesn't honor the order/length contract (a test
    # double, or a future implementation) -- falls back to per-entry
    # internal embedding via add_memory rather than misaligning vectors.
    embeddings = [None] * len(pending)
    get_embeddings = getattr(memory_store, "get_embeddings", None)
    if callable(get_embeddings):
        try:
            candidate = await get_embeddings(list(pending))
            if isinstance(candidate, list) and len(candidate) == len(pending):
                embeddings = candidate
        except Exception as exc:
            logger.warning(
                "[History] Batched embedding fetch failed (%s); falling back "
                "to per-entry embedding.",
                exc,
            )

    stored: list[str] = []
    for text, embedding in zip(pending, embeddings, strict=True):
        try:
            await memory_store.add_memory(
                content=text,
                wing="personal",
                importance=HISTORY_IMPORTANCE,
                source=HISTORY_SOURCE,
                metadata={"history_fingerprint": fingerprint(text)},
                embedding=embedding,
            )
        except Exception as exc:
            logger.error(
                "[History] Could not migrate %r (%s); skipping it.",
                text[:60],
                exc,
            )
            continue
        stored.append(fingerprint(text))

    return stored
