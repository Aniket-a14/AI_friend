"""CommunicativeIntent / BehaviorDecision (Phase 1B, §15 item 4): what stage
6 (the Behavior Tree) decides to say, separated from how stage 8
(realization) says it.

Today's `ActionPlan.payload` is `dict[str, Any]` -- assembled once by
`decision.py` and consumed once by `action.py`, with the connection between
"why this goal" and "what the model may/may not claim" implicit in whichever
prompt lines `_execute_respond_chat` happens to build. `BehaviorDecision`
makes that connection an explicit, typed object instead: one place that says
what the turn is for, how urgent it is, and what's off-limits, so
`persona/policy.py` can validate it before generation and `action.py` can
render it as one consolidated block instead of several independently
assembled ones.

In-process only, not a NATS `Topics` member -- promoting a type to the wire
is Phase 3's job for `SpeechExpression`, once validated here first.
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

    Phase 02 Package B additions: `selected_candidate` and
    `rejected_alternatives` record the `CandidateSelector` outcome
    (`action_candidate.py`) when `Config.PHASE_02_MEMORY_TRUTH` is enabled --
    empty/None otherwise, so `.model_dump()` for a legacy caller is
    unchanged in every value that existed before this field was added.
    `retrieval_degraded` mirrors an `outage_flag` seen on any
    `MemoryActivation` considered for this turn (`memory_activation.py`).
    """

    intent: CommunicativeIntent
    allowed_claims: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    selected_candidate: dict[str, Any] | None = None
    rejected_alternatives: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_degraded: bool = False
