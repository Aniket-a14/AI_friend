import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg
from ..config import Config

logger = logging.getLogger(__name__)

DEFAULT_PERSONALITY_JSON = (
    '{"name":"AI Friend","core_personality":{"immutable":{"values":["Honesty","Privacy","Curiosity"],'
    '"base_tone":"Warm, intellectual, and slightly protective","boundaries":["Will never share user data",'
    '"Will not adopt toxic behavior"]},"adaptive_traits":[]},"speaking_style":{"pace":"natural",'
    '"verbosity":"balanced"},"conversation_rules":{"avoid":[]}}'
)
DEFAULT_HISTORY_JSON = '{"relationship":"Friend","memories":[]}'


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

            logger.info("Connected to Database via asyncpg.")

            # Seed personality/history if the table is empty
            await self._ensure_config_exists()

        except Exception as e:
            logger.error(f"Failed to initialize ConversationHistoryStore: {e}")
            raise

    async def _ensure_config_exists(self):
        """Ensure that the agent_configs table has at least one record (id: 1)."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT id FROM agent_configs WHERE id = 1")
                if not row:
                    logger.info(
                        "No AgentConfig found. Seeding from local JSON files..."
                    )
                    state_dir = os.path.dirname(os.path.abspath(__file__))
                    app_dir = os.path.dirname(state_dir)

                    personality_path = os.path.join(app_dir, "personality.json")
                    history_path = os.path.join(app_dir, "history.json")

                    personality = DEFAULT_PERSONALITY_JSON
                    try:
                        with open(
                            personality_path,
                            "r",
                            encoding="utf-8",
                        ) as f:
                            personality = f.read()
                    except Exception as e:
                        logger.warning(
                            f"Could not read local personality.json for seeding: {e}"
                        )

                    history = DEFAULT_HISTORY_JSON
                    try:
                        with open(
                            history_path,
                            "r",
                            encoding="utf-8",
                        ) as f:
                            history = f.read()
                    except Exception as e:
                        logger.warning(
                            f"Could not read local history.json for seeding: {e}"
                        )

                    await conn.execute(
                        """
                        INSERT INTO agent_configs (id, personality, background_history, evolved_learnings, updated_at)
                        VALUES (1, $1, $2, '', NOW())
                        """,
                        personality,
                        history,
                    )
                    logger.info("AgentConfig seeded with empty Evolved Learnings.")
        except Exception as e:
            logger.error(f"Failed to ensure AgentConfig exists: {e}")

    async def get_agent_config(self) -> Dict[str, str]:
        """Fetch personality, history, and evolved learnings from AgentConfig."""
        if not self.pool:
            return {"personality": "{}", "history": "{}", "evolved_learnings": ""}

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM agent_configs WHERE id = 1")
                if row:
                    # Defensive check in case migration is still propagating
                    data = dict(row)
                    return {
                        "personality": data.get("personality", "{}"),
                        "history": data.get("background_history", "{}"),
                        "evolved_learnings": data.get("evolved_learnings", "") or "",
                    }
        except Exception as e:
            logger.error(f"Failed to fetch AgentConfig: {e}")

        return {"personality": "{}", "history": "{}", "evolved_learnings": ""}

    async def update_evolved_learnings(self, content: str):
        """Update the growing memory of the AI."""
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agent_configs SET evolved_learnings = $1, updated_at = NOW() WHERE id = 1",
                    content,
                )
        except Exception as e:
            logger.error(f"Failed to update evolved learnings: {e}")

    async def update_agent_config(
        self,
        personality: str,
        history: str,
        evolved_learnings: str = "",
    ):
        """Persist the active runtime identity back to durable config storage."""
        if not self.pool:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_configs (
                        id, personality, background_history, evolved_learnings, updated_at
                    )
                    VALUES (1, $1, $2, $3, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        personality = EXCLUDED.personality,
                        background_history = EXCLUDED.background_history,
                        evolved_learnings = EXCLUDED.evolved_learnings,
                        updated_at = NOW()
                    """,
                    personality,
                    history,
                    evolved_learnings or "",
                )
        except Exception as e:
            logger.error(f"Failed to update agent config: {e}")

    async def start_session(self) -> uuid.UUID:
        """Start a new session and return its ID."""
        if not self.pool:
            self.current_session_id = uuid.uuid4()
            return self.current_session_id

        self.current_session_id = uuid.uuid4()
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO sessions (id, started_at) VALUES ($1, NOW())",
                    self.current_session_id,
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
                    content,
                )
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    async def get_recent_sessions_gist(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetch a 'blurry' view of the last few sessions (just first/last messages)."""
        if not self.pool:
            return []

        try:
            async with self.pool.acquire() as conn:
                # Single query: sessions + first/last message via LATERAL (no N+1)
                if self.current_session_id:
                    rows = await conn.fetch(
                        """
                        SELECT s.id AS session_id, s.started_at,
                               m.role, m.content, m.timestamp, m.pos
                        FROM (
                            SELECT id, started_at FROM sessions
                            WHERE id != $2
                            ORDER BY started_at DESC LIMIT $1
                        ) s,
                        LATERAL (
                            (SELECT role, content, timestamp, 1 AS pos FROM messages WHERE session_id = s.id ORDER BY timestamp ASC LIMIT 1)
                            UNION ALL
                            (SELECT role, content, timestamp, 2 AS pos FROM messages WHERE session_id = s.id ORDER BY timestamp DESC LIMIT 1)
                        ) m
                        ORDER BY s.started_at DESC, m.pos ASC
                        """,
                        limit,
                        self.current_session_id,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT s.id AS session_id, s.started_at,
                               m.role, m.content, m.timestamp, m.pos
                        FROM (
                            SELECT id, started_at FROM sessions
                            ORDER BY started_at DESC LIMIT $1
                        ) s,
                        LATERAL (
                            (SELECT role, content, timestamp, 1 AS pos FROM messages WHERE session_id = s.id ORDER BY timestamp ASC LIMIT 1)
                            UNION ALL
                            (SELECT role, content, timestamp, 2 AS pos FROM messages WHERE session_id = s.id ORDER BY timestamp DESC LIMIT 1)
                        ) m
                        ORDER BY s.started_at DESC, m.pos ASC
                        """,
                        limit,
                    )

                # Group rows by session
                gists_by_session = {}
                for row in rows:
                    sid = row["session_id"]
                    if sid not in gists_by_session:
                        gists_by_session[sid] = {
                            "date": row["started_at"].strftime("%Y-%m-%d"),
                            "interaction": [],
                        }
                    gists_by_session[sid]["interaction"].append(
                        {
                            "role": row["role"],
                            "content": row["content"],
                            "timestamp": row["timestamp"],
                        }
                    )

                return list(gists_by_session.values())
        except Exception as e:
            logger.error(f"Failed to fetch session gists: {e}")
            return []

    async def get_last_session_time(self) -> Optional[datetime]:
        """Fetch the ended_at time of the most recent completed session."""
        if not self.pool:
            return None

        try:
            async with self.pool.acquire() as conn:
                if self.current_session_id:
                    row = await conn.fetchrow(
                        """
                        SELECT ended_at
                        FROM sessions
                        WHERE id != $1 AND ended_at IS NOT NULL
                        ORDER BY ended_at DESC
                        LIMIT 1
                        """,
                        self.current_session_id,
                    )
                else:
                    row = await conn.fetchrow(
                        """
                        SELECT ended_at
                        FROM sessions
                        WHERE ended_at IS NOT NULL
                        ORDER BY ended_at DESC
                        LIMIT 1
                        """
                    )
                return row["ended_at"] if row else None
        except Exception as e:
            logger.error(f"Failed to fetch last session time: {e}")
            return None

    async def get_total_sessions_count(self) -> int:
        """Count total historical sessions for milestone tracking."""
        if not self.pool:
            return 0
        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM sessions")
                return count or 0
        except Exception as e:
            logger.error(f"Failed to fetch session count: {e}")
            return 0

    async def get_last_interaction_brief(self) -> Optional[str]:
        """Fetch the very last assistant message content to gauge sentiment."""
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT content FROM messages WHERE role = 'assistant' ORDER BY timestamp DESC LIMIT 1"
                )
                return row["content"] if row else None
        except Exception as e:
            logger.error(f"Failed to fetch last interaction: {e}")
            return None

    async def end_session(self):
        """End the current session."""
        if not self.pool or not self.current_session_id:
            return

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE sessions SET ended_at = NOW() WHERE id = $1",
                    self.current_session_id,
                )
            self.current_session_id = None
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed Database connection pool.")
