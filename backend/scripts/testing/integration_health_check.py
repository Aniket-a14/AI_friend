import asyncio
import logging
import os
import sys

import asyncpg
from dotenv import load_dotenv
from httpx import AsyncClient
from neo4j import GraphDatabase

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("health_check")


async def check_postgres():
    db_url = os.getenv("DATABASE_URL")
    logger.info("Checking Postgres connection...")
    try:
        conn = await asyncpg.connect(db_url)
        # Check if memories table exists
        await conn.execute("SELECT 1 FROM memories LIMIT 1")
        logger.info("✅ Postgres: Connected and 'memories' table found.")
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Postgres: Failed to connect: {e}")
        return False


async def check_neo4j():
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    auth_str = os.getenv("NEO4J_AUTH", "neo4j/password123")
    user, password = (
        auth_str.split("/") if "/" in auth_str else ("neo4j", "password123")
    )

    logger.info(f"Checking Neo4j connection at {uri}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        logger.info("✅ Neo4j: Connected successfully.")
        driver.close()
        return True
    except Exception as e:
        logger.error(f"❌ Neo4j: Failed to connect: {e}")
        return False


async def check_ollama():
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    logger.info(f"Checking Ollama connection at {ollama_url}...")
    try:
        async with AsyncClient() as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            logger.info(f"Ollama: Connected. Found models: {model_names}")

            required = ["llama3.2:latest", "nomic-embed-text:latest"]
            missing = [
                m for m in required if not any(m in name for name in model_names)
            ]

            if missing:
                logger.warning(f"⚠️ Ollama: Missing required models: {missing}")
            else:
                logger.info("✅ Ollama: All required models are present.")

        return True
    except Exception as e:
        logger.error(f"❌ Ollama: Failed to connect: {e}")
        return False


async def main():
    logger.info("🔍 Starting Sovereign Integration Health Check...")

    results = await asyncio.gather(check_postgres(), check_neo4j(), check_ollama())

    if all(results):
        logger.info("🎉 All infrastructure components are responsive!")
    else:
        logger.error("🚫 Some infrastructure checks failed. See errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
