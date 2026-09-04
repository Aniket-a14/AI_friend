"""Phase 04 Package B: governed learning proposals with durable review and
rollback (FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Section 21).

This extends the Phase 5C reviewable-suggestion queue with a structured
`LearningProposal` shared contract (`orchestration/PHASE_04/PLAN.md`
Section 3D): a proposal names the domain it would change and carries the
value needed to undo it, so an approved adaptation can be cleanly rolled
back rather than only ever applied forward. `validate_proposal_safety` is
the hard safety invariant this phase adds: a proposal that touches the
immutable persona core or a safety boundary is rejected at submission
time, before it ever reaches a human reviewer, and again at approval time
in case a mutable proposal was altered in between.

Fix round (peer review, `orchestration/PHASE_04/FIX_PLAN.md` Section 3):
the initial version of this module replaced the prior
`LearningProposal`/`LearningReviewQueue` API outright, breaking
`app/cognitive/learning.py` (`ReflectionService`) and
`tests/test_learning_review.py`. Both are restored here as first-class,
permanently supported call shapes -- `LearningProposal` and
`LearningReviewQueue` now serve both the legacy suggestions-dict workflow
and the new governed-proposal workflow, rather than picking one.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

# Fix round: the initial safety check split `target_domain` on `.`, `:`,
# `/` only and required a resulting segment to *exactly equal* one of the
# markers below. That missed two bypasses a real proposal author (or an
# adversarial one) would find immediately: brackets (`persona[name]` is one
# segment, "persona[name]", which never equals "name") and multi-word
# markers written with an underscore the domain author did not reproduce
# verbatim (`safety.boundaries` never equals the single token
# "safety_boundaries"). The fix: normalize on a wider delimiter set that
# also breaks apart brackets and underscores, then check whether a marker's
# own words appear as a *contiguous run* of tokens anywhere in the
# normalized domain -- "core_values" becomes the two-token phrase
# ("core", "values"), which still matches "persona.core_values",
# "persona[CORE_VALUES]", and "persona core values" alike, while a domain
# like "conversation.nickname_style" (tokens "conversation", "nickname",
# "style") never contains "name" as its own token, so it is not a false
# positive.
_IMMUTABLE_CORE_PHRASES: tuple[tuple[str, ...], ...] = (
    ("name",),
    ("core", "values"),
    ("safety", "boundaries"),
    ("immutable",),
    ("constitutional",),
)
_DOMAIN_DELIMITER_PATTERN = re.compile(r"[.:/\[\]_]")


def _normalize_domain_tokens(target_domain: str) -> list[str]:
    """Canonicalize a target_domain into lowercase whitespace-separated
    tokens, with `.`, `:`, `/`, `[`, `]`, and `_` all treated as the same
    word boundary as a literal space."""
    normalized = _DOMAIN_DELIMITER_PATTERN.sub(" ", target_domain or "")
    return normalized.strip().lower().split()


def _tokens_contain_phrase(tokens: list[str], phrase: tuple[str, ...]) -> bool:
    """True if `phrase` (a tuple of words) appears as a contiguous run
    inside `tokens`, at any offset."""
    phrase_len = len(phrase)
    if phrase_len == 0 or phrase_len > len(tokens):
        return False
    return any(
        tuple(tokens[start : start + phrase_len]) == phrase
        for start in range(len(tokens) - phrase_len + 1)
    )


class LearningProposalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class LearningProposal(BaseModel):
    """A governed, reviewable, rollback-capable adaptation proposal.

    `speaker` and `contradicts_id` are legacy (Phase 5C) fields, kept as
    real, first-class fields rather than compatibility shims layered on
    top -- a contradiction-flagged proposal is exactly as valid a thing to
    track here as a risk-classified one. `id`, `suggestions`, and
    `is_contradiction` are read-only aliases so old call sites that read
    `.id`/`.suggestions`/`.is_contradiction` keep working unchanged.
    """

    proposal_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "reflection"
    # Fix round: these three were required (no default) in the initial
    # version, which made `LearningProposal(suggestions={...})` -- the
    # legacy direct-construction shape `tests/test_learning_review.py`
    # relies on -- impossible to satisfy. Defaulting them to the same
    # values `LearningReviewQueue.submit`'s legacy path already wraps a
    # bare suggestions dict with keeps both construction styles consistent
    # with each other.
    target_domain: str = "persona_adaptive_traits"
    proposed_value: Any = None
    expected_effect: str = "reflection_update"
    risk_class: str = "LOW"
    counterfactual_baseline: str | None = None
    approval_policy: str = "REVIEW_REQUIRED"
    rollback_value: Any = None
    status: LearningProposalStatus = LearningProposalStatus.PENDING
    rejection_reason: str | None = None
    # Legacy (Phase 5C) fields.
    speaker: str | None = None
    contradicts_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_suggestions_kwarg(cls, data: Any) -> Any:
        """Let `LearningProposal(suggestions=...)` construct directly,
        mapping it onto `proposed_value` -- the one legacy constructor
        keyword that has no real field of its own (`suggestions` is a
        read-only property below, so pydantic would otherwise reject it as
        an unknown field)."""
        if isinstance(data, dict) and "suggestions" in data:
            data = dict(data)
            data.setdefault("proposed_value", data.pop("suggestions"))
        return data

    @property
    def id(self) -> str:
        """Legacy alias for `proposal_id`."""
        return self.proposal_id

    @property
    def suggestions(self) -> Any:
        """Legacy alias for `proposed_value`."""
        return self.proposed_value

    @property
    def is_contradiction(self) -> bool:
        return self.contradicts_id is not None


def validate_proposal_safety(proposal: LearningProposal) -> bool:
    """Raise ValueError if `proposal.target_domain` names the immutable
    persona core or a safety boundary, under any delimiter, bracket, or
    casing variation. Returns True otherwise -- the immutable core and
    safety boundaries can never be proposed or altered, by any source, at
    any risk class."""
    tokens = _normalize_domain_tokens(proposal.target_domain)
    for phrase in _IMMUTABLE_CORE_PHRASES:
        if _tokens_contain_phrase(tokens, phrase):
            raise ValueError(
                f"proposal target_domain '{proposal.target_domain}' touches "
                f"immutable persona core or safety boundaries "
                f"('{' '.join(phrase)}') and can never be proposed or modified"
            )
    return True


class LearningReviewQueue:
    """Durable review queue for `LearningProposal`s -- one per running
    agent process. Every proposal remains addressable by `proposal_id`
    (or its legacy alias `id`) after approval, rejection, or rollback, so
    the queue itself is the audit trail (Architecture Section 21's
    "complete audit trail" requirement)."""

    def __init__(self) -> None:
        self._proposals: dict[str, LearningProposal] = {}

    def submit(
        self,
        suggestions: dict[str, Any] | None = None,
        source: str = "reflection",
        speaker: str | None = None,
        contradicts_id: str | None = None,
        proposal: LearningProposal | None = None,
    ) -> LearningProposal:
        """Validate and register a proposal. Raises ValueError (and never
        registers anything) when `validate_proposal_safety` rejects it.

        Two call shapes:
        - New, governed shape: `submit(proposal=LearningProposal(...))`.
        - Legacy (Phase 5C) shape: `submit(suggestions_dict, ...)` --
          `suggestions` is wrapped into a `LearningProposal` with
          `target_domain="persona_adaptive_traits"`,
          `proposed_value=suggestions`, `expected_effect="reflection_update"`,
          matching `ReflectionService._consolidate_persona`'s existing call
          site in `learning.py` exactly.
        """
        if proposal is None:
            proposal = LearningProposal(
                source=source,
                target_domain="persona_adaptive_traits",
                proposed_value=suggestions,
                expected_effect="reflection_update",
                contradicts_id=contradicts_id,
                speaker=speaker,
            )
        validate_proposal_safety(proposal)
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def get(self, proposal_id: str) -> LearningProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(self) -> list[LearningProposal]:
        return list(self._proposals.values())

    def pending(self) -> list[LearningProposal]:
        """Legacy (Phase 5C) accessor: proposals still awaiting review.

        Unlike the old queue (which popped an approved/rejected proposal
        out of its only list), this filters `list_proposals()` by status --
        the proposal keeps existing, addressable via `get()`, once it
        leaves PENDING, but it no longer shows up here, matching the old
        queue's observable behavior for callers that only ever looked at
        `pending()`.
        """
        return [
            p for p in self._proposals.values()
            if p.status == LearningProposalStatus.PENDING
        ]

    def contradictions(self) -> list[LearningProposal]:
        """Legacy (Phase 5C) accessor: pending proposals flagged as
        conflicting with an existing confirmed memory."""
        return [p for p in self.pending() if p.is_contradiction]

    async def approve(
        self, proposal_id: str, identity_manager: Any | None = None
    ) -> LearningProposal | None:
        """Mark a PENDING proposal APPROVED. Returns None for an unknown
        id or a proposal that is not currently PENDING.

        Re-validates safety before applying anything -- a mutable
        `LearningProposal`'s `target_domain` could in principle be changed
        after `submit()` accepted it (pydantic models are not frozen), so
        this is a second, independent enforcement point rather than
        trusting the one at submission time alone. Raises ValueError (and
        leaves the proposal PENDING, not APPROVED) exactly like `submit()`
        does, if the (possibly mutated) proposal now targets the immutable
        core or a safety boundary.

        Legacy (Phase 5C) shape: when `identity_manager` is supplied, this
        stamps `identity_manager.history["evolved_learnings"]` and awaits
        `identity_manager.evolve_persona(proposal.suggestions)` before
        marking the proposal APPROVED -- exactly the prior `approve(id,
        identity_manager)` behavior, including the stamp-before-apply
        ordering `ReflectionService`'s persistence depends on. Governed
        (Phase 04) callers omit `identity_manager` and get pure
        status-transition semantics with no side effect of their own.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != LearningProposalStatus.PENDING:
            return None
        validate_proposal_safety(proposal)
        if identity_manager is not None:
            identity_manager.history["evolved_learnings"] = (
                f"{proposal.created_at}: {proposal.suggestions}"
            )
            await identity_manager.evolve_persona(proposal.suggestions)
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
