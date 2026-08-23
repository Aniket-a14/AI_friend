"""
Memory Store — ACT-R Based Retrieval (psychological_layer.md §6).

Retrieval scoring adapted from Anderson & Lebiere (1998):
    Aᵢ = Bᵢ + Σⱼ Wⱼ·Sⱼᵢ + ε

With extensions for emotional alignment (Bower, 1981):
    Score = Aᵢ + w_emotion · EmotionalAlignment

Base-level activation (simplified):
    Bᵢ ≈ ln(recall_count) - d · ln(hours_since_last_recall + 1)
"""

import asyncio
import functools
import json
import logging
import math
import re
import sqlite3
import time
import uuid
from collections import Counter, OrderedDict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import orjson

from ..config import Config
from ..utils.background_tasks import spawn_background

logger = logging.getLogger(__name__)

@functools.lru_cache(maxsize=4096)
def _cached_ln(x: float) -> float:
    """Natural log, memoized on the value rounded to 3 decimal places.

    Was a bare module-level dict that was never evicted (A6). Rounding bounds
    the key space in practice, but "in practice" is doing real work there: the
    keys are memory ages, so a long-lived process with a wide spread of
    timestamps keeps adding entries for the life of the process, and nothing
    ever removes one.

    `lru_cache` gives the same hit rate for this access pattern with an actual
    ceiling. The rounding happens in the caller so the cache key is the rounded
    value rather than the raw float -- memoizing on the raw float would make
    almost every lookup a miss and the cache pure overhead.
    """
    return math.log(x)


def _ln(x: float) -> float:
    return _cached_ln(round(x, 3))


def _get_stem(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        w = w[:-1]
    if w.endswith("ed") and len(w) > 4:
        if w.endswith("ated"):
            w = w[:-3] + "e"  # calibrated -> calibrate
        else:
            w = w[:-2]
    if w.endswith("ing") and len(w) > 5:
        if w.endswith("ating"):
            w = w[:-5] + "e"  # activating -> activate
        else:
            w = w[:-3]
    return w


# Query-cue synonym expansion is no longer a hardcoded thesaurus. It now reads
# the humanoid's *learned* vocabulary (MentalLexicon, see lexicon_store.py):
# words that co-occur in lived conversation become associated, and recall-time
# expansion draws on what the system has actually learned. See _get_stem below
# for the (generic, morphological) stemming that still normalizes cues.

# Retrieval scoring constants. These were previously inline "magic numbers"
# (one reverse-engineered to make a benchmark metric land on exactly 0.6).
# Named and documented here so the scoring is honest and tunable.
# Additive score bump per literal query cue found in a memory (see
# _apply_direct_cue_boost). Deliberately large relative to the ACT-R
# base/spread-activation terms it's added to -- those typically run roughly
# -3..+3 for a given candidate (see _base_activation / _effective_similarity
# below) -- so that a single literal keyword match can outrank a merely
# similar ACT-R candidate. Unlike PPR_DAMPING just below, which has a
# textbook justification, the 5.0 magnitude itself is a design choice, not
# derived from measurement against real recall data. Flagging it as such
# rather than presenting it as tuned.
DIRECT_CUE_BOOST = 5.0
PPR_DAMPING = 0.85  # canonical PageRank teleport/damping factor

# ACT-R retrieval-scoring weights. These were duplicated inline across three
# scoring paths (Qdrant/SQLite/PG); naming them here keeps the paths in sync and
# makes the affective tuning explicit. base_activation adds an importance term
# and an emotional-proximity bonus to the classic ln(freq) - d·ln(recency) core;
# the similarity gain rewards congruent valence×arousal and suppresses recall
# under stress (arousal×cortisol); the final score subtracts an emotional-
# distance penalty.
ACTR_IMPORTANCE_WEIGHT = 1.5  # weight on importance_score in base activation
ACTR_EMO_PROXIMITY_WEIGHT = 0.15  # bonus for small emotional distance
ACTR_VALENCE_GAIN = 0.1  # similarity gain from congruent valence×arousal
ACTR_STRESS_SUPPRESSION = 0.2  # similarity suppression under arousal×cortisol
ACTR_EMO_DISTANCE_PENALTY = 0.5  # score penalty per unit emotional distance

# Generic English stop words plus a few domain-generic conversational terms,
# stripped from a query before it is used for lexical cue matching. Hoisted to
# module scope: this is a constant, and rebuilding the literal on every
# search_memories call was pure waste. Membership is unchanged (the original
# literal contained duplicates, which a set collapses either way).
SEARCH_STOP_WORDS = frozenset(
    {
        "the", "and", "but", "yet", "for", "nor", "with", "this", "that",
        "these", "those", "you", "your", "yours", "him", "her", "them", "his",
        "hers", "their", "theirs", "was", "were", "been", "have", "has", "had",
        "did", "does", "what", "where", "when", "who", "why", "how", "can",
        "could", "would", "should", "shall", "will", "about", "above", "after",
        "again", "against", "all", "am", "an", "any", "are", "arent", "as",
        "at", "be", "because", "before", "being", "below", "between", "both",
        "by", "cant", "cannot", "didnt", "dont", "down", "during", "each",
        "few", "from", "further", "hadnt", "hasnt", "havent", "having", "he",
        "hed", "hell", "hes", "here", "heres", "herself", "himself", "i", "id",
        "ill", "im", "ive", "if", "in", "into", "isnt", "it", "its", "itself",
        "lets", "me", "more", "most", "mustnt", "my", "myself", "no", "not",
        "of", "off", "on", "once", "only", "or", "other", "ought", "our",
        "ours", "ourselves", "out", "over", "own", "same", "shant", "she",
        "shed", "shell", "shes", "shouldnt", "so", "some", "such", "than",
        "thats", "themselves", "then", "there", "theres", "they", "theyd",
        "theyll", "theyre", "theyve", "through", "to", "too", "under",
        "until", "up", "very", "wasnt", "we", "wed", "well", "weve", "werent",
        "whats", "whens", "wheres", "which", "while", "whos", "whom", "whys",
        "wont", "wouldnt", "youd", "youll", "youre", "youve", "yourself",
        "yourselves", "describe", "compare", "influence", "influenced",
        "friend", "companion", "robot", "human", "development", "developer",
        "developers", "project", "workspace", "shared", "recall", "recalled",
        "experience", "experiences", "related",
    }
)

# Pronoun sets used for speaker/listener cue resolution.
FIRST_PERSON_PRONOUNS = frozenset({"i", "me", "my", "myself", "we", "our", "us"})
SECOND_PERSON_PRONOUNS = frozenset(
    {"you", "your", "yours", "yourself", "yourselves"}
)

# Postgres retrieval fast path. Two variants of the same query: the current
# schema also carries the Eriksonian lifespan columns on `memories`, while a
# not-yet-migrated database has only the base columns. Both take the identical
# 12-argument tuple; see _fetch_surface_actr_rows.
_SURFACE_ACTR_SELECT_HEAD = """
    SELECT
        m.id AS id,
        s.content,
        s.raw_content,
        s.wing,
        s.room,
        s.importance_score,
        s.emotional_weight,
        s.valence,
        s.recall_count,
        s.last_recalled_at,
        s.created_at,
        s.metadata,
        s.similarity,
        s.score"""

_SURFACE_ACTR_FROM_JOIN = """
    FROM surface_actr_memories($1::vector(768), $2::text, $3::text, $4::double precision, $5::double precision, $6::double precision, $7::double precision, $8::double precision, $9::double precision, $10::double precision, $11::integer, $12::timestamptz) s
    LEFT JOIN memories m ON m.content = s.content AND m.wing = s.wing
"""

_SURFACE_ACTR_SQL_ERIKSONIAN = (
    _SURFACE_ACTR_SELECT_HEAD
    + """,
        m.lifespan_stage,
        m.crisis,
        m.virtue,
        m.relations,
        m.relation_circles,
        m.modality"""
    + _SURFACE_ACTR_FROM_JOIN
)

_SURFACE_ACTR_SQL_LEGACY = _SURFACE_ACTR_SELECT_HEAD + _SURFACE_ACTR_FROM_JOIN

# Archive -> active promotion. Same columns in both dialects; only the
# placeholder style and the EXCLUDED casing differ.
_PROMOTE_INSERT_COLUMNS = """INSERT INTO memories (
        id, content, raw_content, wing, room, embedding, importance_score, emotional_weight,
        valence, certainty, source, recall_count, last_recalled_at, created_at,
        metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality
    ) VALUES """

_PROMOTE_INSERT_SQLITE = (
    _PROMOTE_INSERT_COLUMNS
    + """(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        recall_count = excluded.recall_count,
        last_recalled_at = excluded.last_recalled_at,
        importance_score = excluded.importance_score
"""
)

_PROMOTE_INSERT_PG = (
    _PROMOTE_INSERT_COLUMNS
    + """($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
    ON CONFLICT(id) DO UPDATE SET
        recall_count = EXCLUDED.recall_count,
        last_recalled_at = EXCLUDED.last_recalled_at,
        importance_score = EXCLUDED.importance_score
"""
)


class GoalBuffer:
    def __init__(self, capacity=5):
        self.concepts = []  # List of tuples: (concept_word, turn_added)
        self.capacity = capacity
        self.current_turn = 0

    def update_buffer(self, query_text, dynamic_stop_words):
        self.current_turn += 1

        # Extract clean keywords
        new_words = re.findall(r"\b\w{3,}\b", query_text.lower())
        filtered_words = [w for w in new_words if w not in dynamic_stop_words]

        # Add to buffer if not already present
        for w in filtered_words:
            # Update turn to keep it fresh
            self.concepts = [c for c in self.concepts if c[0] != w]
            self.concepts.append((w, self.current_turn))

        # Retain concepts active for a 3-turn window
        self.concepts = [c for c in self.concepts if self.current_turn - c[1] <= 3]

        # Cap to capacity
        if len(self.concepts) > self.capacity:
            self.concepts = self.concepts[-self.capacity :]

    def flush(self):
        self.concepts = []


class MemoryStore:
    def __init__(self, pool, graph_db, ollama_base_url=None):
        self.pool = pool
        self.graph_db = graph_db
        self.ollama_base_url = (
            ollama_base_url or getattr(Config, "OLLAMA_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.embedding_model = "nomic-embed-text"
        self._http_client = httpx.AsyncClient(timeout=30.0)
        # P4-8: strong-reference holder for the background refresh task below.
        self._background_tasks: set[asyncio.Task] = set()

        # ACT-R Parameters (§6.2)
        self.decay_rate = Config.ACTR_DECAY_RATE  # d
        self.spread_weight = Config.ACTR_SPREAD_WEIGHT  # Wⱼ
        self.emotion_weight = Config.ACTR_EMOTION_WEIGHT  # w_emotion

        # 3-State activation thresholds (Eriksonian Cognitive Alignment)
        self.recall_threshold = -1.5  # theta_recall
        self.subconscious_threshold = -2.5  # theta_sub
        self.pruning_threshold = -3.5  # theta_prune

        # L1 Memory Activation Cache. Bounded LRU: keys are full query
        # signatures (query text + affect + limits), so the working set is
        # unbounded across a long session and an unevicted dict would leak.
        # OrderedDict + a max size caps residency; oldest entries fall out first.
        self._l1_cache = OrderedDict()  # key -> (timestamp, results)
        self._l1_cache_ttl = 15.0  # seconds
        self._l1_cache_max = 256  # entries; evict least-recently-used past this

        self._db_stop_words = set()
        self._last_stop_words_update = 0.0

        from .lexicon_store import MentalLexicon
        from .semantic_recall_store import SemanticRecallStore

        self.qdrant_store = SemanticRecallStore()
        # Learned vocabulary: replaces the old static SYNONYM_MAP. Boots with a
        # generic innate seed, then acquires words + associations from experience.
        self.lexicon = MentalLexicon(self.pool)
        self.goal_buffer = GoalBuffer(capacity=5)
        self._last_query_vector = None
        import sys

        if "pytest" in sys.modules:
            self.qdrant_store.client = None

    @property
    def is_sqlite(self) -> bool:
        """Whether the backing pool is actually a stdlib sqlite3 connection under
        the hood (SQLitePool, or a test double shaped like it), rather than real
        asyncpg/Postgres.

        A5: previously sniffed type(self.pool).__name__ against a hardcoded set
        of class names ("MockPGPool", excluding "MagicMock"/"AsyncMock"/"Mock").
        Any pool class not on that exact list - a rename, a subclass, a new test
        double - silently misclassified and routed to the wrong SQL dialect.
        Checking what pool.connection.conn actually *is* (a real sqlite3.Connection,
        the one thing both the production SQLitePool and its test doubles genuinely
        share) is a structural fact instead of a name-matching guess.
        """
        conn = getattr(self.pool, "connection", None)
        return isinstance(getattr(conn, "conn", None), sqlite3.Connection)

    def _in_predicate(
        self, column: str, values: Sequence[Any], param_index: int = 1
    ) -> tuple[str, list[Any]]:
        """Build a `column IN (...)` predicate and its arguments for this backend.

        The two dialects express set membership differently and neither is
        wrong: SQLite wants one placeholder per value, Postgres takes the whole
        list as a single array parameter via `= ANY($n)`. Spelling that out at
        each call site produced the same eight-line if/else repeatedly, where
        the only real content was a column name.

        Returns the clause and the argument list to splat, so callers keep each
        backend's idiom rather than being forced onto a lowest common
        denominator -- flattening Postgres to N placeholders would work but
        would throw away the array form the query planner handles better.

        Deliberately *not* applied to every dual-backend branch in this file.
        Most of them differ for real reasons -- boolean literals (`0`/`1` vs
        `FALSE`/`TRUE`), date arithmetic (`datetime('now', '-24 hours')` vs
        `NOW() - INTERVAL`), `datetime()` normalisation that SQLite needs
        because it stores timestamps as text, and `executemany` which the
        SQLite fallback does not provide. Those are genuine differences between
        the backends, not duplication, and collapsing them would invent a
        sameness that is not there.
        """
        if self.is_sqlite:
            return f"{column} IN ({','.join('?' * len(values))})", list(values)
        return f"{column} = ANY(${param_index})", [list(values)]

    @staticmethod
    def _is_missing_column_error(exc: BaseException) -> bool:
        """True only when a write failed because a column does not exist.

        Distinguishes an un-migrated schema (worth retrying without the
        Eriksonian columns) from constraint violations, serialization
        conflicts, and transient outages (which must propagate). Postgres
        reports SQLSTATE 42703; SQLite only says so in the message text.
        """
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "42703":  # undefined_column
            return True
        if type(exc).__name__ == "UndefinedColumnError":
            return True
        message = str(exc).lower()
        if isinstance(exc, sqlite3.OperationalError):
            return "no column named" in message or "has no column" in message
        return False

    @staticmethod
    def _as_aware_utc(dt):
        """Coerce a datetime to timezone-aware UTC so recency arithmetic never
        mixes naive and aware operands (which raises TypeError).

        Timestamps reach these code paths from two sources: naive values
        (SQLite CURRENT_TIMESTAMP, strptime of stored strings) and aware values
        (Postgres timestamptz, datetime.now(timezone.utc), a caller-supplied
        current_time). Naive inputs are assumed to already be UTC -- which is how
        the stored timestamps are written -- and aware inputs are converted.
        None passes through so callers can apply their own fallback.

        SQLite hands back TEXT for timestamp columns, so archived rows can carry
        an ISO string where the active path carries a datetime. Those are parsed
        here rather than at each call site; anything unparseable degrades to None
        so callers fall back instead of raising mid-retrieval.
        """
        if dt is None:
            return None
        if isinstance(dt, str):
            raw = dt.strip()
            if not raw:
                return None
            # SQLite CURRENT_TIMESTAMP writes "YYYY-MM-DD HH:MM:SS"; fromisoformat
            # handles that plus the "T"-separated and offset-bearing variants.
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                logger.debug("Unparseable stored timestamp %r; treating as missing.", dt)
                return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _l1_cache_put(self, cache_key, value):
        """Insert into the L1 cache with LRU eviction.

        The newest entry is moved to the end; once the cache exceeds
        ``_l1_cache_max`` the least-recently-used entry (front) is dropped.
        """
        self._l1_cache[cache_key] = value
        self._l1_cache.move_to_end(cache_key)
        while len(self._l1_cache) > self._l1_cache_max:
            self._l1_cache.popitem(last=False)

    def _invalidate_l1_cache(self):
        """Drop every cached result set.

        Cache keys are query signatures, not memory ids, so a write to any
        single memory can change the correct result of an unknown set of
        queries. A full clear is the only coherent invalidation; it is called
        only on mutations rare relative to reads (writes, pruning), never on the
        per-recall reinforcement path.
        """
        self._l1_cache.clear()

    async def _find_existing_memory(self, conn, content, wing):
        """Return the id of a memory with identical content+wing, else None.

        Backs reinforce-on-repeat dedup. The ``isinstance(rows, list)`` guard is
        load-bearing: on the PG unit-test path ``conn`` is an AsyncMock whose
        ``fetch`` returns a truthy MagicMock, which would otherwise read as a
        hit and make every add masquerade as a duplicate.

        Dedup is an optimization, not a correctness requirement: if the lookup
        errors, return None so the caller falls through to a normal insert
        rather than dropping the write.
        """
        try:
            if self.is_sqlite:
                rows = await conn.fetch(
                    "SELECT id FROM memories WHERE content = ? AND wing = ? LIMIT 1",
                    content,
                    wing,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id FROM memories WHERE content = $1 AND wing = $2 LIMIT 1",
                    content,
                    wing,
                )
        except Exception as e:
            logger.debug("Dedup lookup failed, proceeding to insert: %s", e)
            return None
        if isinstance(rows, list) and rows:
            return rows[0]["id"]
        return None

    async def _reinforce_memory(self, conn, memory_id, importance, current_time):
        """Strengthen an existing memory when the same statement recurs.

        Repetition consolidates a trace, it never weakens one: bump
        ``recall_count`` (ACT-R frequency), refresh recency, and raise
        ``importance_score`` to the max of old/new so a later low-importance
        restatement cannot demote an already-salient memory.
        """
        if self.is_sqlite:
            # CAST the bound importance to REAL: SQLite would otherwise compare a
            # numeric column against a text-affinity param and MAX() would return
            # the text operand, silently demoting a salient memory.
            if current_time is not None:
                await conn.execute(
                    "UPDATE memories SET recall_count = recall_count + 1, "
                    "last_recalled_at = ?, "
                    "importance_score = MAX(importance_score, CAST(? AS REAL)) WHERE id = ?",
                    current_time,
                    importance,
                    memory_id,
                )
            else:
                await conn.execute(
                    "UPDATE memories SET recall_count = recall_count + 1, "
                    "last_recalled_at = CURRENT_TIMESTAMP, "
                    "importance_score = MAX(importance_score, CAST(? AS REAL)) WHERE id = ?",
                    importance,
                    memory_id,
                )
        else:
            if current_time is not None:
                await conn.execute(
                    "UPDATE memories SET recall_count = recall_count + 1, "
                    "last_recalled_at = $1, "
                    "importance_score = GREATEST(importance_score, $2) WHERE id = $3",
                    current_time,
                    importance,
                    memory_id,
                )
            else:
                await conn.execute(
                    "UPDATE memories SET recall_count = recall_count + 1, "
                    "last_recalled_at = NOW(), "
                    "importance_score = GREATEST(importance_score, $1) WHERE id = $2",
                    importance,
                    memory_id,
                )

    def _base_activation(self, recall_count, hours_since, importance_score, dist_emo):
        """ACT-R base-level activation: ln(freq) - d·ln(recency) plus importance
        and emotional-proximity terms. Shared by every retrieval-scoring path so
        the formula stays identical across the Qdrant, SQLite and PG branches.
        """
        return (
            _ln(recall_count)
            - self.decay_rate * _ln(hours_since + 1.0)
            + ACTR_IMPORTANCE_WEIGHT * importance_score
            + ACTR_EMO_PROXIMITY_WEIGHT * (1.0 - dist_emo)
        )

    def _effective_similarity(
        self, similarity, memory_valence, emotion_weight, current_arousal, current_cortisol
    ):
        """Neuromodulatory gain on cosine similarity: boosted by congruent
        valence×arousal, suppressed under stress (arousal×cortisol).
        """
        return similarity * (
            1.0
            + ACTR_VALENCE_GAIN * memory_valence * emotion_weight
            - ACTR_STRESS_SUPPRESSION * current_arousal * current_cortisol
        )

    @staticmethod
    def _personalized_pagerank(entity_names, adj, seeds, damping, iterations):
        """HippoRAG-inspired Personalized PageRank over the entity graph.

        The numeric power-method loop is delegated to the ``cognitive_rust``
        extension (the same crate that already owns the ACT-R scoring hot loop),
        with an exact pure-Python fallback if the extension is unavailable. Both
        paths preserve the legacy semantics precisely:

          * ``degrees`` holds each node's ORIGINAL neighbor count. A neighbor
            whose name is absent from ``entity_names`` has no resolvable index
            and is dropped from the push, but the mass is still divided by the
            full degree -- so that share leaks out of the graph, unchanged.
          * A degree-0 node is dangling and redistributes uniformly across the
            seeds rather than the whole graph.

        ``seeds`` is a set of node indices; returns the rank vector (list) of
        length ``len(entity_names)``.
        """
        n = len(entity_names)
        if not seeds or n == 0:
            return [0.0] * n

        node_to_idx = {name: idx for idx, name in enumerate(entity_names)}
        seed_list = sorted(seeds)

        # Resolve name-based adjacency to index lists once; keep the original
        # degree so the divisor (and the leaked mass) matches the legacy loop.
        adjacency_idx = []
        degrees = []
        for name in entity_names:
            neighbors = adj.get(name, ())
            degrees.append(len(neighbors))
            adjacency_idx.append([node_to_idx[nb] for nb in neighbors if nb in node_to_idx])

        try:
            import cognitive_rust

            return list(
                cognitive_rust.personalized_pagerank(
                    adjacency_idx, degrees, seed_list, damping, iterations
                )
            )
        except Exception:
            # Pure-Python fallback with identical arithmetic and ordering.
            p_0 = [0.0] * n
            seed_share = 1.0 / len(seed_list)
            for s_idx in seed_list:
                p_0[s_idx] = seed_share
            p = list(p_0)
            for _ in range(iterations):
                p_next = [0.0] * n
                for i in range(n):
                    degree = degrees[i]
                    if degree:
                        val = p[i] / degree
                        for n_idx in adjacency_idx[i]:
                            p_next[n_idx] += val
                    else:
                        dangling_share = p[i] / len(seed_list)
                        for s_idx in seed_list:
                            p_next[s_idx] += dangling_share
                for i in range(n):
                    p_next[i] = damping * p_next[i] + (1.0 - damping) * p_0[i]
                p = p_next
            return p

    # Columns always written; the Eriksonian columns below may be absent on an
    # un-migrated schema, so a failed full insert falls back to just these.
    _MEMORY_BASE_COLUMNS = (
        "id",
        "content",
        "raw_content",
        "wing",
        "room",
        "embedding",
        "importance_score",
        "emotional_weight",
        "valence",
        "certainty",
        "source",
        "metadata",
    )
    _MEMORY_ERIKSONIAN_COLUMNS = (
        "lifespan_stage",
        "crisis",
        "virtue",
        "relations",
        "relation_circles",
        "modality",
    )

    async def _insert_memory_row(
        self,
        conn,
        *,
        memory_id,
        content,
        raw_val,
        wing,
        room,
        vector_str,
        importance,
        emotion,
        valence,
        certainty,
        source,
        metadata_json,
        lifespan_stage,
        crisis,
        virtue,
        relations,
        relation_circles,
        modality,
        current_time,
    ):
        """Insert a memory row from a single column/placeholder builder.

        Collapses what were eight near-identical INSERTs spanning three binary
        axes -- SQLite vs PostgreSQL placeholders, timed vs untimed
        (created_at/last_recalled_at), and the full Eriksonian column set vs a
        legacy fallback for un-migrated schemas. recall_count is always the
        literal 1; an untimed insert lets last_recalled_at default via
        CURRENT_TIMESTAMP.
        """
        base_vals = [
            memory_id,
            content,
            raw_val,
            wing,
            room,
            vector_str,
            importance,
            emotion,
            valence,
            certainty,
            source,
            metadata_json,
        ]
        erik_vals = [lifespan_stage, crisis, virtue, relations, relation_circles, modality]

        async def _insert(include_eriksonian: bool):
            cols = list(self._MEMORY_BASE_COLUMNS)
            vals = list(base_vals)
            if include_eriksonian:
                cols += list(self._MEMORY_ERIKSONIAN_COLUMNS)
                vals += erik_vals

            if self.is_sqlite:
                placeholders = ["?"] * len(vals)
            else:
                placeholders = [f"${i}" for i in range(1, len(vals) + 1)]

            # recall_count is a literal, never a bound parameter.
            cols.append("recall_count")
            placeholders.append("1")

            params = list(vals)
            if current_time is not None:
                cols += ["last_recalled_at", "created_at"]
                if self.is_sqlite:
                    placeholders += ["?", "?"]
                else:
                    placeholders += [f"${len(vals) + 1}", f"${len(vals) + 2}"]
                params += [current_time, current_time]
            else:
                cols.append("last_recalled_at")
                placeholders.append("CURRENT_TIMESTAMP")

            sql = (
                f"INSERT INTO memories ({', '.join(cols)}) "
                f"VALUES ({', '.join(placeholders)})"
            )
            await conn.execute(sql, *params)

        try:
            await _insert(include_eriksonian=True)
        except Exception as e:
            # Only an un-migrated schema justifies dropping the Eriksonian
            # columns. Retrying on *any* failure meant a constraint violation,
            # a serialization conflict, or a transient outage would silently
            # re-insert the row with its developmental metadata stripped.
            if not self._is_missing_column_error(e):
                raise
            logger.warning(
                f"Eriksonian insert failed, falling back to legacy schema: {e}"
            )
            await _insert(include_eriksonian=False)

    async def get_embedding(self, text: str):
        """Generates vector embedding for text using local Ollama."""
        attempts = [
            ("/api/embed", {"model": self.embedding_model, "input": text}),
            ("/api/embeddings", {"model": self.embedding_model, "prompt": text}),
        ]

        last_error = None
        try:
            client = self._http_client
            for endpoint, payload in attempts:
                response = await client.post(
                    f"{self.ollama_base_url}{endpoint}",
                    json=payload,
                )
                if response.status_code == 404:
                    continue

                response.raise_for_status()
                result = response.json()

                embedding = result.get("embedding")
                if embedding:
                    return embedding

                embeddings = result.get("embeddings")
                if isinstance(embeddings, list) and embeddings:
                    return embeddings[0]

                last_error = f"No embedding payload returned by {endpoint}"

            if last_error is None:
                last_error = "All embedding endpoints returned 404"
            raise RuntimeError(last_error)
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            if getattr(Config, "MOCK_LLM_TEXT", False):
                import numpy as np

                vec = np.random.randn(768)
                norm = np.linalg.norm(vec)
                if norm < 1e-6:
                    vec = np.zeros(768)
                    vec[0] = 1.0
                    return vec.tolist()
                return (vec / norm).tolist()
            return None

    async def add_memory(
        self,
        content,
        raw_content=None,
        wing="personal",
        room=None,
        importance=0.5,
        emotion=0.0,
        valence=0.0,
        certainty=1.0,
        source="user",
        metadata=None,
        lifespan_stage=None,
        crisis=None,
        virtue=None,
        relations=None,
        relation_circles=None,
        modality=None,
        current_time=None,
    ):
        """Adds a new memory with ACT-R metadata and hierarchical scope."""
        try:
            import uuid

            # Generate a single UUID for both stores to ensure correlation
            memory_id = str(uuid.uuid4())
            raw_val = raw_content or content

            # Reinforce-on-repeat: an identical statement in the same wing should
            # strengthen the existing trace, not mint a duplicate. Human memory
            # consolidates repetition; duplicating it would inflate retrieval
            # with near-identical rows and distort ACT-R frequency counts. Check
            # before the expensive embedding + graph pre-linking work, and skip
            # both when it is a repeat.
            async with self.pool.acquire() as conn:
                existing_id = await self._find_existing_memory(conn, content, wing)
                if existing_id is not None:
                    await self._reinforce_memory(
                        conn, existing_id, importance, current_time
                    )
                    self._invalidate_l1_cache()
                    # Repetition strengthens word associations too (guarded).
                    await self.lexicon.learn_from_text(content)
                    logger.info(
                        f"🧠 Memory Reinforced [{wing}:{room or 'global'}]: {content[:50]}..."
                    )
                    return True

            # Pre-link entities from graph to metadata
            present_entities = []
            if self.graph_db:
                try:
                    entity_records = await self.graph_db.execute_query(
                        "MATCH (e:Entity) RETURN e.name AS name", use_cache=True
                    )
                    entity_names = [r["name"] for r in entity_records]
                    content_lower = content.lower()
                    for name in entity_names:
                        name_lower = name.lower()
                        pattern = rf"\b{re.escape(name_lower)}\b"
                        if re.search(pattern, content_lower):
                            present_entities.append(name)
                except Exception as ge:
                    logger.debug(
                        f"Failed to fetch entities for pre-linking in add_memory: {ge}"
                    )

            if metadata is None:
                metadata = {}
            metadata["entities"] = present_entities

            vector = await self.get_embedding(content)
            if not vector:
                return False

            vector_str = str(vector)
            async with self.pool.acquire() as conn:
                await self._insert_memory_row(
                    conn,
                    memory_id=memory_id,
                    content=content,
                    raw_val=raw_val,
                    wing=wing,
                    room=room,
                    vector_str=vector_str,
                    importance=importance,
                    emotion=emotion,
                    valence=valence,
                    certainty=certainty,
                    source=source,
                    metadata_json=orjson.dumps(metadata or {}).decode(),
                    lifespan_stage=lifespan_stage,
                    crisis=crisis,
                    virtue=virtue,
                    relations=relations,
                    relation_circles=relation_circles,
                    modality=modality,
                    current_time=current_time,
                )
            # Upsert into Qdrant if online using the same memory_id
            if self.qdrant_store.client:
                qdrant_ts = (
                    str(current_time.timestamp())
                    if current_time is not None
                    else str(time.time())
                )
                metadata_qdrant = {
                    "wing": wing,
                    "room": room or "",
                    "importance_score": importance,
                    "emotional_weight": emotion,
                    "valence": valence,
                    "certainty": certainty,
                    "source": source,
                    "recall_count": 1,
                    "last_recalled_at": qdrant_ts,
                    "created_at": qdrant_ts,
                    "lifespan_stage": lifespan_stage or "",
                    "crisis": crisis or "",
                    "virtue": virtue or "",
                    "relations": relations or "",
                    "relation_circles": relation_circles or "",
                    "modality": modality or "",
                    "entities": present_entities,
                }
                if metadata:
                    metadata_qdrant["custom_metadata"] = orjson.dumps(metadata).decode()

                self.qdrant_store.add_vector_memory(
                    memory_id=memory_id,
                    vector=vector,
                    content=content,
                    metadata=metadata_qdrant,
                )

            logger.info(
                f"🧠 Memory Stored [{wing}:{room or 'global'}]: {content[:50]}..."
            )
            # A new memory can satisfy queries whose cached result sets predate
            # it, so drop the L1 cache to avoid serving stale recalls.
            self._invalidate_l1_cache()
            # Acquire vocabulary + co-occurrence associations from the stored
            # content (guarded internally so it can never fail the write).
            await self.lexicon.learn_from_text(content)
            return True
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

    async def _update_dynamic_stop_words(self):
        """Fetches high-frequency words from active memories to use as stop words."""
        try:
            async with self.pool.acquire() as conn:
                if self.is_sqlite:
                    # SQLite fallback: since SQLite doesn't have regexp_split_to_table,
                    # we can just fetch content and count in Python
                    rows = await conn.fetch("SELECT content FROM memories LIMIT 500")
                    words = []
                    for r in rows:
                        words.extend(re.findall(r"\b\w{3,}\b", r["content"].lower()))
                    counter = Counter(words)
                    # Any word appearing in more than 15% of records
                    cutoff = max(5, int(len(rows) * 0.15))
                    self._db_stop_words = {
                        w for w, count in counter.items() if count > cutoff
                    }
                else:
                    # Postgres pgvector: fetch words appearing in > 10% of memories
                    total = await conn.fetchval("SELECT count(*) FROM memories")
                    if total and total > 50:
                        cutoff = max(20, int(total * 0.10))
                        rows = await conn.fetch(
                            """
                            SELECT word, count(*) as cnt
                            FROM (
                                SELECT regexp_replace(regexp_split_to_table(lower(content), '\\s+'), '[^\\w]', '', 'g') AS word
                                FROM memories
                            ) AS words
                            WHERE length(word) >= 3
                            GROUP BY word
                            HAVING count(*) > $1
                            ORDER BY cnt DESC
                            LIMIT 50
                            """,
                            cutoff,
                        )
                        self._db_stop_words = {r["word"] for r in rows}
                    else:
                        self._db_stop_words = set()
        except Exception as e:
            logger.debug("Failed to load dynamic stop words: %s", e)
            self._db_stop_words = set()

    # ------------------------------------------------------------------
    # search_memories stages (F1)
    #
    # search_memories was a ~1600-line god-function fusing L1 caching, Qdrant
    # retrieval, two SQL dialects, cue extraction, graph building, pronoun
    # resolution, PageRank spreading activation, archive promotion and result
    # formatting into one body. The stages below are that same pipeline, split
    # at its natural seams so each piece can be read and tested on its own.
    # Behavior is intentionally unchanged - the scoring math, ordering and
    # error-swallowing semantics are preserved exactly.
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_mrl_gating(
        current_arousal: float,
        current_cortisol: float,
        limit,
        full_pool: bool,
    ) -> tuple[int, int]:
        """Dynamic Matryoshka (MRL) dimension gating.

        Higher stress/arousal restricts the search to a smaller Matryoshka
        prefix and a smaller candidate pool, bounding retrieval latency when
        the agent is under load.

        `full_pool` picks between the two unstressed tiers: the full pool a
        conversation turn gets (`limit*6`, floor 120) and the cheaper one a
        latency-sensitive caller gets (`limit*3`, floor 20). It is named for
        what it selects. `search_memories` has historically passed
        `refresh_on_recall` here because its two latency-sensitive callers --
        the `action.py` fallback and `surfacing_agent` -- also happen not to
        want recall counters bumped, but those are separate properties and a
        caller that needs one without the other says so explicitly.
        """
        stress_index = max(current_arousal, current_cortisol)
        if stress_index > 0.8:
            return 256, max(10, limit * 2 if limit is not None else 10)
        if stress_index > 0.6:
            return 512, max(30, limit * 3 if limit is not None else 30)
        if full_pool:
            return 768, max(120, limit * 6 if limit is not None else 120)
        return 768, max(20, limit * 3 if limit is not None else 20)

    def _detect_topic_shift(self, query_vector: list) -> None:
        """Flush the goal buffer when the query diverges sharply from the last one."""
        if self._last_query_vector is not None:
            try:
                dot = sum(a * b for a, b in zip(query_vector, self._last_query_vector))
                norm1 = math.sqrt(sum(a * a for a in query_vector))
                norm2 = math.sqrt(sum(b * b for b in self._last_query_vector))
                sim = dot / (norm1 * norm2) if norm1 > 1e-9 and norm2 > 1e-9 else 1.0
                if sim < 0.15:
                    logger.info(
                        f"🔄 Topic Shift Detected (similarity {sim:.3f} < 0.15). Flushing Goal Buffer."
                    )
                    self.goal_buffer.flush()
            except Exception as ts_err:
                logger.debug("Topic-shift calculation failed: %s", ts_err)
        self._last_query_vector = query_vector

    async def _gather_candidate_sources(self, mrl_query_vector, candidate_limit):
        """Fetch vector candidates and the Neo4j entity/relation graph concurrently."""

        async def safe_qdrant_search():
            try:
                if self.qdrant_store.client:
                    return await asyncio.to_thread(
                        self.qdrant_store.search_vector_memories,
                        query_vector=mrl_query_vector,
                        limit=candidate_limit,
                    )
            except Exception as qe:
                logger.error(f"Qdrant retrieval failed: {qe}")
            return []

        async def _dummy_list():
            return []

        candidates, entity_records, relation_records = await asyncio.gather(
            safe_qdrant_search(),
            self.graph_db.execute_query(
                "MATCH (e:Entity) RETURN e.name AS name, e.description AS description",
                use_cache=True,
            )
            if self.graph_db
            else _dummy_list(),
            self.graph_db.execute_query(
                "MATCH (s:Entity)-[r]-(t:Entity) RETURN s.name AS source, t.name AS target",
                use_cache=True,
            )
            if self.graph_db
            else _dummy_list(),
        )

        # Defensive type checks
        if not isinstance(entity_records, list):
            entity_records = []
        if not isinstance(relation_records, list):
            relation_records = []
        return candidates, entity_records, relation_records

    async def _score_qdrant_candidates(
        self,
        candidates,
        *,
        wing,
        room,
        excluded,
        threshold,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
        now_ts,
    ) -> list:
        """Score Qdrant vector hits with ACT-R activation + neuromodulatory gating."""
        raw_candidates = []
        try:
            db_metadata = await self._fetch_candidate_db_metadata(candidates)

            for cand in candidates:
                meta = cand["metadata"]
                c_wing = meta.get("wing")
                c_room = meta.get("room")
                if wing is not None and c_wing != wing:
                    continue
                if room is not None and c_room != room:
                    continue

                c_content = cand["content"]
                if c_content in excluded:
                    continue

                memory_id = cand["id"]
                db_meta = db_metadata.get(str(memory_id))

                memory_valence = (
                    db_meta.get("valence")
                    if (db_meta and db_meta.get("valence") is not None)
                    else meta.get("valence", 0.0)
                )
                emotion_weight_row = (
                    db_meta.get("emotional_weight")
                    if (db_meta and db_meta.get("emotional_weight") is not None)
                    else meta.get("emotional_weight", 0.0)
                )
                importance_score = (
                    db_meta.get("importance_score")
                    if (db_meta and db_meta.get("importance_score") is not None)
                    else meta.get("importance_score", 0.5)
                )
                recall_count = max(
                    1,
                    db_meta.get("recall_count")
                    if (db_meta and db_meta.get("recall_count") is not None)
                    else meta.get("recall_count", 1),
                )

                last_recall_time = self._coerce_last_recall_ts(db_meta, meta, now_ts)
                hours_since = max(0.001, (now_ts - last_recall_time) / 3600.0)

                # 2D/3D Emotional Distance matching the research simulator
                dist_emo = math.sqrt(
                    (memory_valence - current_valence) ** 2
                    + (emotion_weight_row - current_arousal) ** 2
                )

                base_activation = self._base_activation(
                    recall_count, hours_since, importance_score, dist_emo
                )

                similarity = cand["score"]
                effective_similarity = self._effective_similarity(
                    similarity,
                    memory_valence,
                    emotion_weight_row,
                    current_arousal,
                    current_cortisol,
                )

                spread_activation = self.spread_weight * effective_similarity
                score = (
                    base_activation
                    + spread_activation
                    - ACTR_EMO_DISTANCE_PENALTY * dist_emo
                )

                if score <= (threshold - 2.5) and importance_score < 0.7:
                    continue

                created_val = meta.get("created_at")
                try:
                    created = (
                        datetime.fromtimestamp(float(created_val), UTC)
                        if created_val
                        else (
                            current_time
                            if current_time is not None
                            else datetime.now(UTC)
                        )
                    )
                except Exception:
                    created = (
                        current_time
                        if current_time is not None
                        else datetime.now(UTC)
                    )

                custom_metadata = {}
                if "custom_metadata" in meta:
                    try:
                        custom_metadata = orjson.loads(meta["custom_metadata"])
                    except Exception:
                        pass

                raw_candidates.append(
                    {
                        "id": memory_id,
                        "content": c_content,
                        "raw_content": c_content,
                        "wing": c_wing or "personal",
                        "room": c_room,
                        "score": score,
                        "valence": memory_valence,
                        "created_at": created,
                        "recall_count": recall_count,
                        "metadata": custom_metadata,
                        "lifespan_stage": meta.get("lifespan_stage"),
                        "crisis": meta.get("crisis"),
                        "virtue": meta.get("virtue"),
                        "relations": meta.get("relations"),
                        "relation_circles": meta.get("relation_circles"),
                        "modality": meta.get("modality"),
                        "similarity": similarity,
                        "last_recalled_at": datetime.fromtimestamp(
                            last_recall_time, UTC
                        ),
                    }
                )
        except Exception as qe:
            logger.error(f"Qdrant retrieval failed, falling back to database: {qe}")
        return raw_candidates

    async def _fetch_candidate_db_metadata(self, candidates) -> dict:
        """Load the authoritative SQL metadata for a set of Qdrant candidates.

        Qdrant payloads can lag the SQL row (recall_count/last_recalled_at move
        on every recall), so the DB copy wins where present.
        """
        db_metadata = {}
        try:
            cand_ids = [c["id"] for c in candidates if c.get("id")]
            if cand_ids:
                async with self.pool.acquire() as conn:
                    where, args = self._in_predicate("id", cand_ids)
                    rows = await conn.fetch(
                        "SELECT id, importance_score, emotional_weight, valence, "
                        f"recall_count, last_recalled_at FROM memories WHERE {where}",
                        *args,
                    )
                    for r in rows:
                        db_metadata[str(r["id"])] = r
        except Exception as db_err:
            logger.warning(
                f"Failed to fetch updated memory metadata from SQL DB for Qdrant candidates: {db_err}"
            )
        return db_metadata

    @staticmethod
    def _coerce_last_recall_ts(db_meta, meta, now_ts) -> float:
        """Normalize last_recalled_at (datetime | epoch | ISO string) to a float epoch."""
        try:
            if db_meta and db_meta.get("last_recalled_at"):
                last_recall_time = db_meta.get("last_recalled_at")
                if isinstance(last_recall_time, (int, float)):
                    return float(last_recall_time)
                if hasattr(last_recall_time, "timestamp"):
                    return last_recall_time.timestamp()
                dt = datetime.fromisoformat(str(last_recall_time).replace(" ", "T"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt.timestamp()
            return float(meta.get("last_recalled_at", now_ts))
        except (ValueError, TypeError):
            return now_ts

    async def _fetch_sqlite_candidates(
        self,
        conn,
        *,
        query_vector,
        wing,
        room,
        excluded,
        threshold,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
        candidate_limit,
    ) -> tuple[list, float]:
        """SQLite fallback: fetch rows and score them via the Rust ACT-R kernel.

        Returns the candidates plus the `now_ts` it computed, because the
        original inlined body rebound the enclosing now_ts here and that value
        is what later stamps the L1 cache entry.

        audit/ROADMAP.md P2-6 (M2-P3): this used to `SELECT *` with no
        `LIMIT` -- a full-table scan on every cache miss, unlike its Postgres
        sibling (`_fetch_postgres_candidates`), which already receives and
        applies `candidate_limit`. `embedding` stays in the projection
        despite M2-P3's "excludes embedding where unused" suggestion --
        SQLite has no pgvector, so `cognitive_rust.score_memories_actr_sqlite`
        computes cosine similarity from this column in Rust; dropping it
        would silently zero out every candidate's similarity, not just save
        bytes. `ORDER BY last_recalled_at DESC` biases a hard cap toward
        recently-relevant memories rather than an arbitrary rowid-order
        slice; SQLite sorts NULL as smallest, so never-recalled rows land
        last under DESC, which is the right side of the cut to lose first.
        """
        if room is not None:
            rows = await conn.fetch(
                "SELECT * FROM memories WHERE wing = ? AND room = ? "
                "ORDER BY last_recalled_at DESC LIMIT ?",
                wing,
                room,
                candidate_limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM memories WHERE wing = ? "
                "ORDER BY last_recalled_at DESC LIMIT ?",
                wing,
                candidate_limit,
            )

        # Manual cosine similarity and ACT-R scoring (delegated to Rust PyO3).
        # Imported lazily: the compiled extension is optional in some envs and
        # a module-level import would break importing MemoryStore entirely.
        import cognitive_rust

        now = current_time if current_time is not None else datetime.now(UTC)
        now_ts = now.timestamp()

        # Preprocess timestamps for Rust
        for row in rows:
            row["_last_recall_ts"] = self._normalize_recall_ts(
                row.get("last_recalled_at"), now_ts
            )

        scored_indices = cognitive_rust.score_memories_actr_sqlite(
            query_vector,
            rows,
            excluded,
            current_valence,
            current_arousal,
            current_cortisol,
            self.decay_rate,
            self.spread_weight,
            threshold,
            now_ts,
        )

        raw_candidates = []
        for idx, score, similarity in scored_indices:
            row = rows[idx]
            last_recall = row.get("last_recalled_at")
            if last_recall is None:
                last_recall = now
            elif isinstance(last_recall, str):
                try:
                    last_recall = datetime.fromisoformat(last_recall)
                except Exception:
                    last_recall = now
            if last_recall.tzinfo is None:
                last_recall = last_recall.replace(tzinfo=UTC)

            created = row.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except Exception:
                    created = now
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)

            raw_meta = row.get("metadata")
            if isinstance(raw_meta, str):
                try:
                    raw_meta = orjson.loads(raw_meta)
                except Exception:
                    raw_meta = {}

            raw_candidates.append(
                {
                    "id": row.get("id"),
                    "content": row["content"],
                    "raw_content": row.get("raw_content") or row["content"],
                    "wing": row.get("wing", "personal"),
                    "room": row.get("room"),
                    "score": score,
                    "valence": row.get("valence") or 0.0,
                    "created_at": created,
                    "recall_count": max(1, row.get("recall_count") or 1),
                    "metadata": raw_meta or {},
                    "lifespan_stage": row.get("lifespan_stage"),
                    "crisis": row.get("crisis"),
                    "virtue": row.get("virtue"),
                    "relations": row.get("relations"),
                    "relation_circles": row.get("relation_circles"),
                    "modality": row.get("modality"),
                    "similarity": similarity,
                    "last_recalled_at": last_recall,
                }
            )
        return raw_candidates, now_ts

    @staticmethod
    def _normalize_recall_ts(last_recall, now_ts: float) -> float:
        """Coerce a row's last_recalled_at into a float epoch for the Rust kernel."""
        if last_recall is None:
            return now_ts
        if isinstance(last_recall, datetime):
            return last_recall.timestamp()
        if isinstance(last_recall, (int, float)):
            return float(last_recall)
        if isinstance(last_recall, str):
            try:
                return float(last_recall)
            except ValueError:
                try:
                    dt = datetime.fromisoformat(last_recall.replace(" ", "T"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt.timestamp()
                except Exception:
                    return now_ts
        return now_ts

    async def _fetch_postgres_candidates(
        self,
        conn,
        *,
        vector_str,
        wing,
        room,
        excluded,
        threshold,
        candidate_limit,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
    ) -> list:
        """PostgreSQL fast path via the surface_actr_memories() vector procedure."""
        rows = await self._fetch_surface_actr_rows(
            conn,
            vector_str=vector_str,
            wing=wing,
            room=room,
            threshold=threshold,
            candidate_limit=candidate_limit,
            current_valence=current_valence,
            current_arousal=current_arousal,
            current_cortisol=current_cortisol,
            current_time=current_time,
        )

        raw_candidates = []
        for row in rows:
            if row["content"] in excluded:
                continue

            similarity = row.get("similarity") or 0.0
            recall_count = max(1, row.get("recall_count") or 1)

            # Recalculate score with neuromodulatory gating
            last_recall = row.get("last_recalled_at")
            now = (
                self._as_aware_utc(current_time)
                if current_time is not None
                else datetime.now(UTC)
            )
            # `or now` covers both a missing timestamp and one _as_aware_utc
            # could not parse; either way the row is treated as just-recalled
            # rather than raising and discarding the whole result set.
            last_recall = self._as_aware_utc(last_recall) or now

            hours_since = max(0.001, (now - last_recall).total_seconds() / 3600.0)

            memory_valence = row.get("valence") or 0.0
            emotion_weight_row = row.get("emotional_weight") or 0.0

            # 2D/3D Emotional Distance matching the research simulator
            dist_emo = math.sqrt(
                (memory_valence - current_valence) ** 2
                + (emotion_weight_row - current_arousal) ** 2
            )

            base_activation = self._base_activation(
                recall_count,
                hours_since,
                row.get("importance_score") or 0.5,
                dist_emo,
            )

            # Neuromodulatory distance mapping
            effective_similarity = self._effective_similarity(
                similarity,
                memory_valence,
                emotion_weight_row,
                current_arousal,
                current_cortisol,
            )

            spread_activation = self.spread_weight * effective_similarity
            score = (
                base_activation
                + spread_activation
                - ACTR_EMO_DISTANCE_PENALTY * dist_emo
            )

            if score <= (threshold - 2.5) and (row.get("importance_score") or 0.5) < 0.7:
                continue

            created = row.get("created_at")
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)

            raw_meta = row.get("metadata")
            if isinstance(raw_meta, str):
                try:
                    raw_meta = orjson.loads(raw_meta)
                except Exception:
                    raw_meta = {}

            raw_candidates.append(
                {
                    "id": row.get("id"),
                    "content": row["content"],
                    "raw_content": row.get("raw_content") or row["content"],
                    "wing": row.get("wing", "personal"),
                    "room": row.get("room"),
                    "score": score,
                    "valence": row.get("valence") or 0.0,
                    "created_at": created,
                    "recall_count": recall_count,
                    "metadata": raw_meta or {},
                    "lifespan_stage": row.get("lifespan_stage"),
                    "crisis": row.get("crisis"),
                    "virtue": row.get("virtue"),
                    "relations": row.get("relations"),
                    "relation_circles": row.get("relation_circles"),
                    "modality": row.get("modality"),
                    "similarity": similarity,
                    "last_recalled_at": last_recall,
                }
            )
        return raw_candidates

    async def _fetch_surface_actr_rows(
        self,
        conn,
        *,
        vector_str,
        wing,
        room,
        threshold,
        candidate_limit,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
    ):
        """Call surface_actr_memories(), falling back to the pre-Eriksonian schema.

        The two queries take identical arguments and differ only in whether the
        Eriksonian lifespan columns are selected from the JOINed memories row,
        so the argument tuple is built once.
        """
        args = (
            vector_str,
            wing,
            room,
            self.decay_rate,
            self.spread_weight,
            self.emotion_weight,
            current_valence,
            current_arousal,
            current_cortisol,
            threshold - 2.5,
            candidate_limit,
            current_time,
        )
        try:
            return await conn.fetch(_SURFACE_ACTR_SQL_ERIKSONIAN, *args)
        except Exception as pg_err:
            logger.warning(
                f"Eriksonian JOIN pg query failed, falling back to legacy schema: {pg_err}"
            )
            return await conn.fetch(_SURFACE_ACTR_SQL_LEGACY, *args)

    def _resolve_dynamic_stop_words(self, user_id) -> set:
        """Static stop words plus DB-learned ones and the agent/user proper nouns.

        The agent's own name and the speaker's name are suppressed as cues
        because they appear in nearly every memory and would otherwise boost
        everything uniformly.
        """
        dynamic_stop_words = set(SEARCH_STOP_WORDS)
        if getattr(self, "_db_stop_words", None):
            dynamic_stop_words.update(self._db_stop_words)
        ai_name_cfg = getattr(Config, "AI_NAME", None)
        if ai_name_cfg:
            for w in re.findall(r"\b\w{3,}\b", ai_name_cfg.lower()):
                dynamic_stop_words.add(w)
        if user_id:
            for w in re.findall(r"\b\w{3,}\b", user_id.lower()):
                dynamic_stop_words.add(w)
        return dynamic_stop_words

    @staticmethod
    def _compile_entity_pattern(entity_names) -> re.Pattern | None:
        """One compiled alternation over every known entity name.

        audit/ROADMAP.md P2-3 (M2-P1): three call sites each used to build
        and search a fresh `\bname\b` pattern per (candidate, entity) pair
        -- an uncompiled regex re-created O(candidates x entities) times per
        `search_memories` call. A single compiled alternation, searched once
        per candidate via `finditer`, finds the same set of whole-word
        matches in one pass. Longest names first so that if two entity names
        were ever identical after lowercasing (not expected, but not
        enforced anywhere either), the longer alternative is preferred --
        `\b` boundaries alone already prevent a *shorter* name matching
        inside a longer one that merely contains it (e.g. "Sam" cannot match
        inside "Samantha": there is no word boundary between them).
        """
        if not entity_names:
            return None
        escaped = sorted(
            (re.escape(n.lower()) for n in entity_names), key=len, reverse=True
        )
        return re.compile(r"\b(?:" + "|".join(escaped) + r")\b")

    @staticmethod
    def _compute_candidate_entities(raw_candidates, entity_names) -> dict:
        """Base candidate-index -> mentioned-entity-names mapping.

        Computed once and shared by `_build_entity_graph` (co-occurrence
        edges), `_collect_ppr_seeds` (seed fallback) and the first-person
        pronoun layer `_apply_ppr_spreading_activation` adds once
        `agent_node_name` is known (not yet resolved at this point -- see
        the call site). A candidate's own `metadata["entities"]` wins when
        present (`add_memory` precomputes it); only candidates without that
        fall back to scanning content with the compiled pattern below.
        """
        pattern = MemoryStore._compile_entity_pattern(entity_names)
        lower_to_name = {n.lower(): n for n in entity_names}

        cand_entities: dict[int, set] = {}
        for idx, cand in enumerate(raw_candidates):
            payload_meta = cand.get("metadata") or {}
            meta_entities = payload_meta.get("entities")
            if isinstance(meta_entities, list) and meta_entities:
                cand_entities[idx] = set(meta_entities)
                continue
            if pattern is None:
                cand_entities[idx] = set()
                continue
            content_lower = cand["content"].lower()
            cand_entities[idx] = {
                lower_to_name[m.group(0)]
                for m in pattern.finditer(content_lower)
                if m.group(0) in lower_to_name
            }
        return cand_entities

    @staticmethod
    def _build_entity_graph(entity_records, relation_records, raw_candidates):
        """Build the entity list, co-occurrence adjacency, and base
        candidate->entities mapping used by PPR.

        Edges come from Neo4j relations plus entity co-occurrence within each
        candidate memory.
        """
        entity_names = [r["name"] for r in entity_records]
        adj = {}

        for r in relation_records:
            src = r["source"]
            tgt = r["target"]
            adj.setdefault(src, set()).add(tgt)
            adj.setdefault(tgt, set()).add(src)

        cand_entities = MemoryStore._compute_candidate_entities(
            raw_candidates, entity_names
        )

        # Add co-occurrence connections from candidate memories
        for ents in cand_entities.values():
            ents = list(ents)
            for i in range(len(ents)):
                for j in range(i + 1, len(ents)):
                    e1 = ents[i]
                    e2 = ents[j]
                    adj.setdefault(e1, set()).add(e2)
                    adj.setdefault(e2, set()).add(e1)

        return entity_names, adj, cand_entities

    @staticmethod
    def _resolve_identity_nodes(entity_records, entity_names, adj, user_id):
        """Discover which graph nodes represent the agent and the user.

        Falls back through description text, configured AI_NAME, and finally
        the most-connected non-agent entity, so pronoun resolution still works
        on a graph that was never explicitly annotated.
        """
        agent_node_name = None
        user_node_name = None

        # 1. Discover Agent Node Name dynamically
        for r in entity_records:
            desc = r.get("description") or ""
            if "central cognitive system" in desc.lower():
                agent_node_name = r["name"]
                break
        if not agent_node_name:
            ai_name = getattr(Config, "AI_NAME", "AI Friend")
            for name in entity_names:
                if name.lower() == ai_name.lower():
                    agent_node_name = name
                    break
        if not agent_node_name:
            agent_node_name = getattr(Config, "AI_NAME", "AI Friend")

        # 2. Discover User Node Name dynamically
        if user_id:
            for name in entity_names:
                if name.lower() == user_id.lower():
                    user_node_name = name
                    break
        if not user_node_name:
            for r in entity_records:
                desc = r.get("description") or ""
                if (
                    "user" in desc.lower()
                    or "companion" in desc.lower()
                    or "friend" in desc.lower()
                ) and r["name"] != agent_node_name:
                    user_node_name = r["name"]
                    break
        if not user_node_name and entity_names:
            ai_names = {"ai friend", "my friend", agent_node_name.lower()}
            if getattr(Config, "AI_NAME", None):
                ai_names.add(Config.AI_NAME.lower())
            candidates_names = [
                name for name in entity_names if name.lower() not in ai_names
            ]
            if candidates_names:
                candidates_names.sort(
                    key=lambda name: len(adj.get(name, set())), reverse=True
                )
                user_node_name = candidates_names[0]
        if not user_node_name:
            user_node_name = user_id or "user"

        return agent_node_name, user_node_name

    @staticmethod
    def _resolve_pronoun_cues(
        query_text, agent_node_name, user_node_name, user_id, is_self_reflection
    ) -> set:
        """Context-aware speaker/listener pronoun resolution.

        Who "I" and "you" refer to flips depending on whether the agent is
        reflecting on itself or the user is speaking.
        """
        query_words_all = re.findall(r"\b\w+\b", query_text.lower())
        resolved_cues = set()

        if is_self_reflection:
            # Agent speaking: "I" -> Agent, "you" -> User
            speaker, listener = agent_node_name, user_node_name
        else:
            # User speaking: "I" -> User, "you" -> Agent
            speaker, listener = user_node_name, agent_node_name

        if any(p in query_words_all for p in FIRST_PERSON_PRONOUNS) and speaker:
            resolved_cues.add(speaker.lower())
        if any(p in query_words_all for p in SECOND_PERSON_PRONOUNS) and listener:
            resolved_cues.add(listener.lower())

        # Add user/agent names if explicitly mentioned in query
        user_aliases = {"user"}
        if user_id:
            user_aliases.add(user_id.lower())
        if user_node_name:
            user_aliases.add(user_node_name.lower())

        agent_aliases = {"ai friend", "my friend"}
        if getattr(Config, "AI_NAME", None):
            agent_aliases.add(Config.AI_NAME.lower())
        if agent_node_name:
            agent_aliases.add(agent_node_name.lower())

        for word in query_words_all:
            if word in user_aliases and user_node_name:
                resolved_cues.add(user_node_name.lower())
            if word in agent_aliases and agent_node_name:
                resolved_cues.add(agent_node_name.lower())

        return resolved_cues

    @staticmethod
    def _apply_direct_cue_boost(raw_candidates, matched_cues) -> set:
        """Add DIRECT_CUE_BOOST per literal query cue found in a memory.

        Returns the indices that were boosted; PPR treats these as seeds when
        the query itself names no known entity.
        """
        direct_boosted_indices = set()
        if not matched_cues:
            return direct_boosted_indices
        for idx, cand in enumerate(raw_candidates):
            content_lower = cand["content"].lower()
            match_count = sum(1 for mc in matched_cues if mc in content_lower)
            if match_count > 0:
                cand["score"] += DIRECT_CUE_BOOST * match_count
                direct_boosted_indices.add(idx)
        return direct_boosted_indices

    def _apply_ppr_spreading_activation(
        self,
        raw_candidates,
        entity_names,
        adj,
        matched_cues,
        direct_boosted_indices,
        agent_node_name,
        cand_entities,
    ) -> None:
        """HippoRAG-inspired Personalized PageRank spreading activation.

        Seeds are the query's entity cues (or, failing that, the entities of
        directly-cued memories), and each candidate gains a degree-scaled boost
        for the seeded entities it mentions.

        `cand_entities` is the *base* mapping from `_build_entity_graph`,
        computed before `agent_node_name` was known (see the call site in
        `search_memories`). The first-person-pronoun addition -- "I"/"me"/
        etc. count as a mention of the agent itself -- is layered on here,
        once agent_node_name is available, rather than recomputed from
        scratch the way the pre-P2-3 `_map_candidate_entities` did.

        **The layer must go on after `_collect_ppr_seeds`, not before.**
        Pre-P2-3 the pronoun attribution lived only in
        `_map_candidate_entities`, which ran *after* seeds were picked, so
        seeding never saw it -- a directly-cued memory mentioning "I" but no
        named entity produced no seeds, hence an empty PPR vector and no
        boost for anyone. Applying the layer first would silently make the
        agent node seed that case, which is a ranking change, not the
        behavior-preserving hoist this refactor is meant to be.
        """
        if not entity_names:
            return
        try:
            seeds = self._collect_ppr_seeds(
                entity_names, matched_cues, direct_boosted_indices, cand_entities
            )

            if agent_node_name:
                pronoun_pattern = re.compile(
                    r"\b(?:"
                    + "|".join(re.escape(p) for p in FIRST_PERSON_PRONOUNS)
                    + r")\b"
                )
                for idx, cand in enumerate(raw_candidates):
                    if pronoun_pattern.search(cand["content"].lower()):
                        cand_entities.setdefault(idx, set()).add(agent_node_name)

            # Compute Personalized PageRank Vector (3-iteration power method,
            # delegated to the Rust hot loop with a Python fallback).
            # PPR_DAMPING is the canonical teleport factor.
            if not seeds:
                ppr = {}
            else:
                p = self._personalized_pagerank(
                    entity_names, adj, seeds, PPR_DAMPING, 3
                )
                ppr = {entity_names[i]: p[i] for i in range(len(entity_names))}

            # Apply spreading activation boost based on PPR probability
            for idx, cand in enumerate(raw_candidates):
                if idx in direct_boosted_indices:
                    continue
                boost_sum = 0.0
                for ent in cand_entities.get(idx, ()):
                    if ent in ppr:
                        deg = len(adj.get(ent, set()))
                        # HippoRAG-inspired degree-scaled activation boost
                        boost = (1.2 * ppr[ent]) / (1.0 + math.log(max(1, deg)))
                        boost_sum += boost
                if boost_sum > 0:
                    cand["score"] += boost_sum

        except Exception as ne_err:
            logger.error(f"PPR spreading activation failed: {ne_err}")

    @staticmethod
    def _collect_ppr_seeds(
        entity_names, matched_cues, direct_boosted_indices, cand_entities
    ) -> set:
        """Pick the PPR seed entities for this query.

        Reads the shared `cand_entities` mapping (see `_build_entity_graph`)
        rather than re-scanning candidate content -- this fallback branch
        used to duplicate the same per-entity regex search a third time.
        """
        seeds = set()
        name_to_idx = {name.lower(): i for i, name in enumerate(entity_names)}

        # 1. Query cues that match entity names
        for cue in matched_cues:
            idx = name_to_idx.get(cue.lower())
            if idx is not None:
                seeds.add(idx)

        # 2. If no direct query seeds, use entities from directly cued memories
        #    (vector-guided associative recall)
        if not seeds:
            for idx in direct_boosted_indices:
                for ent in cand_entities.get(idx, ()):
                    e_idx = name_to_idx.get(ent.lower())
                    if e_idx is not None:
                        seeds.add(e_idx)
        return seeds

    def _apply_goal_buffer_boost(self, raw_candidates) -> None:
        """Prime candidates that mention concepts held in the active goal buffer."""
        active_concepts = [c[0] for c in self.goal_buffer.concepts]
        if not active_concepts:
            return
        for cand in raw_candidates:
            content_lower = cand["content"].lower()
            match_count = sum(1 for c in active_concepts if c in content_lower)
            if match_count > 0:
                w_j = 1.5 / len(active_concepts)
                boost = match_count * w_j * 1.2
                cand["score"] += boost
                logger.debug(
                    f"GoalBuffer Prime: Added +{boost:.3f} spreading activation to memory {cand.get('id') or cand.get('content', 'N/A')}"
                )

    @staticmethod
    def _format_results(raw_candidates, threshold) -> list:
        """Drop sub-threshold candidates and project them to the public shape."""
        results = []
        for cand in raw_candidates:
            if cand["score"] <= threshold:
                continue
            results.append(
                {
                    "content": cand["content"],
                    "raw_content": cand["raw_content"],
                    "wing": cand["wing"],
                    "room": cand["room"],
                    "score": cand["score"],
                    "valence": cand["valence"],
                    "created_at": cand["created_at"].isoformat()
                    if cand["created_at"]
                    else None,
                    "recall_count": cand["recall_count"],
                    "metadata": cand["metadata"],
                    # Eriksonian columns
                    "lifespan_stage": cand.get("lifespan_stage"),
                    "crisis": cand.get("crisis"),
                    "virtue": cand.get("virtue"),
                    "relations": cand.get("relations"),
                    "relation_circles": cand.get("relation_circles"),
                    "modality": cand.get("modality"),
                }
            )
        return results

    # --- L3 sub-conscious archive search and promotion -------------------

    def _expand_archive_cues(
        self, query_words, dynamic_stop_words, matched_cues, resolved_cues, user_id
    ) -> set:
        """Build the lexical cue set used to probe archived (L3) memories.

        Unlike the active-tier cues, the speaker's own name is *kept* here: an
        archived memory is often only findable by who it was about. Cues are
        then widened by stemming and the learned mental lexicon.
        """
        archive_stop_words = set(dynamic_stop_words)
        if user_id:
            for w in re.findall(r"\b\w{3,}\b", user_id.lower()):
                archive_stop_words.discard(w)
        archive_cues = [w for w in query_words if w not in archive_stop_words]

        # Also include any resolved cues (agent name / resolved user name)
        for cue in resolved_cues:
            if cue not in archive_cues:
                archive_cues.append(cue)

        if not archive_cues:
            archive_cues = list(matched_cues)

        # Apply lexical priming/synonym expansion to cues
        expanded_cues = set()
        for cue in archive_cues:
            expanded_cues.add(cue)
            stem = _get_stem(cue)
            expanded_cues.add(stem)
            # Learned lexical priming: pull the cue's strongest acquired
            # associates (empty until the lexicon has learned them).
            expanded_cues.update(self.lexicon.expand(cue))
            expanded_cues.update(self.lexicon.expand(stem))
        return expanded_cues

    async def _fetch_archive_rows(self, expanded_cues_list, wing, vector_str) -> list:
        """Hybrid semantic + lexical lookup against archived_memories."""
        patterns = [f"%{cue}%" for cue in expanded_cues_list]
        # Fetch more candidates than needed so they can be re-ranked by keyword
        # match count and ACT-R score before the promotion cut.
        archive_limit = 250
        try:
            async with self.pool.acquire() as conn:
                if self.is_sqlite:
                    where_clause = " OR ".join(
                        "lower(content) LIKE ?" for _ in expanded_cues_list
                    )
                    query = f"""
                        SELECT * FROM archived_memories
                        WHERE wing = ? AND ({where_clause})
                        ORDER BY importance_score DESC, last_recalled_at DESC
                        LIMIT ?
                    """
                    return await conn.fetch(query, wing, *patterns, archive_limit)
                # Postgres pgvector: hybrid semantic + lexical synonym search
                # using the HNSW index over halfvec.
                query = """
                    SELECT *, (1 - (embedding <=> $2::halfvec))::double precision AS similarity_arch
                    FROM archived_memories
                    WHERE wing = $1 AND (embedding <=> $2::halfvec < 0.45 OR content ILIKE ANY($3))
                    ORDER BY coalesce((1 - (embedding <=> $2::halfvec)), 0.0) DESC, importance_score DESC, last_recalled_at DESC
                    LIMIT $4
                """
                return await conn.fetch(
                    query, wing, vector_str, patterns, archive_limit
                )
        except Exception as arch_err:
            logger.error(f"Archived memories hybrid lookup failed: {arch_err}")
            return []

    @staticmethod
    def _parse_stored_embedding(emb_val):
        """Parse an archived embedding stored as JSON text, a vector literal, or a list."""
        if not emb_val:
            return None
        if isinstance(emb_val, list):
            return emb_val
        if isinstance(emb_val, str):
            try:
                return json.loads(emb_val)
            except Exception:
                try:
                    return [
                        float(x)
                        for x in re.findall(
                            r"[-+]?\d*\.\d+|\d+e[-+]?\d+|[-+]?\d+", emb_val
                        )
                    ]
                except Exception:
                    return None
        return None

    def _archive_row_activation(
        self,
        row,
        similarity,
        *,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
    ):
        """ACT-R activation for one archived row.

        Returns (score, spread_activation, dist_emo, recall_count) - the extra
        terms are reused when the row is promoted and rescored as active.
        """
        recall_count = max(1, row.get("recall_count") or 1)
        last_recall = row.get("last_recalled_at")
        now = (
            self._as_aware_utc(current_time)
            if current_time is not None
            else datetime.now(UTC)
        )
        # `or now`: an unparseable stored timestamp must not raise here and
        # discard otherwise valid archive candidates.
        last_recall = self._as_aware_utc(last_recall) or now

        hours_since = max(0.001, (now - last_recall).total_seconds() / 3600.0)
        memory_valence = row.get("valence") or 0.0
        emotion_weight_row = row.get("emotional_weight") or 0.0

        dist_emo = math.sqrt(
            (memory_valence - current_valence) ** 2
            + (emotion_weight_row - current_arousal) ** 2
        )

        base_activation = self._base_activation(
            recall_count, hours_since, row.get("importance_score") or 0.5, dist_emo
        )
        effective_similarity = self._effective_similarity(
            similarity,
            memory_valence,
            emotion_weight_row,
            current_arousal,
            current_cortisol,
        )
        spread_activation = self.spread_weight * effective_similarity
        score = (
            base_activation + spread_activation - ACTR_EMO_DISTANCE_PENALTY * dist_emo
        )
        return score, spread_activation, dist_emo, recall_count, now

    async def _rank_archive_rows(
        self,
        archive_rows,
        expanded_cues,
        query_vector,
        *,
        limit,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
    ) -> list:
        """Score archived rows and keep the best few for promotion."""
        scored_archive_rows = []
        for row in archive_rows:
            content = row.get("content", "")
            similarity = row.get("similarity_arch")
            if similarity is None:
                similarity = self._archive_similarity_fallback(row, query_vector)

            score, _spread, _dist, _recall, _now = self._archive_row_activation(
                row,
                similarity,
                current_valence=current_valence,
                current_arousal=current_arousal,
                current_cortisol=current_cortisol,
                current_time=current_time,
            )

            # Lexical match count boost so direct query matches sort higher
            # (HippoRAG key-relevance ranking).
            content_lower = content.lower()
            match_count = sum(1 for cue in expanded_cues if cue in content_lower)
            ranking_score = score + DIRECT_CUE_BOOST * match_count

            scored_archive_rows.append((ranking_score, score, similarity, row))

        scored_archive_rows.sort(key=lambda x: x[0], reverse=True)
        # Limit the promotion list to prevent flooding the active tier
        promote_limit = min(5, limit) if limit else 5
        return scored_archive_rows[:promote_limit]

    @staticmethod
    def _archive_similarity_fallback(row, query_vector) -> float:
        """Cosine similarity computed in Python when the DB did not supply one."""
        emb = MemoryStore._parse_stored_embedding(row.get("embedding"))
        if not emb or not query_vector:
            return 0.0
        import numpy as np

        q_arr = np.array(query_vector)
        emb_arr = np.array(emb)
        norm_q = np.linalg.norm(q_arr)
        norm_emb = np.linalg.norm(emb_arr)
        if norm_q > 0 and norm_emb > 0:
            return float(np.dot(q_arr, emb_arr) / (norm_q * norm_emb))
        return 0.0

    async def _write_promoted_memory(
        self, mem_id, content, row, emb, recall_count, now, payload_meta, sql_meta
    ):
        """Move one archived row back into the active tier (SQL + Qdrant).

        `sql_meta` is the row's own metadata envelope and `payload_meta` the
        Qdrant search payload; they are deliberately not the same object. Qdrant
        needs the denormalized scalars flattened for filtering, while the SQL
        `metadata` column is the authoritative record and must round-trip what
        `add_memory` would have written.

        Raises on failure so the caller does not report an unpersisted memory.
        On PostgreSQL the insert and the archive delete run in one transaction;
        the SQLite shim commits per statement, so there the delete is merely
        ordered after the insert. The insert is an idempotent upsert, so a
        partial failure re-converges on retry rather than duplicating.
        """
        insert_values = (
            mem_id,
            content,
            row.get("raw_content"),
            row.get("wing"),
            row.get("room"),
            str(emb),
            row.get("importance_score"),
            row.get("emotional_weight"),
            row.get("valence"),
            row.get("certainty"),
            row.get("source"),
            recall_count + 1,
            now,
            row.get("created_at"),
            json.dumps(sql_meta),
            row.get("lifespan_stage"),
            row.get("crisis"),
            row.get("virtue"),
            row.get("relations"),
            row.get("relation_circles"),
            row.get("modality"),
        )

        async def _move(conn):
            if self.is_sqlite:
                await conn.execute(_PROMOTE_INSERT_SQLITE, *insert_values)
                await conn.execute(
                    "DELETE FROM archived_memories WHERE id = ?", mem_id
                )
            else:
                await conn.execute(_PROMOTE_INSERT_PG, *insert_values)
                await conn.execute(
                    "DELETE FROM archived_memories WHERE id = $1", mem_id
                )

        async with self.pool.acquire() as conn:
            transaction = getattr(conn, "transaction", None)
            if not self.is_sqlite and callable(transaction):
                async with transaction():
                    await _move(conn)
            else:
                await _move(conn)

        # Upsert Qdrant. The SQL move above is the authoritative promotion and
        # has already committed: the active row exists and the archive row is
        # gone. Letting a vector-store failure propagate here would make the
        # caller skip a memory that is, in fact, promoted -- stranding it out of
        # both the returned results and the archive. Log and carry on; the
        # vector index is a search accelerator, rebuildable from SQL.
        if self.qdrant_store and self.qdrant_store.client:
            try:
                await asyncio.to_thread(
                    self.qdrant_store.add_vector_memory,
                    mem_id,
                    emb,
                    content,
                    payload_meta,
                )
            except Exception as qerr:
                logger.error(
                    f"Promoted memory {mem_id} committed to SQL but its Qdrant "
                    f"upsert failed; vector index is stale for this row: {qerr}"
                )

        logger.info(
            f"📥 [Memory Promotion] Promoted memory '{content[:40]}...' from archive back to active storage."
        )

    @staticmethod
    def _build_promotion_payload(row, raw_meta) -> dict:
        """Qdrant payload for a memory being promoted out of the archive.

        Mirrors the canonical shape `add_memory` writes: the authoritative
        columns stay sourced from the row itself, and the memory's own metadata
        goes under `custom_metadata` where the read path expects it. Splatting
        `raw_meta` at the top level (as this once did) let a stored key named
        `wing` or `room` silently overwrite the real one, and hid the custom
        fields from readers looking for the envelope.
        """
        created_at = MemoryStore._as_aware_utc(row.get("created_at"))
        return {
            "wing": row.get("wing", "personal"),
            "room": row.get("room") or "",
            "importance_score": row.get("importance_score"),
            "emotional_weight": row.get("emotional_weight"),
            "valence": row.get("valence"),
            "certainty": row.get("certainty"),
            "source": row.get("source"),
            "created_at": created_at.isoformat() if created_at else None,
            "lifespan_stage": row.get("lifespan_stage") or "",
            "crisis": row.get("crisis") or "",
            "virtue": row.get("virtue") or "",
            "relations": row.get("relations") or "",
            "relation_circles": row.get("relation_circles") or "",
            "modality": row.get("modality") or "",
            # Serialized, matching add_memory's writer and the orjson.loads()
            # in the Qdrant read path.
            "custom_metadata": orjson.dumps(raw_meta or {}).decode(),
        }

    async def _promote_archived_rows(
        self,
        scored_archive_rows,
        matched_cues,
        *,
        threshold,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
    ) -> list:
        """Promote qualifying archived rows to the active tier and return them."""
        promoted_results = []
        for _ranking_score, score, similarity, row in scored_archive_rows:
            content = row["content"]

            emb = self._parse_stored_embedding(row.get("embedding"))
            # Fallback to the embedding API if the archived row has none
            if not emb:
                emb = await self.get_embedding(content)
                if not emb:
                    continue

            (
                _score,
                spread_activation,
                dist_emo,
                recall_count,
                now,
            ) = self._archive_row_activation(
                row,
                similarity,
                current_valence=current_valence,
                current_arousal=current_arousal,
                current_cortisol=current_cortisol,
                current_time=current_time,
            )

            # Only promote if it passes the threshold or is a milestone memory
            if not (
                score > (threshold - 2.5)
                or (row.get("importance_score") or 0.5) >= 0.7
            ):
                continue

            mem_id = str(row.get("id") or uuid.uuid4())
            raw_meta = row.get("metadata")
            if isinstance(raw_meta, str):
                try:
                    raw_meta = json.loads(raw_meta)
                except Exception:
                    raw_meta = {}
            elif not isinstance(raw_meta, dict):
                raw_meta = {}

            payload_meta = self._build_promotion_payload(row, raw_meta)

            try:
                await self._write_promoted_memory(
                    mem_id,
                    content,
                    row,
                    emb,
                    recall_count,
                    now,
                    payload_meta,
                    sql_meta=raw_meta,
                )
            except Exception as prom_err:
                # The move did not persist, so this memory is still archived.
                # Returning it anyway surfaced a result the next turn could not
                # find again, and cached it as though it were active.
                logger.error(f"Failed to promote memory {mem_id}: {prom_err}")
                continue

            created = self._as_aware_utc(row.get("created_at"))

            # Rescore as an active memory: recall_count was incremented on
            # promotion and last_recalled_at is now, so recency is ~0.
            base_activation_active = self._base_activation(
                recall_count + 1, 0.001, row.get("importance_score") or 0.5, dist_emo
            )
            score_active = (
                base_activation_active
                + spread_activation
                - ACTR_EMO_DISTANCE_PENALTY * dist_emo
            )
            # Apply direct cue boost since it was promoted for keyword matches
            match_count = sum(1 for mc in matched_cues if mc in content.lower())
            score_active += DIRECT_CUE_BOOST * match_count

            promoted_results.append(
                {
                    "content": content,
                    "raw_content": row.get("raw_content") or content,
                    "wing": row.get("wing", "personal"),
                    "room": row.get("room"),
                    "score": score_active,
                    "valence": row.get("valence") or 0.0,
                    "created_at": created.isoformat() if created else None,
                    "recall_count": recall_count + 1,
                    "metadata": raw_meta or {},
                    "lifespan_stage": row.get("lifespan_stage"),
                    "crisis": row.get("crisis"),
                    "virtue": row.get("virtue"),
                    "relations": row.get("relations"),
                    "relation_circles": row.get("relation_circles"),
                    "modality": row.get("modality"),
                }
            )
        return promoted_results

    async def _recall_from_archive(
        self,
        *,
        query_words,
        dynamic_stop_words,
        matched_cues,
        resolved_cues,
        user_id,
        wing,
        vector_str,
        query_vector,
        existing_results,
        excluded,
        limit,
        threshold,
        current_valence,
        current_arousal,
        current_cortisol,
        current_time,
    ) -> list:
        """L3 sub-conscious search: surface archived memories and promote the best."""
        expanded_cues = self._expand_archive_cues(
            query_words, dynamic_stop_words, matched_cues, resolved_cues, user_id
        )
        archive_rows = await self._fetch_archive_rows(
            list(expanded_cues), wing, vector_str
        )
        if not archive_rows:
            return []

        active_contents = {res["content"] for res in existing_results}
        archive_rows = [
            r
            for r in archive_rows
            if r.get("content")
            and r["content"] not in active_contents
            and r["content"] not in excluded
        ]
        if not archive_rows:
            return []

        scored_archive_rows = await self._rank_archive_rows(
            archive_rows,
            expanded_cues,
            query_vector,
            limit=limit,
            current_valence=current_valence,
            current_arousal=current_arousal,
            current_cortisol=current_cortisol,
            current_time=current_time,
        )
        return await self._promote_archived_rows(
            scored_archive_rows,
            matched_cues,
            threshold=threshold,
            current_valence=current_valence,
            current_arousal=current_arousal,
            current_cortisol=current_cortisol,
            current_time=current_time,
        )

    async def search_memories(
        self,
        query_text,
        wing: str = "personal",
        room: str | None = None,
        threshold=-1.5,
        limit=5,
        refresh_on_recall=True,
        exclude_contents: Iterable[str] | None = None,
        current_valence: float = 0.0,
        current_arousal: float = 0.5,
        current_cortisol: float = 0.0,
        user_id: str | None = None,
        is_self_reflection: bool = False,
        current_time=None,
        *,
        full_candidate_pool: bool | None = None,
    ):
        """
        ACT-R Based Retrieval with Hierarchical & Neuromodulatory Gating:
            Score = B_i + w_spread*Similarity_eff + w_emotion*EmotionalAlignment

        Filters results by 'wing' and optionally 'room' before scoring.

        The pipeline runs as: L1 cache -> embed + MRL gating -> candidate fetch
        (Qdrant, else SQL) -> lexical/graph cue analysis -> spreading-activation
        boosts -> threshold + format -> L3 archive promotion -> sort/limit.
        Each stage is a `_`-prefixed helper defined above.

        Args:
            full_candidate_pool: How wide a candidate pool to gather, when the
                agent is not stressed. Defaults to `refresh_on_recall`, which is
                how this has always been decided -- but the two are different
                properties that happened to coincide, and reading one off the
                other silently narrows the search for anyone who wants the
                counters left alone. Pass it explicitly to say which you mean.
        """
        # L1 Cache lookup to bypass DB and math activation loops for active topics
        cache_key = (
            query_text,
            wing,
            room,
            threshold,
            limit,
            current_valence,
            current_arousal,
            current_cortisol,
            tuple(sorted(exclude_contents or [])),
            user_id,
            # Pronoun cues resolve in opposite directions depending on this flag
            # ("I"/"my" bind to the agent when self-reflecting, to the user
            # otherwise), so the two modes must not share a cache entry.
            is_self_reflection,
            current_time.isoformat() if current_time is not None else None,
        )
        now_ts = current_time.timestamp() if current_time is not None else time.time()
        if cache_key in self._l1_cache:
            ts, cached_results = self._l1_cache[cache_key]
            if now_ts - ts < self._l1_cache_ttl:
                self._l1_cache.move_to_end(cache_key)
                if cached_results and refresh_on_recall:
                    await self._refresh_memories(
                        cached_results,
                        current_valence=current_valence,
                        current_time=current_time,
                    )
                return cached_results

        try:
            # Periodically refresh database-derived stop words (TTL = 5 minutes)
            if (
                not hasattr(self, "_last_stop_words_update")
                or now_ts - self._last_stop_words_update > 300.0
            ):
                await self._update_dynamic_stop_words()
                # Reload the learned-vocabulary association cache on the same
                # cadence (first call also creates tables + plants the seed).
                await self.lexicon.refresh()
                self._last_stop_words_update = now_ts

            query_vector = await self.get_embedding(query_text)
            if not query_vector:
                return []

            mrl_dim, candidate_limit = self._compute_mrl_gating(
                current_arousal,
                current_cortisol,
                limit,
                refresh_on_recall
                if full_candidate_pool is None
                else full_candidate_pool,
            )

            # Slice query_vector to mrl_dim and pad with zeros to 768
            mrl_query_vector = list(query_vector)
            for i in range(mrl_dim, len(mrl_query_vector)):
                mrl_query_vector[i] = 0.0

            self._detect_topic_shift(query_vector)

            vector_str = str(mrl_query_vector)
            excluded = {content for content in (exclude_contents or []) if content}
            is_sqlite = self.is_sqlite

            # Concurrently fetch vector candidates and Neo4j graph data
            (
                candidates,
                entity_records,
                relation_records,
            ) = await self._gather_candidate_sources(mrl_query_vector, candidate_limit)

            # 1. Qdrant Selective Vector Path
            raw_candidates = []
            if self.qdrant_store.client and candidates:
                raw_candidates = await self._score_qdrant_candidates(
                    candidates,
                    wing=wing,
                    room=room,
                    excluded=excluded,
                    threshold=threshold,
                    current_valence=current_valence,
                    current_arousal=current_arousal,
                    current_cortisol=current_cortisol,
                    current_time=current_time,
                    now_ts=now_ts,
                )

            # 2. Database Fallback (Qdrant offline or returned no candidates)
            if not raw_candidates:
                async with self.pool.acquire() as conn:
                    if is_sqlite:
                        # The SQLite path recomputes "now"; keep its value, it is
                        # what stamps the L1 cache entry below.
                        raw_candidates, now_ts = await self._fetch_sqlite_candidates(
                            conn,
                            query_vector=query_vector,
                            wing=wing,
                            room=room,
                            excluded=excluded,
                            threshold=threshold,
                            current_valence=current_valence,
                            current_arousal=current_arousal,
                            current_cortisol=current_cortisol,
                            current_time=current_time,
                            candidate_limit=candidate_limit,
                        )
                    else:
                        raw_candidates = await self._fetch_postgres_candidates(
                            conn,
                            vector_str=vector_str,
                            wing=wing,
                            room=room,
                            excluded=excluded,
                            threshold=threshold,
                            candidate_limit=candidate_limit,
                            current_valence=current_valence,
                            current_arousal=current_arousal,
                            current_cortisol=current_cortisol,
                            current_time=current_time,
                        )

            # 3. Post-process in Python: direct cue boost + spreading activation
            query_words = re.findall(r"\b\w{3,}\b", query_text.lower())
            dynamic_stop_words = self._resolve_dynamic_stop_words(user_id)
            matched_cues = [w for w in query_words if w not in dynamic_stop_words]
            self.goal_buffer.update_buffer(query_text, dynamic_stop_words)

            entity_names = []
            adj = {}
            cand_entities = {}
            agent_node_name = None
            user_node_name = None
            try:
                entity_names, adj, cand_entities = self._build_entity_graph(
                    entity_records, relation_records, raw_candidates
                )
                agent_node_name, user_node_name = self._resolve_identity_nodes(
                    entity_records, entity_names, adj, user_id
                )
            except Exception as e:
                logger.debug("Failed to process entities: %s", e)

            resolved_cues = self._resolve_pronoun_cues(
                query_text,
                agent_node_name,
                user_node_name,
                user_id,
                is_self_reflection,
            )
            for cue in resolved_cues:
                if cue not in matched_cues:
                    matched_cues.append(cue)

            direct_boosted_indices = self._apply_direct_cue_boost(
                raw_candidates, matched_cues
            )
            self._apply_ppr_spreading_activation(
                raw_candidates,
                entity_names,
                adj,
                matched_cues,
                direct_boosted_indices,
                agent_node_name,
                cand_entities,
            )
            self._apply_goal_buffer_boost(raw_candidates)

            # 4. Filter by final threshold, format and return results
            results = self._format_results(raw_candidates, threshold)

            # L3 Sub-conscious Search and Promotion
            if matched_cues:
                promoted_results = await self._recall_from_archive(
                    query_words=query_words,
                    dynamic_stop_words=dynamic_stop_words,
                    matched_cues=matched_cues,
                    resolved_cues=resolved_cues,
                    user_id=user_id,
                    wing=wing,
                    vector_str=vector_str,
                    query_vector=query_vector,
                    existing_results=results,
                    excluded=excluded,
                    limit=limit,
                    threshold=threshold,
                    current_valence=current_valence,
                    current_arousal=current_arousal,
                    current_cortisol=current_cortisol,
                    current_time=current_time,
                )
                if promoted_results:
                    results.extend(promoted_results)

            if results:
                # Sort and limit results to maintain full compatibility with offline tests
                results.sort(key=lambda x: x["score"], reverse=True)
                if limit:
                    results = results[:limit]

                logger.info(
                    f"\U0001f9e0 ACT-R Recall: {len(results)} memories for: '{query_text[:30]}...'"
                )

            if results and refresh_on_recall:

                def _done_callback(t):
                    try:
                        t.result()
                    except Exception as e:
                        logger.error(f"Background Memory Refresh Failed: {e}")

                # P4-8: spawn_background keeps a strong reference so this
                # task cannot be GC'd mid-refresh; _done_callback is chained
                # after it purely for the existing error-logging behavior.
                task = spawn_background(
                    self._background_tasks,
                    self._refresh_memories(
                        results,
                        current_valence=current_valence,
                        current_time=current_time,
                    ),
                )
                task.add_done_callback(_done_callback)

            # Cache results in L1 memory cache before returning
            self._l1_cache_put(cache_key, (now_ts, results))
            return results

        except Exception as e:
            import traceback

            traceback.print_exc()
            logger.error(f"Memory search failed: {e}")
            return []


    async def _refresh_memories(
        self, memories: list[dict], current_valence: float = 0.0, current_time=None
    ):
        """
        Updates last_recalled_at and increments recall_count (ACT-R frequency).
        This strengthens the base-level activation for recently accessed memories.
        Also performs emotional habituation / PTSD extinction decay under neutral/positive context.
        """
        try:
            contents = [
                memory["content"] for memory in memories if memory.get("content")
            ]
            if not contents:
                return
            async with self.pool.acquire() as conn:
                if self.is_sqlite:
                    placeholders = ",".join("?" for _ in contents)
                    try:
                        if current_time is not None:
                            params = [
                                current_time,
                                current_valence,
                                current_valence,
                            ] + contents
                            time_placeholder = "?"
                        else:
                            params = [current_valence, current_valence] + contents
                            time_placeholder = "CURRENT_TIMESTAMP"

                        await conn.execute(
                            f"""
                            UPDATE memories
                            SET last_recalled_at = {time_placeholder},
                                 recall_count = recall_count + 1,
                                 emotional_weight = CASE
                                     WHEN valence < -0.4 AND ? >= 0.0 THEN emotional_weight * 0.95
                                     ELSE emotional_weight
                                 END,
                                 importance_score = CASE
                                     WHEN valence < -0.4 AND ? >= 0.0 THEN importance_score * 0.98
                                     ELSE importance_score
                                 END
                            WHERE content IN ({placeholders})
                            """,
                            *params,
                        )
                    except Exception as sq_err:
                        logger.warning(
                            f"Decay refresh failed, falling back to legacy: {sq_err}"
                        )
                        if current_time is not None:
                            await conn.execute(
                                f"""
                                UPDATE memories
                                SET last_recalled_at = ?,
                                     recall_count = recall_count + 1
                                WHERE content IN ({placeholders})
                                """,
                                current_time,
                                *contents,
                            )
                        else:
                            await conn.execute(
                                f"""
                                UPDATE memories
                                SET last_recalled_at = CURRENT_TIMESTAMP,
                                     recall_count = recall_count + 1
                                WHERE content IN ({placeholders})
                                """,
                                *contents,
                            )
                else:
                    try:
                        if current_time is not None:
                            await conn.execute(
                                """
                                UPDATE memories
                                SET last_recalled_at = $3,
                                     recall_count = recall_count + 1,
                                     emotional_weight = CASE
                                         WHEN valence < -0.4 AND $2 >= 0.0 THEN emotional_weight * 0.95
                                         ELSE emotional_weight
                                     END,
                                     importance_score = CASE
                                         WHEN valence < -0.4 AND $2 >= 0.0 THEN importance_score * 0.98
                                         ELSE importance_score
                                     END
                                WHERE content = ANY($1)
                                """,
                                contents,
                                current_valence,
                                current_time,
                            )
                        else:
                            await conn.execute(
                                """
                                UPDATE memories
                                SET last_recalled_at = CURRENT_TIMESTAMP,
                                     recall_count = recall_count + 1,
                                     emotional_weight = CASE
                                         WHEN valence < -0.4 AND $2 >= 0.0 THEN emotional_weight * 0.95
                                         ELSE emotional_weight
                                     END,
                                     importance_score = CASE
                                         WHEN valence < -0.4 AND $2 >= 0.0 THEN importance_score * 0.98
                                         ELSE importance_score
                                     END
                                WHERE content = ANY($1)
                                """,
                                contents,
                                current_valence,
                            )
                    except Exception as pg_err:
                        logger.warning(
                            f"Decay refresh failed, falling back to legacy: {pg_err}"
                        )
                        if current_time is not None:
                            await conn.execute(
                                """
                                UPDATE memories
                                SET last_recalled_at = $2,
                                     recall_count = recall_count + 1
                                WHERE content = ANY($1)
                                """,
                                contents,
                                current_time,
                            )
                        else:
                            await conn.execute(
                                """
                                UPDATE memories
                                SET last_recalled_at = CURRENT_TIMESTAMP,
                                     recall_count = recall_count + 1
                                WHERE content = ANY($1)
                                """,
                                contents,
                            )
        except Exception as e:
            logger.error(f"Failed to refresh memories: {e}")

    async def get_recent_unconsolidated_episodes(self, limit: int = 10):
        """Fetches recent user and assistant dialogue entries from messages for consolidation within 24 hours."""
        try:
            async with self.pool.acquire() as conn:
                if self.is_sqlite:
                    rows = await conn.fetch(
                        "SELECT id, role, content, timestamp FROM messages WHERE consolidated = 0 AND role != 'system' AND timestamp >= datetime('now', '-24 hours') ORDER BY timestamp DESC LIMIT ?",
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT id, role, content, timestamp FROM messages WHERE consolidated = FALSE AND role != 'system' AND timestamp >= NOW() - INTERVAL '24 hours' ORDER BY timestamp DESC LIMIT $1",
                        limit,
                    )
                return rows
        except Exception as e:
            logger.error(f"Failed to fetch recent episodes: {e}")
            return []

    async def mark_episodes_consolidated(self, message_ids: list[str]):
        """Marks specific dialogue messages as consolidated to avoid duplicate processing."""
        if not message_ids:
            return
        try:
            async with self.pool.acquire() as conn:
                where, args = self._in_predicate("id", message_ids)
                # `1` vs `TRUE` stays a dialect literal: a Postgres boolean
                # column will not accept the integer, so this is a real
                # difference rather than noise the helper should absorb.
                truth = "1" if self.is_sqlite else "TRUE"
                await conn.execute(
                    f"UPDATE messages SET consolidated = {truth} WHERE {where}",
                    *args,
                )
        except Exception as e:
            logger.error(f"Failed to mark episodes consolidated: {e}")

    async def apply_actr_decay(self, memory_contents: list[str], current_time=None):
        """Decays the importance score of consolidated raw episodic memories using ACT-R feedback."""
        import json

        try:
            if not memory_contents:
                return

            # Deduplicate memory contents to prevent repeated decay updates in SQLite loop
            unique_contents = list(dict.fromkeys(memory_contents))

            async with self.pool.acquire() as conn:
                # 1. Fetch matching memories
                where, args = self._in_predicate("content", unique_contents)
                rows = await conn.fetch(
                    "SELECT id, content, recall_count, created_at, metadata, "
                    f"importance_score FROM memories WHERE {where}",
                    *args,
                )

                if not rows:
                    return

                to_delete = []
                to_update = []

                for row in rows:
                    mem_id = row.get("id")
                    recall_count = row.get("recall_count")
                    created_at = row.get("created_at")
                    metadata = row.get("metadata")
                    importance_score = row.get("importance_score") or 0.5

                    # Fallbacks
                    n_recalls = max(1, recall_count if recall_count is not None else 1)

                    # Parse created_at safely
                    if not created_at:
                        created_at = (
                            current_time if current_time is not None else datetime.now()
                        )

                    if isinstance(created_at, str):
                        for fmt in (
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S.%f",
                            "%Y-%m-%dT%H:%M:%S.%f",
                        ):
                            try:
                                dt = datetime.strptime(created_at.split("+")[0], fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            dt = (
                                current_time
                                if current_time is not None
                                else datetime.now()
                            )
                    else:
                        dt = created_at

                    # Calculate hours since creation. Coerce both operands to
                    # aware-UTC so a naive stored created_at and an aware
                    # current_time (or vice versa) never raise on subtraction.
                    now = (
                        self._as_aware_utc(current_time)
                        if current_time is not None
                        else datetime.now(UTC)
                    )
                    delta = now - (self._as_aware_utc(dt) or now)
                    hours_since = max(0.0, delta.total_seconds() / 3600.0)

                    # Extract decay_rate from metadata if possible
                    meta = {}
                    if isinstance(metadata, str):
                        try:
                            meta = json.loads(metadata)
                        except Exception:
                            pass
                    elif isinstance(metadata, dict):
                        meta = metadata

                    decay_rate = (
                        float(meta.get("decay_rate", self.decay_rate))
                        if meta
                        else self.decay_rate
                    )

                    # Shield recent memories created in the last 24 hours from pruning (deletion)
                    is_shielded = hours_since < 24.0

                    # Milestones (importance >= 0.7) are protected from active importance decay,
                    # but they are allowed to decay and be pruned to the archive when inactive.
                    activation = math.log(n_recalls) - decay_rate * math.log(
                        hours_since + 1.0
                    )

                    # Dual-threshold active pruning:
                    # Distractors (< 0.5) pruned below -3.5, Anecdotes/Milestones (>= 0.5) pruned below -4.5
                    threshold = -3.5 if importance_score < 0.5 else -4.5
                    if activation < threshold and not is_shielded:
                        to_delete.append(mem_id)
                    elif importance_score < 0.7:
                        # Decay importance score slightly for non-milestones
                        new_importance = max(0.01, importance_score * 0.8)
                        to_update.append((new_importance, mem_id))

                # 2. Execute Archiving, Deletions and Updates
                if to_delete:
                    if self.is_sqlite:
                        placeholders = ",".join("?" for _ in to_delete)
                        # Copy to archived_memories
                        await conn.execute(
                            f"""
                            INSERT INTO archived_memories (
                                id, content, raw_content, wing, room, importance_score, emotional_weight,
                                valence, certainty, source, recall_count, last_recalled_at, created_at,
                                metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality, embedding
                            )
                            SELECT
                                id, content, raw_content, wing, room, importance_score, emotional_weight,
                                valence, certainty, source, recall_count, last_recalled_at, created_at,
                                metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality, embedding
                            FROM memories
                            WHERE id IN ({placeholders})
                            ON CONFLICT(id) DO UPDATE SET
                                recall_count = excluded.recall_count,
                                last_recalled_at = excluded.last_recalled_at,
                                importance_score = excluded.importance_score
                            """,
                            *to_delete,
                        )
                        # Delete from memories
                        await conn.execute(
                            f"DELETE FROM memories WHERE id IN ({placeholders})",
                            *to_delete,
                        )
                    else:
                        # Copy to archived_memories
                        await conn.execute(
                            """
                            INSERT INTO archived_memories (
                                id, content, raw_content, wing, room, importance_score, emotional_weight,
                                valence, certainty, source, recall_count, last_recalled_at, created_at,
                                metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality, embedding
                            )
                            SELECT
                                id, content, raw_content, wing, room, importance_score, emotional_weight,
                                valence, certainty, source, recall_count, last_recalled_at, created_at,
                                metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality, embedding::halfvec
                            FROM memories
                            WHERE id = ANY($1)
                            ON CONFLICT(id) DO UPDATE SET
                                recall_count = EXCLUDED.recall_count,
                                last_recalled_at = EXCLUDED.last_recalled_at,
                                importance_score = EXCLUDED.importance_score
                            """,
                            to_delete,
                        )
                        # Delete from memories
                        await conn.execute(
                            "DELETE FROM memories WHERE id = ANY($1)", to_delete
                        )

                    # Delete from Qdrant if active
                    if self.qdrant_store and self.qdrant_store.client:
                        try:
                            from qdrant_client.http import models

                            await asyncio.to_thread(
                                self.qdrant_store.client.delete,
                                collection_name=self.qdrant_store.collection_name,
                                points_selector=models.PointIdsList(
                                    points=[str(pid) for pid in to_delete]
                                ),
                            )
                        except Exception as qe:
                            logger.error(f"Failed to delete points from Qdrant: {qe}")

                    logger.info(
                        f"🗑️ Pruned {len(to_delete)} memories with base activation below {self.pruning_threshold} to subconscious archive."
                    )

                if to_update:
                    if self.is_sqlite:
                        for importance, mem_id in to_update:
                            await conn.execute(
                                "UPDATE memories SET importance_score = ? WHERE id = ?",
                                importance,
                                mem_id,
                            )
                    else:
                        # Batch update for PostgreSQL
                        await conn.executemany(
                            "UPDATE memories SET importance_score = $1 WHERE id = $2",
                            to_update,
                        )

                # 3. Permanent Cleanup on archived_memories based on biological timelines
                now_cleanup = (
                    current_time
                    if current_time is not None
                    else datetime.now(UTC)
                )
                cutoff_distractors = now_cleanup - timedelta(days=30)
                cutoff_anecdotes = now_cleanup - timedelta(days=180)
                cutoff_milestones = now_cleanup - timedelta(days=720)

                try:
                    # COALESCE(last_recalled_at, created_at): a memory that was
                    # archived but never recalled has NULL last_recalled_at, and
                    # `NULL < cutoff` is NULL (never true) -- such rows would be
                    # immortal in the archive. Age them out by creation time
                    # instead, matching how the activation SQL already coalesces
                    # this column (db/schema.sql).
                    if self.is_sqlite:
                        # Normalise both operands through datetime(): the SQLite
                        # fallback stores timestamps as text, so a raw string
                        # comparison of differing ISO formats/precision/offsets
                        # is unreliable. datetime() canonicalises to UTC.
                        await conn.execute(
                            """
                            DELETE FROM archived_memories
                            WHERE (importance_score < 0.5 AND datetime(COALESCE(last_recalled_at, created_at)) < datetime(?))
                               OR (importance_score >= 0.5 AND importance_score < 0.7 AND datetime(COALESCE(last_recalled_at, created_at)) < datetime(?))
                               OR (importance_score >= 0.7 AND importance_score < 0.9 AND datetime(COALESCE(last_recalled_at, created_at)) < datetime(?));
                            """,
                            cutoff_distractors.isoformat(),
                            cutoff_anecdotes.isoformat(),
                            cutoff_milestones.isoformat(),
                        )
                    else:
                        await conn.execute(
                            """
                            DELETE FROM archived_memories
                            WHERE (importance_score < 0.5 AND COALESCE(last_recalled_at, created_at) < $1)
                               OR (importance_score >= 0.5 AND importance_score < 0.7 AND COALESCE(last_recalled_at, created_at) < $2)
                               OR (importance_score >= 0.7 AND importance_score < 0.9 AND COALESCE(last_recalled_at, created_at) < $3);
                            """,
                            cutoff_distractors,
                            cutoff_anecdotes,
                            cutoff_milestones,
                        )
                    logger.info(
                        "🗑️ Completed permanent cleanup on subconscious archived memories."
                    )
                except Exception as clean_err:
                    logger.error(f"Failed subconscious archive cleanup: {clean_err}")

            # Pruning and importance decay change what search over the active
            # `memories` table should return, so drop the L1 cache when either
            # actually mutated rows. (Archive cleanup alone touches only
            # archived_memories, which the cached search path never reads.)
            if to_delete or to_update:
                self._invalidate_l1_cache()

            logger.info(
                f"📉 Checked and decayed {len(rows)} memories (pruned: {len(to_delete)})."
            )
        except Exception as e:
            logger.error(f"Failed to apply ACT-R decay pruning: {e}")

    async def close(self):
        """Close the persistent HTTP client."""
        await self._http_client.aclose()
