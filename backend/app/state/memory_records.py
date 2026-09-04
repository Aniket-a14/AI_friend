"""Typed records and deterministic contradiction decisions for durable memory."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExperienceRecord(BaseModel):
    """An immutable, timestamped account of one observed experience."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    session_id: str
    participants: list[str]
    interval_start: float
    interval_end: float
    source_evidence_ids: list[str] = Field(default_factory=list)
    appraisal_snapshot: dict[str, float] = Field(default_factory=dict)
    action_id: str | None = None
    outcome_id: str | None = None
    summary: str
    recorded_at: float = Field(default_factory=time.time)


class BeliefRecord(BaseModel):
    """A semantic assertion with valid-time and recorded-time provenance."""

    record_id: str
    subject: str
    predicate: str
    object: str
    valid_from: float
    valid_until: float | None = None
    recorded_at: float = Field(default_factory=time.time)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: Literal["ACTIVE", "SUPERSEDED", "INVALIDATED", "DISPUTED"] = "ACTIVE"
    superseded_by: str | None = None
    contradicts_id: str | None = None
    provenance: str = "conversation"


class ProcedureRecord(BaseModel):
    """A learned procedure and its observed success or failure history."""

    procedure_id: str
    name: str
    preconditions: list[str] = Field(default_factory=list)
    expected_effects: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    rollback_pointer: str | None = None


ContradictionType = Literal["ELABORATION", "UPDATE", "CORRECTION", "CONFLICT"]


class ContradictionDecision(BaseModel):
    """An auditable decision for a relationship between two belief records."""

    contradiction_type: ContradictionType
    existing_record_id: str
    new_record_id: str
    action_taken: str
    reason: str


_TEMPORAL_PROGRESSION_MARKERS = (
    "after ",
    "as of ",
    "currently ",
    "from now ",
    "now ",
    "since ",
    "today ",
)


def classify_contradiction(
    existing: BeliefRecord,
    new_subject: str,
    new_predicate: str,
    new_object: str,
    explicit_correction: bool = False,
) -> ContradictionType:
    """Classify an assertion against a belief with the same semantic slot.

    Temporal progression is explicit in this small classifier: a closed prior
    interval or a present-time marker on the incoming object makes a different
    value an update. An unresolved different value otherwise remains a conflict
    instead of silently overwriting truth.
    """
    if existing.subject != new_subject or existing.predicate != new_predicate:
        raise ValueError("Contradiction classification requires matching subject and predicate")
    if existing.object == new_object:
        return "ELABORATION"
    if explicit_correction:
        return "CORRECTION"
    normalized_object = new_object.lower().strip()
    if existing.valid_until is not None or normalized_object.startswith(
        _TEMPORAL_PROGRESSION_MARKERS
    ):
        return "UPDATE"
    return "CONFLICT"
