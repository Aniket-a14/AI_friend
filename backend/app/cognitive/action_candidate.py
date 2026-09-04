"""Phase 02 Package B: ActionCandidate and CandidateSelector -- explicit,
scored action candidates with constraint-first boundary filtering, applied
before any candidate reaches language realization (FINAL_HUMANOID_BRAIN_
ARCHITECTURE.md Sections 8, 11, 22, 39).

Constraint-first means filter_constraints always runs before score_and_select
sees a candidate: a candidate that violates an identity boundary or safety
refusal must never win on score alone, however useful it would otherwise
score. Package A (backend/app/state/memory_records.py, temporal_store.py) is
a separate, parallel work package this module does not import from -- see
orchestration/PHASE_02/CLAUDE_TASK.md's file ownership split.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

ActionCandidateKind = Literal[
    "SPEAK", "ASK", "WAIT", "OBSERVE", "RETRIEVE", "VERIFY", "REFLECT", "UPDATE_GOAL"
]

# Weight applied to goal alignment (the fraction of a candidate's
# target_goal_ids present in the turn's active goals) on top of its raw
# score. Kept well below 1.0 so alignment nudges the ranking rather than
# overriding a candidate's own evaluated score.
_GOAL_ALIGNMENT_WEIGHT = 0.2


class ActionCandidate(BaseModel):
    """One explicit, evaluable option for what the agent could do this turn."""

    candidate_id: str
    kind: ActionCandidateKind
    source: str  # e.g. "reflex", "goal", "policy", "memory_activation", "model"
    target_goal_ids: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    predicted_outcomes: list[str] = Field(default_factory=list)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    cost: float = 0.0
    constraint_claims: list[str] = Field(default_factory=list)
    score: float = 0.0


def new_candidate_id() -> str:
    return f"cand-{uuid.uuid4().hex}"


def _claims_overlap(claim: str, forbidden: str) -> bool:
    """Case-insensitive containment in either direction: a candidate claim
    of "romantic escalation" is caught by a forbidden claim of "romantic",
    and a candidate claim that repeats a forbidden claim verbatim is caught
    too."""
    claim_n = claim.strip().lower()
    forbidden_n = forbidden.strip().lower()
    if not claim_n or not forbidden_n:
        return False
    return claim_n in forbidden_n or forbidden_n in claim_n


class CandidateSelector:
    """Constraint-first candidate filtering and scoring."""

    def filter_constraints(
        self, candidates: list[ActionCandidate], forbidden_claims: list[str]
    ) -> list[ActionCandidate]:
        """Removes any candidate whose constraint_claims overlap with
        forbidden_claims (identity boundaries, safety refusals). Runs before
        any scoring -- a candidate that does not survive this can never win
        regardless of how it would otherwise have scored."""
        if not forbidden_claims:
            return list(candidates)
        survivors = []
        for candidate in candidates:
            violated = any(
                _claims_overlap(claim, forbidden)
                for claim in candidate.constraint_claims
                for forbidden in forbidden_claims
            )
            if not violated:
                survivors.append(candidate)
        return survivors

    def _goal_alignment(
        self, candidate: ActionCandidate, active_goals: list[str]
    ) -> float:
        if not candidate.target_goal_ids or not active_goals:
            return 0.0
        overlap = set(candidate.target_goal_ids) & set(active_goals)
        return len(overlap) / len(candidate.target_goal_ids)

    def score_and_select(
        self, candidates: list[ActionCandidate], active_goals: list[str]
    ) -> tuple[ActionCandidate, list[dict[str, Any]]]:
        """Ranks surviving candidates by score plus goal alignment.

        Raises ValueError on an empty candidate list -- this method never
        invents a winner. A caller with zero surviving candidates (e.g.
        everything failed filter_constraints) must supply a safe fallback
        candidate (such as WAIT, with no constraint_claims) before reaching
        this point.

        Returns (winner, rejected) where rejected carries a reason dict per
        runner-up, ordered from strongest to weakest alternative.
        """
        if not candidates:
            raise ValueError("score_and_select requires at least one candidate")

        def combined_score(candidate: ActionCandidate) -> float:
            return candidate.score + _GOAL_ALIGNMENT_WEIGHT * self._goal_alignment(
                candidate, active_goals
            )

        ranked = sorted(candidates, key=combined_score, reverse=True)
        winner = ranked[0]
        rejected = [
            {
                "candidate_id": candidate.candidate_id,
                "kind": candidate.kind,
                "source": candidate.source,
                "combined_score": combined_score(candidate),
                "reason": "lower_ranked_score",
            }
            for candidate in ranked[1:]
        ]
        return winner, rejected
