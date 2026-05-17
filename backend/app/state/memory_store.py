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
from datetime import timezone
from typing import Iterable
from ..config import Config

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, pool, ollama_base_url=None):
        self.pool = pool
        self.ollama_base_url = (
            ollama_base_url or getattr(Config, "OLLAMA_URL", "http://localhost:11434")
        ).rstrip("/")
        self.embedding_model = "nomic-embed-text"
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # ACT-R Parameters (§6.2)
        self.decay_rate = Config.ACTR_DECAY_RATE  # d
        self.spread_weight = Config.ACTR_SPREAD_WEIGHT  # Wⱼ
        self.emotion_weight = Config.ACTR_EMOTION_WEIGHT  # w_emotion

        # L1 Memory Activation Cache
        self._l1_cache = {}  # key -> (timestamp, results)
        self._l1_cache_ttl = 15.0  # seconds

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
    ):
        """Adds a new memory with ACT-R metadata and hierarchical scope."""
        try:
            vector = await self.get_embedding(content)
            if not vector:
                return False

            vector_str = str(vector)
            raw_val = raw_content or content

            async with self.pool.acquire() as conn:
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
        threshold=0.3,
        limit=5,
        refresh_on_recall=True,
        exclude_contents: Iterable[str] = None,
        current_valence: float = 0.0,
    ):
        """
        ACT-R Based Retrieval with Hierarchical Scoping:
            Score = Bᵢ + w_spread·Similarity + w_emotion·EmotionalAlignment

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
            tuple(sorted(exclude_contents or []))
        )
        now_ts = time.time()
        if cache_key in self._l1_cache:
            ts, cached_results = self._l1_cache[cache_key]
            if now_ts - ts < self._l1_cache_ttl:
                return cached_results

        try:
            query_vector = await self.get_embedding(query_text)
            if not query_vector:
                return []

            vector_str = str(query_vector)
            excluded = {content for content in (exclude_contents or []) if content}

            results = []
            async with self.pool.acquire() as conn:
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
                    threshold,
                    limit,
                )

                for row in rows:
                    if row["content"] in excluded:
                        continue

                    score = row.get("score")
                    similarity = row.get("similarity") or 0.0
                    recall_count = max(1, row.get("recall_count") or 1)

                    if score is None:
                        # Fallback calculation for offline mock-based unit tests
                        last_recall = row.get("last_recalled_at")
                        from datetime import datetime
                        now = datetime.now(timezone.utc)

                        if last_recall is None:
                            last_recall = now
                        elif last_recall.tzinfo is None:
                            last_recall = last_recall.replace(tzinfo=timezone.utc)

                        hours_since = max(0.001, (now - last_recall).total_seconds() / 3600.0)

                        import math
                        base_activation = math.log(recall_count) - self.decay_rate * math.log(hours_since + 1)
                        spread_activation = self.spread_weight * similarity
                        memory_valence = row.get("valence") or 0.0
                        emotion_weight_row = row.get("emotional_weight") or 0.0
                        alignment = math.exp(-abs(memory_valence - current_valence))
                        emotion_boost = self.emotion_weight * emotion_weight_row * alignment
                        score = base_activation + spread_activation + emotion_boost

                    if score <= threshold:
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

                    results.append(
                        {
                            "content": row["content"],
                            "raw_content": row.get("raw_content") or row["content"],
                            "wing": row.get("wing", "personal"),
                            "room": row.get("room"),
                            "score": score,
                            "valence": row.get("valence") or 0.0,
                            "created_at": created.isoformat() if created else None,
                            "recall_count": recall_count,
                            "metadata": raw_meta or {},
                        }
                    )

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

    async def close(self):
        """Close the persistent HTTP client."""
        await self._http_client.aclose()
