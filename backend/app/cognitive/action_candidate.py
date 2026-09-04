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

import re
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


import functools


@functools.lru_cache(maxsize=1024)
def _compile_word_boundary_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)


def _phrase_in_text(
    phrase: str,
    text: str,
    phrase_lower: str | None = None,
    text_lower: str | None = None,
) -> bool:
    """Whole-word, case-insensitive containment: `phrase` must appear in
    `text` bounded by word edges on both sides, not merely as a character
    run. Regex-escaped so a phrase containing punctuation is matched
    literally rather than as a pattern.

    This is what makes "body" not match inside "somebody" (Codex review
    finding B6): `\\bbody\\b` requires a non-word boundary immediately
    before "body", and "somebody" has "m" there, so the boundary never
    forms. A short single-word phrase like "body" still correctly matches
    "physical body" (a boundary exists on both sides of "body" there).
    """
    if not phrase:
        return False
    p_lower = phrase_lower if phrase_lower is not None else phrase.lower()
    t_lower = text_lower if text_lower is not None else text.lower()
    # Substring pre-filter: a word-bounded phrase must first be a substring
    if p_lower not in t_lower:
        return False
    return _compile_word_boundary_pattern(phrase).search(text) is not None


def _claims_overlap(claim: str, forbidden: str) -> bool:
    """Word-boundary phrase containment in either direction: a candidate
    claim of "physical body" is caught by a forbidden claim of "never claim
    to have a physical body" (the shorter phrase found whole inside the
    longer one), and vice versa for a shorter forbidden claim inside a
    longer candidate claim. Fixed from Codex review finding B6: the prior
    bidirectional *substring* check (`c in f or f in c`) matched "body"
    inside "somebody", a false positive raw character containment cannot
    avoid. Word-boundary matching is a narrower, sound relation than that,
    though it still cannot catch a lexically different but semantically
    equivalent claim (e.g. "boyfriend" against a forbidden "romantic
    relationship" claim) -- that requires a structured claim-identifier
    taxonomy, out of scope for this fix.
    """
    claim_n = claim.strip()
    forbidden_n = forbidden.strip()
    if not claim_n or not forbidden_n:
        return False
    len_c = len(claim_n)
    len_f = len(forbidden_n)
    if len_c == len_f:
        return claim_n.lower() == forbidden_n.lower()
    elif len_c < len_f:
        return _phrase_in_text(claim_n, forbidden_n)
    else:
        return _phrase_in_text(forbidden_n, claim_n)


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

        norm_forbidden = [
            (f.strip(), f.strip().lower(), len(f.strip()))
            for f in forbidden_claims
            if f.strip()
        ]
        if not norm_forbidden:
            return list(candidates)

        survivors = []
        for candidate in candidates:
            violated = False
            for claim in candidate.constraint_claims:
                c = claim.strip()
                if not c:
                    continue
                cl = c.lower()
                lc = len(c)
                for f, fl, lf in norm_forbidden:
                    if lc == lf:
                        if cl == fl:
                            violated = True
                            break
                    elif lc < lf:
                        if _phrase_in_text(c, f, cl, fl):
                            violated = True
                            break
                    else:
                        if _phrase_in_text(f, c, fl, cl):
                            violated = True
                            break
                if violated:
                    break
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
