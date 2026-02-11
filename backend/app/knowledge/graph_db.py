from neo4j import GraphDatabase
import logging
import os

logger = logging.getLogger(__name__)

class GraphDB:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password123"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    async def execute_query(self, query, parameters=None):
        """Generic query execution."""
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

    async def create_relationship(self, subject, relation, target):
        """
        Creates a fundamental triple in the knowledge graph.
        Example: (User)-[:LIKES]->(Pizza)
        """
        query = (
            "MERGE (s:Entity {name: $sub}) "
            "MERGE (t:Entity {name: $tar}) "
            f"MERGE (s)-[r:{relation.upper()}]->(t) "
            "RETURN s, r, t"
        )
        await self.execute_query(query, {"sub": subject, "tar": target})
        logger.info(f"Graph Store: Recorded relationship {subject} -[{relation}]-> {target}")
