import os
import json
import logging
import sqlite3
from typing import List, Dict, Any, Optional
import redis

logger = logging.getLogger("working_memory_store")


class WorkingMemoryStore:
    """
    Tier-1 Working Memory Store.
    Uses Redis (127.0.0.1:6379) for distributed state sync and under-10ms latency,
    with an automatic local SQLite fallback (`working_memory.db`) if Redis is offline.
    """

    def __init__(
        self,
        redis_host: str = "127.0.0.1",
        redis_port: int = 6379,
        db_path: str = "working_memory.db",
        max_turns: int = 8
    ):
        self.max_turns = max_turns
        self.db_path = db_path
        self.redis_client: Optional[redis.Redis] = None

        # 1. Attempt Redis Connection
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                socket_connect_timeout=1.0,
                decode_responses=True
            )
            # Ping to confirm live connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis Working Memory on {redis_host}:{redis_port}")
        except Exception as e:
            self.redis_client = None
            logger.warning(
                f"Redis Working Memory unavailable: {e}. Falling back to SQLite: {db_path}"
            )

        # 2. Setup SQLite fallback DB structure
        if self.redis_client is None and db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(db_dir, exist_ok=True)

        self._initialize_sqlite()

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_sqlite(self):
        if self.redis_client is not None:
            return

        with self._get_sqlite_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS working_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS working_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    # --- Real-Time Turns Playout (Last 5–8 turns) ---

    def add_turn(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Append a dialogue turn, immediately trimming excess turns to prevent context bloat."""
        meta_json = json.dumps(metadata or {})
        turn_data = {"role": role, "content": content, "metadata": meta_json}

        if self.redis_client:
            try:
                # Add to Redis List
                self.redis_client.rpush("working:turns", json.dumps(turn_data))
                # Trim list to max_turns
                self.redis_client.ltrim("working:turns", -self.max_turns, -1)
                return
            except Exception as e:
                logger.error(f"Redis add_turn failed: {e}. Falling back to SQLite.")
                # Fall through to SQLite

        # SQLite Fallback execution
        try:
            with self._get_sqlite_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO working_turns (role, content, metadata) VALUES (?, ?, ?)",
                    (role, content, meta_json)
                )
                conn.commit()

                # Trim SQLite table to keep only the last max_turns
                cursor.execute("""
                    DELETE FROM working_turns
                    WHERE id NOT IN (
                        SELECT id FROM working_turns
                        ORDER BY id DESC LIMIT ?
                    )
                """, (self.max_turns,))
                conn.commit()
        except Exception as e:
            logger.error(f"SQLite add_turn failed: {e}")

    def get_recent_turns(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve recent conversation turns in chronological order."""
        limit = limit or self.max_turns
        if self.redis_client:
            try:
                raw_turns = self.redis_client.lrange("working:turns", -limit, -1)
                turns = []
                for rt in raw_turns:
                    t = json.loads(rt)
                    turns.append({
                        "role": t["role"],
                        "content": t["content"],
                        "metadata": json.loads(t["metadata"])
                    })
                return turns
            except Exception as e:
                logger.error(f"Redis get_recent_turns failed: {e}. Falling back to SQLite.")

        # SQLite Fallback
        try:
            with self._get_sqlite_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT role, content, metadata FROM working_turns ORDER BY id ASC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                return [{
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"])
                } for row in rows]
        except Exception as e:
            logger.error(f"SQLite get_recent_turns failed: {e}")
            return []

    def clear_turns(self):
        """Reset the active working memory turns (e.g. on new session starts)."""
        if self.redis_client:
            try:
                self.redis_client.delete("working:turns")
                return
            except Exception as e:
                logger.error(f"Redis clear_turns failed: {e}. Falling back to SQLite.")

        try:
            with self._get_sqlite_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM working_turns")
                conn.commit()
        except Exception as e:
            logger.error(f"SQLite clear_turns failed: {e}")

    # --- Short-Term Affect / Goals / Variables Synchronization ---

    def set_state_var(self, key: str, value: Any):
        """Set a synced working memory variable (e.g. goals, short-term emotional states)."""
        val_str = json.dumps(value)
        if self.redis_client:
            try:
                self.redis_client.hset("working:state", key, val_str)
                return
            except Exception as e:
                logger.error(f"Redis set_state_var failed: {e}. Falling back to SQLite.")

        try:
            with self._get_sqlite_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO working_state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, val_str)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"SQLite set_state_var failed: {e}")

    def get_state_var(self, key: str, default: Any = None) -> Any:
        """Get a synced working memory variable."""
        if self.redis_client:
            try:
                val_str = self.redis_client.hget("working:state", key)
                if val_str is not None:
                    return json.loads(val_str)
                return default
            except Exception as e:
                logger.error(f"Redis get_state_var failed: {e}. Falling back to SQLite.")

        try:
            with self._get_sqlite_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM working_state WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row["value"])
        except Exception as e:
            logger.error(f"SQLite get_state_var failed: {e}")
        return default
