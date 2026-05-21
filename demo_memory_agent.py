import asyncio
import logging
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.agents.base import BaseAgent
from app.knowledge.graph_db import GraphDB
from app.knowledge.triple_extractor import TripleExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MemoryAgentDemo")


async def demo_memory_agent():
    """
    Demonstrates the v3.0 Memory Agent:
    1. Listens to conversation events on NATS
    2. Extracts knowledge triples
    3. Stores them in Neo4j
    """
    logger.info("🚀 Starting Memory Agent Demo...")

    # Initialize components
    db = GraphDB()
    extractor = TripleExtractor(graph_db=db)
    agent = BaseAgent(name="MemoryAgent")

    try:
        await agent.connect()

        # Simulate conversation events
        conversations = [
            "I live in Mumbai and work as a software engineer",
            "My favorite food is pizza",
            "I have a brother named Rahul",
        ]

        logger.info("📝 Processing conversations and building knowledge graph...")
        for text in conversations:
            logger.info(f"Processing: '{text}'")
            triples = await extractor.extract_and_store(text, user_id="User")
            if triples:
                logger.info(f"  Extracted: {triples}")

        logger.info("✅ Memory Agent Demo Complete!")
        logger.info("🌐 View your knowledge graph at: http://localhost:7474")
        logger.info("   Username: neo4j, Password: password123")
        logger.info("   Run: MATCH (n)-[r]->(m) RETURN n, r, m")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
    finally:
        db.close()
        if agent.nc:
            await agent.nc.close()


if __name__ == "__main__":
    asyncio.run(demo_memory_agent())
