"""SQLite-backed compare-and-swap repository for cognitive workspaces."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Protocol

from .workspace import (
    CognitiveWorkspace,
    CognitiveWorkspaceSnapshot,
    StaleWorkspaceError,
    WorkspaceCommand,
    WorkspaceDivergenceError,
    WorkspaceTransitionRecord,
)


class WorkspaceStore(Protocol):
    """Persistence boundary for one authoritative foreground state."""

    async def get_snapshot(self, session_id: str) -> CognitiveWorkspaceSnapshot:
        """Load a detached snapshot, creating revision zero when absent."""
        ...

    async def commit_transition(
        self, command: WorkspaceCommand
    ) -> CognitiveWorkspaceSnapshot:
        """Atomically apply ``command`` when its CAS expectations are current."""
        ...

    async def increment_epoch(self, session_id: str) -> CognitiveWorkspaceSnapshot:
        """Fence older workers and begin revision zero in the next epoch."""
        ...

    async def list_transitions(
        self, session_id: str
    ) -> list[WorkspaceTransitionRecord]:
        """Return the append-only transition history for ``session_id``."""
        ...


class SQLiteWorkspaceStore:
    """Durable workspace repository using SQLite transactions for CAS.

    Public methods move blocking SQLite work off the event loop. A per-instance
    lock makes its shared connection safe across worker threads, while
    ``BEGIN IMMEDIATE`` serializes competing writers from other connections or
    processes before either can validate a stale revision.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            os.makedirs(db_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,
            timeout=5.0,
        )
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.execute("PRAGMA busy_timeout = 5000")
            if self.db_path != ":memory:":
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspace_state (
                    session_id TEXT PRIMARY KEY,
                    epoch INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    focus TEXT,
                    active_goals TEXT NOT NULL,
                    pending_action TEXT,
                    affect_snapshot TEXT NOT NULL,
                    last_percept_id TEXT,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workspace_transitions (
                    transition_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    from_revision INTEGER NOT NULL,
                    to_revision INTEGER NOT NULL,
                    command_source TEXT NOT NULL,
                    percept_id TEXT,
                    timestamp REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS workspace_transitions_session_idx
                    ON workspace_transitions (session_id, epoch, to_revision);

                CREATE TABLE IF NOT EXISTS workspace_epoch (
                    session_id TEXT PRIMARY KEY,
                    current_epoch INTEGER NOT NULL
                );
                """
            )

    async def get_snapshot(self, session_id: str) -> CognitiveWorkspaceSnapshot:
        return await asyncio.to_thread(self._get_snapshot_sync, session_id)

    def _get_snapshot_sync(self, session_id: str) -> CognitiveWorkspaceSnapshot:
        with self._lock:
            self._begin_write()
            try:
                workspace = self._load_or_create_workspace(session_id)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return workspace.to_snapshot()

    async def commit_transition(
        self, command: WorkspaceCommand
    ) -> CognitiveWorkspaceSnapshot:
        return await asyncio.to_thread(self._commit_transition_sync, command)

    def _commit_transition_sync(
        self, command: WorkspaceCommand
    ) -> CognitiveWorkspaceSnapshot:
        with self._lock:
            self._begin_write()
            try:
                current = self._load_or_create_workspace(command.session_id)
                self._validate_cas(current, command)
                updated = self._apply_command(current, command)
                self._write_transition(current, updated, command)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return updated.to_snapshot()

    async def increment_epoch(self, session_id: str) -> CognitiveWorkspaceSnapshot:
        return await asyncio.to_thread(self._increment_epoch_sync, session_id)

    def _increment_epoch_sync(self, session_id: str) -> CognitiveWorkspaceSnapshot:
        with self._lock:
            self._begin_write()
            try:
                epoch_row = self._connection.execute(
                    "SELECT current_epoch FROM workspace_epoch WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                next_epoch = int(epoch_row["current_epoch"]) + 1 if epoch_row else 1
                self._connection.execute(
                    """
                    INSERT INTO workspace_epoch (session_id, current_epoch)
                    VALUES (?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        current_epoch = excluded.current_epoch
                    """,
                    (session_id, next_epoch),
                )
                current = self._read_workspace(session_id)
                workspace = self._workspace_for_new_epoch(
                    session_id, next_epoch, current
                )
                self._upsert_workspace(workspace)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise
        return workspace.to_snapshot()

    async def list_transitions(
        self, session_id: str
    ) -> list[WorkspaceTransitionRecord]:
        return await asyncio.to_thread(self._list_transitions_sync, session_id)

    def _list_transitions_sync(
        self, session_id: str
    ) -> list[WorkspaceTransitionRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT transition_id, session_id, from_revision, to_revision,
                       epoch, command_source, percept_id, timestamp
                FROM workspace_transitions
                WHERE session_id = ?
                ORDER BY epoch, to_revision, timestamp, transition_id
                """,
                (session_id,),
            ).fetchall()
        return [
            WorkspaceTransitionRecord(
                transition_id=str(row["transition_id"]),
                session_id=str(row["session_id"]),
                from_revision=int(row["from_revision"]),
                to_revision=int(row["to_revision"]),
                epoch=int(row["epoch"]),
                command_source=str(row["command_source"]),
                percept_id=row["percept_id"],
                timestamp=float(row["timestamp"]),
            )
            for row in rows
        ]

    async def close(self) -> None:
        """Close the connection after all outstanding operations finish."""
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            self._connection.close()

    def _begin_write(self) -> None:
        self._connection.execute("BEGIN IMMEDIATE")

    def _load_or_create_workspace(self, session_id: str) -> CognitiveWorkspace:
        epoch_row = self._connection.execute(
            "SELECT current_epoch FROM workspace_epoch WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if epoch_row is None:
            epoch = 1
            self._connection.execute(
                "INSERT INTO workspace_epoch (session_id, current_epoch) VALUES (?, ?)",
                (session_id, epoch),
            )
        else:
            epoch = int(epoch_row["current_epoch"])

        workspace = self._read_workspace(session_id)
        if workspace is None:
            workspace = CognitiveWorkspace.fresh(session_id, epoch)
            self._insert_workspace(workspace)
        elif workspace.epoch != epoch:
            raise WorkspaceDivergenceError(
                f"Workspace epoch metadata diverged for session {session_id!r}"
            )
        return workspace

    def _read_workspace(self, session_id: str) -> CognitiveWorkspace | None:
        row = self._connection.execute(
            "SELECT * FROM workspace_state WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return CognitiveWorkspace(
            session_id=str(row["session_id"]),
            epoch=int(row["epoch"]),
            revision=int(row["revision"]),
            focus=row["focus"],
            active_goals=list(json.loads(row["active_goals"])),
            pending_action=(
                json.loads(row["pending_action"])
                if row["pending_action"] is not None
                else None
            ),
            affect_snapshot={
                str(key): float(value)
                for key, value in json.loads(row["affect_snapshot"]).items()
            },
            last_percept_id=row["last_percept_id"],
            updated_at=float(row["updated_at"]),
        )

    def _validate_cas(
        self, current: CognitiveWorkspace, command: WorkspaceCommand
    ) -> None:
        if command.expected_epoch != current.epoch:
            raise StaleWorkspaceError(
                "Workspace epoch is stale: "
                f"expected {command.expected_epoch}, current {current.epoch}"
            )
        if command.expected_revision != current.revision:
            raise StaleWorkspaceError(
                "Workspace revision is stale: "
                f"expected {command.expected_revision}, current {current.revision}"
            )

    def _apply_command(
        self, current: CognitiveWorkspace, command: WorkspaceCommand
    ) -> CognitiveWorkspace:
        removed_goals = set(command.remove_goals)
        active_goals = [
            goal for goal in current.active_goals if goal not in removed_goals
        ]
        for goal in command.add_goals:
            if goal not in active_goals:
                active_goals.append(goal)

        affect_snapshot = dict(current.affect_snapshot)
        if command.affect_update is not None:
            affect_snapshot.update(command.affect_update)

        pending_action = copy.deepcopy(current.pending_action)
        if command.pending_action is not None:
            if pending_action is None:
                pending_action = {}
            pending_action.update(copy.deepcopy(command.pending_action))
        if command.clear_pending_action:
            pending_action = None

        focus = (
            command.focus_update if command.focus_update is not None else current.focus
        )
        if command.clear_focus:
            focus = None

        return CognitiveWorkspace(
            session_id=current.session_id,
            epoch=current.epoch,
            revision=current.revision + 1,
            focus=focus,
            active_goals=active_goals,
            pending_action=pending_action,
            affect_snapshot=affect_snapshot,
            last_percept_id=(
                command.percept_id
                if command.percept_id is not None
                else current.last_percept_id
            ),
            updated_at=time.time(),
        )

    def _write_transition(
        self,
        current: CognitiveWorkspace,
        updated: CognitiveWorkspace,
        command: WorkspaceCommand,
    ) -> None:
        cursor = self._connection.execute(
            """
            UPDATE workspace_state
            SET epoch = ?, revision = ?, focus = ?, active_goals = ?,
                pending_action = ?, affect_snapshot = ?, last_percept_id = ?,
                updated_at = ?
            WHERE session_id = ? AND epoch = ? AND revision = ?
            """,
            self._workspace_update_values(updated, current),
        )
        if cursor.rowcount != 1:
            raise StaleWorkspaceError(
                "Workspace changed while applying the validated transition"
            )

        self._connection.execute(
            """
            INSERT INTO workspace_transitions (
                transition_id, session_id, epoch, from_revision, to_revision,
                command_source, percept_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                command.session_id,
                updated.epoch,
                current.revision,
                updated.revision,
                command.command_source,
                command.percept_id,
                updated.updated_at,
            ),
        )

    @staticmethod
    def _workspace_update_values(
        updated: CognitiveWorkspace, current: CognitiveWorkspace
    ) -> tuple[object, ...]:
        return (
            updated.epoch,
            updated.revision,
            updated.focus,
            json.dumps(updated.active_goals),
            json.dumps(updated.pending_action)
            if updated.pending_action is not None
            else None,
            json.dumps(updated.affect_snapshot),
            updated.last_percept_id,
            updated.updated_at,
            updated.session_id,
            current.epoch,
            current.revision,
        )

    def _workspace_for_new_epoch(
        self,
        session_id: str,
        epoch: int,
        current: CognitiveWorkspace | None,
    ) -> CognitiveWorkspace:
        if current is None:
            return CognitiveWorkspace.fresh(session_id, epoch)
        return CognitiveWorkspace(
            session_id=session_id,
            epoch=epoch,
            revision=0,
            focus=current.focus,
            active_goals=list(current.active_goals),
            pending_action=copy.deepcopy(current.pending_action),
            affect_snapshot=dict(current.affect_snapshot),
            last_percept_id=current.last_percept_id,
            updated_at=time.time(),
        )

    def _insert_workspace(self, workspace: CognitiveWorkspace) -> None:
        self._connection.execute(
            """
            INSERT INTO workspace_state (
                session_id, epoch, revision, focus, active_goals,
                pending_action, affect_snapshot, last_percept_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._workspace_insert_values(workspace),
        )

    def _upsert_workspace(self, workspace: CognitiveWorkspace) -> None:
        self._connection.execute(
            """
            INSERT INTO workspace_state (
                session_id, epoch, revision, focus, active_goals,
                pending_action, affect_snapshot, last_percept_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                epoch = excluded.epoch,
                revision = excluded.revision,
                focus = excluded.focus,
                active_goals = excluded.active_goals,
                pending_action = excluded.pending_action,
                affect_snapshot = excluded.affect_snapshot,
                last_percept_id = excluded.last_percept_id,
                updated_at = excluded.updated_at
            """,
            self._workspace_insert_values(workspace),
        )

    @staticmethod
    def _workspace_insert_values(workspace: CognitiveWorkspace) -> tuple[object, ...]:
        return (
            workspace.session_id,
            workspace.epoch,
            workspace.revision,
            workspace.focus,
            json.dumps(workspace.active_goals),
            json.dumps(workspace.pending_action)
            if workspace.pending_action is not None
            else None,
            json.dumps(workspace.affect_snapshot),
            workspace.last_percept_id,
            workspace.updated_at,
        )
