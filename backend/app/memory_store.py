import logging
import asyncio
import httpx
import json
import math
from datetime import datetime

logger = logging.getLogger(__name__)

class MemoryStore:
    def __init__(self, pool):
        self.pool = pool
        self.ollama_base_url = "http://localhost:11434"
        self.embedding_model = "nomic-embed-text"
        self.lambda_decay = 0.001  # Decay constant for memory fading
        self.beta_emotion = 0.5   # Boost factor for emotional weight

    async def get_embedding(self, text: str):
        """Generates vector embedding for text using local Ollama."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("embedding")
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            return None

    async def add_memory(self, content, importance=0.5, emotion=0.0, certainty=1.0, source='user', metadata=None):
        """Adds a new memory with utility metadata to the local Postgres database."""
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
                        certainty, source, metadata, last_recalled_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
                    """,
                    content,
                    vector_str,
                    importance,
                    emotion,
                    certainty,
                    source,
                    json.dumps(metadata or {}),
                )
            logger.info(f"🧠 Identity Memory Stored: {content[:50]}... (Imp: {importance}, Emo: {emotion})")
            return True
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

    async def search_memories(self, query_text, threshold=0.6, limit=5):
        """
        Searches and re-scores memories using a Utility Score:
        Score = Similarity * (Importance * Decay) * (1 + Beta * Emotion)
        """
        try:
            query_vector = await self.get_embedding(query_text)
            if not query_vector:
                return []

            vector_str = str(query_vector)
            now = datetime.now()

            results = []
            async with self.pool.acquire() as conn:
                # Fetch top-K candidates by raw cosine similarity first
                rows = await conn.fetch(
                    """
                    SELECT 
                        content, 
                        importance_score, 
                        emotional_weight, 
                        last_recalled_at,
                        1 - (embedding <=> $1) as similarity
                    FROM memories
                    ORDER BY embedding <=> $1
                    LIMIT $2
                    """,
                    vector_str,
                    limit * 3, # Fetch a larger set to re-score
                )
                
                scored_candidates = []
                for row in rows:
                    sim = row["similarity"]
                    last_recall = row["last_recalled_at"]
                    importance = row["importance_score"]
                    emotion = row["emotional_weight"]
                    
                    # Calculate decay based on time elapsed (seconds)
                    delta_t = (now - last_recall).total_seconds()
                    decay = math.exp(-self.lambda_decay * (delta_t / 3600)) # Decay by hours
                    
                    # Utility Score formula
                    utility_score = sim * (importance * decay)
                    if emotion > 0:
                        utility_score *= (1 + self.beta_emotion * emotion)
                    
                    if utility_score > threshold:
                        scored_candidates.append({
                            "content": row["content"],
                            "score": utility_score
                        })
                
                # Sort by utility score and limit
                scored_candidates.sort(key=lambda x: x["score"], reverse=True)
                results = scored_candidates[:limit]

            if results:
                logger.info(
                    f"🧠 Intel-Recall: {len(results)} memories for: '{query_text[:30]}...'"
                )
            
            # Update last_recalled_at for the top results to 'refresh' them
            if results:
                # Actual Implementation: Robust background task safety wrapper
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
        """Updates the last_recalled_at timestamp to prevent decay of recently used memories."""
        try:
            contents = [memory["content"] for memory in memories if memory.get("content")]
            if not contents:
                return
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE memories SET last_recalled_at = CURRENT_TIMESTAMP WHERE content = ANY($1)",
                    contents
                )
        except Exception as e:
            logger.error(f"Failed to refresh memories: {e}")
