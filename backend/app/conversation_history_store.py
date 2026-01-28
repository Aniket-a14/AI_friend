import asyncio
import logging
import os
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg
from .config import Config

logger = logging.getLogger(__name__)

class ConversationHistoryStore:
    def __init__(self):
        self.dsn = Config.DATABASE_URL
        self.pool: Optional[asyncpg.Pool] = None
        self.current_session_id: Optional[uuid.UUID] = None

    async def initialize(self):
        """Initialize the database connection pool."""
        try:
            if not self.dsn:
                raise ValueError("DATABASE_URL is not set.")
            
            # Use statement_cache_size=0 for pgbouncer compatibility
            self.pool = await asyncpg.create_pool(dsn=self.dsn, statement_cache_size=0)
            
            # We don't create tables here anymore since Prisma handles schema management
            # and we pushed it in the frontend step.
            
            logger.info("Connected to Supabase via asyncpg.")
            
            # Seed personality/history if the table is empty
            await self._ensure_config_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize ConversationHistoryStore: {e}")
            raise

    async def _ensure_config_exists(self):
        """Ensure that the agent_configs table has at least one record (id: 1)."""
        if not self.pool: return
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT id FROM agent_configs WHERE id = 1")
                if not row:
                    logger.info("No AgentConfig found. Seeding from local JSON files...")
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    
                    personality = "{}"
                    try:
                        with open(os.path.join(current_dir, "personality.json"), "r", encoding="utf-8") as f:
                            personality = f.read()
                    except Exception as e:
                        logger.warning(f"Could not read local personality.json for seeding: {e}")

                    history = "{}"
                    try:
                        with open(os.path.join(current_dir, "history.json"), "r", encoding="utf-8") as f:
                            history = f.read()
                    except Exception as e:
                        logger.warning(f"Could not read local history.json for seeding: {e}")

                    await conn.execute(
                        """
                        INSERT INTO agent_configs (id, personality, background_history, updated_at)
                        VALUES (1, $1, $2, NOW())
                        """,
                        personality,
                        history
                    )
                    logger.info("AgentConfig seeded successfully.")
        except Exception as e:
            logger.error(f"Failed to ensure AgentConfig exists: {e}")

    async def get_agent_config(self) -> Dict[str, str]:
        """Fetch personality and history from AgentConfig."""
        if not self.pool:
            return {"personality": "{}", "history": "{}"}
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT personality, background_history FROM agent_configs WHERE id = 1")
                if row:
                    return {
                        "personality": row["personality"],
                        "history": row["background_history"]
                    }
        except Exception as e:
            logger.error(f"Failed to fetch AgentConfig: {e}")
        
        return {"personality": "{}", "history": "{}"}

    async def start_session(self) -> uuid.UUID:
        """Start a new session and return its ID."""
        if not self.pool:
            self.current_session_id = uuid.uuid4()
            return self.current_session_id

        self.current_session_id = uuid.uuid4()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO sessions (id, started_at) VALUES ($1, NOW())',
                    self.current_session_id
                )
            logger.info(f"Started new session: {self.current_session_id}")
            return self.current_session_id
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return self.current_session_id

    async def log_message(self, role: str, content: str):
        """Log a message to the current session."""
        if not self.pool or not self.current_session_id:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO messages (id, session_id, role, content, timestamp)
                    VALUES ($1, $2, $3, $4, NOW())
                    """,
                    uuid.uuid4(),
                    self.current_session_id,
                    role,
                    content
                )
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    async def end_session(self):
        """End the current session."""
        if not self.pool or not self.current_session_id:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE sessions SET ended_at = NOW() WHERE id = $1",
                    self.current_session_id
                )
            self.current_session_id = None
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed Supabase connection pool.")
