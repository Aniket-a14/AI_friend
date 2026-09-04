"""Trusted learning governance and learning-progress curiosity.

Formalizes FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Section 21 ("Learning") and
Section 38 Phase 6 ("Optional advanced learning and planning"): every
persistent behavior change is a `LearningProposal` that must be validated,
approved under a risk-tiered policy, activated as one versioned step, and
remain reversible by a single atomic rollback. Generated inferences cannot
promote themselves, and identity core / safety boundaries are never learned.

Naming note (orchestration/PHASE_06): this module intentionally does not
reuse the `app/cognitive/learning.py` path named in CLAUDE_TASK.md/PLAN.md.
That path is already occupied by `ReflectionService` (Phase "AI Friend Solid
State Learning Layer"), and `app/cognitive/learning_review.py` (Phase 04)
already defines a `LearningProposal` / `LearningProposalStatus` pair with a
different, incompatible schema (PENDING/APPROVED/REJECTED/ROLLED_BACK, no
`activation_revision`, string `risk_class`). Reusing either name here would
either overwrite production code used across 5+ call sites and tests, or
create two same-named-but-incompatible `LearningProposal` classes inside one
package. This module is additive and does not modify either existing file;
see orchestration/PHASE_06/CLAUDE_RESULT.md for the full rationale.

Trusted learning follows the pipeline Section 21 describes: observe outcome
-> attribute credit cautiously -> propose -> validate schema/safety -> test
on held-out and retention suites -> approve by policy/risk -> activate
versioned change -> monitor -> rollback on regression. `LearningGovernor`
owns exactly this state machine; `LearningApprovalGate` owns only the
risk-tiered approval decision, kept separate so an approval policy can be
swapped or unit-tested without touching lifecycle bookkeeping.
"""

from __future__ import annotations

import re
import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..persona.profile import IMMUTABLE_CORE, PersonaProfile, Tier


class LearningRiskClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LearningProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    ACTIVATED = "ACTIVATED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class LearningProposal(BaseModel):
    """Section 21's proposal record. Every field the architecture requires
    ("source records, proposed target/value, expected effect, risk class,
    ... counterfactual baseline, approval policy, activation revision,
    rollback value") is a real field here, not a dict key a caller has to
    remember to set."""

    proposal_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source_records: list[str] = Field(default_factory=list)
    target_domain: str
    proposed_value: dict[str, Any]
    expected_effect: str
    risk_class: LearningRiskClass
    counterfactual_baseline: float | None = None
    approval_policy: str = "risk_tiered"
    activation_revision: int | None = None
    rollback_value: dict[str, Any] | None = None
    status: LearningProposalStatus = LearningProposalStatus.PROPOSED
    # Populated at construction time rather than a literal 0.0 default: a
    # proposal's audit trail is only useful if "when was this proposed"
    # survives without every caller remembering to stamp it.
    created_at: float = Field(default_factory=time.time)
    evaluated_at: float | None = None
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Hard invariant: identity core, constitutional bounds, and safety
# boundaries can never be a learning target, at any risk class, from any
# source. `target_domain` is a free-text dotted/delimited path (e.g.
# "persona.mood_decay_rate", "identity.core_values"); the check below
# tokenizes it on any common delimiter so a proposal cannot dodge the block
# by choice of separator, bracket, or case.
# ---------------------------------------------------------------------------

_STATIC_PROTECTED_PHRASES: tuple[tuple[str, ...], ...] = (
    ("immutable",),
    ("constitutional",),
    ("safety", "invariant"),
    ("safety", "invariants"),
    ("safety", "boundary"),
    ("safety", "boundaries"),
)

_DOMAIN_DELIMITER_PATTERN = re.compile(r"[.:/\[\]_\-\s]+")


def _normalize_domain_tokens(target_domain: str) -> list[str]:
    """Lowercase whitespace/delimiter-separated tokens for `target_domain`,
    treating `.`, `:`, `/`, `[`, `]`, `_`, and `-` all as the same word
    boundary as a literal space."""
    return [t for t in _DOMAIN_DELIMITER_PATTERN.split((target_domain or "").lower()) if t]


def _tokens_contain_phrase(tokens: list[str], phrase: tuple[str, ...]) -> bool:
    """True if `phrase` appears as a contiguous run inside `tokens`."""
    phrase_len = len(phrase)
    if phrase_len == 0 or phrase_len > len(tokens):
        return False
    return any(
        tuple(tokens[start : start + phrase_len]) == phrase
        for start in range(len(tokens) - phrase_len + 1)
    )


def _protected_phrases() -> tuple[tuple[str, ...], ...]:
    """Static safety/immutable markers, plus every IMMUTABLE_CORE key and
    every CONSTITUTIONAL-tier PersonaProfile field name, split on `_` so a
    multi-word field like `mood_decay_rate` matches as a phrase rather than
    requiring an exact underscored token."""
    phrases = list(_STATIC_PROTECTED_PHRASES)
    phrases.extend(tuple(key.split("_")) for key in IMMUTABLE_CORE)
    phrases.extend(
        tuple(name.split("_")) for name in PersonaProfile.fields_in(Tier.CONSTITUTIONAL)
    )
    return tuple(phrases)


# Computed once: IMMUTABLE_CORE and the CONSTITUTIONAL field set are both
# fixed at import time (schema constants), not runtime state.
_PROTECTED_PHRASES: tuple[tuple[str, ...], ...] = _protected_phrases()


def check_targets_protected_domain(target_domain: str) -> tuple[bool, str]:
    """(True, reason) if `target_domain` names the immutable persona core, a
    safety invariant, or a CONSTITUTIONAL-tier field, under any delimiter or
    casing variation; (False, "") otherwise. This is the one check every
    lifecycle entry point below re-runs -- Section 21's "Identity core and
    safety boundaries are never learned" admits no exception by risk class
    or source."""
    tokens = _normalize_domain_tokens(target_domain)
    for phrase in _PROTECTED_PHRASES:
        if _tokens_contain_phrase(tokens, phrase):
            return True, (
                f"target_domain '{target_domain}' names a protected region "
                f"('{' '.join(phrase)}') -- immutable core, safety invariant, "
                "or constitutional bound -- and can never be a learning target"
            )
    return False, ""


class LearningApprovalGate:
    """The risk-tiered approval policy alone, stateless apart from the
    optional gatekeeper callback. Kept separate from `LearningGovernor` so
    the policy itself -- what LOW/MEDIUM/HIGH/CRITICAL actually mean -- can
    be tested and swapped without touching proposal bookkeeping.

    Policy: LOW risk auto-approves (a threshold gate, not a bypass -- the
    hard immutable/constitutional check below still applies first).
    MEDIUM and HIGH require an explicit gatekeeper decision. CRITICAL is
    permanently blocked; there is no configuration of this gate that can
    approve one, matching Section 38's "permanently reject online
    uncontrolled self-modification".
    """

    def __init__(self, gatekeeper: Any = None) -> None:
        # gatekeeper: Callable[[LearningProposal], bool] | None. Represents
        # the human or governance-board decision Section 21 requires for
        # MEDIUM/HIGH risk ("approve by policy/human according to risk").
        self._gatekeeper = gatekeeper

    def evaluate(self, proposal: LearningProposal) -> tuple[bool, str]:
        """(approved, reason). Never mutates `proposal`."""
        protected, reason = check_targets_protected_domain(proposal.target_domain)
        if protected:
            return False, reason

        if proposal.risk_class is LearningRiskClass.CRITICAL:
            return False, "CRITICAL risk class is permanently blocked from approval"

        if proposal.risk_class is LearningRiskClass.LOW:
            return True, "LOW risk auto-approved under the risk-tiered policy"

        # MEDIUM or HIGH.
        if self._gatekeeper is None:
            return False, (
                f"{proposal.risk_class.value} risk requires an explicit gatekeeper "
                "decision and none is configured"
            )
        approved = bool(self._gatekeeper(proposal))
        return approved, ("gatekeeper approved" if approved else "gatekeeper rejected")


class LearningGovernor:
    """Owns the `LearningProposal` lifecycle end to end: submit -> validate
    -> approve -> activate -> rollback. One instance per running agent
    process. `_proposals` is the durable, append-only audit trail Section 21
    requires -- a proposal is never deleted, only transitioned, so its full
    history stays addressable by `proposal_id`.
    """

    def __init__(self, gate: LearningApprovalGate | None = None, state_applier: Any = None) -> None:
        self._gate = gate or LearningApprovalGate()
        self._proposals: dict[str, LearningProposal] = {}
        self._revision = 0
        # state_applier(target_domain, value) -> None. How an activated
        # proposal's `proposed_value` is actually written, and how
        # `rollback_value` gets restored. None means the governor only
        # tracks status transitions and leaves applying state to the caller.
        self._state_applier = state_applier

    def submit(self, proposal: LearningProposal) -> LearningProposal:
        """Register a new PROPOSED proposal. Raises ValueError -- and
        registers nothing -- for a duplicate id, a non-PROPOSED status, a
        missing `rollback_value` (a proposal with nothing to roll back to
        can never be safely activated), or a protected `target_domain`.
        Rejecting here, before the proposal is even stored, is the
        strictest reading of "strictly reject" the hard invariant asks for.
        """
        if proposal.proposal_id in self._proposals:
            raise ValueError(f"duplicate proposal_id {proposal.proposal_id!r}")
        if proposal.status is not LearningProposalStatus.PROPOSED:
            raise ValueError(
                f"a newly submitted proposal must be PROPOSED, got {proposal.status.value}"
            )
        if proposal.rollback_value is None:
            raise ValueError(
                "proposal has no rollback_value; a change that cannot be "
                "undone in one step cannot be submitted"
            )
        protected, reason = check_targets_protected_domain(proposal.target_domain)
        if protected:
            raise ValueError(reason)
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def validate(self, proposal_id: str) -> LearningProposal:
        """PROPOSED -> VALIDATED, or REJECTED if a defense-in-depth
        immutable/constitutional re-check now fails (the model is mutable,
        so `target_domain` could in principle have changed since submit)."""
        proposal = self._transition(proposal_id, LearningProposalStatus.PROPOSED)
        protected, reason = check_targets_protected_domain(proposal.target_domain)
        if protected:
            return self._reject(proposal, reason)
        proposal.status = LearningProposalStatus.VALIDATED
        return proposal

    def approve(self, proposal_id: str) -> LearningProposal:
        """VALIDATED -> APPROVED via the risk-tiered gate, or REJECTED with
        the gate's stated reason."""
        proposal = self._transition(proposal_id, LearningProposalStatus.VALIDATED)
        approved, reason = self._gate.evaluate(proposal)
        proposal.evaluated_at = time.time()
        if not approved:
            return self._reject(proposal, reason)
        proposal.status = LearningProposalStatus.APPROVED
        return proposal

    def activate(self, proposal_id: str) -> LearningProposal:
        """APPROVED -> ACTIVATED. Applies `proposed_value` via the
        configured `state_applier` (if any) and stamps a new, monotonically
        increasing `activation_revision` -- the versioned change Section 21
        requires so a later rollback restores a specific, named revision
        rather than an ambiguous "previous" state."""
        proposal = self._transition(proposal_id, LearningProposalStatus.APPROVED)
        if self._state_applier is not None:
            self._state_applier(proposal.target_domain, proposal.proposed_value)
        self._revision += 1
        proposal.activation_revision = self._revision
        proposal.status = LearningProposalStatus.ACTIVATED
        return proposal

    def rollback(self, proposal_id: str) -> LearningProposal:
        """1-step atomic rollback: ACTIVATED -> ROLLED_BACK, restoring
        `rollback_value` via `state_applier` in the same transition that
        flips status. There is no intermediate, partially-rolled-back state
        another reader of this governor can observe -- either this call
        raises and nothing changes, or it fully restores and marks the
        proposal ROLLED_BACK."""
        proposal = self._transition(proposal_id, LearningProposalStatus.ACTIVATED)
        if self._state_applier is not None:
            self._state_applier(proposal.target_domain, proposal.rollback_value)
        proposal.status = LearningProposalStatus.ROLLED_BACK
        return proposal

    def get(self, proposal_id: str) -> LearningProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(self) -> list[LearningProposal]:
        return list(self._proposals.values())

    def _reject(self, proposal: LearningProposal, reason: str) -> LearningProposal:
        proposal.status = LearningProposalStatus.REJECTED
        proposal.rejection_reason = reason
        return proposal

    def _transition(
        self, proposal_id: str, required_status: LearningProposalStatus
    ) -> LearningProposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise KeyError(f"unknown proposal_id {proposal_id!r}")
        if proposal.status is not required_status:
            raise ValueError(
                f"proposal {proposal_id!r} is {proposal.status.value}, "
                f"expected {required_status.value}"
            )
        return proposal


class LearningProgressCuriosity:
    """Learning-progress curiosity (Section 38 Phase 6): ranks domains by
    how fast an empirical error/loss signal is improving, not by how good
    or bad it currently is. This is what keeps exploration off both dead
    ends a naive novelty signal falls into: a domain already mastered (flat,
    near-zero error) is not interesting because there is nothing left to
    learn, and a domain that is pure noise (no consistent trend) is not
    interesting because nothing is actually being learned there either --
    only a domain with a real, sustained error reduction ranks.
    """

    def __init__(
        self,
        window_size: int = 5,
        noise_threshold: float = 0.02,
        mastery_threshold: float = 0.05,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2 to form two windows")
        if noise_threshold < 0.0:
            raise ValueError("noise_threshold must be non-negative")
        if mastery_threshold < 0.0:
            raise ValueError("mastery_threshold must be non-negative")
        self.window_size = window_size
        self.noise_threshold = noise_threshold
        self.mastery_threshold = mastery_threshold
        self._history: dict[str, list[float]] = {}

    def record(self, domain: str, error: float) -> None:
        """Append one empirical error/loss observation for `domain` (lower
        is better competence). Keeps only the samples needed for two
        adjacent windows, so this stays bounded regardless of how long a
        domain has been tracked."""
        history = self._history.setdefault(domain, [])
        history.append(error)
        max_len = self.window_size * 2
        if len(history) > max_len:
            del history[: len(history) - max_len]

    def progress_delta(self, domain: str) -> float | None:
        """Older-window mean error minus recent-window mean error: positive
        means the domain is improving, negative means it is getting worse.
        `None` until two full adjacent windows exist."""
        history = self._history.get(domain, [])
        if len(history) < self.window_size * 2:
            return None
        recent = history[-self.window_size :]
        older = history[-self.window_size * 2 : -self.window_size]
        return (sum(older) / len(older)) - (sum(recent) / len(recent))

    def is_mastered(self, domain: str) -> bool:
        """True if the recent window's mean error is already at or below
        `mastery_threshold` -- a flat, already-solved routine."""
        history = self._history.get(domain, [])
        if len(history) < self.window_size:
            return False
        recent = history[-self.window_size :]
        return (sum(recent) / len(recent)) <= self.mastery_threshold

    def rank(self) -> list[tuple[str, float]]:
        """Domains with a real (above-`noise_threshold`) positive progress
        delta, excluding mastered ones, ranked highest-progress first."""
        ranked: list[tuple[str, float]] = []
        for domain in self._history:
            if self.is_mastered(domain):
                continue
            delta = self.progress_delta(domain)
            if delta is None or delta <= self.noise_threshold:
                continue
            ranked.append((domain, delta))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked
