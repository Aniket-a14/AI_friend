import copy
import json
import logging
import os
import sqlite3
import threading
from typing import Any

logger = logging.getLogger("identity_core_store")


class IdentityCoreStore:
    """
    Tier-1 SQLite Store for Persistent and Immutable Identity Core.
    Guarantees sub-millisecond local cached lookups for real-time speech paths.
    """

    _instances = []

    def __init__(self, db_path: str = "identity_core.db", publish_cb=None):
        self.db_path = db_path
        self._cache_lock = threading.Lock()
        self._cached_identity: dict[str, Any] = {}
        self.publish_cb = publish_cb
        # P4-8: strong-reference holder for the fire-and-forget cache.sync
        # broadcast below.
        self._background_tasks: set = set()
        IdentityCoreStore._instances.append(self)

        if db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:")
            self._conn.row_factory = sqlite3.Row
        else:
            self._conn = None
            db_dir = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(db_dir, exist_ok=True)

        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn:
            return self._conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _release_connection(self, conn: sqlite3.Connection):
        if conn != self._conn:
            conn.close()

    def _initialize_db(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS identity_core (
                    id INTEGER PRIMARY KEY,
                    name TEXT DEFAULT 'AI Friend',
                    values_list TEXT DEFAULT '[]',
                    base_tone TEXT DEFAULT 'Warm, intellectual, and slightly protective',
                    boundaries TEXT DEFAULT '[]',
                    speaking_style_pace TEXT DEFAULT 'natural',
                    speaking_style_verbosity TEXT DEFAULT 'balanced',
                    avoid_rules TEXT DEFAULT '[]',
                    relationship TEXT DEFAULT 'Friend',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            self._release_connection(conn)

        # Seed initial defaults if empty
        self.load_into_cache()
        if not self.get_identity():
            self._seed_default_identity()

    def _seed_default_identity(self):
        default_data = {
            "name": "AI Friend",
            "values_list": ["Honesty", "Privacy", "Curiosity"],
            "base_tone": "Warm, intellectual, and slightly protective",
            "boundaries": [
                "Will never share user data",
                "Will not adopt toxic behavior",
            ],
            "speaking_style_pace": "natural",
            "speaking_style_verbosity": "balanced",
            "avoid_rules": [],
            "relationship": "Friend",
        }
        self.update_identity(default_data)

    def load_into_cache(self) -> dict[str, Any]:
        """Loads identity values directly into memory for Tier-1 sub-ms lookups."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM identity_core WHERE id = 1")
            row = cursor.fetchone()
            if row:
                cached = {
                    "name": row["name"],
                    "values": json.loads(row["values_list"]),
                    "base_tone": row["base_tone"],
                    "boundaries": json.loads(row["boundaries"]),
                    "speaking_style_pace": row["speaking_style_pace"],
                    "speaking_style_verbosity": row["speaking_style_verbosity"],
                    "avoid_rules": json.loads(row["avoid_rules"]),
                    "relationship": row["relationship"],
                }
                with self._cache_lock:
                    self._cached_identity = cached
                return cached
        except Exception as e:
            logger.error(f"Failed to load identity core from SQLite: {e}")
            with self._cache_lock:
                self._cached_identity = {}
        finally:
            self._release_connection(conn)
        return {}

    def get_identity(self) -> dict[str, Any]:
        """Sub-millisecond memory-cached getter."""
        with self._cache_lock:
            cached = self._cached_identity
        if not cached:
            return copy.deepcopy(self.load_into_cache())
        return copy.deepcopy(cached)

    def update_identity(self, data: dict[str, Any]):
        """Persists identity mutations to SQLite and updates memory cache."""
        name = data.get("name", "AI Friend")
        values = data.get("values", data.get("values_list", []))
        base_tone = data.get("base_tone", "Warm, intellectual, and slightly protective")
        boundaries = data.get("boundaries", [])
        pace = data.get("speaking_style_pace", "natural")
        verbosity = data.get("speaking_style_verbosity", "balanced")
        avoid = data.get("avoid_rules", [])
        rel = data.get("relationship", "Friend")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO identity_core (
                    id, name, values_list, base_tone, boundaries,
                    speaking_style_pace, speaking_style_verbosity, avoid_rules, relationship, updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    values_list = excluded.values_list,
                    base_tone = excluded.base_tone,
                    boundaries = excluded.boundaries,
                    speaking_style_pace = excluded.speaking_style_pace,
                    speaking_style_verbosity = excluded.speaking_style_verbosity,
                    avoid_rules = excluded.avoid_rules,
                    relationship = excluded.relationship,
                    updated_at = CURRENT_TIMESTAMP
            """,
                (
                    name,
                    json.dumps(values),
                    base_tone,
                    json.dumps(boundaries),
                    pace,
                    verbosity,
                    json.dumps(avoid),
                    rel,
                ),
            )
            conn.commit()
            self.load_into_cache()
            logger.info("Identity Core Store updated and cached.")

            # Broadcast cache invalidation to other processes via NATS if registered
            if self.publish_cb:
                try:
                    import asyncio

                    from ..utils.background_tasks import spawn_background

                    if asyncio.iscoroutinefunction(self.publish_cb):
                        spawn_background(
                            self._background_tasks,
                            self.publish_cb(
                                "cache.sync",
                                {"store": "identity_core", "action": "invalidate"},
                            ),
                        )
                    else:
                        self.publish_cb(
                            "cache.sync",
                            {"store": "identity_core", "action": "invalidate"},
                        )
                except Exception as sync_err:
                    logger.warning(
                        f"Failed to publish cache sync broadcast: {sync_err}"
                    )
        except Exception as e:
            logger.error(f"Failed to update identity core in SQLite: {e}")
            raise
        finally:
            self._release_connection(conn)

    @classmethod
    def invalidate_all_local_caches(cls):
        """Invalidates and reloads the cached identities on all local active store instances."""
        for inst in cls._instances:
            try:
                inst.load_into_cache()
            except Exception as e:
                logger.warning(f"Failed to invalidate local cache instance: {e}")
