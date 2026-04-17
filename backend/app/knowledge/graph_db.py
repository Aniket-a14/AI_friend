from neo4j import GraphDatabase
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GraphDB:
    def __init__(
        self, uri=None, user=None, password=None
    ):
        uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = user or os.getenv("NEO4J_USER", "neo4j")
        password = password or os.getenv("NEO4J_PASSWORD", "password123")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    async def execute_query(self, query, parameters=None):
        """Generic query execution."""
        # Note: Using synchronous session for compatibility with legacy pattern in this env.
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

    async def create_entity(self, label: str, name: str, properties: Dict[str, Any] = None):
        """
        Creates/Updates a node with metadata: certainty, source, version.
        """
        props = properties or {}
        props['name'] = name
        props.setdefault('certainty', 1.0)
        props.setdefault('source', 'agent_inference')
        props.setdefault('version', 1)
        
        label = label[0].upper() + label[1:]
        
        query = (
            f"MERGE (e:{label} {{name: $name}}) "
            "SET e += $props "
            "RETURN e"
        )
        await self.execute_query(query, {"name": name, "props": props})
        logger.debug(f"Graph Store: Hydrated Identity Node ({label} {{name: '{name}'}})")

    async def create_relationship(self, subject_name: str, subject_label: str, 
                                  relation: str, 
                                  target_name: str, target_label: str,
                                  properties: Dict[str, Any] = None):
        """
        Creates a relationship with properties (e.g., TrustLevel, weight).
        Adheres to UPPER_SNAKE_CASE for relationships.
        """
        rel_type = relation.upper().replace(" ", "_")
        s_label = subject_label[0].upper() + subject_label[1:]
        t_label = target_label[0].upper() + target_label[1:]
        
        props = properties or {}
        props.setdefault('weight', 0.5)
        props.setdefault('certainty', 1.0)
        
        query = (
            f"MERGE (s:{s_label} {{name: $s_name}}) "
            f"MERGE (t:{t_label} {{name: $t_name}}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r += $props "
            "RETURN s, r, t"
        )
        await self.execute_query(query, {
            "s_name": subject_name, 
            "t_name": target_name,
            "props": props
        })
        logger.info(f"Graph Store: Linked {subject_name} -[:{rel_type} {{weight: {props['weight']}}}]-> {target_name}")
