"""
Memory Store — ACT-R Based Retrieval (psycological_layer.md §6).

Retrieval scoring adapted from Anderson & Lebiere (1998):
    Aᵢ = Bᵢ + Σⱼ Wⱼ·Sⱼᵢ + ε

With extensions for emotional alignment (Bower, 1981):
    Score = Aᵢ + w_emotion · EmotionalAlignment

Base-level activation (simplified):
    Bᵢ ≈ ln(recall_count) - d · ln(hours_since_last_recall + 1)
"""

import logging
import asyncio
import httpx
import json
import math
from datetime import datetime, timezone
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

        # ACT-R Parameters (§6.2)
        self.decay_rate = getattr(Config, "ACTR_DECAY_RATE", 0.5)       # d
        self.spread_weight = getattr(Config, "ACTR_SPREAD_WEIGHT", 1.0)  # Wⱼ
        self.emotion_weight = getattr(Config, "ACTR_EMOTION_WEIGHT", 0.5)  # w_emotion

    async def get_embedding(self, text: str):
        """Generates vector embedding for text using local Ollama."""
        attempts = [
            ("/api/embed", {"model": self.embedding_model, "input": text}),
            ("/api/embeddings", {"model": self.embedding_model, "prompt": text}),
        ]

        last_error = None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
        importance=0.5,
        emotion=0.0,
        valence=0.0,
        certainty=1.0,
        source='user',
        metadata=None,
    ):
        """Adds a new memory with ACT-R metadata to the local Postgres database."""
        try:
            vector = await self.get_embedding(content)
            if not vector:
                return False

            vector_str = str(vector)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memories (
                        content, embedding, importance_score, emotional_weight,
                        valence, certainty, source, metadata,
                        recall_count, last_recalled_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, CURRENT_TIMESTAMP)
                    """,
                    content,
                    vector_str,
                    importance,
                    emotion,
                    valence,
                    certainty,
                    source,
                    json.dumps(metadata or {}),
                )
            logger.info(f"🧠 Memory Stored: {content[:50]}... (Imp: {importance}, V: {valence})")
            return True
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

    async def search_memories(
        self,
        query_text,
        threshold=0.3,
        limit=5,
        refresh_on_recall=True,
        exclude_contents: Iterable[str] = None,
        current_valence: float = 0.0,
    ):
        """
        ACT-R Based Retrieval (§6.2–6.4):
            Score = Bᵢ + w_spread·Similarity + w_emotion·EmotionalAlignment

        Where:
            Bᵢ ≈ ln(recall_count) - d · ln(hours_since_last + 1)
            EmotionalAlignment = exp(-|Memory.V - Current.V|)  (Bower, 1981)
        """
        try:
            query_vector = await self.get_embedding(query_text)
            if not query_vector:
                return []

            vector_str = str(query_vector)
            now = datetime.now(timezone.utc)
            excluded = {content for content in (exclude_contents or []) if content}

            results = []
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        content,
                        importance_score,
                        emotional_weight,
                        valence,
                        recall_count,
                        last_recalled_at,
                        created_at,
                        metadata,
                        1 - (embedding <=> $1) as similarity
                    FROM memories
                    ORDER BY embedding <=> $1
                    LIMIT $2
                    """,
                    vector_str,
                    limit * 3,
                )

                scored_candidates = []
                for row in rows:
                    if row["content"] in excluded:
                        continue

                    similarity = row["similarity"]
                    recall_count = max(1, row["recall_count"] or 1)
                    last_recall = row["last_recalled_at"]
                    memory_valence = row["valence"] or 0.0

                    if last_recall is None:
                        last_recall = now
                    elif last_recall.tzinfo is None:
                        last_recall = last_recall.replace(tzinfo=timezone.utc)

                    # ACT-R Base-Level Activation (§6.2)
                    hours_since = max(0.001, (now - last_recall).total_seconds() / 3600.0)
                    base_activation = (
                        math.log(max(1, recall_count))
                        - self.decay_rate * math.log(hours_since + 1)
                    )

                    # Spreading Activation ≈ cosine similarity (§6.2)
                    spread_activation = self.spread_weight * similarity

                    # Emotional Alignment (§6.4 — Bower, 1981)
                    emotional_alignment = math.exp(
                        -abs(memory_valence - current_valence)
                    )
                    emotion_boost = self.emotion_weight * emotional_alignment

                    # Final ACT-R Score
                    score = base_activation + spread_activation + emotion_boost

                    if score > threshold:
                        created = row["created_at"]
                        if created and created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)

                        raw_meta = row["metadata"]
                        if isinstance(raw_meta, str):
                            try:
                                raw_meta = json.loads(raw_meta)
                            except (json.JSONDecodeError, TypeError):
                                raw_meta = {}

                        scored_candidates.append({
                            "content": row["content"],
                            "score": score,
                            # Episodic context for narrative surfacing
                            "valence": memory_valence,
                            "created_at": created.isoformat() if created else None,
                            "recall_count": recall_count,
                            "metadata": raw_meta or {},
                        })

                scored_candidates.sort(key=lambda x: x["score"], reverse=True)
                results = scored_candidates[:limit]

            if results:
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
            contents = [memory["content"] for memory in memories if memory.get("content")]
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
                    contents
                )
        except Exception as e:
            logger.error(f"Failed to refresh memories: {e}")
