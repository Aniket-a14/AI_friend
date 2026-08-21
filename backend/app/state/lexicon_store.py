"""MentalLexicon -- the humanoid's learned vocabulary.

Replaces the former static ``SYNONYM_MAP`` thesaurus. Instead of a frozen lookup
table, the system boots with a small generic innate seed (see ``lexicon_seed``)
and then *acquires* words and *learns which words relate* from its own lived
conversation, via distributional co-occurrence ("you shall know a word by the
company it keeps"). Associations are reinforced each time two words are
experienced together -- the same Hebbian / ACT-R spreading-activation principle
the rest of the memory system already runs on -- and persisted in the DB tier.

Recall-time cue expansion (in ``MemoryStore.search_memories``) then reads the
*learned* associations from an in-memory cache, exactly where it used to read
``SYNONYM_MAP``. An empty lexicon expands nothing and retrieval falls back to
literal cue matching -- an honest cold start, no worse than a person who has not
yet learned the word.

Design notes:
  * Storage mirrors ``memories``: a Postgres ``vocabulary`` / ``lexical_associations``
    pair (see ``db/schema.sql``) with a SQLite fallback (see ``sqlite_fallback.py``).
  * The SQL is dialect-neutral: ``$n`` placeholders, ``ON CONFLICT`` upserts and
    ``current_timestamp`` run natively on Postgres and are translated for SQLite
    by ``SQLiteConnection._translate_query``. All bound arguments are strings;
    association weights are SQL literals, so no numeric argument is ever coerced.
  * The per-word ``embedding`` column is intentionally left unpopulated this
    iteration; it is reserved for a future semantic-neighbor augmentation.
"""

import asyncio
import logging

from .lexicon_seed import INNATE_CLUSTERS, INNATE_WEIGHT

logger = logging.getLogger("mental_lexicon")

# Generic English function words dropped before learning/expansion. These are
# universal stop words, not corpus- or domain-specific terms.
_STOP_WORDS = {
    "the", "and", "but", "for", "nor", "yet", "with", "this", "that", "these",
    "those", "you", "your", "yours", "was", "were", "are", "has", "have", "had",
    "not", "which", "who", "what", "when", "where", "why", "how", "all", "any",
    "can", "will", "would", "could", "should", "then", "than", "there", "their",
    "them", "they", "from", "into", "onto", "our", "ours", "his", "her", "hers",
    "its", "about", "just", "also", "very", "some", "such", "here",
}


class MentalLexicon:
    """Learned vocabulary + co-occurrence association store."""

    def __init__(self, pool):
        self.pool = pool
        # term -> {associate_term: weight}. Populated from the DB by refresh()
        # and updated incrementally as learning happens.
        self._assoc_cache: dict[str, dict[str, float]] = {}
        self._ready = False
        self._init_lock = asyncio.Lock()

        self._expand_limit = 6          # associates returned per cue
        self._min_weight = 1.0          # a single co-occurrence already qualifies
        self._max_words_per_text = 12   # cap pair fan-out per learned memory
        self._cache_row_limit = 8000    # bound the in-memory association cache

    # ---- schema + seed -----------------------------------------------------

    async def _ensure_ready(self):
        """Idempotently create the tables and plant the innate seed once."""
        if self._ready:
            return
        async with self._init_lock:
            if self._ready:
                return
            try:
                await self._ensure_schema()
                await self._seed_innate()
                self._ready = True
            except Exception as e:  # never let lexicon setup break a memory op
                logger.debug("MentalLexicon not ready (%s); expansion disabled", e)

    async def _ensure_schema(self):
        """Portable safety-net DDL. Production uses db/schema.sql (Postgres) and
        sqlite_fallback.py (SQLite); these IF-NOT-EXISTS statements only matter
        when the lexicon runs against a bare pool (e.g. a focused unit test)."""
        statements = (
            ("CREATE TABLE IF NOT EXISTS vocabulary ("
            "term text PRIMARY KEY, surface_forms text DEFAULT '[]', "
            "embedding text, times_seen integer DEFAULT 1, "
            "source text DEFAULT 'acquired', "
            "first_seen timestamp DEFAULT current_timestamp, "
            "last_seen timestamp DEFAULT current_timestamp)"),
            ("CREATE TABLE IF NOT EXISTS lexical_associations ("
            "term_a text NOT NULL, term_b text NOT NULL, "
            "weight real DEFAULT 1.0, "
            "last_reinforced timestamp DEFAULT current_timestamp, "
            "PRIMARY KEY (term_a, term_b))"),
            "CREATE INDEX IF NOT EXISTS lexical_assoc_a_idx ON lexical_associations(term_a)",
            "CREATE INDEX IF NOT EXISTS lexical_assoc_b_idx ON lexical_associations(term_b)",
        )
        async with self.pool.acquire() as conn:
            for stmt in statements:
                await conn.execute(stmt)

    async def _seed_innate(self):
        """Plant the generic innate vocabulary + association clusters, but only
        on a fresh lexicon (empty vocabulary)."""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM vocabulary")
            try:
                already = int(count) > 0
            except (TypeError, ValueError):
                already = False  # mock/None -> treat as empty
            if already:
                return

            seen_terms = set()
            for cluster in INNATE_CLUSTERS:
                stems = []
                for word in cluster:
                    stem = self._stem(word)
                    if len(stem) < 3 or stem in _STOP_WORDS:
                        continue
                    if stem not in stems:
                        stems.append(stem)
                for stem in stems:
                    if stem not in seen_terms:
                        seen_terms.add(stem)
                        await conn.execute(
                            "INSERT INTO vocabulary (term, source) VALUES ($1, 'innate') "
                            "ON CONFLICT (term) DO NOTHING",
                            stem,
                        )
                for i in range(len(stems)):
                    for j in range(i + 1, len(stems)):
                        a, b = sorted((stems[i], stems[j]))
                        if a == b:
                            continue
                        await conn.execute(
                            "INSERT INTO lexical_associations (term_a, term_b, weight) "
                            f"VALUES ($1, $2, {INNATE_WEIGHT}) "
                            "ON CONFLICT (term_a, term_b) DO NOTHING",
                            a,
                            b,
                        )

    # ---- learning ----------------------------------------------------------

    async def learn_from_text(self, text: str):
        """Acquire the content words of a stored memory and reinforce the
        co-occurrence links between them. Fully guarded: a learning failure must
        never propagate into (and fail) the memory write that triggered it."""
        try:
            if not text:
                return
            await self._ensure_ready()
            words = self._tokenize(text)
            if not words:
                return
            async with self.pool.acquire() as conn:
                for term in words:
                    await conn.execute(
                        "INSERT INTO vocabulary (term, source) VALUES ($1, 'acquired') "
                        "ON CONFLICT (term) DO UPDATE SET "
                        "times_seen = times_seen + 1, last_seen = current_timestamp",
                        term,
                    )
                for i in range(len(words)):
                    for j in range(i + 1, len(words)):
                        a, b = sorted((words[i], words[j]))
                        if a == b:
                            continue
                        await conn.execute(
                            "INSERT INTO lexical_associations (term_a, term_b, weight) "
                            "VALUES ($1, $2, 1.0) ON CONFLICT (term_a, term_b) DO UPDATE SET "
                            "weight = weight + 1.0, last_reinforced = current_timestamp",
                            a,
                            b,
                        )
                        self._bump_cache(a, b, 1.0)
        except Exception as e:
            logger.debug("MentalLexicon.learn_from_text skipped: %s", e)

    # ---- expansion (recall hot path) --------------------------------------

    def expand(self, cue: str, limit: int | None = None) -> list[str]:
        """Return the strongest learned associates of a cue, for query-cue
        expansion. Synchronous cache read (no I/O); empty when nothing has been
        learned for the cue, so retrieval degrades to literal matching."""
        if not cue:
            return []
        limit = limit or self._expand_limit
        keys = {cue.lower(), self._stem(cue)}
        out: list[str] = []
        for key in keys:
            associates = self._assoc_cache.get(key)
            if not associates:
                continue
            for term, weight in sorted(
                associates.items(), key=lambda kv: kv[1], reverse=True
            ):
                if weight < self._min_weight or term in keys or term in out:
                    continue
                out.append(term)
                if len(out) >= limit:
                    return out
        return out

    # ---- cache refresh -----------------------------------------------------

    async def refresh(self):
        """Ensure the store is ready and (re)load the association cache from the
        DB. Called on the same periodic cadence as the dynamic stop words."""
        try:
            await self._ensure_ready()
            await self._load_cache()
        except Exception as e:
            logger.debug("MentalLexicon.refresh skipped: %s", e)

    async def _load_cache(self):
        cache: dict[str, dict[str, float]] = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT term_a, term_b, weight FROM lexical_associations "
                "ORDER BY weight DESC LIMIT $1",
                self._cache_row_limit,
            )
        for r in rows or []:
            a = r["term_a"]
            b = r["term_b"]
            try:
                w = float(r["weight"])
            except (TypeError, ValueError):
                continue
            cache.setdefault(a, {})[b] = w
            cache.setdefault(b, {})[a] = w
        self._assoc_cache = cache

    # ---- helpers -----------------------------------------------------------

    def _bump_cache(self, a: str, b: str, delta: float):
        a_assoc = self._assoc_cache.setdefault(a, {})
        a_assoc[b] = a_assoc.get(b, 0.0) + delta
        b_assoc = self._assoc_cache.setdefault(b, {})
        b_assoc[a] = b_assoc.get(a, 0.0) + delta

    @staticmethod
    def _stem(word: str) -> str:
        # Reuse MemoryStore's morphological stemmer so learned terms and query
        # cues normalize identically. Lazy import avoids an import cycle.
        from .memory_store import _get_stem

        return _get_stem(word.lower())

    def _tokenize(self, text: str) -> list[str]:
        import re

        distinct: list[str] = []
        for raw in re.findall(r"\b\w{3,}\b", text.lower()):
            if raw in _STOP_WORDS:
                continue
            stem = self._stem(raw)
            if len(stem) < 3 or stem in _STOP_WORDS:
                continue
            if stem not in distinct:
                distinct.append(stem)
            if len(distinct) >= self._max_words_per_text:
                break
        return distinct
