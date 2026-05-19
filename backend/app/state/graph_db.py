from neo4j import AsyncGraphDatabase
import logging
import re
import time
import json
import asyncio
from typing import Dict, Any, List
from ..config import Config

logger = logging.getLogger("graph_db")
_CYPHER_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class GraphDB:
    """
    Asynchronous Knowledge Mesh for CVS-1.0.
    Manages persistent entities and relationships without blocking the cognitive loop.
    """

    def __init__(self, uri=None, user=None, password=None):
        uri = uri or Config.NEO4J_URI
        user = user or Config.NEO4J_USER
        password = password or Config.NEO4J_PASSWORD

        if not password or password in ["password", "neo4j", "placeholder"]:
            logger.error(
                "🛑 Security Violation: Weak or Placeholder Neo4j Password Detected."
            )
            raise ValueError(
                "A strong, non-default NEO4J_PASSWORD must be provided in your .env file."
            )

        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

        # Perceptual Belief Cache
        self._belief_cache = {}
        self._cache_ttl = getattr(Config, "GRAPH_CACHE_TTL", 300)

        # Asynchronously bootstrap uniqueness constraints and indexes on startup
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self.bootstrap_constraints())
        except RuntimeError:
            # If no running event loop (e.g. mock setup), bootstrap will run on first query or be skipped
            pass

    async def bootstrap_constraints(self):
        """Asynchronously initialize schema unique constraints and indexes to guarantee O(1) performance."""
        queries = [
            "CREATE CONSTRAINT agent_name_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
        ]
        for query in queries:
            try:
                async with self.driver.session() as session:
                    # Run schema operations inside explicit transaction functions
                    async def _tx(tx):
                        return await tx.run(query)

                    await session.execute_write(_tx)
                logger.debug(f"Graph Store Schema: Constraint initialized ({query})")
            except Exception as e:
                logger.warning(
                    f"Graph Store Schema: Optional index/constraint initialization skipped ({query}): {e}"
                )

    @staticmethod
    def _safe_label(label: str | None) -> str:
        label = (label or "Entity").strip()
        label = label[0].upper() + label[1:] if label else "Entity"
        if not _CYPHER_IDENTIFIER_RE.fullmatch(label):
            raise ValueError(f"Unsafe Cypher label: {label!r}")
        return label

    @staticmethod
    def _safe_relation(relation: str) -> str:
        rel_type = relation.upper().replace(" ", "_").replace("-", "_")
        if not _CYPHER_IDENTIFIER_RE.fullmatch(rel_type):
            raise ValueError(f"Unsafe Cypher relation: {relation!r}")
        return rel_type

    async def close(self):
        await self.driver.close()

    async def invalidate_cache(self, affected_entity: str = None):
        """Public cache flush hook for stateful services."""
        await self._invalidate_cache(affected_entity)

    async def _invalidate_cache(self, affected_entity: str = None):
        """Flush cache to prevent stale context."""
        self._belief_cache.clear()
        if affected_entity:
            logger.debug(
                f"Graph Store: Cache flushed due to update in '{affected_entity}'"
            )

    async def execute_query(
        self,
        query: str,
        parameters: Dict[str, Any] = None,
        use_cache: bool = False,
        write: bool = False,
        strong_consistency: bool = False,
    ) -> List[Any]:
        """Generic async query execution with TTL caching and explicit read/write transaction routing."""
        cache_key = (query, json.dumps(parameters) if parameters else None)

        if use_cache and cache_key in self._belief_cache:
            ts, result = self._belief_cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return result

        try:
            async with self.driver.session() as session:
                attempt = 0
                if write or strong_consistency:
                    # Execute as explicit write transaction function (directing queries to the Leader to bypass lag)
                    async def write_tx(tx):
                        nonlocal attempt
                        attempt += 1
                        if attempt > 1:
                            logger.warning(
                                f"Graph Store: Transient write transaction retry #{attempt - 1} for query: '{query[:50]}...'"
                            )
                        res = await tx.run(query, parameters)
                        return [record async for record in res]

                    records = await session.execute_write(write_tx)
                else:
                    # Execute as explicit read transaction function (which can be routed to followers/read-replicas)
                    async def read_tx(tx):
                        nonlocal attempt
                        attempt += 1
                        if attempt > 1:
                            logger.warning(
                                f"Graph Store: Transient read transaction retry #{attempt - 1} for query: '{query[:50]}...'"
                            )
                        res = await tx.run(query, parameters)
                        return [record async for record in res]

                    records = await session.execute_read(read_tx)

                if use_cache:
                    self._belief_cache[cache_key] = (time.time(), records)
                return records
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return []

    async def create_entity(
        self, label: str, name: str, properties: Dict[str, Any] = None
    ):
        """
        Creates/Updates a node with metadata: certainty, source, version.
        """
        await self._invalidate_cache(name)
        props = properties or {}
        props["name"] = name
        props.setdefault("certainty", 1.0)
        props.setdefault("source", "agent_inference")
        props.setdefault("version", 1)

        label = self._safe_label(label)

        query = f"MERGE (e:{label} {{name: $name}}) SET e += $props RETURN e"
        await self.execute_query(query, {"name": name, "props": props}, write=True)
        logger.debug(
            f"Graph Store: Hydrated Identity Node ({label} {{name: '{name}'}})"
        )

    async def create_relationship(
        self,
        subject_name: str,
        subject_label: str,
        relation: str,
        target_name: str,
        target_label: str,
        properties: Dict[str, Any] = None,
    ):
        """
        Creates a relationship with properties (e.g., TrustLevel, weight).
        Adheres to UPPER_SNAKE_CASE for relationships.
        """
        await self._invalidate_cache(subject_name)
        rel_type = self._safe_relation(relation)
        s_label = self._safe_label(subject_label)
        t_label = self._safe_label(target_label)

        props = properties or {}
        props.setdefault("weight", 0.5)
        props.setdefault("certainty", 1.0)

        query = (
            f"MERGE (s:{s_label} {{name: $s_name}}) "
            f"MERGE (t:{t_label} {{name: $t_name}}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r += $props "
            "RETURN s, r, t"
        )
        await self.execute_query(
            query,
            {"s_name": subject_name, "t_name": target_name, "props": props},
            write=True,
        )
        logger.info(
            f"Graph Store: Linked {subject_name} -[:{rel_type} {{weight: {props['weight']}}}]-> {target_name}"
        )

    async def consolidate_relationship(
        self,
        subject_name: str,
        relation: str,
        target_name: str,
        properties: Dict[str, Any] = None,
    ):
        """
        Consolidates a relationship, incrementing weight on match or setting default properties.
        """
        await self._invalidate_cache(subject_name)
        rel_type = self._safe_relation(relation)

        props = properties or {}
        props.setdefault("certainty", 1.0)

        # Cypher query with ON CREATE and ON MATCH logic for weight consolidation
        query = (
            f"MERGE (s:Entity {{name: $s_name}}) "
            f"MERGE (t:Entity {{name: $t_name}}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "ON CREATE SET r += $props, r.weight = 1 "
            "ON MATCH SET r.weight = coalesce(r.weight, 1) + 1, r.certainty = $props.certainty "
            "RETURN s, r, t"
        )
        await self.execute_query(
            query,
            {"s_name": subject_name, "t_name": target_name, "props": props},
            write=True,
        )
        logger.info(
            f"Graph Store: Consolidated relationship {subject_name} -[:{rel_type}]-> {target_name}"
        )

    async def create_triplet(
        self,
        subject: str,
        relation: str,
        target: str,
        properties: Dict[str, Any] = None,
    ):
        """High-level transactional helper to write a semantic triplet directly with weight consolidation."""
        await self.consolidate_relationship(
            subject_name=subject,
            relation=relation,
            target_name=target,
            properties=properties,
        )
