"""Typed communicative intent and claim boundaries shared by decision and realization.

DecisionService assembles BehaviorDecision inside ActionPlan.payload. Persona
policy validates its boundaries before ActionService renders it for generation.
These are in-process contracts; the speech expression wire is defined separately
in app.contracts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RelationalStance = Literal["distant", "guarded", "neutral", "warm", "close"]
InterruptionPolicy = Literal["deliberative", "reflex"]


class InternalState(BaseModel):
    """Thin typed view over `StateService.get_context_snapshot()`'s dict.
    Constructed on demand from the snapshot, never persisted itself -- it
    exists so a caller that wants mood/trust/attachment doesn't re-read the
    raw dict with its own copy of the default values."""

    mood: float = 0.0
    energy: float = 0.5
    dominance: float = 0.5
    trust: float = 0.5
    attachment: float = 0.1

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any] | None) -> InternalState:
        snapshot = snapshot or {}
        return cls(
            mood=float(snapshot.get("mood", 0.0)),
            energy=float(snapshot.get("energy", 0.5)),
            dominance=float(snapshot.get("dominance", 0.5)),
            trust=float(snapshot.get("trust", 0.5)),
            attachment=float(snapshot.get("attachment", 0.1)),
        )


class CommunicativeIntent(BaseModel):
    """What this turn is trying to do, in typed form."""

    act: str  # event.intent, e.g. "CHAT", "RECALL"
    goal: str  # MAUT-selected goal, e.g. "ENGAGE", "COMFORT"
    urgency: float = Field(default=0.5, ge=0.0, le=1.0)
    relational_stance: RelationalStance = "neutral"
    interruption_policy: InterruptionPolicy = "deliberative"


class BehaviorDecision(BaseModel):
    """The typed decision stage 6 hands to stage 8's realization: an intent
    plus the claim boundaries `persona/policy.py` enforces before
    generation.

    `selected_candidate` and `rejected_alternatives` record the selector
    outcome when memory truth or affect control enables candidate selection.
    They remain None/empty when candidate selection is disabled.
    `retrieval_degraded` mirrors an `outage_flag` seen on any
    `MemoryActivation` considered for this turn (`memory_activation.py`).
    """

    intent: CommunicativeIntent
    allowed_claims: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    selected_candidate: dict[str, Any] | None = None
    rejected_alternatives: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_degraded: bool = False
