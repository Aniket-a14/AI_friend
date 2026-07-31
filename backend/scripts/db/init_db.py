import asyncio
import logging
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")


async def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is required to initialize the database")

    logger.info("Connecting to database to initialize schema...")
    conn = None

    try:
        conn = await asyncpg.connect(db_url)

        # 1. Enable pgvector
        logger.info("Enabling pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

        # 2. Optional destructive reset, disabled by default for local-first data.
        if os.getenv("ALLOW_DESTRUCTIVE_DB_RESET", "false").lower() == "true":
            logger.warning(
                "Dropping existing tables because ALLOW_DESTRUCTIVE_DB_RESET=true"
            )
            await conn.execute("DROP TABLE IF EXISTS messages CASCADE")
            await conn.execute("DROP TABLE IF EXISTS sessions CASCADE")
            await conn.execute("DROP TABLE IF EXISTS agent_configs CASCADE")
            await conn.execute("DROP TABLE IF EXISTS memories CASCADE")

        # 3. Create memories table (Phase 2: ACT-R enhanced)
        logger.info("Creating memories table (ACT-R enhanced)...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                embedding vector(768),
                metadata JSONB DEFAULT '{}'::jsonb,
                importance_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                emotional_weight DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                valence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                certainty DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'user',
                recall_count INTEGER NOT NULL DEFAULT 0,
                last_recalled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Create Index
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS memories_embedding_idx ON memories USING hnsw (embedding vector_cosine_ops);"
        )

        # 5. Create sessions table
        logger.info("Creating sessions table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id UUID PRIMARY KEY,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP WITH TIME ZONE,
                metadata JSONB DEFAULT '{}'::jsonb
            );
        """)

        # 6. Create messages table
        logger.info("Creating messages table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                session_id UUID REFERENCES sessions(id),
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 7. Create agent_configs table
        logger.info("Creating agent_configs table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_configs (
                id INTEGER PRIMARY KEY,
                personality JSONB,
                background_history JSONB,
                evolved_learnings TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        logger.info("✅ Clean Database initialization complete (Phase 2: ACT-R + PAD)!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(init_db())
