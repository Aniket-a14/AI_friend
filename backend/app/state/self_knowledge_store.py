"""SelfKnowledgeStore -- what the agent knows, and does not know, about itself.

The existing grounding gate in ``ActionService`` protects the *user's* facts: it
catches "you told me…" and "remember when we…" claims whose content appears
nowhere in context. It has no counterpart for the agent's own life, so an LLM
asked about a sibling it has never been told about will invent one, fluently and
in character. For an agent whose whole point is to be a *particular* person that
is the worst available failure: a confident fabrication is much harder to notice
and undo than a blank.

This store supplies the two things that gate needs.

**Known terms.** The vocabulary of the agent's seeded biography, loaded once and
cached. Grounding a self-claim only against the handful of memories surfaced
*this turn* would reject true statements whenever the relevant passage happened
not to surface -- retrieval returns what is relevant to the conversation, not
everything the agent knows. Checking against the biography's whole vocabulary
instead means the agent can talk freely about its real life and is stopped only
on specifics that appear nowhere the user ever wrote.

**Gaps.** When the gate does fire, the unsupported specifics are recorded rather
than discarded. Those terms are the map of what the biography is still missing,
ordered by how often they actually come up. Nothing reads them automatically
yet; they are the substrate for the agent eventually raising them itself.

Storage follows ``MentalLexicon``: dialect-neutral SQL with ``$n`` placeholders
and ``ON CONFLICT`` upserts, which run natively on Postgres and are translated
for SQLite by ``SQLiteConnection._translate_query``. Every operation is
best-effort -- a store that is unreachable degrades the gate to surfaced-memory
grounding, and must never break a turn.
"""

import asyncio
import logging
import re

logger = logging.getLogger("self_knowledge_store")

# Matches the tokenisation the grounding gate uses, so a term counted as
# "unsupported" there is looked up in exactly the form stored here.
_WORD_RE = re.compile(r"\b[a-z0-9']{3,}\b")

# The biography is prose about a person, so its vocabulary is dominated by
# ordinary English. That is harmless: extra grounding terms only ever make the
# gate *more* permissive, and the gate's real precision comes from requiring
# several unsupported specifics rather than from this set being tight.
_MAX_KNOWN_TERMS = 20000

# How many gap terms one failed response may record. A single fabricated
# sentence should not be able to flood the table.
_MAX_GAPS_PER_HIT = 8


class SelfKnowledgeStore:
    """Biography vocabulary cache plus a record of ungrounded self-claims."""

    def __init__(self, pool, seed_terms: set[str] | None = None):
        self.pool = pool
        # Terms true of the agent regardless of what the biography says -- its
        # own name, most obviously, which a biography written in the third
        # person ("she talks calmly…") never actually contains.
        self._seed_terms = {t.lower() for t in (seed_terms or set())}
        self._known_terms: set[str] = set(self._seed_terms)
        self._ready = False
        self._init_lock = asyncio.Lock()

    @property
    def known_terms(self) -> set[str]:
        """Biography vocabulary, for the grounding gate to read synchronously.

        Returns the live set rather than a copy: this is read once per gated
        response and copying twenty thousand strings on that path would cost
        more than the check it feeds.
        """
        return self._known_terms

    # ---- schema ------------------------------------------------------------

    async def _ensure_ready(self):
        """Idempotently create the table. Never raises."""
        if self._ready:
            return
        async with self._init_lock:
            if self._ready:
                return
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS self_knowledge_gaps ("
                        "term text PRIMARY KEY, "
                        "times_hit integer NOT NULL DEFAULT 1, "
                        "example_prompt text, "
                        "first_seen timestamp DEFAULT current_timestamp, "
                        "last_seen timestamp DEFAULT current_timestamp)"
                    )
                self._ready = True
            except Exception as e:
                logger.debug(f"SelfKnowledgeStore not ready ({e}); gaps not recorded")

    # ---- known terms -------------------------------------------------------

    async def refresh_known_terms(self) -> int:
        """Reload the biography vocabulary into the cache. Returns term count.

        Reads only ``source = 'biography'`` rows. Ordinary conversational
        memories are deliberately excluded: they are things the *user* said,
        and grounding the agent's autobiography in its own past chatter would
        let one hallucinated detail become the evidence for the next.
        """
        if self.pool is None:
            return len(self._known_terms)
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT content FROM memories WHERE source = $1", "biography"
                )
        except Exception as e:
            logger.debug(f"Could not refresh self-knowledge terms ({e})")
            return len(self._known_terms)

        terms = set(self._seed_terms)
        for row in rows or ():
            content = dict(row).get("content") or ""
            terms.update(_WORD_RE.findall(content.lower()))
            if len(terms) >= _MAX_KNOWN_TERMS:
                break

        self._known_terms = terms
        logger.info(
            "[SelfKnowledge] %d biography term(s) available for grounding.",
            len(terms),
        )
        return len(terms)

    # ---- gaps --------------------------------------------------------------

    async def record_gap(self, terms, example_prompt: str = "") -> int:
        """Record specifics the agent could not ground about itself.

        Returns the number of terms written. Best-effort throughout: a gap that
        fails to persist is a lost note, while an exception here would abort a
        turn that has already been correctly stopped from lying.
        """
        await self._ensure_ready()
        if not self._ready or not terms:
            return 0

        # Sorted so the cap is deterministic rather than set-iteration order --
        # a test asserting which terms survived should not depend on hashing.
        selected = sorted({str(t).lower() for t in terms if t})[:_MAX_GAPS_PER_HIT]
        snippet = (example_prompt or "")[:500]

        written = 0
        try:
            async with self.pool.acquire() as conn:
                for term in selected:
                    await conn.execute(
                        "INSERT INTO self_knowledge_gaps "
                        "(term, times_hit, example_prompt, first_seen, last_seen) "
                        "VALUES ($1, 1, $2, current_timestamp, current_timestamp) "
                        "ON CONFLICT (term) DO UPDATE SET "
                        "times_hit = self_knowledge_gaps.times_hit + 1, "
                        "last_seen = current_timestamp",
                        term,
                        snippet,
                    )
                    written += 1
        except Exception as e:
            logger.debug(f"Could not record self-knowledge gap ({e})")

        if written:
            logger.info(
                "[SelfKnowledge] Recorded %d ungrounded self-claim term(s): %s",
                written,
                ", ".join(selected[:5]),
            )
        return written

    async def top_gaps(self, limit: int = 20) -> list[dict]:
        """The most frequently hit gaps, for inspection and for later asking."""
        await self._ensure_ready()
        if not self._ready:
            return []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT term, times_hit, example_prompt, last_seen "
                    "FROM self_knowledge_gaps ORDER BY times_hit DESC LIMIT $1",
                    int(limit),
                )
            return [dict(r) for r in rows or ()]
        except Exception as e:
            logger.debug(f"Could not read self-knowledge gaps ({e})")
            return []
