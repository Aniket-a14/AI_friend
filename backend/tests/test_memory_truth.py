"""Temporal memory truth, contradiction, and SQLite concurrency tests."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.state.memory_records import (
    BeliefRecord,
    ContradictionDecision,
    DuplicateRecordError,
    ExperienceRecord,
    InvalidIntervalError,
    ProcedureRecord,
    RecordNotFoundError,
    classify_contradiction,
)
from app.state.temporal_store import TemporalMemoryStore


def _belief(
    record_id: str,
    object_value: str,
    *,
    valid_from: float = 10.0,
    valid_until: float | None = None,
    recorded_at: float = 10.0,
    confidence: float = 1.0,
) -> BeliefRecord:
    return BeliefRecord(
        record_id=record_id,
        subject="Ari",
        predicate="lives_in",
        object=object_value,
        valid_from=valid_from,
        valid_until=valid_until,
        recorded_at=recorded_at,
        confidence=confidence,
    )


def _decision(
    contradiction_type: str, existing_id: str, new_id: str
) -> ContradictionDecision:
    return ContradictionDecision(
        contradiction_type=contradiction_type,
        existing_record_id=existing_id,
        new_record_id=new_id,
        action_taken=contradiction_type.lower(),
        reason="test decision",
    )


@pytest.mark.asyncio
async def test_experience_records_are_immutable_and_append_only():
    """An experience must survive persistence without allowing rewrites."""
    store = TemporalMemoryStore(":memory:")
    record = ExperienceRecord(
        record_id="experience-1",
        session_id="session-1",
        participants=["Ari", "Nia"],
        interval_start=1.0,
        interval_end=2.0,
        source_evidence_ids=["evidence-1"],
        appraisal_snapshot={"valence": 0.3},
        action_id="action-1",
        outcome_id="outcome-1",
        summary="Ari and Nia discussed a move.",
        recorded_at=3.0,
    )
    try:
        with pytest.raises(ValidationError):
            record.summary = "rewritten"  # type: ignore[misc]

        await store.store_experience(record)
        persisted = await store.get_experience(record.record_id)

        assert persisted == record
        with pytest.raises(DuplicateRecordError):
            await store.store_experience(record)
        assert await store.get_experience(record.record_id) == record
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_bitemporal_current_and_historical_belief_queries():
    """A current query changes with time while history retains both facts."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("belief-old", "Lisbon", valid_from=10.0, recorded_at=11.0)
    new = _belief("belief-new", "Seoul", valid_from=20.0, recorded_at=21.0)
    try:
        await store.store_belief(old)
        assert [record.object for record in await store.query_current_beliefs(
            "Ari", as_of=15.0
        )] == ["Lisbon"]

        await store.apply_contradiction(_decision("UPDATE", old.record_id, new.record_id), new)

        assert [record.object for record in await store.query_current_beliefs(
            "Ari", as_of=25.0
        )] == ["Seoul"]
        assert [record.object for record in await store.query_current_beliefs(
            "Ari", as_of=15.0
        )] == ["Lisbon"]
        historical = await store.query_historical_beliefs("Ari")
        assert [record.record_id for record in historical] == ["belief-old", "belief-new"]
        assert historical[0].status == "SUPERSEDED"
        assert historical[0].valid_until == new.valid_from
        assert historical[0].superseded_by == new.record_id
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_update_closes_old_interval_and_activates_replacement():
    """An update must atomically supersede exactly one prior active belief."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon", confidence=0.8)
    new = _belief("new", "Seoul", valid_from=30.0, confidence=0.9)
    try:
        await store.store_belief(old)
        await store.apply_contradiction(_decision("UPDATE", "old", "new"), new)

        stored_old = await store.get_belief("old")
        stored_new = await store.get_belief("new")
        assert stored_old is not None
        assert stored_new is not None
        assert stored_old.status == "SUPERSEDED"
        assert stored_old.valid_until == 30.0
        assert stored_old.superseded_by == "new"
        assert stored_new.status == "ACTIVE"
        assert stored_new.contradicts_id == "old"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_correction_invalidates_old_belief_and_records_replacement():
    """An explicit correction must preserve the invalidated record for audit."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon")
    new = _belief("new", "Seoul", valid_from=20.0)
    try:
        await store.store_belief(old)
        before = time.time()
        await store.apply_contradiction(_decision("CORRECTION", "old", "new"), new)
        after = time.time()

        stored_old = await store.get_belief("old")
        stored_new = await store.get_belief("new")
        assert stored_old is not None
        assert stored_new is not None
        assert stored_old.status == "INVALIDATED"
        assert stored_old.valid_until is not None
        assert before <= stored_old.valid_until <= after
        assert stored_new.status == "ACTIVE"
        assert stored_new.contradicts_id == "old"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_conflict_disputes_both_beliefs_and_halves_confidence():
    """Competing assertions must remain visible and lose equal confidence."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon", confidence=0.8)
    new = _belief("new", "Seoul", confidence=0.6)
    try:
        await store.store_belief(old)
        await store.apply_contradiction(_decision("CONFLICT", "old", "new"), new)

        stored_old = await store.get_belief("old")
        stored_new = await store.get_belief("new")
        assert stored_old is not None
        assert stored_new is not None
        assert stored_old.status == "DISPUTED"
        assert stored_new.status == "DISPUTED"
        assert stored_old.confidence == pytest.approx(0.4)
        assert stored_new.confidence == pytest.approx(0.3)
        assert stored_old.contradicts_id == "new"
        assert stored_new.contradicts_id == "old"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_elaboration_reinforces_existing_belief_without_invalidation():
    """Repeated evidence must improve confidence without creating rival truth."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon", confidence=0.4)
    reinforcement = _belief("reinforcement", "Lisbon", confidence=0.9)
    try:
        await store.store_belief(old)
        await store.apply_contradiction(
            _decision("ELABORATION", "old", "reinforcement"), reinforcement
        )

        stored_old = await store.get_belief("old")
        assert stored_old is not None
        assert stored_old.status == "ACTIVE"
        assert stored_old.confidence == 0.9
        assert await store.get_belief("reinforcement") is None
        assert [record.record_id for record in await store.query_historical_beliefs()] == [
            "old"
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_transition_cannot_reopen_a_nonactive_belief():
    """A completed transition must reject a delayed competing replacement."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon")
    first = _belief("first", "Seoul", valid_from=20.0)
    delayed = _belief("delayed", "Tokyo", valid_from=30.0)
    try:
        await store.store_belief(old)
        await store.apply_contradiction(_decision("UPDATE", "old", "first"), first)

        with pytest.raises(ValueError, match="active existing belief"):
            await store.apply_contradiction(
                _decision("UPDATE", "old", "delayed"), delayed
            )
        assert await store.get_belief("delayed") is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_backdated_update_cannot_invert_the_superseded_interval():
    """A backdated replacement must not make its predecessor invalid from birth."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon", valid_from=20.0)
    backdated = _belief("backdated", "Seoul", valid_from=10.0)
    try:
        await store.store_belief(old)

        with pytest.raises(InvalidIntervalError, match="cannot start before"):
            await store.apply_contradiction(
                _decision("UPDATE", old.record_id, backdated.record_id), backdated
            )

        stored_old = await store.get_belief(old.record_id)
        assert stored_old == old
        assert await store.get_belief(backdated.record_id) is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_missing_transition_record_raises_a_domain_error():
    """Callers must not need SQLite or KeyError details for a missing belief."""
    store = TemporalMemoryStore(":memory:")
    new = _belief("new", "Seoul", valid_from=20.0)
    try:
        with pytest.raises(RecordNotFoundError, match="does not exist"):
            await store.apply_contradiction(_decision("UPDATE", "missing", "new"), new)
    finally:
        await store.close()


def test_contradiction_classifier_requires_a_slot_and_is_deterministic():
    """Classification must not silently compare unrelated semantic assertions."""
    existing = _belief("old", "Lisbon", valid_until=20.0)

    assert classify_contradiction(existing, "Ari", "lives_in", "Lisbon") == "ELABORATION"
    assert (
        classify_contradiction(
            existing, "Ari", "lives_in", "Seoul", explicit_correction=True
        )
        == "CORRECTION"
    )
    assert classify_contradiction(existing, "Ari", "lives_in", "Seoul") == "UPDATE"
    active = _belief("active", "Lisbon")
    assert classify_contradiction(active, "Ari", "lives_in", "Seoul") == "CONFLICT"
    with pytest.raises(ValueError, match="matching subject and predicate"):
        classify_contradiction(active, "Nia", "lives_in", "Seoul")


def test_contradiction_classifier_updates_newer_equally_confident_slot_values():
    """A newer equally trusted value is a temporal update, not a conflict."""
    existing = _belief("old", "Lisbon", valid_from=10.0, recorded_at=10.0, confidence=0.8)
    incoming = _belief("new", "Seoul", valid_from=20.0, recorded_at=20.0, confidence=0.8)
    simultaneous = _belief(
        "simultaneous", "Tokyo", valid_from=10.0, recorded_at=10.0, confidence=0.8
    )

    assert classify_contradiction(existing, incoming) == "UPDATE"
    assert classify_contradiction(existing, simultaneous) == "CONFLICT"


@pytest.mark.asyncio
async def test_procedure_records_round_trip_through_sqlite():
    """Procedures must remain available after their learning turn has completed."""
    store = TemporalMemoryStore(":memory:")
    procedure = ProcedureRecord(
        procedure_id="procedure-1",
        name="make tea",
        steps=["boil water", "steep leaves"],
        preconditions=["kettle is filled"],
        postconditions=["tea is ready"],
        created_at=12.5,
    )
    try:
        assert await store.store_procedure(procedure) == procedure.procedure_id
        assert await store.get_procedure(procedure.procedure_id) == procedure
        with pytest.raises(DuplicateRecordError):
            await store.store_procedure(procedure)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_as_of_boundary_conditions():
    """Valid-time intervals include their start and exclude their end exactly."""
    store = TemporalMemoryStore(":memory:")
    old = _belief("old", "Lisbon", valid_from=10.0)
    new = _belief("new", "Seoul", valid_from=20.0)
    try:
        await store.store_belief(old)
        await store.apply_contradiction(_decision("UPDATE", "old", "new"), new)

        at_start = await store.query_current_beliefs("Ari", as_of=10.0)
        at_end = await store.query_current_beliefs("Ari", as_of=20.0)
        during_superseded_interval = await store.query_current_beliefs("Ari", as_of=15.0)

        assert [record.record_id for record in at_start] == ["old"]
        assert [record.record_id for record in at_end] == ["new"]
        assert [record.record_id for record in during_superseded_interval] == ["old"]
        as_datetime = await store.query_current_beliefs(
            "Ari", as_of=datetime.fromtimestamp(15.0, tz=UTC)
        )
        assert [record.record_id for record in as_datetime] == ["old"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_concurrent_belief_inserts_from_multiple_connections_are_atomic(tmp_path):
    """Concurrent writers must not cause SQLite locking errors or lost rows."""
    db_path = tmp_path / "temporal-memory.db"
    stores = [TemporalMemoryStore(db_path) for _ in range(4)]
    records = [
        BeliefRecord(
            record_id=f"belief-{index}",
            subject="Ari",
            predicate="has_note",
            object=f"note-{index}",
            valid_from=1.0,
            recorded_at=float(index),
        )
        for index in range(32)
    ]
    try:
        await asyncio.gather(
            *(stores[index % len(stores)].store_belief(record) for index, record in enumerate(records))
        )

        historical = await stores[0].query_historical_beliefs("Ari")
        assert len(historical) == len(records)
        assert {record.record_id for record in historical} == {
            record.record_id for record in records
        }
    finally:
        await asyncio.gather(*(store.close() for store in stores))


@pytest.mark.asyncio
async def test_concurrent_contradiction_handling(tmp_path):
    """Racing replacements must serialize so only one successor becomes active."""
    db_path = tmp_path / "temporal-contradictions.db"
    stores = [TemporalMemoryStore(db_path) for _ in range(2)]
    old = _belief("old", "Lisbon", valid_from=10.0)
    first = _belief("first", "Seoul", valid_from=20.0)
    second = _belief("second", "Tokyo", valid_from=30.0)
    try:
        await stores[0].store_belief(old)
        results = await asyncio.gather(
            stores[0].apply_contradiction(_decision("UPDATE", "old", "first"), first),
            stores[1].apply_contradiction(_decision("UPDATE", "old", "second"), second),
            return_exceptions=True,
        )

        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, ValueError) for result in results) == 1
        historical = await stores[0].query_historical_beliefs("Ari")
        active = await stores[0].query_current_beliefs("Ari")
        assert len(active) == 1
        assert active[0].record_id in {"first", "second"}
        assert {record.record_id for record in historical} == {"old", active[0].record_id}
        old_after_race = next(record for record in historical if record.record_id == "old")
        assert old_after_race.valid_until == active[0].valid_from
    finally:
        await asyncio.gather(*(store.close() for store in stores))
