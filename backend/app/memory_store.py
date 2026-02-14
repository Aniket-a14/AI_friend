import logging
import asyncio
from google import genai
from .config import Config

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, pool):
        self.pool = pool
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)

    async def get_embedding(self, text):
        """Generates vector embedding for text using Gemini."""
        try:
            # New SDK usage
            result = await asyncio.to_thread(
                self.client.models.embed_content,
                model="models/text-embedding-004",
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    async def add_memory(self, content, metadata=None):
        """Adds a new memory to the database."""
        try:
            vector = await self.get_embedding(content)
            if not vector:
                return False

            # Format vector for pgvector (string representation '[0.1, 0.2, ...]')
            vector_str = str(vector)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO memories (content, embedding, metadata)
                    VALUES ($1, $2, $3)
                    """,
                    content,
                    vector_str,
                    metadata or {},
                )
            logger.info(f"🧠 Remembered: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return False

    async def search_memories(self, query_text, threshold=0.7, limit=3):
        """Searches for semantically similar memories."""
        try:
            # Generate query embedding
            vector_result = await asyncio.to_thread(
                self.client.models.embed_content,
                model="models/text-embedding-004",
                contents=query_text,
            )
            query_vector = vector_result.embeddings[0].values
            vector_str = str(query_vector)

            # Search in DB
            results = []
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT content, 1 - (embedding <=> $1) as similarity
                    FROM memories
                    WHERE 1 - (embedding <=> $1) > $2
                    ORDER BY embedding <=> $1
                    LIMIT $3
                    """,
                    vector_str,
                    threshold,
                    limit,
                )
                for row in rows:
                    results.append(row["content"])

            if results:
                logger.info(
                    f"🧠 Recalled {len(results)} memories for: '{query_text[:30]}...'"
                )
            return results

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []
