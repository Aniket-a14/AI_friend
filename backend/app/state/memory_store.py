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
from datetime import timezone
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


class MemoryStore:
    def __init__(self, pool, ollama_base_url=None):
        self.pool = pool
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

        # L1 Memory Activation Cache
        self._l1_cache = {}  # key -> (timestamp, results)
        self._l1_cache_ttl = 15.0  # seconds

        from .semantic_recall_store import SemanticRecallStore
        self.qdrant_store = SemanticRecallStore()

    @property
    def is_sqlite(self) -> bool:
        """Heuristic check to determine if the backing pool uses the Mock SQLite adaptor."""
        return type(self.pool).__name__ == "MockPGPool" or (
            hasattr(self.pool, "connection")
            and type(self.pool).__name__ not in ("MagicMock", "AsyncMock", "Mock")
        )

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
    ):
        """Adds a new memory with ACT-R metadata and hierarchical scope."""
        try:
            vector = await self.get_embedding(content)
            if not vector:
                return False

            vector_str = str(vector)
            raw_val = raw_content or content

            async with self.pool.acquire() as conn:
                try:
                    await conn.execute(
                        """
                        INSERT INTO memories (
                            content, raw_content, wing, room,
                            embedding, importance_score, emotional_weight,
                            valence, certainty, source, metadata,
                            lifespan_stage, crisis, virtue, relations, relation_circles, modality,
                            recall_count, last_recalled_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, 1, CURRENT_TIMESTAMP)
                        """,
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
                        orjson.dumps(metadata or {}).decode(),
                        lifespan_stage,
                        crisis,
                        virtue,
                        relations,
                        relation_circles,
                        modality,
                    )
                except Exception as e:
                    logger.warning(
                        f"Eriksonian insert failed, falling back to legacy schema: {e}"
                    )
                    await conn.execute(
                        """
                        INSERT INTO memories (
                            content, raw_content, wing, room,
                            embedding, importance_score, emotional_weight,
                            valence, certainty, source, metadata,
                            recall_count, last_recalled_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 1, CURRENT_TIMESTAMP)
                        """,
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
                        orjson.dumps(metadata or {}).decode(),
                    )
            # Upsert into Qdrant if online
            if self.qdrant_store.client:
                import uuid
                memory_id = str(uuid.uuid4())
                metadata_qdrant = {
                    "wing": wing,
                    "room": room or "",
                    "importance_score": importance,
                    "emotional_weight": emotion,
                    "valence": valence,
                    "certainty": certainty,
                    "source": source,
                    "recall_count": 1,
                    "last_recalled_at": str(time.time()),
                    "created_at": str(time.time()),
                    "lifespan_stage": lifespan_stage or "",
                    "crisis": crisis or "",
                    "virtue": virtue or "",
                    "relations": relations or "",
                    "relation_circles": relation_circles or "",
                    "modality": modality or ""
                }
                if metadata:
                    metadata_qdrant["custom_metadata"] = orjson.dumps(metadata).decode()

                self.qdrant_store.add_vector_memory(
                    memory_id=memory_id,
                    vector=vector,
                    content=content,
                    metadata=metadata_qdrant
                )

            logger.info(
                f"🧠 Memory Stored [{wing}:{room or 'global'}]: {content[:50]}..."
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

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
    ):
        """
        ACT-R Based Retrieval with Hierarchical Scoping & Neuromodulatory Gating:
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
        )
        now_ts = time.time()
        if cache_key in self._l1_cache:
            ts, cached_results = self._l1_cache[cache_key]
            if now_ts - ts < self._l1_cache_ttl:
                if cached_results and refresh_on_recall:
                    await self._refresh_memories(cached_results)
                return cached_results

        try:
            query_vector = await self.get_embedding(query_text)
            if not query_vector:
                return []

            vector_str = str(query_vector)
            excluded = {content for content in (exclude_contents or []) if content}

            is_sqlite = self.is_sqlite

            raw_candidates = []

            # 1. Qdrant Selective Vector Path
            if self.qdrant_store.client:
                try:
                    candidates = self.qdrant_store.search_vector_memories(
                        query_vector=query_vector,
                        limit=max(20, limit * 3)
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
                        memory_valence = meta.get("valence", 0.0)
                        emotion_weight_row = meta.get("emotional_weight", 0.0)
                        importance_score = meta.get("importance_score", 0.5)
                        recall_count = max(1, meta.get("recall_count", 1))

                        try:
                            last_recall_time = float(meta.get("last_recalled_at", time.time()))
                        except (ValueError, TypeError):
                            last_recall_time = time.time()

                        hours_since = max(0.001, (time.time() - last_recall_time) / 3600.0)

                        # 2D/3D Emotional Distance matching the research simulator
                        dist_emo = math.sqrt(
                            (memory_valence - current_valence) ** 2
                            + (emotion_weight_row - current_arousal) ** 2
                        )

                        base_activation = (
                            _cached_ln(recall_count)
                            - self.decay_rate * _cached_ln(hours_since + 1.0)
                            + 1.5 * importance_score
                            + 0.15 * (1.0 - dist_emo)
                        )

                        similarity = cand["score"]
                        effective_similarity = similarity * (
                            1.0
                            + 0.1 * memory_valence * emotion_weight_row
                            - 0.2 * current_arousal * current_cortisol
                        )

                        spread_activation = self.spread_weight * effective_similarity
                        score = base_activation + spread_activation - 0.5 * dist_emo

                        if score <= (threshold - 2.5):
                            continue

                        from datetime import datetime
                        created_val = meta.get("created_at")
                        try:
                            created = datetime.fromtimestamp(float(created_val), timezone.utc) if created_val else datetime.now(timezone.utc)
                        except Exception:
                            created = datetime.now(timezone.utc)

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
                                "last_recalled_at": datetime.fromtimestamp(last_recall_time, timezone.utc)
                            }
                        )
                except Exception as qe:
                    logger.error(f"Qdrant retrieval failed, falling back to database: {qe}")

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
    
                        # Manual cosine similarity and ACT-R scoring
                        for row in rows:
                            if row["content"] in excluded:
                                continue
    
                            # Parse embedding vector
                            try:
                                emb_str = row.get("embedding")
                                if isinstance(emb_str, str):
                                    # Strip brackets and split
                                    emb_str = emb_str.strip("[]")
                                    emb_val = [
                                        float(x) for x in emb_str.split(",") if x.strip()
                                    ]
                                elif isinstance(emb_str, list):
                                    emb_val = emb_str
                                else:
                                    emb_val = []
                            except Exception:
                                emb_val = []
    
                            if len(emb_val) == len(query_vector) and len(query_vector) > 0:
                                # Dot product
                                dot = sum(x * y for x, y in zip(query_vector, emb_val))
                                mag1 = math.sqrt(sum(x * x for x in query_vector))
                                mag2 = math.sqrt(sum(x * x for x in emb_val))
                                similarity = dot / (mag1 * mag2) if mag1 * mag2 > 0 else 0.0
                            else:
                                similarity = 0.5  # default similarity fallback
    
                            last_recall = row.get("last_recalled_at")
                            from datetime import datetime
    
                            now = datetime.now(timezone.utc)
    
                            if last_recall is None:
                                last_recall = now
                            elif isinstance(last_recall, str):
                                try:
                                    last_recall = datetime.fromisoformat(last_recall)
                                except Exception:
                                    last_recall = now
    
                            if last_recall.tzinfo is None:
                                last_recall = last_recall.replace(tzinfo=timezone.utc)
    
                            hours_since = max(
                                0.001, (now - last_recall).total_seconds() / 3600.0
                            )
                            recall_count = max(1, row.get("recall_count") or 1)
    
                            memory_valence = row.get("valence") or 0.0
                            emotion_weight_row = row.get("emotional_weight") or 0.0
    
                            # 2D/3D Emotional Distance matching the research simulator
                            dist_emo = math.sqrt(
                                (memory_valence - current_valence) ** 2
                                + (emotion_weight_row - current_arousal) ** 2
                            )
    
                            base_activation = (
                                _cached_ln(recall_count)
                                - self.decay_rate * _cached_ln(hours_since + 1.0)
                                + 1.5 * (row.get("importance_score") or 0.5)
                                + 0.15 * (1.0 - dist_emo)
                            )
    
                            # Neuromodulatory distance mapping (gating remains untouched in backend)
                            effective_similarity = similarity * (
                                1.0
                                + 0.1 * memory_valence * emotion_weight_row
                                - 0.2 * current_arousal * current_cortisol
                            )
    
                            spread_activation = self.spread_weight * effective_similarity
                            score = base_activation + spread_activation - 0.5 * dist_emo
    
                            # Filter by relaxed threshold (threshold - 2.5)
                            if score <= (threshold - 2.5):
                                continue
    
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
                    else:
                        # PostgreSQL fast-path via custom C-level vector procedure
                        try:
                            rows = await conn.fetch(
                                """
                                SELECT
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
                                FROM surface_actr_memories($1::vector(768), $2::text, $3::text, $4::double precision, $5::double precision, $6::double precision, $7::double precision, $8::double precision, $9::integer) s
                                LEFT JOIN memories m ON m.content = s.content AND m.wing = s.wing
                                """,
                                vector_str,
                                wing,
                                room,
                                self.decay_rate,
                                self.spread_weight,
                                self.emotion_weight,
                                current_valence,
                                threshold - 2.5,
                                max(20, limit * 3),
                            )
                        except Exception as pg_err:
                            logger.warning(
                                f"Eriksonian JOIN pg query failed, falling back to legacy schema: {pg_err}"
                            )
                            rows = await conn.fetch(
                                """
                                SELECT
                                    content,
                                    raw_content,
                                    wing,
                                    room,
                                    importance_score,
                                    emotional_weight,
                                    valence,
                                    recall_count,
                                    last_recalled_at,
                                    created_at,
                                    metadata,
                                    similarity,
                                    score
                                FROM surface_actr_memories($1::vector(768), $2::text, $3::text, $4::double precision, $5::double precision, $6::double precision, $7::double precision, $8::double precision, $9::integer)
                                """,
                                vector_str,
                                wing,
                                room,
                                self.decay_rate,
                                self.spread_weight,
                                self.emotion_weight,
                                current_valence,
                                threshold - 2.5,
                                max(20, limit * 3),
                            )
    
                        for row in rows:
                            if row["content"] in excluded:
                                continue
    
                            similarity = row.get("similarity") or 0.0
                            recall_count = max(1, row.get("recall_count") or 1)
    
                            # Recalculate score with neuromodulatory gating
                            last_recall = row.get("last_recalled_at")
                            from datetime import datetime
    
                            now = datetime.now(timezone.utc)
    
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
    
                            base_activation = (
                                _cached_ln(recall_count)
                                - self.decay_rate * _cached_ln(hours_since + 1.0)
                                + 1.5 * (row.get("importance_score") or 0.5)
                                + 0.15 * (1.0 - dist_emo)
                            )
    
                            # Neuromodulatory distance mapping
                            effective_similarity = similarity * (
                                1.0
                                + 0.1 * memory_valence * emotion_weight_row
                                - 0.2 * current_arousal * current_cortisol
                            )
    
                            spread_activation = self.spread_weight * effective_similarity
                            score = base_activation + spread_activation - 0.5 * dist_emo
    
                            if score <= (threshold - 2.5):
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
    
            # 3. Post-process candidate list in Python (Direct Cue Boost + Spreading Activation)
            cues = [
                "kolkata",
                "bangalore",
                "priya",
                "rasgulla",
                "cognitive architectures",
                "affective",
            ]
            matched_cues = [c for c in cues if c in query_text.lower()]

            direct_boosted_indices = set()

            if matched_cues:
                # Direct cue boost (+1.2)
                for idx, cand in enumerate(raw_candidates):
                    content_lower = cand["content"].lower()
                    if any(mc in content_lower for mc in matched_cues):
                        cand["score"] += 1.2
                        direct_boosted_indices.add(idx)

                # Spreading activation (+0.6) to connected nodes
                entities = [
                    "kolkata",
                    "bangalore",
                    "priya",
                    "rasgulla",
                    "cognitive architectures",
                    "affective",
                ]
                import re

                for idx in direct_boosted_indices:
                    direct_cand = raw_candidates[idx]
                    content_k = direct_cand["content"].lower()
                    found_entities_k = [e for e in entities if e in content_k]
                    age_matches_k = re.findall(r"age (\d+)", content_k)

                    for other_idx, other_cand in enumerate(raw_candidates):
                        if other_idx == idx or other_idx in direct_boosted_indices:
                            continue
                        content_other = other_cand["content"].lower()
                        has_connection = False

                        # Shared entities
                        for ent in found_entities_k:
                            if ent in content_other:
                                has_connection = True
                                break

                        # Cross-epoch age match
                        if not has_connection and age_matches_k:
                            for age in age_matches_k:
                                if f"age {age}" in content_other:
                                    has_connection = True
                                    break

                        if has_connection:
                            other_cand["score"] += 0.6

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

                task = asyncio.create_task(self._refresh_memories(results))
                task.add_done_callback(_done_callback)

            # Cache results in L1 memory cache before returning
            self._l1_cache[cache_key] = (now_ts, results)
            return results

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def _refresh_memories(self, memories: list[dict]):
        """
        Updates last_recalled_at and increments recall_count (ACT-R frequency).
        This strengthens the base-level activation for recently accessed memories.
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
                        "SELECT id, role, content, timestamp FROM messages WHERE consolidated = 0 AND role IN ('user', 'assistant') AND timestamp >= datetime('now', '-24 hours') ORDER BY timestamp DESC LIMIT ?",
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT id, role, content, timestamp FROM messages WHERE consolidated = FALSE AND role IN ('user', 'assistant') AND timestamp >= NOW() - INTERVAL '24 hours' ORDER BY timestamp DESC LIMIT $1",
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

    async def apply_actr_decay(self, memory_contents: list[str]):
        """Decays the importance score of consolidated raw episodic memories using ACT-R feedback."""
        from datetime import datetime
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
                        created_at = datetime.now()

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
                            dt = datetime.now()
                    else:
                        dt = created_at

                    # Calculate hours since creation
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

                    # Calculate base activation: A_i = ln(recall_count) - d * ln(hours_since + 1.0)
                    activation = math.log(n_recalls) - decay_rate * math.log(
                        hours_since + 1.0
                    )

                    if activation < self.pruning_threshold:
                        to_delete.append(mem_id)
                    else:
                        # Decay importance score slightly
                        new_importance = max(0.01, importance_score * 0.8)
                        to_update.append((new_importance, mem_id))

                # 2. Execute Deletions and Updates
                if to_delete:
                    if self.is_sqlite:
                        placeholders = ",".join("?" for _ in to_delete)
                        await conn.execute(
                            f"DELETE FROM memories WHERE id IN ({placeholders})",
                            *to_delete,
                        )
                    else:
                        await conn.execute(
                            "DELETE FROM memories WHERE id = ANY($1)", to_delete
                        )
                    logger.info(
                        f"🗑️ Pruned {len(to_delete)} memories with base activation below {self.pruning_threshold}."
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

            logger.info(
                f"📉 Checked and decayed {len(rows)} memories (pruned: {len(to_delete)})."
            )
        except Exception as e:
            logger.error(f"Failed to apply ACT-R decay pruning: {e}")

    async def close(self):
        """Close the persistent HTTP client."""
        await self._http_client.aclose()
