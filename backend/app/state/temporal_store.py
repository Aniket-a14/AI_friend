"""SQLite repository for append-only experiences and temporal beliefs."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from .memory_records import BeliefRecord, ContradictionDecision, ExperienceRecord


class TemporalMemoryStore:
    """Persist memory truth with serialized SQLite transitions.

    SQLite calls run in worker threads. The instance lock protects its shared
    connection, while ``BEGIN IMMEDIATE`` serializes writers using separate
    store instances backed by the same database file.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
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
                CREATE TABLE IF NOT EXISTS experiences (
                    record_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    interval_start REAL NOT NULL,
                    interval_end REAL NOT NULL,
                    source_evidence_ids TEXT NOT NULL,
                    appraisal_snapshot TEXT NOT NULL,
                    action_id TEXT,
                    outcome_id TEXT,
                    summary TEXT NOT NULL,
                    recorded_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS beliefs (
                    record_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    valid_from REAL NOT NULL,
                    valid_until REAL,
                    recorded_at REAL NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    superseded_by TEXT,
                    contradicts_id TEXT,
                    provenance TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS beliefs_current_idx
                    ON beliefs (subject, status, valid_from, valid_until);
                CREATE INDEX IF NOT EXISTS beliefs_recorded_idx
                    ON beliefs (subject, recorded_at, record_id);

                CREATE TABLE IF NOT EXISTS belief_reinforcements (
                    reinforcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    existing_record_id TEXT NOT NULL,
                    new_record_id TEXT NOT NULL UNIQUE,
                    confidence REAL NOT NULL,
                    recorded_at REAL NOT NULL
                );
                """
            )

    async def store_experience(self, record: ExperienceRecord) -> None:
        """Append an experience once; duplicate identifiers are rejected."""
        await asyncio.to_thread(self._store_experience_sync, record)

    def _store_experience_sync(self, record: ExperienceRecord) -> None:
        with self._lock:
            self._begin_write()
            try:
                self._connection.execute(
                    """
                    INSERT INTO experiences (
                        record_id, session_id, participants, interval_start,
                        interval_end, source_evidence_ids, appraisal_snapshot,
                        action_id, outcome_id, summary, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.record_id,
                        record.session_id,
                        json.dumps(record.participants),
                        record.interval_start,
                        record.interval_end,
                        json.dumps(record.source_evidence_ids),
                        json.dumps(record.appraisal_snapshot),
                        record.action_id,
                        record.outcome_id,
                        record.summary,
                        record.recorded_at,
                    ),
                )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise

    async def get_experience(self, record_id: str) -> ExperienceRecord | None:
        """Return the immutable experience identified by ``record_id``."""
        return await asyncio.to_thread(self._get_experience_sync, record_id)

    def _get_experience_sync(self, record_id: str) -> ExperienceRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM experiences WHERE record_id = ?", (record_id,)
            ).fetchone()
        if row is None:
            return None
        return ExperienceRecord(
            record_id=str(row["record_id"]),
            session_id=str(row["session_id"]),
            participants=list(json.loads(row["participants"])),
            interval_start=float(row["interval_start"]),
            interval_end=float(row["interval_end"]),
            source_evidence_ids=list(json.loads(row["source_evidence_ids"])),
            appraisal_snapshot={
                str(key): float(value)
                for key, value in json.loads(row["appraisal_snapshot"]).items()
            },
            action_id=row["action_id"],
            outcome_id=row["outcome_id"],
            summary=str(row["summary"]),
            recorded_at=float(row["recorded_at"]),
        )

    async def store_belief(self, record: BeliefRecord) -> None:
        """Store one belief exactly as supplied without overwriting history."""
        await asyncio.to_thread(self._store_belief_sync, record)

    def _store_belief_sync(self, record: BeliefRecord) -> None:
        with self._lock:
            self._begin_write()
            try:
                self._insert_belief(record)
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise

    async def get_belief(self, record_id: str) -> BeliefRecord | None:
        """Return the belief identified by ``record_id``, if it exists."""
        return await asyncio.to_thread(self._get_belief_sync, record_id)

    def _get_belief_sync(self, record_id: str) -> BeliefRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM beliefs WHERE record_id = ?", (record_id,)
            ).fetchone()
        return self._belief_from_row(row) if row is not None else None

    async def query_current_beliefs(
        self, subject: str | None = None, as_of: float | None = None
    ) -> list[BeliefRecord]:
        """Return active beliefs valid at ``as_of`` or at the current time."""
        query_time = time.time() if as_of is None else as_of
        return await asyncio.to_thread(
            self._query_current_beliefs_sync, subject, query_time
        )

    def _query_current_beliefs_sync(
        self, subject: str | None, query_time: float
    ) -> list[BeliefRecord]:
        sql = (
            "SELECT * FROM beliefs WHERE status = 'ACTIVE' "
            "AND valid_from <= ? AND (valid_until IS NULL OR valid_until > ?)"
        )
        parameters: tuple[object, ...] = (query_time, query_time)
        if subject is not None:
            sql += " AND subject = ?"
            parameters += (subject,)
        sql += " ORDER BY valid_from, recorded_at, record_id"
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        return [self._belief_from_row(row) for row in rows]

    async def query_historical_beliefs(
        self, subject: str | None = None
    ) -> list[BeliefRecord]:
        """Return every stored belief in recorded-time order."""
        return await asyncio.to_thread(self._query_historical_beliefs_sync, subject)

    def _query_historical_beliefs_sync(
        self, subject: str | None
    ) -> list[BeliefRecord]:
        sql = "SELECT * FROM beliefs"
        parameters: tuple[object, ...] = ()
        if subject is not None:
            sql += " WHERE subject = ?"
            parameters = (subject,)
        sql += " ORDER BY recorded_at, record_id"
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        return [self._belief_from_row(row) for row in rows]

    async def apply_contradiction(
        self, decision: ContradictionDecision, new_record: BeliefRecord
    ) -> None:
        """Atomically apply one classified truth transition and its audit data."""
        await asyncio.to_thread(self._apply_contradiction_sync, decision, new_record)

    def _apply_contradiction_sync(
        self, decision: ContradictionDecision, new_record: BeliefRecord
    ) -> None:
        if decision.new_record_id != new_record.record_id:
            raise ValueError("Decision new_record_id must match new_record.record_id")
        with self._lock:
            self._begin_write()
            try:
                existing = self._require_belief(decision.existing_record_id)
                if existing.status != "ACTIVE":
                    raise ValueError(
                        "Contradiction transitions require an active existing belief"
                    )
                if decision.contradiction_type == "UPDATE":
                    self._connection.execute(
                        """
                        UPDATE beliefs
                        SET valid_until = ?, status = 'SUPERSEDED', superseded_by = ?
                        WHERE record_id = ?
                        """,
                        (new_record.valid_from, new_record.record_id, existing.record_id),
                    )
                    self._insert_belief(
                        new_record.model_copy(
                            update={"status": "ACTIVE", "contradicts_id": existing.record_id}
                        )
                    )
                elif decision.contradiction_type == "CORRECTION":
                    self._connection.execute(
                        """
                        UPDATE beliefs
                        SET valid_until = ?, status = 'INVALIDATED', contradicts_id = ?
                        WHERE record_id = ?
                        """,
                        (time.time(), new_record.record_id, existing.record_id),
                    )
                    self._insert_belief(
                        new_record.model_copy(
                            update={"status": "ACTIVE", "contradicts_id": existing.record_id}
                        )
                    )
                elif decision.contradiction_type == "CONFLICT":
                    self._connection.execute(
                        """
                        UPDATE beliefs
                        SET status = 'DISPUTED', confidence = confidence * 0.5,
                            contradicts_id = ?
                        WHERE record_id = ?
                        """,
                        (new_record.record_id, existing.record_id),
                    )
                    self._insert_belief(
                        new_record.model_copy(
                            update={
                                "status": "DISPUTED",
                                "confidence": new_record.confidence * 0.5,
                                "contradicts_id": existing.record_id,
                            }
                        )
                    )
                else:
                    self._connection.execute(
                        """
                        UPDATE beliefs
                        SET confidence = CASE WHEN confidence < ? THEN ? ELSE confidence END
                        WHERE record_id = ?
                        """,
                        (new_record.confidence, new_record.confidence, existing.record_id),
                    )
                    self._connection.execute(
                        """
                        INSERT INTO belief_reinforcements (
                            existing_record_id, new_record_id, confidence, recorded_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            existing.record_id,
                            new_record.record_id,
                            new_record.confidence,
                            new_record.recorded_at,
                        ),
                    )
                self._connection.commit()
            except BaseException:
                self._connection.rollback()
                raise

    async def close(self) -> None:
        """Close the SQLite connection after outstanding work completes."""
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            self._connection.close()

    def _begin_write(self) -> None:
        self._connection.execute("BEGIN IMMEDIATE")

    def _insert_belief(self, record: BeliefRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO beliefs (
                record_id, subject, predicate, object, valid_from, valid_until,
                recorded_at, confidence, status, superseded_by, contradicts_id,
                provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.subject,
                record.predicate,
                record.object,
                record.valid_from,
                record.valid_until,
                record.recorded_at,
                record.confidence,
                record.status,
                record.superseded_by,
                record.contradicts_id,
                record.provenance,
            ),
        )

    def _require_belief(self, record_id: str) -> BeliefRecord:
        row = self._connection.execute(
            "SELECT * FROM beliefs WHERE record_id = ?", (record_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Belief record {record_id!r} does not exist")
        return self._belief_from_row(row)

    @staticmethod
    def _belief_from_row(row: sqlite3.Row) -> BeliefRecord:
        return BeliefRecord.model_validate(dict(row))
