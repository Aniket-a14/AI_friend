"""Phase 04 Package B: governed learning proposals with durable review and
rollback (FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Section 21).

This replaces the Phase 5C reviewable-suggestion queue with a structured
`LearningProposal` shared contract (`orchestration/PHASE_04/PLAN.md`
Section 3D): a proposal names the domain it would change and carries the
value needed to undo it, so an approved adaptation can be cleanly rolled
back rather than only ever applied forward. `validate_proposal_safety` is
the hard safety invariant this phase adds: a proposal that touches the
immutable persona core or a safety boundary is rejected at submission
time, before it ever reaches a human reviewer.

BREAKING CHANGE: the prior `LearningProposal`/`LearningReviewQueue` API
(`submit(suggestions, ...)`, `.id`, `.suggestions`, `.contradicts_id`,
`approve(id, identity_manager)`) is replaced outright by the schema below,
per the Phase 04 shared contract. `app/cognitive/learning.py`
(`ReflectionService`) and `tests/test_learning_review.py` still call the
old shape and are not owned by this package (see
`orchestration/PHASE_04/PLAN.md` Section 2) -- reconciling them is
tracked as follow-up work, not done here.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Segments of a dotted/colon/slash-separated target_domain that name the
# immutable persona core or a safety boundary -- matched as whole path
# segments (not substrings) so "nickname" or "username" cannot collide with
# the "name" marker.
_IMMUTABLE_CORE_MARKERS = frozenset({"name", "core_values", "safety_boundaries", "immutable"})
_DOMAIN_SEGMENT_PATTERN = re.compile(r"[.:/]")


class LearningProposalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class LearningProposal(BaseModel):
    """A governed, reviewable, rollback-capable adaptation proposal."""

    proposal_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "reflection"
    target_domain: str
    proposed_value: Any
    expected_effect: str
    risk_class: str = "LOW"
    counterfactual_baseline: str | None = None
    approval_policy: str = "REVIEW_REQUIRED"
    rollback_value: Any = None
    status: LearningProposalStatus = LearningProposalStatus.PENDING
    rejection_reason: str | None = None


def validate_proposal_safety(proposal: LearningProposal) -> bool:
    """Raise ValueError if `proposal.target_domain` names the immutable
    persona core or a safety boundary. Returns True otherwise -- the
    immutable core and safety boundaries can never be proposed or altered,
    by any source, at any risk class."""
    segments = {
        segment.strip().lower()
        for segment in _DOMAIN_SEGMENT_PATTERN.split(proposal.target_domain or "")
        if segment.strip()
    }
    violated = segments & _IMMUTABLE_CORE_MARKERS
    if violated:
        raise ValueError(
            f"proposal target_domain '{proposal.target_domain}' touches "
            f"immutable persona core or safety boundaries ({sorted(violated)}) "
            "and can never be proposed or modified"
        )
    return True


class LearningReviewQueue:
    """Durable review queue for `LearningProposal`s -- one per running
    agent process. Every proposal remains addressable by `proposal_id`
    after approval, rejection, or rollback, so the queue itself is the
    audit trail (Architecture Section 21's "complete audit trail"
    requirement)."""

    def __init__(self) -> None:
        self._proposals: dict[str, LearningProposal] = {}

    def submit(self, proposal: LearningProposal) -> LearningProposal:
        """Validate and register `proposal`. Raises ValueError (and never
        registers the proposal) when `validate_proposal_safety` rejects it."""
        validate_proposal_safety(proposal)
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def get(self, proposal_id: str) -> LearningProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(self) -> list[LearningProposal]:
        return list(self._proposals.values())

    def approve(self, proposal_id: str) -> LearningProposal | None:
        """Mark a PENDING proposal APPROVED. Returns None for an unknown
        id or a proposal that is not currently PENDING."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != LearningProposalStatus.PENDING:
            return None
        proposal.status = LearningProposalStatus.APPROVED
        return proposal

    def reject(self, proposal_id: str, reason: str = "") -> LearningProposal | None:
        """Mark a PENDING proposal REJECTED. Returns None for an unknown
        id or a proposal that is not currently PENDING."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != LearningProposalStatus.PENDING:
            return None
        proposal.status = LearningProposalStatus.REJECTED
        proposal.rejection_reason = reason
        return proposal

    def rollback(self, proposal_id: str) -> tuple[LearningProposal | None, Any]:
        """Mark an APPROVED proposal ROLLED_BACK and hand back its
        `rollback_value` for the caller to restore. Returns `(None, None)`
        for an unknown id or a proposal that was never APPROVED -- only an
        applied change can be rolled back."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != LearningProposalStatus.APPROVED:
            return (None, None)
        proposal.status = LearningProposalStatus.ROLLED_BACK
        return (proposal, proposal.rollback_value)
