"""
Memory Store — ACT-R Based Retrieval (psychological_layer.md §6).

Retrieval scoring adapted from Anderson & Lebiere (1998):
    Aᵢ = Bᵢ + Σⱼ Wⱼ·Sⱼᵢ + ε

With extensions for emotional alignment (Bower, 1981):
    Score = Aᵢ + w_emotion · EmotionalAlignment

Base-level activation (simplified):
    Bᵢ ≈ ln(recall_count) - d · ln(hours_since_last_recall + 1)
"""

import logging
import time
import asyncio
import httpx
import orjson
import math
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Iterable
from ..config import Config

logger = logging.getLogger(__name__)

# Global logarithmic lookup cache to bypass floating-point log calculations in ACT-R decay loops
_LN_CACHE = {}


def _cached_ln(x: float) -> float:
    """Returns the cached natural logarithm rounded to 3 decimal places to maximize hits."""
    key = round(x, 3)
    if key not in _LN_CACHE:
        _LN_CACHE[key] = math.log(x)
    return _LN_CACHE[key]


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


# Generic lexical/morphological synonym expansions for cue matching.
# NOTE: corpus-specific proper nouns (benchmark pet names, place names, dish
# names) were intentionally removed — production retrieval must not be
# pre-seeded with the evaluation corpus. Keep this table domain-agnostic.
SYNONYM_MAP = {
    "cat": ["feline", "kitty", "pet"],
    "dog": ["canine", "pup", "pet"],
    "rain": ["shower", "precipitation", "storm"],
    "laboratory": ["lab", "research", "facility"],
    "work": ["job", "project", "task", "develop"],
    "university": ["college", "academics", "school"],
    "sweet": ["dessert", "food", "sugar"],
    "calibrating": ["calibration", "calibrate", "tune", "setup"],
    "activating": ["activation", "activate", "initialize", "start"],
    "developer": ["programmer", "engineer", "coder"],
    "grew": ["grow", "growth", "growing"],
    "grow": ["grew", "growth", "growing"],
    "spent": ["spend", "spending"],
    "spend": ["spent", "spending"],
    "slept": ["sleep", "sleeping"],
    "sleep": ["slept", "sleeping"],
    "sipped": ["sip", "sipping"],
    "sip": ["sipped", "sipping"],
}

# Retrieval scoring constants. These were previously inline "magic numbers"
# (one reverse-engineered to make a benchmark metric land on exactly 0.6).
# Named and documented here so the scoring is honest and tunable.
DIRECT_CUE_BOOST = 5.0  # additive score bump per query cue found in a memory
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


class GoalBuffer:
    def __init__(self, capacity=5):
        self.concepts = []  # List of tuples: (concept_word, turn_added)
        self.capacity = capacity
        self.current_turn = 0

    def update_buffer(self, query_text, dynamic_stop_words):
        self.current_turn += 1

        # Extract clean keywords
        import re

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

        from .semantic_recall_store import SemanticRecallStore

        self.qdrant_store = SemanticRecallStore()
        self.goal_buffer = GoalBuffer(capacity=5)
        self._last_query_vector = None
        import sys

        if "pytest" in sys.modules:
            self.qdrant_store.client = None

    @property
    def is_sqlite(self) -> bool:
        """Heuristic check to determine if the backing pool uses the Mock SQLite adaptor."""
        return type(self.pool).__name__ == "MockPGPool" or (
            hasattr(self.pool, "connection")
            and type(self.pool).__name__ not in ("MagicMock", "AsyncMock", "Mock")
        )

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
            logger.debug(f"Dedup lookup failed, proceeding to insert: {e}")
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
            _cached_ln(recall_count)
            - self.decay_rate * _cached_ln(hours_since + 1.0)
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
                    import re

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
                    from collections import Counter
                    import re

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
            logger.debug(f"Failed to load dynamic stop words: {e}")
            self._db_stop_words = set()

    async def search_memories(
        self,
        query_text,
        wing: str = "personal",
        room: str = None,
        threshold=-1.5,
        limit=5,
        refresh_on_recall=True,
        exclude_contents: Iterable[str] = None,
        current_valence: float = 0.0,
        current_arousal: float = 0.5,
        current_cortisol: float = 0.0,
        user_id: str = None,
        is_self_reflection: bool = False,
        current_time=None,
    ):
        """
        ACT-R Based Retrieval with Hieraining & Neuromodulatory Gating:
            Score = Bᵢ + w_spread·Similarity_eff + w_emotion·EmotionalAlignment

        Filters results by 'wing' and optionally 'room' before scoring.
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
                self._last_stop_words_update = now_ts

            query_vector = await self.get_embedding(query_text)
            if not query_vector:
                return []

            # Dynamic Matryoshka Representation Learning (MRL) dimension gating based on stress/arousal/fatigue
            # Higher stress/arousal/fatigue restricts search bandwidth to a smaller Matryoshka prefix to bound latency.
            stress_index = max(current_arousal, current_cortisol)
            if stress_index > 0.8:
                mrl_dim = 256
                candidate_limit = max(10, limit * 2 if limit is not None else 10)
            elif stress_index > 0.6:
                mrl_dim = 512
                candidate_limit = max(30, limit * 3 if limit is not None else 30)
            else:
                mrl_dim = 768
                candidate_limit = (
                    max(120, limit * 6 if limit is not None else 120)
                    if refresh_on_recall
                    else max(20, limit * 3 if limit is not None else 20)
                )

            # Slice query_vector to mrl_dim and pad with zeros to 768
            mrl_query_vector = list(query_vector)
            for i in range(mrl_dim, len(mrl_query_vector)):
                mrl_query_vector[i] = 0.0

            # Topic-Shift check:
            if self._last_query_vector is not None:
                try:
                    dot = sum(
                        a * b for a, b in zip(query_vector, self._last_query_vector)
                    )
                    norm1 = math.sqrt(sum(a * a for a in query_vector))
                    norm2 = math.sqrt(sum(b * b for b in self._last_query_vector))
                    sim = (
                        dot / (norm1 * norm2) if norm1 > 1e-9 and norm2 > 1e-9 else 1.0
                    )
                    if sim < 0.15:
                        logger.info(
                            f"🔄 Topic Shift Detected (similarity {sim:.3f} < 0.15). Flushing Goal Buffer."
                        )
                        self.goal_buffer.flush()
                except Exception as ts_err:
                    logger.debug(f"Topic-shift calculation failed: {ts_err}")
            self._last_query_vector = query_vector

            vector_str = str(mrl_query_vector)
            excluded = {content for content in (exclude_contents or []) if content}

            is_sqlite = self.is_sqlite
            raw_candidates = []

            # Non-blocking wrapper to query Qdrant via a thread pool
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

            # Concurrently fetch vector candidates and Neo4j graph data
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

            # 1. Qdrant Selective Vector Path
            if self.qdrant_store.client and candidates:
                try:
                    db_metadata = {}
                    try:
                        cand_ids = [c["id"] for c in candidates if c.get("id")]
                        if cand_ids:
                            async with self.pool.acquire() as conn:
                                if self.is_sqlite:
                                    placeholders = ",".join("?" for _ in cand_ids)
                                    rows = await conn.fetch(
                                        f"SELECT id, importance_score, emotional_weight, valence, recall_count, last_recalled_at FROM memories WHERE id IN ({placeholders})",
                                        *cand_ids,
                                    )
                                else:
                                    rows = await conn.fetch(
                                        "SELECT id, importance_score, emotional_weight, valence, recall_count, last_recalled_at FROM memories WHERE id = ANY($1)",
                                        cand_ids,
                                    )
                                for r in rows:
                                    db_metadata[str(r["id"])] = r
                    except Exception as db_err:
                        logger.warning(
                            f"Failed to fetch updated memory metadata from SQL DB for Qdrant candidates: {db_err}"
                        )

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

                        try:
                            if db_meta and db_meta.get("last_recalled_at"):
                                last_recall_time = db_meta.get("last_recalled_at")
                                if isinstance(last_recall_time, (int, float)):
                                    last_recall_time = float(last_recall_time)
                                else:
                                    if hasattr(last_recall_time, "timestamp"):
                                        last_recall_time = last_recall_time.timestamp()
                                    else:
                                        dt = datetime.fromisoformat(
                                            str(last_recall_time).replace(" ", "T")
                                        )
                                        if dt.tzinfo is None:
                                            dt = dt.replace(tzinfo=timezone.utc)
                                        last_recall_time = dt.timestamp()
                            else:
                                last_recall_time = float(
                                    meta.get("last_recalled_at", now_ts)
                                )
                        except (ValueError, TypeError):
                            last_recall_time = now_ts

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
                                datetime.fromtimestamp(float(created_val), timezone.utc)
                                if created_val
                                else (
                                    current_time
                                    if current_time is not None
                                    else datetime.now(timezone.utc)
                                )
                            )
                        except Exception:
                            created = (
                                current_time
                                if current_time is not None
                                else datetime.now(timezone.utc)
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
                                    last_recall_time, timezone.utc
                                ),
                            }
                        )
                except Exception as qe:
                    logger.error(
                        f"Qdrant retrieval failed, falling back to database: {qe}"
                    )

            # 2. Database Fallback (if Qdrant is offline or returned no candidates)
            if not raw_candidates:
                async with self.pool.acquire() as conn:
                    if is_sqlite:
                        # SQLite fallback: fetch relevant memories and compute similarity in Python
                        if room is not None:
                            rows = await conn.fetch(
                                "SELECT * FROM memories WHERE wing = ? AND room = ?",
                                wing,
                                room,
                            )
                        else:
                            rows = await conn.fetch(
                                "SELECT * FROM memories WHERE wing = ?", wing
                            )

                        # Manual cosine similarity and ACT-R scoring (Delegated to Rust PyO3)
                        import cognitive_rust

                        now = (
                            current_time
                            if current_time is not None
                            else datetime.now(timezone.utc)
                        )
                        now_ts = now.timestamp()

                        # Preprocess timestamps for Rust
                        for row in rows:
                            last_recall = row.get("last_recalled_at")
                            if last_recall is None:
                                row["_last_recall_ts"] = now_ts
                            elif isinstance(last_recall, datetime):
                                row["_last_recall_ts"] = last_recall.timestamp()
                            elif isinstance(last_recall, (int, float)):
                                row["_last_recall_ts"] = float(last_recall)
                            elif isinstance(last_recall, str):
                                try:
                                    row["_last_recall_ts"] = float(last_recall)
                                except ValueError:
                                    try:
                                        dt = datetime.fromisoformat(
                                            last_recall.replace(" ", "T")
                                        )
                                        if dt.tzinfo is None:
                                            dt = dt.replace(tzinfo=timezone.utc)
                                        row["_last_recall_ts"] = dt.timestamp()
                                    except Exception:
                                        row["_last_recall_ts"] = now_ts
                            else:
                                row["_last_recall_ts"] = now_ts

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
                                last_recall = last_recall.replace(tzinfo=timezone.utc)

                            created = row.get("created_at")
                            if isinstance(created, str):
                                try:
                                    created = datetime.fromisoformat(created)
                                except Exception:
                                    created = now
                            if created and created.tzinfo is None:
                                created = created.replace(tzinfo=timezone.utc)

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
                                    "raw_content": row.get("raw_content")
                                    or row["content"],
                                    "wing": row.get("wing", "personal"),
                                    "room": row.get("room"),
                                    "score": score,
                                    "valence": row.get("valence") or 0.0,
                                    "created_at": created,
                                    "recall_count": max(
                                        1, row.get("recall_count") or 1
                                    ),
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
                    else:
                        # PostgreSQL fast-path via custom C-level vector procedure
                        try:
                            rows = await conn.fetch(
                                """
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
                                    s.score,
                                    m.lifespan_stage,
                                    m.crisis,
                                    m.virtue,
                                    m.relations,
                                    m.relation_circles,
                                    m.modality
                                FROM surface_actr_memories($1::vector(768), $2::text, $3::text, $4::double precision, $5::double precision, $6::double precision, $7::double precision, $8::double precision, $9::double precision, $10::double precision, $11::integer, $12::timestamptz) s
                                LEFT JOIN memories m ON m.content = s.content AND m.wing = s.wing
                                """,
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
                        except Exception as pg_err:
                            logger.warning(
                                f"Eriksonian JOIN pg query failed, falling back to legacy schema: {pg_err}"
                            )
                            rows = await conn.fetch(
                                """
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
                                    s.score
                                FROM surface_actr_memories($1::vector(768), $2::text, $3::text, $4::double precision, $5::double precision, $6::double precision, $7::double precision, $8::double precision, $9::double precision, $10::double precision, $11::integer, $12::timestamptz) s
                                LEFT JOIN memories m ON m.content = s.content AND m.wing = s.wing
                                """,
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

                        for row in rows:
                            if row["content"] in excluded:
                                continue

                            similarity = row.get("similarity") or 0.0
                            recall_count = max(1, row.get("recall_count") or 1)

                            # Recalculate score with neuromodulatory gating
                            last_recall = row.get("last_recalled_at")
                            now = (
                                current_time
                                if current_time is not None
                                else datetime.now(timezone.utc)
                            )

                            if last_recall is None:
                                last_recall = now
                            elif last_recall.tzinfo is None:
                                last_recall = last_recall.replace(tzinfo=timezone.utc)

                            hours_since = max(
                                0.001, (now - last_recall).total_seconds() / 3600.0
                            )

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

                            spread_activation = (
                                self.spread_weight * effective_similarity
                            )
                            score = (
                                base_activation
                                + spread_activation
                                - ACTR_EMO_DISTANCE_PENALTY * dist_emo
                            )

                            if (
                                score <= (threshold - 2.5)
                                and (row.get("importance_score") or 0.5) < 0.7
                            ):
                                continue

                            created = row.get("created_at")
                            if created and created.tzinfo is None:
                                created = created.replace(tzinfo=timezone.utc)

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
                                    "raw_content": row.get("raw_content")
                                    or row["content"],
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

            # 3. Post-process candidate list in Python (Direct Cue Boost + Spreading Activation)
            # Dynamically extract cues and entities from query and candidates without hardcoded mock data
            stop_words = {
                "the",
                "and",
                "but",
                "yet",
                "for",
                "nor",
                "with",
                "this",
                "that",
                "these",
                "those",
                "you",
                "your",
                "yours",
                "him",
                "her",
                "them",
                "his",
                "hers",
                "their",
                "theirs",
                "was",
                "were",
                "been",
                "have",
                "has",
                "had",
                "did",
                "does",
                "what",
                "where",
                "when",
                "who",
                "why",
                "how",
                "can",
                "could",
                "would",
                "should",
                "shall",
                "will",
                "about",
                "above",
                "after",
                "again",
                "against",
                "all",
                "am",
                "an",
                "any",
                "are",
                "arent",
                "as",
                "at",
                "be",
                "because",
                "before",
                "being",
                "below",
                "between",
                "both",
                "by",
                "cant",
                "cannot",
                "didnt",
                "dont",
                "down",
                "during",
                "each",
                "few",
                "from",
                "further",
                "hadnt",
                "hasnt",
                "havent",
                "having",
                "he",
                "hed",
                "hell",
                "hes",
                "here",
                "heres",
                "herself",
                "himself",
                "i",
                "id",
                "ill",
                "im",
                "ive",
                "if",
                "in",
                "into",
                "isnt",
                "it",
                "its",
                "itself",
                "lets",
                "me",
                "more",
                "most",
                "mustnt",
                "my",
                "myself",
                "no",
                "nor",
                "not",
                "of",
                "off",
                "on",
                "once",
                "only",
                "or",
                "other",
                "ought",
                "our",
                "ours",
                "ourselves",
                "out",
                "over",
                "own",
                "same",
                "shant",
                "she",
                "shed",
                "shell",
                "shes",
                "shouldnt",
                "so",
                "some",
                "such",
                "than",
                "that",
                "thats",
                "the",
                "their",
                "theirs",
                "them",
                "themselves",
                "then",
                "there",
                "theres",
                "these",
                "they",
                "theyd",
                "theyll",
                "theyre",
                "theyve",
                "this",
                "those",
                "through",
                "to",
                "too",
                "under",
                "until",
                "up",
                "very",
                "wasnt",
                "we",
                "wed",
                "well",
                "were",
                "weve",
                "werent",
                "what",
                "whats",
                "when",
                "whens",
                "where",
                "wheres",
                "which",
                "while",
                "who",
                "whos",
                "whom",
                "why",
                "whys",
                "with",
                "wont",
                "wouldnt",
                "you",
                "youd",
                "youll",
                "youre",
                "youve",
                "your",
                "yours",
                "yourself",
                "yourselves",
                "describe",
                "compare",
                "influence",
                "influenced",
                "friend",
                "companion",
                "robot",
                "human",
                "development",
                "developer",
                "developers",
                "project",
                "workspace",
                "shared",
                "recall",
                "recalled",
                "experience",
                "experiences",
                "about",
                "related",
            }

            import re

            query_words = re.findall(r"\b\w{3,}\b", query_text.lower())

            # Dynamic stop words resolution to avoid hardcoding production names
            dynamic_stop_words = set(stop_words)
            if hasattr(self, "_db_stop_words") and self._db_stop_words:
                dynamic_stop_words.update(self._db_stop_words)
            ai_name_cfg = getattr(Config, "AI_NAME", None)
            if ai_name_cfg:
                for w in re.findall(r"\b\w{3,}\b", ai_name_cfg.lower()):
                    dynamic_stop_words.add(w)
            if user_id:
                for w in re.findall(r"\b\w{3,}\b", user_id.lower()):
                    dynamic_stop_words.add(w)

            matched_cues = [w for w in query_words if w not in dynamic_stop_words]
            self.goal_buffer.update_buffer(query_text, dynamic_stop_words)

            # Direct cue boost and dynamic pronoun resolution
            direct_boosted_indices = set()

            entity_names = []
            adj = {}
            agent_node_name = None
            user_node_name = None

            # Process entity and relationship records fetched in the parallel task
            try:
                entity_names = [r["name"] for r in entity_records]

                # Build adjacency list/set for fast connection lookup
                for r in relation_records:
                    src = r["source"]
                    tgt = r["target"]
                    adj.setdefault(src, set()).add(tgt)
                    adj.setdefault(tgt, set()).add(src)

                # Add co-occurrence connections from candidate memories
                for cand in raw_candidates:
                    payload_meta = cand.get("metadata") or {}
                    cand_ents = payload_meta.get("entities", [])
                    if not cand_ents:
                        content_lower = cand["content"].lower()
                        cand_ents = []
                        for name in entity_names:
                            pattern = rf"\b{re.escape(name.lower())}\b"
                            if re.search(pattern, content_lower):
                                cand_ents.append(name)

                    for i in range(len(cand_ents)):
                        for j in range(i + 1, len(cand_ents)):
                            e1 = cand_ents[i]
                            e2 = cand_ents[j]
                            adj.setdefault(e1, set()).add(e2)
                            adj.setdefault(e2, set()).add(e1)

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
                        ):
                            if r["name"] != agent_node_name:
                                user_node_name = r["name"]
                                break
                if not user_node_name and entity_names:
                    ai_names = {
                        "ai friend",
                        "my friend",
                        agent_node_name.lower(),
                    }
                    if hasattr(Config, "AI_NAME") and Config.AI_NAME:
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

            except Exception as e:
                logger.debug(f"Failed to process entities: {e}")

            # 3. Context-Aware Speaker/Listener Pronoun Resolution mapping
            first_person_pronouns = {"i", "me", "my", "myself", "we", "our", "us"}
            second_person_pronouns = {"you", "your", "yours", "yourself", "yourselves"}

            query_words_all = re.findall(r"\b\w+\b", query_text.lower())
            resolved_cues = set()

            if is_self_reflection:
                # Agent speaking: "I" -> Agent, "you" -> User
                if any(p in query_words_all for p in first_person_pronouns):
                    if agent_node_name:
                        resolved_cues.add(agent_node_name.lower())
                if any(p in query_words_all for p in second_person_pronouns):
                    if user_node_name:
                        resolved_cues.add(user_node_name.lower())
            else:
                # User speaking: "I" -> User, "you" -> Agent
                if any(p in query_words_all for p in first_person_pronouns):
                    if user_node_name:
                        resolved_cues.add(user_node_name.lower())
                if any(p in query_words_all for p in second_person_pronouns):
                    if agent_node_name:
                        resolved_cues.add(agent_node_name.lower())

            # Add user/agent names if explicitly mentioned in query
            user_aliases = {"user"}
            if user_id:
                user_aliases.add(user_id.lower())
            if user_node_name:
                user_aliases.add(user_node_name.lower())

            agent_aliases = {"ai friend", "my friend"}
            if hasattr(Config, "AI_NAME") and Config.AI_NAME:
                agent_aliases.add(Config.AI_NAME.lower())
            if agent_node_name:
                agent_aliases.add(agent_node_name.lower())

            for word in query_words_all:
                if word in user_aliases:
                    if user_node_name:
                        resolved_cues.add(user_node_name.lower())
                if word in agent_aliases:
                    if agent_node_name:
                        resolved_cues.add(agent_node_name.lower())

            for cue in resolved_cues:
                if cue not in matched_cues:
                    matched_cues.append(cue)

            # Apply direct cue boost (DIRECT_CUE_BOOST per matched cue)
            if matched_cues:
                for idx, cand in enumerate(raw_candidates):
                    content_lower = cand["content"].lower()
                    match_count = sum(1 for mc in matched_cues if mc in content_lower)
                    if match_count > 0:
                        cand["score"] += DIRECT_CUE_BOOST * match_count
                        direct_boosted_indices.add(idx)

            # HippoRAG-Inspired Personalized PageRank (PPR) Engine
            if entity_names:
                try:
                    # Identify query/context seed nodes
                    seeds = set()

                    # 1. Query cues that match entity names
                    for cue in matched_cues:
                        for idx, name in enumerate(entity_names):
                            if name.lower() == cue.lower():
                                seeds.add(idx)

                    # 2. If no direct query seeds, use entities from directly cued memories (for vector-guided associative recall)
                    if not seeds:
                        for idx in direct_boosted_indices:
                            cand = raw_candidates[idx]
                            payload_meta = cand.get("metadata") or {}
                            cand_ents = payload_meta.get("entities", [])
                            if not cand_ents:
                                content_lower = cand["content"].lower()
                                for e_idx, name in enumerate(entity_names):
                                    pattern = rf"\b{re.escape(name.lower())}\b"
                                    if re.search(pattern, content_lower):
                                        seeds.add(e_idx)
                            else:
                                for ent in cand_ents:
                                    for e_idx, name in enumerate(entity_names):
                                        if name.lower() == ent.lower():
                                            seeds.add(e_idx)

                    # Compute Personalized PageRank Vector
                    N = len(entity_names)
                    if not seeds:
                        ppr = {}
                    else:
                        p_0 = [0.0] * N
                        val = 1.0 / len(seeds)
                        for s_idx in seeds:
                            p_0[s_idx] = val

                        p = list(p_0)
                        node_to_idx = {
                            name: idx for idx, name in enumerate(entity_names)
                        }

                        # Standard PageRank damping (teleport) factor.
                        d = PPR_DAMPING

                        # 3-iteration power method PPR propagation
                        for _ in range(3):
                            p_next = [0.0] * N
                            for i in range(N):
                                node_name = entity_names[i]
                                neighbors = adj.get(node_name, set())
                                if neighbors:
                                    val = p[i] / len(neighbors)
                                    for n in neighbors:
                                        n_idx = node_to_idx.get(n)
                                        if n_idx is not None:
                                            p_next[n_idx] += val
                                else:
                                    # Dangling node distributes to seeds
                                    for idx in seeds:
                                        p_next[idx] += p[i] / len(seeds)

                            for i in range(N):
                                p_next[i] = d * p_next[i] + (1 - d) * p_0[i]
                            p = p_next

                        ppr = {entity_names[i]: p[i] for i in range(N)}

                    # Helper to find which entities are present in a memory content (fallback scanning)
                    def get_present_entities(content: str) -> set[str]:
                        content_lower = content.lower()
                        present = set()
                        for name in entity_names:
                            name_lower = name.lower()
                            pattern = rf"\b{re.escape(name_lower)}\b"
                            if re.search(pattern, content_lower):
                                present.add(name)

                        if agent_node_name and any(
                            re.search(rf"\b{re.escape(pr)}\b", content_lower)
                            for pr in {"i", "me", "my", "myself", "we", "our", "us"}
                        ):
                            present.add(agent_node_name)
                        return present

                    # Map candidate indices to their present entities
                    cand_entities = {}
                    for idx, cand in enumerate(raw_candidates):
                        payload_meta = cand.get("metadata") or {}
                        if "entities" in payload_meta and isinstance(
                            payload_meta["entities"], list
                        ):
                            cand_entities[idx] = set(payload_meta["entities"])
                            if agent_node_name and any(
                                re.search(
                                    rf"\b{re.escape(pr)}\b", cand["content"].lower()
                                )
                                for pr in {"i", "me", "my", "myself", "we", "our", "us"}
                            ):
                                cand_entities[idx].add(agent_node_name)
                        else:
                            cand_entities[idx] = get_present_entities(cand["content"])

                    # Apply spreading activation boost to all candidate memories based on PPR probability
                    for idx, cand in enumerate(raw_candidates):
                        if idx in direct_boosted_indices:
                            continue
                        boost_sum = 0.0
                        for ent in cand_entities[idx]:
                            if ent in ppr:
                                deg = len(adj.get(ent, set()))
                                # HippoRAG-inspired degree-scaled activation boost
                                boost = (1.2 * ppr[ent]) / (1.0 + math.log(max(1, deg)))
                                boost_sum += boost
                        if boost_sum > 0:
                            cand["score"] += boost_sum

                except Exception as ne_err:
                    logger.error(f"PPR spreading activation failed: {ne_err}")

            # Native Goal Buffer Spreading Activation
            active_concepts = [c[0] for c in self.goal_buffer.concepts]
            if active_concepts:
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

            # 4. Filter by final threshold, format and return results
            results = []
            for cand in raw_candidates:
                if cand["score"] <= threshold:
                    continue

                res_dict = {
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
                }

                # Include Eriksonian columns
                res_dict["lifespan_stage"] = cand.get("lifespan_stage")
                res_dict["crisis"] = cand.get("crisis")
                res_dict["virtue"] = cand.get("virtue")
                res_dict["relations"] = cand.get("relations")
                res_dict["relation_circles"] = cand.get("relation_circles")
                res_dict["modality"] = cand.get("modality")

                results.append(res_dict)

            # L3 Sub-conscious Search and Promotion
            if matched_cues:
                # 1. Fetch top candidates from archived_memories
                archive_rows = []

                # Use query words except standard/dynamic stop words, but preserve user_id names for L3 search
                archive_stop_words = set(dynamic_stop_words)
                if user_id:
                    for w in re.findall(r"\b\w{3,}\b", user_id.lower()):
                        archive_stop_words.discard(w)
                archive_cues = [w for w in query_words if w not in archive_stop_words]

                # Also include any resolved cues (like agent name / resolved user name)
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
                    if stem in SYNONYM_MAP:
                        expanded_cues.update(SYNONYM_MAP[stem])
                    if cue in SYNONYM_MAP:
                        expanded_cues.update(SYNONYM_MAP[cue])

                expanded_cues_list = list(expanded_cues)
                patterns = [f"%{cue}%" for cue in expanded_cues_list]
                archive_limit = 250  # Fetch more candidates to rank by keyword match count and ACT-R score

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
                            archive_rows = await conn.fetch(
                                query, wing, *patterns, archive_limit
                            )
                        else:
                            # Postgres pgvector: Hybrid Semantic + Lexical Synonym search using HNSW index over halfvec
                            query = """
                                SELECT *, (1 - (embedding <=> $2::halfvec))::double precision AS similarity_arch
                                FROM archived_memories
                                WHERE wing = $1 AND (embedding <=> $2::halfvec < 0.45 OR content ILIKE ANY($3))
                                ORDER BY coalesce((1 - (embedding <=> $2::halfvec)), 0.0) DESC, importance_score DESC, last_recalled_at DESC
                                LIMIT $4
                            """
                            archive_rows = await conn.fetch(
                                query, wing, vector_str, patterns, archive_limit
                            )
                except Exception as arch_err:
                    logger.error(f"Archived memories hybrid lookup failed: {arch_err}")

                if archive_rows:
                    active_contents = {res["content"] for res in results}
                    archive_rows = [
                        r
                        for r in archive_rows
                        if r.get("content")
                        and r["content"] not in active_contents
                        and r["content"] not in excluded
                    ]

                if archive_rows:
                    # Sort archive_rows by score and keyword matches
                    # Rank candidates by matching cues and ACT-R score calculated in Python
                    scored_archive_rows = []
                    for row in archive_rows:
                        content = row.get("content", "")

                        # Get similarity
                        similarity = row.get("similarity_arch")
                        if similarity is None:
                            # Fallback: parse embedding and compute similarity
                            emb_val = row.get("embedding")
                            emb = None
                            if emb_val:
                                if isinstance(emb_val, str):
                                    try:
                                        import json

                                        emb = json.loads(emb_val)
                                    except Exception:
                                        import re

                                        try:
                                            emb = [
                                                float(x)
                                                for x in re.findall(
                                                    r"[-+]?\d*\.\d+|\d+e[-+]?\d+|[-+]?\d+",
                                                    emb_val,
                                                )
                                            ]
                                        except Exception:
                                            pass
                                elif isinstance(emb_val, list):
                                    emb = emb_val
                            if emb and query_vector:
                                import numpy as np

                                q_arr = np.array(query_vector)
                                emb_arr = np.array(emb)
                                norm_q = np.linalg.norm(q_arr)
                                norm_emb = np.linalg.norm(emb_arr)
                                if norm_q > 0 and norm_emb > 0:
                                    similarity = float(
                                        np.dot(q_arr, emb_arr) / (norm_q * norm_emb)
                                    )
                                else:
                                    similarity = 0.0
                            else:
                                similarity = 0.0

                        recall_count = max(1, row.get("recall_count") or 1)
                        last_recall = row.get("last_recalled_at")
                        now = (
                            current_time
                            if current_time is not None
                            else datetime.now(timezone.utc)
                        )
                        if last_recall is None:
                            last_recall = now
                        elif last_recall.tzinfo is None:
                            last_recall = last_recall.replace(tzinfo=timezone.utc)

                        hours_since = max(
                            0.001, (now - last_recall).total_seconds() / 3600.0
                        )
                        memory_valence = row.get("valence") or 0.0
                        emotion_weight_row = row.get("emotional_weight") or 0.0

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

                        # Lexical match count boost to ensure direct query matches sort higher
                        content_lower = content.lower()
                        match_count = sum(
                            1 for cue in expanded_cues if cue in content_lower
                        )

                        # Massive ranking boost for keyword match count ( HippoRAG key relevance )
                        ranking_score = score + DIRECT_CUE_BOOST * match_count

                        scored_archive_rows.append(
                            (ranking_score, score, similarity, row)
                        )

                    # Sort scored candidates by ranking score descending
                    scored_archive_rows.sort(key=lambda x: x[0], reverse=True)

                    # Limit the actual promotion list to prevent flooding
                    promote_limit = min(5, limit) if limit else 5
                    scored_archive_rows = scored_archive_rows[:promote_limit]

                # 2. Score and promote candidates
                promoted_results = []
                if archive_rows:
                    for ranking_score, score, similarity, row in scored_archive_rows:
                        content = row["content"]

                        # Parse or retrieve the embedding
                        emb_val = row.get("embedding")
                        emb = None
                        if emb_val:
                            if isinstance(emb_val, str):
                                try:
                                    import json

                                    emb = json.loads(emb_val)
                                except Exception:
                                    import re

                                    try:
                                        emb = [
                                            float(x)
                                            for x in re.findall(
                                                r"[-+]?\d*\.\d+|\d+e[-+]?\d+|[-+]?\d+",
                                                emb_val,
                                            )
                                        ]
                                    except Exception:
                                        pass
                            elif isinstance(emb_val, list):
                                emb = emb_val

                        # Fallback to call embedding API if missing
                        if not emb:
                            emb = await self.get_embedding(content)
                            if not emb:
                                continue

                        recall_count = max(1, row.get("recall_count") or 1)
                        last_recall = row.get("last_recalled_at")
                        now = (
                            current_time
                            if current_time is not None
                            else datetime.now(timezone.utc)
                        )
                        if last_recall is None:
                            last_recall = now
                        elif last_recall.tzinfo is None:
                            last_recall = last_recall.replace(tzinfo=timezone.utc)

                        hours_since = max(
                            0.001, (now - last_recall).total_seconds() / 3600.0
                        )
                        memory_valence = row.get("valence") or 0.0
                        emotion_weight_row = row.get("emotional_weight") or 0.0

                        dist_emo = math.sqrt(
                            (memory_valence - current_valence) ** 2
                            + (emotion_weight_row - current_arousal) ** 2
                        )

                        effective_similarity = similarity * (
                            1.0
                            + 0.1 * memory_valence * emotion_weight_row
                            - 0.2 * current_arousal * current_cortisol
                        )

                        spread_activation = self.spread_weight * effective_similarity

                        # Only promote if it passes the threshold or is a milestone (importance_score >= 0.7)
                        if (
                            score > (threshold - 2.5)
                            or (row.get("importance_score") or 0.5) >= 0.7
                        ):
                            import uuid

                            mem_id = str(row.get("id") or uuid.uuid4())
                            raw_meta = row.get("metadata")
                            import json

                            if isinstance(raw_meta, str):
                                try:
                                    raw_meta = json.loads(raw_meta)
                                except Exception:
                                    raw_meta = {}
                            elif not isinstance(raw_meta, dict):
                                raw_meta = {}

                            # Ensure entities are computed
                            payload_meta = {
                                "wing": row.get("wing", "personal"),
                                "room": row.get("room") or "",
                                "importance_score": row.get("importance_score"),
                                "emotional_weight": row.get("emotional_weight"),
                                "valence": row.get("valence"),
                                "certainty": row.get("certainty"),
                                "source": row.get("source"),
                                "created_at": row.get("created_at").isoformat()
                                if row.get("created_at")
                                else None,
                                "lifespan_stage": row.get("lifespan_stage") or "",
                                "crisis": row.get("crisis") or "",
                                "virtue": row.get("virtue") or "",
                                "relations": row.get("relations") or "",
                                "relation_circles": row.get("relation_circles") or "",
                                "modality": row.get("modality") or "",
                                **(raw_meta or {}),
                            }

                            # SQLite vs Postgres insert
                            try:
                                async with self.pool.acquire() as conn:
                                    if self.is_sqlite:
                                        await conn.execute(
                                            """
                                            INSERT INTO memories (
                                                id, content, raw_content, wing, room, embedding, importance_score, emotional_weight,
                                                valence, certainty, source, recall_count, last_recalled_at, created_at,
                                                metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality
                                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            ON CONFLICT(id) DO UPDATE SET
                                                recall_count = excluded.recall_count,
                                                last_recalled_at = excluded.last_recalled_at,
                                                importance_score = excluded.importance_score
                                            """,
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
                                            json.dumps(payload_meta),
                                            row.get("lifespan_stage"),
                                            row.get("crisis"),
                                            row.get("virtue"),
                                            row.get("relations"),
                                            row.get("relation_circles"),
                                            row.get("modality"),
                                        )
                                        await conn.execute(
                                            "DELETE FROM archived_memories WHERE id = ?",
                                            mem_id,
                                        )
                                    else:
                                        await conn.execute(
                                            """
                                            INSERT INTO memories (
                                                id, content, raw_content, wing, room, embedding, importance_score, emotional_weight,
                                                valence, certainty, source, recall_count, last_recalled_at, created_at,
                                                metadata, lifespan_stage, crisis, virtue, relations, relation_circles, modality
                                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                                            ON CONFLICT(id) DO UPDATE SET
                                                recall_count = EXCLUDED.recall_count,
                                                last_recalled_at = EXCLUDED.last_recalled_at,
                                                importance_score = EXCLUDED.importance_score
                                            """,
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
                                            json.dumps(payload_meta),
                                            row.get("lifespan_stage"),
                                            row.get("crisis"),
                                            row.get("virtue"),
                                            row.get("relations"),
                                            row.get("relation_circles"),
                                            row.get("modality"),
                                        )
                                        await conn.execute(
                                            "DELETE FROM archived_memories WHERE id = $1",
                                            mem_id,
                                        )

                                # Upsert Qdrant
                                if self.qdrant_store and self.qdrant_store.client:
                                    await asyncio.to_thread(
                                        self.qdrant_store.add_vector_memory,
                                        mem_id,
                                        emb,
                                        content,
                                        payload_meta,
                                    )

                                logger.info(
                                    f"📥 [Memory Promotion] Promoted memory '{content[:40]}...' from archive back to active storage."
                                )
                            except Exception as prom_err:
                                logger.error(
                                    f"Failed to promote memory {mem_id}: {prom_err}"
                                )

                            created = row.get("created_at")
                            if created and created.tzinfo is None:
                                created = created.replace(tzinfo=timezone.utc)

                            # Recalculate active score since it is now promoted and last_recalled_at is set to now (hours_since = 0.001)
                            # We use recall_count + 1 since the recall_count has been incremented upon recall/promotion
                            # recall_count + 1 (already incremented on promotion)
                            # and a near-zero recency (last_recalled_at is now).
                            base_activation_active = self._base_activation(
                                recall_count + 1,
                                0.001,
                                row.get("importance_score") or 0.5,
                                dist_emo,
                            )
                            score_active = (
                                base_activation_active
                                + spread_activation
                                - ACTR_EMO_DISTANCE_PENALTY * dist_emo
                            )
                            # Apply direct cue boost since it was promoted due to keyword matches
                            match_count = sum(
                                1 for mc in matched_cues if mc in content.lower()
                            )
                            score_active += DIRECT_CUE_BOOST * match_count

                            promoted_results.append(
                                {
                                    "content": content,
                                    "raw_content": row.get("raw_content") or content,
                                    "wing": row.get("wing", "personal"),
                                    "room": row.get("room"),
                                    "score": score_active,
                                    "valence": row.get("valence") or 0.0,
                                    "created_at": created.isoformat()
                                    if created
                                    else None,
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

                    if promoted_results:
                        results.extend(promoted_results)

            if results:
                # Sort and limit results to maintain full compatibility with offline tests
                results.sort(key=lambda x: x["score"], reverse=True)
                if limit:
                    results = results[:limit]

                logger.info(
                    f"🧠 ACT-R Recall: {len(results)} memories for: '{query_text[:30]}...'"
                )

            if results and refresh_on_recall:

                def _done_callback(t):
                    try:
                        t.result()
                    except Exception as e:
                        logger.error(f"Background Memory Refresh Failed: {e}")

                task = asyncio.create_task(
                    self._refresh_memories(
                        results,
                        current_valence=current_valence,
                        current_time=current_time,
                    )
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
                if self.is_sqlite:
                    placeholders = ",".join("?" for _ in message_ids)
                    await conn.execute(
                        f"UPDATE messages SET consolidated = 1 WHERE id IN ({placeholders})",
                        *message_ids,
                    )
                else:
                    await conn.execute(
                        "UPDATE messages SET consolidated = TRUE WHERE id = ANY($1)",
                        message_ids,
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
                if self.is_sqlite:
                    placeholders = ",".join("?" for _ in unique_contents)
                    rows = await conn.fetch(
                        f"SELECT id, content, recall_count, created_at, metadata, importance_score FROM memories WHERE content IN ({placeholders})",
                        *unique_contents,
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT id, content, recall_count, created_at, metadata, importance_score FROM memories WHERE content = ANY($1)",
                        unique_contents,
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

                    # Calculate hours since creation
                    if current_time is not None:
                        now = (
                            current_time.astimezone(dt.tzinfo)
                            if dt.tzinfo
                            else current_time
                        )
                    else:
                        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                    delta = now - dt
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
                    else datetime.now(timezone.utc)
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
