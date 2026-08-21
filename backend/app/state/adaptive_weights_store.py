"""
Persistence for small per-agent adaptive-parameter dicts that sit outside
`AgentState`'s PAD/trust/relational charter — `StateService` owns those
exclusively (see CLAUDE.md, "State is single-owner"; finding A2). This store
is for the two structurally identical dicts that charter doesn't cover:
`ReappraisalEngine.appraisal_weights` and `DecisionService.goal_utilities`
(#117 / H6, #118 / H7). Both are a handful of named floats, mutated only by
their own engine's own synchronous logic within a single cognitive turn — not
by a fire-and-forget background task the way short-term affect is — so unlike
`AgentState` there is no concurrent writer to guard against and no shared lock
to route through.

One `(agent_name, weight_key)` row per dict rather than adding columns to
`StateService`'s `agent_state` table, so persisting cognitive-engine internals
never needs to touch — or lock — the affect row `StateService` owns.
"""

import asyncio
import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)


class AdaptiveWeightsStore:
    """SQLite-backed load/save for one named dict[str, float] per agent."""

    def __init__(self, db_path: str = "state_cache.db"):
        self.db_path = db_path
        self._initialize_sqlite()

    def _initialize_sqlite(self) -> None:
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS adaptive_weights (
                    agent_name TEXT NOT NULL,
                    weight_key TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (agent_name, weight_key)
                )
                """
            )
        conn.close()

    async def load(self, agent_name: str, weight_key: str) -> dict[str, float] | None:
        """Returns the persisted dict, or None if nothing was ever saved."""
        return await asyncio.to_thread(self._load_sync, agent_name, weight_key)

    def _load_sync(self, agent_name: str, weight_key: str) -> dict[str, float] | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT weights_json FROM adaptive_weights "
                    "WHERE agent_name = ? AND weight_key = ?",
                    (agent_name, weight_key),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return json.loads(row[0])
        except Exception as e:
            logger.error(
                "[AdaptiveWeights] Failed to load %s/%s: %s", agent_name, weight_key, e
            )
            return None

    async def save(
        self, agent_name: str, weight_key: str, weights: dict[str, float]
    ) -> None:
        await asyncio.to_thread(self._save_sync, agent_name, weight_key, weights)

    def _save_sync(
        self, agent_name: str, weight_key: str, weights: dict[str, float]
    ) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO adaptive_weights
                            (agent_name, weight_key, weights_json, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(agent_name, weight_key) DO UPDATE SET
                            weights_json = excluded.weights_json,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (agent_name, weight_key, json.dumps(weights)),
                    )
            finally:
                # `finally`, not a trailing call: matches `agent_state.py`'s
                # `_write_state_row` -- an exception mid-INSERT must not leak
                # the connection.
                conn.close()
        except Exception as e:
            logger.error(
                "[AdaptiveWeights] Failed to save %s/%s: %s", agent_name, weight_key, e
            )
