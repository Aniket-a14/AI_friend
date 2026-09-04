"""Phase 1 causal slice (§22, §38): `ActionIntent` and `OutcomeRecord` --
the explicit commitment and terminal result either side of Stage 8's
generation, per `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`.

Before this, a turn's decision (`decision.py::BehaviorDecision`) went straight
into `action.py`'s prompt assembly with nothing durable recording that the
decision was made, from which workspace revision, or what actually happened
once it played (or was cut short). `ActionIntent` is committed by
`CognitivePipeline.execute` at Stage 6, before any text is generated;
`OutcomeRecord` is emitted by `BrainAgent` once playback finishes or is
interrupted. Together they are the "committing an explicit ActionIntent
before execution ... recording a terminal OutcomeRecord upon speech
completion or interruption truncation" half of the Phase 1 objective -- the
`CognitiveWorkspaceSnapshot`/`WorkspaceStore` half is a separate, parallel
piece of work and is not implemented here.

In-process only, not a NATS `Topics` member, same reasoning as
`behavior_contracts.BehaviorDecision`: promoting these to the wire is later
work, once the shape has proven itself here first.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

# Phase 02 Package B: widened to also accept the ActionCandidate kinds that
# have no Phase 1 analogue (RETRIEVE, VERIFY, UPDATE_GOAL) -- a superset, so
# every ActionIntent ever committed under Phase 1 remains a valid ActionKind.
#
# Fix round (Codex review B7): architecture section 22's full action-kind
# set also includes UPDATE_STATE, EXTERNAL_ACT, and CONTINUE (INTERRUPT was
# already present above). Adding them now, with no candidate generator or
# executor wired to them yet, avoids a second incompatible widening later --
# this Literal is a schema ceiling, not a claim that every kind is reachable
# today.
#
# Phase 03 Package B: adds REAPPRAISE, REDIRECT_ATTENTION and
# SUPPRESS_EXPRESSION -- emotion regulation actions (Architecture Sections
# 9, 10, 21, 38), selectable candidates rather than silent affect
# overwriting. REAPPRAISE and REDIRECT_ATTENTION have generators in
# decision.py and executors in action.py; SUPPRESS_EXPRESSION is added to
# the type now with neither wired up yet, same "schema ceiling, not a
# reachability claim" reasoning as UPDATE_STATE/EXTERNAL_ACT/CONTINUE above.
ActionKind = Literal[
    "SPEAK",
    "ASK",
    "WAIT",
    "OBSERVE",
    "REFLECT",
    "INTERRUPT",
    "RETRIEVE",
    "VERIFY",
    "UPDATE_GOAL",
    "UPDATE_STATE",
    "EXTERNAL_ACT",
    "CONTINUE",
    "REAPPRAISE",
    "REDIRECT_ATTENTION",
    "SUPPRESS_EXPRESSION",
]
OutcomeStatus = Literal["COMPLETED", "TRUNCATED", "CANCELLED", "FAILED"]


class ActionIntent(BaseModel):
    """The typed commitment Stage 6 makes before Stage 8 generates anything --
    carries the exact workspace revision it was derived from, per the
    Causal Trace Completeness invariant (`ACCEPTANCE_CRITERIA.md` AC-05)."""

    intent_id: str
    turn_id: str
    workspace_epoch: int
    workspace_revision: int
    kind: ActionKind
    behavior_decision: dict[str, Any]
    committed_at: float = Field(default_factory=time.time)


class OutcomeRecord(BaseModel):
    """The terminal record of what an `ActionIntent` actually produced --
    `actual_delivered_text`/`character_offset` must match what was actually
    heard, not what was generated (`ACCEPTANCE_CRITERIA.md` AC-06)."""

    outcome_id: str
    intent_id: str
    turn_id: str
    status: OutcomeStatus
    actual_delivered_text: str | None = None
    character_offset: int = 0
    elapsed_ms: float = 0.0
    recorded_at: float = Field(default_factory=time.time)
    error: str | None = None


def new_intent_id() -> str:
    return f"intent-{uuid.uuid4().hex}"


def new_outcome_id() -> str:
    return f"outcome-{uuid.uuid4().hex}"


def build_action_intent(
    *,
    turn_id: str,
    workspace_epoch: int,
    workspace_revision: int,
    kind: ActionKind,
    behavior_decision: dict[str, Any],
) -> ActionIntent:
    """Convenience constructor stamping a fresh `intent_id`/`committed_at`."""
    return ActionIntent(
        intent_id=new_intent_id(),
        turn_id=turn_id,
        workspace_epoch=workspace_epoch,
        workspace_revision=workspace_revision,
        kind=kind,
        behavior_decision=behavior_decision,
    )


def build_outcome_record(
    intent: ActionIntent,
    *,
    status: OutcomeStatus,
    actual_delivered_text: str | None = None,
    character_offset: int = 0,
    error: str | None = None,
) -> OutcomeRecord:
    """Convenience constructor binding an outcome to its `ActionIntent`:
    `intent_id`/`turn_id` copied across, `elapsed_ms` derived from
    `intent.committed_at` rather than asking every caller to time it."""
    elapsed_ms = max(0.0, (time.time() - intent.committed_at) * 1000.0)
    return OutcomeRecord(
        outcome_id=new_outcome_id(),
        intent_id=intent.intent_id,
        turn_id=intent.turn_id,
        status=status,
        actual_delivered_text=actual_delivered_text,
        character_offset=character_offset,
        elapsed_ms=elapsed_ms,
        error=error,
    )
