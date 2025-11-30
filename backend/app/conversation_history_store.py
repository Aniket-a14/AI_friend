import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg

logger = logging.getLogger(__name__)

class ConversationHistoryStore:
    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST")
        self.port = os.getenv("POSTGRES_PORT")
        self.user = os.getenv("POSTGRES_USER")
        self.password = os.getenv("POSTGRES_PASSWORD")
        self.database = os.getenv("POSTGRES_DB")
        self.pool: Optional[asyncpg.Pool] = None
        self.current_session_id: Optional[uuid.UUID] = None

    async def initialize(self):
        """Initialize the database connection pool and create tables if they don't exist."""
        try:
            self.pool = await asyncpg.create_pool(
                user=self.user,
                password=self.password,
                database=self.database,
                host=self.host,
                port=self.port
            )
            await self._create_tables()
            logger.info("Connected to PostgreSQL database and ensured tables exist.")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def _create_tables(self):
        """Create sessions and messages tables if they don't exist."""
        if not self.pool:
            raise RuntimeError("Database pool is not initialized.")

        async with self.pool.acquire() as conn:
            # Create sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id UUID PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ended_at TIMESTAMPTZ
                );
            """)

            # Create messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY,
                    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL
                );
            """)

    async def start_session(self) -> uuid.UUID:
        """Start a new session and return its ID."""
        if not self.pool:
            logger.warning("Database not initialized, cannot start session.")
            return uuid.uuid4() # Return a dummy ID if DB is down to prevent crash

        self.current_session_id = uuid.uuid4()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO sessions (id, started_at) VALUES ($1, NOW())",
                    self.current_session_id
                )
            logger.info(f"Started new session: {self.current_session_id}")
            return self.current_session_id
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return self.current_session_id

    async def log_message(self, role: str, content: str):
        """Log a message to the current session."""
        if not self.pool:
            logger.warning("Database not initialized, cannot log message.")
            return

        if not self.current_session_id:
            logger.warning("No active session, cannot log message.")
            return

        if role not in ('user', 'assistant'):
            logger.error(f"Invalid role: {role}")
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
            logger.debug(f"Logged message ({role}): {content[:50]}...")
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    async def end_session(self):
        """End the current session."""
        if not self.pool:
            return

        if not self.current_session_id:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE sessions SET ended_at = NOW() WHERE id = $1",
                    self.current_session_id
                )
            logger.info(f"Ended session: {self.current_session_id}")
            self.current_session_id = None
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

    async def get_session_history(self, session_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Retrieve all messages for a specific session."""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, session_id, role, content, timestamp
                    FROM messages
                    WHERE session_id = $1
                    ORDER BY timestamp ASC
                    """,
                    session_id
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    async def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Retrieve all sessions."""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, started_at, ended_at
                    FROM sessions
                    ORDER BY started_at DESC
                    """
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all sessions: {e}")
            return []

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed PostgreSQL connection pool.")
