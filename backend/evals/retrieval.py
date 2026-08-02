"""Retrievers the conversation suite can put behind a context strategy.

The recall suite's whole point is the gap between strategies. `full_history`
shows the model everything and `recent_window` shows it the tail; both are
bounds, not systems. What this project actually claims is that a memory layer
picks better than either, and that claim is only testable if something can be
plugged into the same seam and measured.

Two retrievers, because one is not enough to attribute a result:

- `LexicalRetriever` is a plain BM25 over the transcript. It is the control. If
  the memory layer cannot beat it, then whatever `full_history` was losing was
  lost to context length rather than to anything the architecture addresses.
- `MemoryStoreRetriever` is the real `MemoryStore.search_memories` -- ACT-R
  activation, the learned lexicon, graph boost, vectors -- reached through the
  same construction production uses. The gap between it and BM25 is this
  repo's contribution, stated as a number instead of an intention.

Indexing is idempotent per transcript so two strategies sharing a retriever pay
for it once, and it is scoped per probe so one probe's filler cannot answer
another probe's question.
"""

import hashlib
import logging
import math
import re
from collections import Counter
from typing import NamedTuple, Protocol

logger = logging.getLogger("evals.retrieval")

# The wing every eval-written memory lands in. Deliberately not "personal":
# this suite writes hundreds of scripted filler lines into whatever database it
# is pointed at, and those must never become things the agent believes about
# its user. Scoping them here is what makes the cleanup at the end total.
EVAL_WING = "eval_harness"

_WORD_RE = re.compile(r"\b\w+\b")


class Turn(NamedTuple):
    """Mirrors `conversation.Turn`; redeclared to keep the import one-way."""

    speaker: str
    text: str


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def transcript_fingerprint(turns: list) -> str:
    """Identity of a transcript, for skipping a re-index that would be a no-op."""
    digest = hashlib.sha256()
    for turn in turns:
        digest.update(turn.speaker.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(turn.text.encode("utf-8"))
        digest.update(b"\x01")
    return digest.hexdigest()[:16]


class Retriever(Protocol):
    """Something that can be asked which turns matter for a question."""

    name: str

    async def index(self, turns: list) -> None:
        ...

    async def search(self, query: str, limit: int) -> list:
        ...

    async def close(self) -> None:
        ...


class LexicalRetriever:
    """BM25 over the transcript. The control, and deliberately unclever.

    No embeddings, no database, no decay -- so it isolates "retrieval happened"
    from "this project's retrieval happened". A memory layer that cannot beat
    a fifty-line ranking function on a planted-fact probe has not yet earned
    the infrastructure it costs.

    Okapi BM25 with the usual k1/b; `b` is doing real work here because the
    turns are short and wildly uneven in length.
    """

    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._turns: list = []
        self._docs: list[list[str]] = []
        self._df: Counter = Counter()
        self._avg_len = 0.0
        self._fingerprint = ""

    async def index(self, turns: list) -> None:
        fingerprint = transcript_fingerprint(turns)
        if fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        self._turns = list(turns)
        self._docs = [_tokenize(turn.text) for turn in turns]
        self._df = Counter()
        for doc in self._docs:
            for term in set(doc):
                self._df[term] += 1
        self._avg_len = (
            sum(len(doc) for doc in self._docs) / len(self._docs)
            if self._docs
            else 0.0
        )

    def _score(self, doc: list[str], query_terms: list[str]) -> float:
        if not doc or not self._avg_len:
            return 0.0
        counts = Counter(doc)
        total = len(self._docs)
        score = 0.0
        for term in query_terms:
            freq = counts.get(term, 0)
            if not freq:
                continue
            # +0.5 smoothing on both sides keeps the idf of a term appearing in
            # every turn at zero rather than negative -- filler words are then
            # merely useless, not actively repellent.
            idf = math.log(
                1 + (total - self._df[term] + 0.5) / (self._df[term] + 0.5)
            )
            denom = freq + self.k1 * (
                1 - self.b + self.b * len(doc) / self._avg_len
            )
            score += idf * (freq * (self.k1 + 1)) / denom
        return score

    async def search(self, query: str, limit: int) -> list:
        query_terms = _tokenize(query)
        scored = [
            (self._score(doc, query_terms), index)
            for index, doc in enumerate(self._docs)
        ]
        # Ties break on transcript order, so the ranking is total and a rerun
        # cannot reorder equally-scored turns.
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [
            self._turns[index] for score, index in scored[:limit] if score > 0
        ]

    async def close(self) -> None:
        return None


class MemoryStoreRetriever:
    """The production memory layer, reached the way production reaches it.

    Every turn is written through `add_memory` and recalled through
    `search_memories`, so this exercises the real path: embeddings into Qdrant,
    the graph into Neo4j, ACT-R activation and cue expansion over Postgres. A
    reimplementation here would measure a thing nobody ships.

    Writes are confined to `EVAL_WING` and removed by `close()`. The suite
    otherwise inserts hundreds of scripted lines into the same database the
    agent uses to remember its user, which would be a considerably worse bug
    than anything the suite is trying to detect.
    """

    name = "memory_store"

    def __init__(self, store, wing: str = EVAL_WING):
        self.store = store
        self.wing = wing
        self._room = ""
        self._by_content: dict[str, Turn] = {}
        self._fingerprint = ""
        # Counts from the most recent index, so a caller can tell a real recall
        # failure from a transcript that never made it into the store.
        self.indexed = 0
        self.index_failures = 0

    async def index(self, turns: list) -> None:
        fingerprint = transcript_fingerprint(turns)
        if fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint

        # Purge before writing, and this is load-bearing rather than tidy.
        # `add_memory` deduplicates on content across the whole table, not
        # within a room -- measured, after a run where this retriever returned
        # zero turns on five probes. Probes share filler verbatim, so the
        # second probe's writes were swallowed as duplicates of the first
        # probe's rows, which live in the first probe's room. Its own room came
        # up empty and every result read as a memory-layer failure that was
        # entirely an artifact of leaving the previous probe in place.
        #
        # A room per transcript therefore documents intent; the purge is what
        # actually delivers isolation.
        await self._purge()
        self._room = f"probe_{fingerprint}"
        self._by_content = {}

        written = 0
        failed = 0
        for turn in turns:
            content = turn.text
            self._by_content.setdefault(content, turn)
            try:
                ok = await self.store.add_memory(
                    content=content,
                    wing=self.wing,
                    room=self._room,
                    source="eval",
                )
            except Exception as exc:
                failed += 1
                logger.warning("[eval] add_memory raised for a turn: %s", exc)
                continue
            # `add_memory` reports failure by returning False rather than
            # raising, so an unchecked call cannot distinguish "stored" from
            # "silently dropped".
            written += 1 if ok else 0
            failed += 0 if ok else 1

        # A partly-written index answers queries from a transcript the model
        # was never given, and the report has no column that would show it. The
        # last run this suite produced was invalidated by exactly this shape of
        # silence -- an empty index read as a memory layer that could not
        # recall -- so it is said out loud rather than inferred later.
        if failed:
            logger.error(
                "[eval] %d of %d turns failed to index; retrieval results for "
                "this probe describe an incomplete transcript and are not "
                "evidence about the memory layer",
                failed,
                len(turns),
            )
        self.indexed = written
        self.index_failures = failed

    async def search(self, query: str, limit: int) -> list:
        # `refresh_on_recall` is what makes retrieval strengthen a memory --
        # every hit takes `recall_count + 1`, which feeds straight back into
        # the ln(frequency) term of the next query's activation. That is
        # correct for an agent living its life and wrong for an instrument:
        # four strategies ask the same room the same question, and each one
        # would rank against a store the previous one had already reshaped.
        # Measured, not assumed -- the frequency term is large enough to
        # reorder these results on its own (see the ledger entry on
        # `_base_activation`), so leaving this on makes probe order a variable.
        #
        # `full_candidate_pool=True` is not optional decoration. That flag is
        # normally read off `refresh_on_recall`, so switching the refresh off
        # also drops the candidate pool from 120 to 20 -- and a retriever
        # searching a sixth of production's candidates is not the thing this
        # suite claims to be measuring. Found in review, after a live run had
        # already been published against the narrower pool.
        results = await self.store.search_memories(
            query_text=query,
            wing=self.wing,
            room=self._room,
            limit=limit,
            refresh_on_recall=False,
            full_candidate_pool=True,
        )
        turns: list = []
        for row in results:
            content = row.get("content") if isinstance(row, dict) else None
            if content is None:
                continue
            turn = self._by_content.get(content)
            if turn is not None and turn not in turns:
                turns.append(turn)
        return turns

    async def close(self) -> None:
        """Remove everything this retriever wrote, from every tier it wrote to.

        This is not tidiness. The suite inserts hundreds of scripted filler
        lines into the same database the agent uses to remember its user, so a
        cleanup that silently half-worked would leave "the bus was late again"
        sitting in the agent's autobiography, indistinguishable from something
        the user actually said.
        """
        await self._purge()

    async def _purge(self) -> None:
        """Delete every eval-written memory, across all three tiers.

        Ids are read back before the delete because `add_memory` returns a
        bool, and the vector tier is keyed by the same id -- without them,
        Postgres would be clean while Qdrant still answered queries from the
        rows it no longer has. Loud on failure: a silent half-clean is how eval
        filler ends up in the agent's autobiography run after run.
        """
        ids: list[str] = []
        try:
            async with self.store.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id FROM memories WHERE wing = $1", self.wing
                )
                ids = [str(row["id"]) for row in rows]
                await conn.execute(
                    "DELETE FROM memories WHERE wing = $1", self.wing
                )
        except Exception as exc:
            logger.error(
                "[eval] could not clean wing %r from the relational tier: %s "
                "-- eval filler is still in the agent's memory",
                self.wing,
                exc,
            )
            return

        client = getattr(self.store.qdrant_store, "client", None)
        collection = getattr(self.store.qdrant_store, "collection_name", None)
        if client is not None and collection and ids:
            try:
                client.delete(collection_name=collection, points_selector=ids)
            except Exception as exc:
                logger.error(
                    "[eval] %d eval vectors remain in Qdrant collection %r: %s",
                    len(ids),
                    collection,
                    exc,
                )

        graph = self.store.graph_db
        if graph is not None:
            try:
                await graph.execute_query(
                    "MATCH (n) WHERE n.wing = $wing DETACH DELETE n",
                    {"wing": self.wing},
                    write=True,
                )
            except Exception as exc:
                logger.warning(
                    "[eval] graph nodes for wing %r may remain: %s",
                    self.wing,
                    exc,
                )

        logger.info(
            "[eval] cleaned %d eval memories from wing %r", len(ids), self.wing
        )


__all__ = [
    "EVAL_WING",
    "LexicalRetriever",
    "MemoryStoreRetriever",
    "Retriever",
    "transcript_fingerprint",
]
