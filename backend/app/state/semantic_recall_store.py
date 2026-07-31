import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger("semantic_recall_store")


class SemanticRecallStore:
    """
    Tier-2 Semantic Memory Recall Store.
    Connects to Qdrant (127.0.0.1:6333) for high-dimensional vector search.
    Provides associative memory retrieval and metadata-based filtering.
    """

    def __init__(
        self,
        qdrant_host: str | None = None,
        qdrant_port: int | None = None,
        collection_name: str = "ai_friend_memories",
        vector_size: int = 768,
    ):
        from ..config import Config

        q_host = qdrant_host or getattr(Config, "QDRANT_HOST", "127.0.0.1")
        q_port = qdrant_port or getattr(Config, "QDRANT_PORT", 6333)

        self.collection_name = collection_name
        self.vector_size = vector_size
        self.client: QdrantClient | None = None

        try:
            self.client = QdrantClient(host=q_host, port=q_port, timeout=2.0)
            self._ensure_collection_exists()
            logger.info(f"Connected to Qdrant Semantic Store on {q_host}:{q_port}")
        except Exception as e:
            self.client = None
            logger.warning(
                f"Qdrant Semantic Store unavailable: {e}. Running in selective bypass mode."
            )

    def _ensure_collection_exists(self):
        if not self.client:
            return

        try:
            # Check if collection exists
            collections = self.client.get_collections()
            exist = any(
                col.name == self.collection_name for col in collections.collections
            )

            if not exist:
                logger.info(
                    f"Creating Qdrant collection: {self.collection_name} ({self.vector_size} Dimensions, Cosine)"
                )
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size, distance=models.Distance.COSINE
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to verify/create Qdrant collection: {e}")
            self.client = None

    def add_vector_memory(
        self,
        memory_id: str,
        vector: list[float],
        content: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Upsert memory vector and content payload into Qdrant."""
        if not self.client:
            logger.debug("Qdrant client offline. Skipping vector upsert.")
            return False

        if len(vector) != self.vector_size:
            logger.error(
                f"Vector dimension mismatch: expected {self.vector_size}, got {len(vector)}"
            )
            return False

        payload = {"content": content, **metadata}

        try:
            # Convert string memory_id (like UUID) to a format Qdrant accepts (UUID string or integer)
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(id=memory_id, vector=vector, payload=payload)
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Qdrant upsert failed: {e}")
            return False

    def search_vector_memories(
        self,
        query_vector: list[float],
        limit: int = 5,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search similar memories with option to filter by metadata criteria."""
        if not self.client:
            logger.debug("Qdrant offline. Returning empty search results.")
            return []

        # Build Qdrant Match filters if requested
        qdrant_filter = None
        if filter_dict:
            conditions = []
            for key, val in filter_dict.items():
                conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=val))
                )
            if conditions:
                qdrant_filter = models.Filter(must=conditions)

        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
                with_payload=True,
            )

            matched_memories = []
            for res in results:
                payload = res.payload or {}
                matched_memories.append(
                    {
                        "id": res.id,
                        "content": payload.get("content", ""),
                        "score": res.score,
                        "metadata": {
                            k: v for k, v in payload.items() if k != "content"
                        },
                    }
                )
            return matched_memories

        except Exception as e:
            logger.error(f"Qdrant vector search failed: {e}")
            return []
