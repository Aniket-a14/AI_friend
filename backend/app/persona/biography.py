"""
Seeding a friend with a life.

`config/persona.toml` describes *temperament* — how someone feels, how fast,
for how long. It cannot describe a person. Who they are is mostly episodes:
what happened to them, who is in their life, how they argue, the phrase they
always use when they are tired.

That material does not belong in the persona schema and it does not belong in
the system prompt either. A biography of any real length would sit in the
context window of every single turn, costing latency on each one, while most of
it is irrelevant to whatever is being said right now. The agent already has the
right machine for this — an episodic memory store with vector search, graph
links and ACT-R activation — and it was only ever fed by conversation.

So a `biography.md` is read once and written into memory as episodes. From then
on the ordinary retrieval path decides what surfaces: mention her sister and the
sister paragraphs come back; talk about work and they stay put. The documentary
can be fifty pages, because only the relevant few sentences are ever in play.

**Granularity is paragraphs, not sections.** A whole section as one memory
retrieves all-or-nothing, so a question about one detail drags in five unrelated
ones and crowds out everything else. Each paragraph carries its heading as
context, which is what makes an isolated line like "she never apologises first"
still mean something when it surfaces on its own.
"""

import hashlib
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Config

logger = logging.getLogger(__name__)

DEFAULT_BIOGRAPHY_FILE = "config/biography.md"

# Biography material is foundational rather than incidental: it should outrank a
# passing remark from last Tuesday when both match a cue. Not pinned to the
# maximum, because things the user actually says should still be able to win.
BIOGRAPHY_IMPORTANCE = 0.75

# Marks these memories as seeded rather than lived, so they can be told apart
# later -- for re-seeding, for pruning, and for honesty about where the agent's
# sense of a shared past actually came from.
BIOGRAPHY_SOURCE = "biography"

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass(frozen=True)
class BiographyEntry:
    """One paragraph of the documentary, with the heading it sat under."""

    heading: str
    text: str

    @property
    def fingerprint(self) -> str:
        """Identity of this paragraph, for seeding it exactly once.

        Over heading *and* text, so moving a paragraph to a different section
        counts as new — its meaning depends on what it was filed under.
        """
        digest = hashlib.sha256()
        digest.update(self.heading.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(self.text.encode("utf-8"))
        return digest.hexdigest()

    @property
    def memory_text(self) -> str:
        """What actually gets stored.

        The heading is folded in rather than kept as metadata because retrieval
        matches on content: a paragraph filed under "Her sister" that never says
        "sister" would otherwise be unreachable by the obvious cue.
        """
        if not self.heading:
            return self.text
        return f"{self.heading}: {self.text}"


def parse_biography(markdown: str) -> list[BiographyEntry]:
    """Split prose into paragraphs, each tagged with its nearest heading.

    Deliberately forgiving. This file is written by a person describing someone
    they know, not authored against a spec, so anything structural that is
    missing is inferred rather than rejected: text before the first heading is
    kept, blank-line-separated paragraphs are the unit, and heading depth is
    ignored beyond nesting the trail.
    """
    entries: list[BiographyEntry] = []
    heading_trail: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        text = " ".join(" ".join(buffer).split()).strip()
        buffer.clear()
        if text:
            # Empty slots are dropped only here, at the point of use. The trail
            # itself stays depth-aligned -- see below for why that matters.
            entries.append(
                BiographyEntry(
                    heading=" / ".join(h for h in heading_trail if h), text=text
                )
            )

    for line in (markdown or "").splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            depth = len(match.group(1))
            # Keep the enclosing headings so "How she argues / With family"
            # reads as one place rather than two unrelated labels.
            heading_trail = heading_trail[: depth - 1]
            while len(heading_trail) < depth - 1:
                heading_trail.append("")
            heading_trail.append(match.group(2))
            # Deliberately NOT compacted here. The trail is indexed by heading
            # depth, so dropping empty slots destroys that alignment: in a file
            # whose sections all start at `##` with no `#` above them, slot 0 is
            # legitimately empty, and compacting it made the next `##` believe
            # it was nesting under the previous one. Every section after the
            # first was then filed as "First Section / Second Section", and
            # since the heading is folded into the stored text, every single
            # memory carried the first section's name -- so a cue matching that
            # name matched the entire biography.
            continue

        if not line.strip():
            flush()
            continue

        buffer.append(line.strip())

    flush()
    return entries


def read_biography(path: Path | None) -> list[BiographyEntry]:
    """Parse the biography file, returning `[]` on any problem.

    Never raises: an unreadable biography must not stop the agent from starting.
    A friend who does not remember your history is still a friend you can talk
    to; a process that will not boot is not.
    """
    if path is None:
        return []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        logger.error(
            "[Biography] Could not read %s (%s). The agent will start without "
            "its seeded history.",
            path,
            exc,
        )
        return []
    return parse_biography(text)


def find_biography_file(explicit: str | None = None) -> Path | None:
    """Locate the biography: an explicit path, then `BIOGRAPHY_PATH`, then discovery.

    Discovery walks up from this module rather than trusting the process working
    directory, because the agents are launched from several places (the repo
    root, `backend/`, and a container WORKDIR) and a relative path would resolve
    differently in each.

    `BIOGRAPHY_PATH` is the counterpart to `PERSONA_PROFILE_PATH`, and exists
    for the same reason plus a sharper one. The persona is a temperament and
    could reasonably live in the repo; a biography is an actual person's life,
    written by someone who knows them, and a system that can only read it from
    a tracked path forces that material into git to be used at all.

    A path that is set but missing resolves to "no biography" and is *not*
    retried through discovery. Falling back would quietly seed the repo's own
    example file — and seeding is fingerprinted and effectively one-way, so a
    typo would plant a stranger's history that then has to be pruned back out.
    """
    if explicit is None:
        explicit = getattr(Config, "BIOGRAPHY_PATH", None) or None

    if explicit:
        path = Path(explicit)
        if path.exists():
            return path
        logger.warning(
            "[Biography] No biography file at %s; continuing without one. "
            "Discovery is deliberately not attempted for an explicit path.",
            explicit,
        )
        return None

    for parent in Path(__file__).resolve().parents:
        candidate = parent / DEFAULT_BIOGRAPHY_FILE
        if candidate.exists():
            return candidate
    return None


def pending_entries(
    entries: Sequence[BiographyEntry], already_seeded: Iterable[str]
) -> list[BiographyEntry]:
    """The paragraphs not yet written to memory.

    Per-paragraph rather than a single "seeded" flag so the documentary can be
    *added to*. Writing another page later seeds only the new pages, instead of
    forcing a choice between duplicating the whole file and never extending it.
    """
    seen: set[str] = set(already_seeded or ())
    return [entry for entry in entries if entry.fingerprint not in seen]


def stale_fingerprints(
    entries: Sequence[BiographyEntry], already_seeded: Iterable[str]
) -> list[str]:
    """Seeded passages the biography no longer contains.

    The counterpart to `pending_entries`. Adding a paragraph seeded it; deleting
    one did nothing, so a passage removed because it was wrong — or because the
    person it described asked for it to go — stayed in memory forever and kept
    surfacing. The file looked like the source of truth and was not.

    Editing a paragraph shows up here as one stale fingerprint plus one pending
    entry, which is the correct reading: the fingerprint covers heading and
    text, so an edited passage is a different passage.
    """
    current = {entry.fingerprint for entry in entries}
    return [mark for mark in (already_seeded or ()) if mark not in current]


async def prune_biography(
    stale: Sequence[str], memory_store: Any
) -> list[str]:
    """Delete memories for passages no longer in the biography.

    Returns the fingerprints actually removed, for the caller to drop from the
    ledger. A fingerprint whose row is already gone still counts as removed —
    the ledger is a record of what was seeded, and leaving an entry for a
    memory that does not exist means retrying the delete on every boot forever.
    """
    if memory_store is None or not stale:
        return []
    pool = getattr(memory_store, "pool", None)
    if pool is None:
        return []

    is_sqlite = bool(getattr(memory_store, "is_sqlite", False))
    # Fingerprints whose scan raised. They are held back from the ledger so the
    # next boot tries again — dropping one on a transient database error would
    # orphan its row permanently, since nothing would ever look for it after.
    unscanned: set[str] = set()

    logger.info("[Biography] Pruning %d deleted passage(s) from memory.", len(stale))

    async with pool.acquire() as conn:
        for table in ("memories", "archived_memories"):
            for mark in stale:
                try:
                    if is_sqlite:
                        # `metadata` is TEXT here, so the JSON has to be parsed
                        # by the query rather than indexed into. json1 ships
                        # with the stdlib build.
                        rows = await conn.fetch(
                            f"SELECT id FROM {table} WHERE "
                            "json_extract(metadata, '$.biography_fingerprint') = ?",
                            mark,
                        )
                    else:
                        rows = await conn.fetch(
                            f"SELECT id FROM {table} WHERE "
                            "metadata->>'biography_fingerprint' = $1",
                            mark,
                        )
                except Exception as exc:
                    logger.warning(
                        "[Biography] Could not scan %s for %s (%s); skipping.",
                        table,
                        mark[:12],
                        exc,
                    )
                    unscanned.add(mark)
                    continue

                ids = [str(dict(r)["id"]) for r in rows or ()]
                if not ids:
                    continue

                marks = ",".join("?" if is_sqlite else f"${i + 1}" for i in range(len(ids)))
                await conn.execute(f"DELETE FROM {table} WHERE id IN ({marks})", *ids)
                await _drop_vectors(memory_store, ids)

    # Every *scanned* fingerprint leaves the ledger, including ones that matched
    # no row. Keeping those would mean re-running this scan on every single boot
    # for a memory that no longer exists. A fingerprint whose scan failed is a
    # different case: there we do not know whether a row is still out there, and
    # the ledger entry is the only thing that will ever make us look again.
    removed = [mark for mark in stale if mark not in unscanned]
    if unscanned:
        logger.warning(
            "[Biography] %d passage(s) could not be scanned; retrying next boot.",
            len(unscanned),
        )
    return removed


async def _drop_vectors(memory_store: Any, ids: Sequence[str]) -> None:
    """Remove the vectors for deleted memories.

    Retrieval fuses Qdrant hits with SQL rows, so a vector left behind after
    its row is gone means the pruned passage keeps being *found* — the search
    returns a candidate that no longer exists.
    """
    store = getattr(memory_store, "qdrant_store", None)
    if not store or not getattr(store, "client", None) or not ids:
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
        logger.error("[Biography] Could not delete %d vector(s): %s", len(ids), exc)


async def seed_biography(
    entries: Sequence[BiographyEntry],
    memory_store: Any,
    already_seeded: Iterable[str] = (),
) -> list[str]:
    """Write pending paragraphs into episodic memory.

    Returns the fingerprints actually stored, for the caller to persist. A
    failure on one paragraph is logged and skipped rather than aborting: a
    partly-seeded history is worth more than none, and the next boot retries
    only what is still missing.
    """
    if memory_store is None:
        return []

    pending = pending_entries(entries, already_seeded)
    if not pending:
        return []

    logger.info("[Biography] Seeding %d new passage(s) into memory.", len(pending))

    # P4-12 (roadmap leftovers Item 1): one boot-time embedding call for all
    # pending passages instead of one per passage. get_embeddings() is
    # order-preserving and length-preserving even on partial failure, so a
    # None here just means add_memory falls back to its own internal fetch
    # for that one passage rather than the whole batch degrading. The length
    # check below is defensive against a test double or future memory_store
    # implementation whose get_embeddings doesn't honor that contract --
    # falling back to per-item internal embedding rather than misaligning
    # embeddings to passages if it doesn't.
    embeddings = [None] * len(pending)
    get_embeddings = getattr(memory_store, "get_embeddings", None)
    if callable(get_embeddings):
        try:
            candidate = await get_embeddings([entry.memory_text for entry in pending])
            if isinstance(candidate, list) and len(candidate) == len(pending):
                embeddings = candidate
        except Exception as exc:
            logger.warning(
                "[Biography] Batched embedding fetch failed (%s); falling back "
                "to per-passage embedding.",
                exc,
            )

    stored: list[str] = []
    for entry, embedding in zip(pending, embeddings, strict=True):
        try:
            await memory_store.add_memory(
                content=entry.memory_text,
                wing="personal",
                room=entry.heading or None,
                importance=BIOGRAPHY_IMPORTANCE,
                source=BIOGRAPHY_SOURCE,
                metadata={
                    "biography_heading": entry.heading,
                    "biography_fingerprint": entry.fingerprint,
                },
                embedding=embedding,
            )
        except Exception as exc:
            logger.error(
                "[Biography] Could not seed passage under %r (%s); skipping it.",
                entry.heading or "(untitled)",
                exc,
            )
            continue
        stored.append(entry.fingerprint)

    return stored
