import asyncio
import asyncpg
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

async def init_db():
    db_url = os.getenv("DATABASE_URL")
    logger.info("Connecting to database to initialize schema...")
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # 1. Enable pgvector
        logger.info("Enabling pgvector extension...")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
        await conn.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')
        
        # 2. DROP EVERYTHING FIRST (FOR RE-INIT)
        logger.info("Dropping old tables for clean init...")
        await conn.execute("DROP TABLE IF EXISTS messages CASCADE")
        await conn.execute("DROP TABLE IF EXISTS sessions CASCADE")
        await conn.execute("DROP TABLE IF EXISTS agent_configs CASCADE")
        await conn.execute("DROP TABLE IF EXISTS memories CASCADE")

        # 3. Create memories table
        logger.info("Creating memories table...")
        await conn.execute('''
            CREATE TABLE memories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                embedding vector(768),
                metadata JSONB,
                importance_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                emotional_weight DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                certainty DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'user',
                last_recalled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # 4. Create Index
        await conn.execute('CREATE INDEX IF NOT EXISTS memories_embedding_idx ON memories USING hnsw (embedding vector_cosine_ops);')

        # 5. Create sessions table
        logger.info("Creating sessions table...")
        await conn.execute('''
            CREATE TABLE sessions (
                id UUID PRIMARY KEY,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP WITH TIME ZONE,
                metadata JSONB
            );
        ''')

        # 6. Create messages table
        logger.info("Creating messages table...")
        await conn.execute('''
            CREATE TABLE messages (
                id UUID PRIMARY KEY,
                session_id UUID REFERENCES sessions(id),
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # 7. Create agent_configs table
        logger.info("Creating agent_configs table...")
        await conn.execute('''
            CREATE TABLE agent_configs (
                id INTEGER PRIMARY KEY,
                personality JSONB,
                background_history JSONB,
                evolved_learnings TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        logger.info("✅ Clean Database initialization complete!")
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")

if __name__ == "__main__":
    asyncio.run(init_db())
