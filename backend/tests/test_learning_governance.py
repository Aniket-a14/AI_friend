"""Phase 06 Package B: trusted learning governance, curiosity, and offline
adapter gating (FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Section 21, 38, 40).

Covers: LearningProposal validation, full lifecycle transitions, hard
rejection of proposals targeting the immutable core or constitutional
bounds, risk-tiered approval gating, atomic rollback fidelity,
learning-progress curiosity ranking, and offline adapter qualification /
regression detection.
"""

import pytest
from pydantic import ValidationError

from app.cognitive.learning_governance import (
    LearningApprovalGate,
    LearningGovernor,
    LearningProgressCuriosity,
    LearningProposal,
    LearningProposalStatus,
    LearningRiskClass,
    LearningStateApplyError,
    check_targets_protected_domain,
)
from app.llm.adapter_gate import (
    AdapterQualificationRequest,
    AdapterQualificationResult,
    OfflineAdapterGate,
    compute_constitution_digest,
    compute_prompt_digest,
)
from app.persona.profile import PersonaProfile


def make_proposal(**overrides) -> LearningProposal:
    defaults = {
        "source_records": ["episode-1", "episode-2"],
        "target_domain": "procedure.greeting_style",
        "proposed_value": {"style": "warmer"},
        "expected_effect": "warmer greetings improve rapport",
        "risk_class": LearningRiskClass.LOW,
        "rollback_value": {"style": "neutral"},
    }
    defaults.update(overrides)
    return LearningProposal(**defaults)


# ---------------------------------------------------------------------------
# LearningProposal validation
# ---------------------------------------------------------------------------


def test_proposal_requires_risk_class():
    """risk_class has no default: a proposal that does not name its own
    risk cannot be constructed, let alone silently default to LOW."""
    with pytest.raises(ValidationError):
        LearningProposal(
            target_domain="procedure.greeting_style",
            proposed_value={"style": "warmer"},
            expected_effect="warmer greetings improve rapport",
        )


def test_proposal_rejects_unknown_risk_class():
    with pytest.raises(ValidationError):
        make_proposal(risk_class="SUPER_CRITICAL")


def test_proposal_defaults_to_proposed_status():
    proposal = make_proposal()
    assert proposal.status == LearningProposalStatus.PROPOSED
    assert proposal.activation_revision is None
    assert proposal.evaluated_at is None


def test_proposal_stamps_created_at_automatically():
    """Two proposals built moments apart should not carry an identical
    literal-zero default -- a proposal only defends its own timeline if
    created_at is populated for free."""
    first = make_proposal()
    second = make_proposal()
    assert first.created_at > 0.0
    assert second.created_at > 0.0


# ---------------------------------------------------------------------------
# Full lifecycle: PROPOSED -> VALIDATED -> APPROVED -> ACTIVATED -> ROLLED_BACK
# ---------------------------------------------------------------------------


def test_full_lifecycle_low_risk_activates_and_rolls_back():
    applied: list[tuple[str, dict]] = []
    governor = LearningGovernor(state_applier=lambda domain, value: applied.append((domain, value)))
    proposal = make_proposal()

    governor.submit(proposal)
    assert proposal.status == LearningProposalStatus.PROPOSED

    governor.validate(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.VALIDATED

    governor.approve(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.APPROVED

    governor.activate(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.ACTIVATED
    assert proposal.activation_revision == 1
    assert applied == [("procedure.greeting_style", {"style": "warmer"})]

    governor.rollback(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.ROLLED_BACK
    assert applied[-1] == ("procedure.greeting_style", {"style": "neutral"})


def test_lifecycle_rejects_out_of_order_transition():
    """Activating a proposal that has never been validated or approved must
    be refused, not silently treated as if it had passed through those
    steps."""
    governor = LearningGovernor()
    proposal = make_proposal()
    governor.submit(proposal)

    with pytest.raises(ValueError):
        governor.activate(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.PROPOSED


def test_governor_rejects_unknown_proposal_id():
    governor = LearningGovernor()
    with pytest.raises(KeyError):
        governor.validate("does-not-exist")


def test_submit_requires_rollback_value():
    """A proposal with nothing to undo it can never be safely activated, so
    it must be refused at the earliest point: submission."""
    governor = LearningGovernor()
    proposal = make_proposal(rollback_value=None)
    with pytest.raises(ValueError):
        governor.submit(proposal)
    assert governor.get(proposal.proposal_id) is None


def test_submit_rejects_duplicate_proposal_id():
    governor = LearningGovernor()
    proposal = make_proposal()
    governor.submit(proposal)
    with pytest.raises(ValueError):
        governor.submit(proposal)


# ---------------------------------------------------------------------------
# Immutable core / safety invariant hard rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target_domain",
    [
        "persona.immutable.values",
        "identity.core_values",
        "safety.boundaries",
        "safety_invariant.consent",
        "PERSONA.CONSTITUTIONAL.baseline_valence",
        "persona[mood_decay_rate]",
        "persona-mood-decay-rate",
        "identity.name",
    ],
)
def test_protected_domains_are_flagged(target_domain):
    protected, reason = check_targets_protected_domain(target_domain)
    assert protected is True
    assert reason


def test_ordinary_domain_is_not_protected():
    protected, _ = check_targets_protected_domain("procedure.greeting_style")
    assert protected is False


def test_submit_hard_rejects_immutable_core_target():
    governor = LearningGovernor()
    proposal = make_proposal(target_domain="persona.immutable.values", risk_class=LearningRiskClass.LOW)
    with pytest.raises(ValueError):
        governor.submit(proposal)
    assert governor.get(proposal.proposal_id) is None


def test_submit_hard_rejects_constitutional_bound_target():
    governor = LearningGovernor()
    proposal = make_proposal(
        target_domain="persona.mood_decay_rate",
        risk_class=LearningRiskClass.LOW,
        proposed_value={"mood_decay_rate": 0.0},
        rollback_value={"mood_decay_rate": 0.05},
    )
    with pytest.raises(ValueError):
        governor.submit(proposal)


def test_protected_target_cannot_be_approved_even_via_gate_directly():
    """Even calling the gate in isolation -- bypassing the governor's
    submit-time check -- must still refuse a protected target. The hard
    invariant lives in the domain check itself, not only at one call site."""
    gate = LearningApprovalGate(gatekeeper=lambda proposal: True)
    proposal = make_proposal(
        target_domain="safety.boundaries",
        risk_class=LearningRiskClass.LOW,
        status=LearningProposalStatus.VALIDATED,
    )
    approved, reason = gate.evaluate(proposal)
    assert approved is False
    assert "protected" in reason or "boundar" in reason


# ---------------------------------------------------------------------------
# Fix round (P0-1, orchestration/PHASE_06/FIX_PLAN.md): the hard invariant
# must catch a protected field smuggled into proposed_value/rollback_value
# (not only named in target_domain), expanded delimiters (braces, parens,
# commas, backslashes) and joined/camelCase spellings, and a proposal
# mutated after it already passed submit/validate/approve honestly.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "proposed_value",
    [
        {"mood_decay_rate": 0.0},
        {"nested": {"mood_decay_rate": 0.0}},
        {"items": [{"baseline_valence": 0.9}]},
    ],
)
def test_check_protected_domain_catches_protected_proposed_value_keys(proposed_value):
    """A benign target_domain must not be a loophole for smuggling a
    protected field into proposed_value at any nesting depth."""
    protected, reason = check_targets_protected_domain(
        "procedure.greeting_style", proposed_value
    )
    assert protected is True
    assert reason


def test_check_protected_domain_catches_protected_rollback_value_keys():
    protected, reason = check_targets_protected_domain(
        "procedure.greeting_style", {}, {"traits": ["gone"]}
    )
    assert protected is True
    assert reason


@pytest.mark.parametrize(
    "target_domain",
    [
        "persona{mood_decay_rate}",
        "persona(mood_decay_rate)",
        "persona,mood_decay_rate",
        "persona\\mood_decay_rate",
        "moodDecayRate",
        "mooddecayrate",
    ],
)
def test_check_protected_domain_catches_expanded_delimiters_and_camel_case(target_domain):
    protected, reason = check_targets_protected_domain(target_domain)
    assert protected is True
    assert reason


def test_check_protected_domain_joined_match_does_not_false_positive_on_single_word():
    """The joined-substring check is restricted to multi-word phrases so a
    single common protected word (e.g. "name") does not false-positive
    against an unrelated word that merely contains it as a substring."""
    protected, _ = check_targets_protected_domain("user.nickname")
    assert protected is False


def test_submit_hard_rejects_protected_proposed_value_key():
    governor = LearningGovernor()
    proposal = make_proposal(
        target_domain="procedure.greeting_style",
        proposed_value={"mood_decay_rate": 0.0},
    )
    with pytest.raises(ValueError):
        governor.submit(proposal)
    assert governor.get(proposal.proposal_id) is None


def test_activate_rejects_proposal_whose_target_domain_was_mutated_after_approval():
    """A proposal that honestly named a benign target through submit and
    approve, then had target_domain mutated afterward (LearningProposal is
    not frozen), must be caught at the last checkpoint before activation --
    never silently applied."""
    applied: list[tuple[str, dict]] = []
    governor = LearningGovernor(
        state_applier=lambda domain, value: applied.append((domain, value))
    )
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.APPROVED

    proposal.target_domain = "persona.mood_decay_rate"
    result = governor.activate(proposal.proposal_id)

    assert result.status == LearningProposalStatus.REJECTED
    assert applied == []


def test_activate_rejects_proposal_whose_proposed_value_was_mutated_after_approval():
    applied: list[tuple[str, dict]] = []
    governor = LearningGovernor(
        state_applier=lambda domain, value: applied.append((domain, value))
    )
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)

    proposal.proposed_value = {"mood_decay_rate": 0.0}
    result = governor.activate(proposal.proposal_id)

    assert result.status == LearningProposalStatus.REJECTED
    assert applied == []


def test_rollback_refuses_and_preserves_activated_status_when_rollback_value_mutated():
    """Unlike activate(), a protected mutation caught at rollback time must
    not relabel the proposal REJECTED -- real state may already reflect the
    ACTIVATED change -- so this raises and leaves status ACTIVATED instead."""
    applied: list[tuple[str, dict]] = []
    governor = LearningGovernor(
        state_applier=lambda domain, value: applied.append((domain, value))
    )
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    governor.activate(proposal.proposal_id)
    applied.clear()

    proposal.rollback_value = {"mood_decay_rate": 0.05}
    with pytest.raises(ValueError):
        governor.rollback(proposal.proposal_id)

    assert governor.get(proposal.proposal_id).status == LearningProposalStatus.ACTIVATED
    assert applied == []


# ---------------------------------------------------------------------------
# Fix round (P1-2): a failing state_applier must never leave proposal
# status out of sync with whether the write actually happened.
# ---------------------------------------------------------------------------


def test_activate_raises_state_apply_error_and_leaves_status_approved():
    def failing_applier(domain, value):
        raise RuntimeError("simulated write failure")

    governor = LearningGovernor(state_applier=failing_applier)
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)

    with pytest.raises(LearningStateApplyError):
        governor.activate(proposal.proposal_id)

    assert governor.get(proposal.proposal_id).status == LearningProposalStatus.APPROVED
    assert proposal.activation_revision is None


def test_rollback_raises_state_apply_error_and_leaves_status_activated():
    calls = {"n": 0}

    def flaky_applier(domain, value):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated write failure")

    governor = LearningGovernor(state_applier=flaky_applier)
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    governor.activate(proposal.proposal_id)

    with pytest.raises(LearningStateApplyError):
        governor.rollback(proposal.proposal_id)

    assert governor.get(proposal.proposal_id).status == LearningProposalStatus.ACTIVATED


# ---------------------------------------------------------------------------
# Fix round (P1-1): Section 21 training/eval provenance and post-activation
# measurement, preserved through the lifecycle like every other field.
# ---------------------------------------------------------------------------


def test_proposal_carries_training_provenance_and_measurement_through_lifecycle():
    governor = LearningGovernor()
    proposal = make_proposal(
        training_provenance={"eval_report": "evals/out/candidate.json"},
    )
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    governor.activate(proposal.proposal_id)
    proposal.post_activation_measurement = {"pass_rate": 0.98}

    stored = governor.get(proposal.proposal_id)
    assert stored.training_provenance == {"eval_report": "evals/out/candidate.json"}
    assert stored.post_activation_measurement == {"pass_rate": 0.98}
    assert stored.status == LearningProposalStatus.ACTIVATED


def test_proposal_provenance_and_measurement_default_to_none():
    proposal = make_proposal()
    assert proposal.training_provenance is None
    assert proposal.post_activation_measurement is None


# ---------------------------------------------------------------------------
# Risk-tiered approval gating
# ---------------------------------------------------------------------------


def test_low_risk_auto_approves():
    gate = LearningApprovalGate()
    proposal = make_proposal(risk_class=LearningRiskClass.LOW)
    approved, _ = gate.evaluate(proposal)
    assert approved is True


def test_critical_risk_is_always_blocked_even_with_gatekeeper_approval():
    gate = LearningApprovalGate(gatekeeper=lambda proposal: True)
    proposal = make_proposal(risk_class=LearningRiskClass.CRITICAL)
    approved, reason = gate.evaluate(proposal)
    assert approved is False
    assert "CRITICAL" in reason


@pytest.mark.parametrize("risk_class", [LearningRiskClass.MEDIUM, LearningRiskClass.HIGH])
def test_medium_and_high_risk_require_gatekeeper(risk_class):
    gate_without_gatekeeper = LearningApprovalGate()
    proposal = make_proposal(risk_class=risk_class)
    approved, reason = gate_without_gatekeeper.evaluate(proposal)
    assert approved is False
    assert "gatekeeper" in reason

    gate_with_gatekeeper = LearningApprovalGate(gatekeeper=lambda p: True)
    approved, _ = gate_with_gatekeeper.evaluate(proposal)
    assert approved is True


def test_gatekeeper_rejection_is_honored():
    gate = LearningApprovalGate(gatekeeper=lambda proposal: False)
    proposal = make_proposal(risk_class=LearningRiskClass.HIGH)
    approved, reason = gate.evaluate(proposal)
    assert approved is False
    assert "rejected" in reason


def test_governor_approve_marks_rejected_proposal_with_reason():
    governor = LearningGovernor(gate=LearningApprovalGate())
    proposal = make_proposal(risk_class=LearningRiskClass.HIGH)
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.REJECTED
    assert proposal.rejection_reason
    assert proposal.evaluated_at is not None


# ---------------------------------------------------------------------------
# Atomic rollback fidelity
# ---------------------------------------------------------------------------


def test_rollback_restores_exact_rollback_value_not_a_derived_copy():
    applied: list[dict] = []
    governor = LearningGovernor(state_applier=lambda domain, value: applied.append(value))
    proposal = make_proposal(
        proposed_value={"style": "warmer", "extra": "field"},
        rollback_value={"style": "neutral"},
    )
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    governor.activate(proposal.proposal_id)
    governor.rollback(proposal.proposal_id)

    assert applied[-1] == {"style": "neutral"}


def test_rollback_cannot_run_twice():
    governor = LearningGovernor()
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)
    governor.activate(proposal.proposal_id)
    governor.rollback(proposal.proposal_id)

    with pytest.raises(ValueError):
        governor.rollback(proposal.proposal_id)


def test_rollback_before_activation_is_refused():
    governor = LearningGovernor()
    proposal = make_proposal()
    governor.submit(proposal)
    governor.validate(proposal.proposal_id)
    governor.approve(proposal.proposal_id)

    with pytest.raises(ValueError):
        governor.rollback(proposal.proposal_id)
    assert proposal.status == LearningProposalStatus.APPROVED


def test_activation_revision_increments_across_proposals():
    governor = LearningGovernor()
    first = make_proposal()
    second = make_proposal(target_domain="procedure.farewell_style")

    for proposal in (first, second):
        governor.submit(proposal)
        governor.validate(proposal.proposal_id)
        governor.approve(proposal.proposal_id)
        governor.activate(proposal.proposal_id)

    assert first.activation_revision == 1
    assert second.activation_revision == 2


# ---------------------------------------------------------------------------
# Learning-progress curiosity ranking
# ---------------------------------------------------------------------------


def _feed(curiosity: LearningProgressCuriosity, domain: str, errors: list) -> None:
    for error in errors:
        curiosity.record(domain, error)


def test_progress_delta_is_none_until_two_full_windows():
    curiosity = LearningProgressCuriosity(window_size=3)
    _feed(curiosity, "d", [0.9, 0.8, 0.7, 0.6])
    assert curiosity.progress_delta("d") is None


def test_progress_delta_positive_for_improving_domain():
    curiosity = LearningProgressCuriosity(window_size=3)
    _feed(curiosity, "d", [0.9, 0.85, 0.8, 0.5, 0.4, 0.3])
    delta = curiosity.progress_delta("d")
    assert delta is not None
    assert delta > 0


def test_mastered_domain_is_excluded_even_with_flat_history():
    curiosity = LearningProgressCuriosity(window_size=3, mastery_threshold=0.05)
    _feed(curiosity, "solved", [0.01, 0.02, 0.01, 0.01, 0.02, 0.01])
    assert curiosity.is_mastered("solved") is True
    assert curiosity.progress_delta("solved") is not None
    assert "solved" not in dict(curiosity.rank())


def test_noisy_domain_without_trend_is_excluded():
    curiosity = LearningProgressCuriosity(window_size=3, noise_threshold=0.5)
    _feed(curiosity, "noisy", [0.5, 0.9, 0.5, 0.9, 0.5, 0.9])
    ranked = dict(curiosity.rank())
    assert "noisy" not in ranked


def test_rank_orders_learnable_region_above_noise_and_mastery():
    curiosity = LearningProgressCuriosity(window_size=3, noise_threshold=0.02, mastery_threshold=0.05)
    _feed(curiosity, "learning", [0.9, 0.85, 0.8, 0.5, 0.4, 0.3])
    _feed(curiosity, "mastered", [0.01, 0.02, 0.01, 0.01, 0.02, 0.01])
    # Same three values in both the older and recent window -- oscillation
    # with zero net trend, the actual shape "noise" should look like.
    _feed(curiosity, "noisy", [0.5, 0.05, 0.9, 0.5, 0.05, 0.9])

    ranked_domains = [domain for domain, _ in curiosity.rank()]
    assert ranked_domains == ["learning"]


def test_curiosity_rejects_window_size_below_two():
    with pytest.raises(ValueError):
        LearningProgressCuriosity(window_size=1)


def test_curiosity_rejects_negative_stability_factor():
    with pytest.raises(ValueError):
        LearningProgressCuriosity(stability_factor=-1.0)


@pytest.mark.parametrize("bad_error", [float("nan"), float("inf"), float("-inf")])
def test_record_rejects_non_finite_error(bad_error):
    """Fix round (P1-3): NaN/infinity are not empirical measurements -- a
    NaN in particular would silently poison every downstream mean/delta
    rather than raising anywhere near its actual source."""
    curiosity = LearningProgressCuriosity(window_size=3)
    with pytest.raises(ValueError):
        curiosity.record("d", bad_error)


def test_rank_excludes_high_variance_oscillation_even_with_large_raw_delta():
    """Fix round (P1-3): peer review's exact adversarial example. A
    window-3 sequence oscillating between 0 and 1 produces a large raw
    two-window-mean delta (0.53) despite being pure noise, not a real
    trend, and must rank below genuine steady progress rather than above
    it."""
    curiosity = LearningProgressCuriosity(window_size=3, noise_threshold=0.02)
    _feed(curiosity, "noisy-oscillation", [1, 0, 1, 0.2, 0, 0.2])
    _feed(curiosity, "steady-progress", [0.9, 0.85, 0.8, 0.5, 0.4, 0.3])

    # The raw delta alone would have cleared the noise threshold -- proving
    # this is genuinely testing the new stability filter, not a domain the
    # old threshold-only check would have excluded anyway.
    assert curiosity.progress_delta("noisy-oscillation") > curiosity.noise_threshold

    ranked_domains = [domain for domain, _ in curiosity.rank()]
    assert ranked_domains == ["steady-progress"]


# ---------------------------------------------------------------------------
# Offline adapter qualification and regression detection
# ---------------------------------------------------------------------------


def make_gate(min_pass_rate: float = 0.0) -> OfflineAdapterGate:
    return OfflineAdapterGate(
        incumbent_adapter_id="base-v1",
        incumbent_base_model_tag="qwen2.5:3b",
        incumbent_prompt_digest="prompt-abc",
        incumbent_constitution_digest="const-abc",
        min_pass_rate=min_pass_rate,
    )


def make_request(**overrides) -> AdapterQualificationRequest:
    defaults = {
        "adapter_id": "candidate-v2",
        "base_model_tag": "qwen2.5:3b",
        "held_out_eval_file": "evals/out/candidate.json",
        "prompt_digest": "prompt-abc",
        "metadata": {"constitution_digest": "const-abc"},
    }
    defaults.update(overrides)
    return AdapterQualificationRequest(**defaults)


def test_qualify_passes_with_no_regression_and_matching_digests():
    gate = make_gate()
    request = make_request()
    baseline = {"p1": True, "p2": False, "p3": True}
    candidate = {"p1": True, "p2": True, "p3": True}

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.qualified is True
    assert result.regression_detected is False
    assert result.pass_rate == pytest.approx(1.0)


def test_qualify_detects_regression_on_a_probe_that_used_to_pass():
    gate = make_gate()
    request = make_request()
    baseline = {"p1": True, "p2": True}
    candidate = {"p1": True, "p2": False}

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.regression_detected is True
    assert result.qualified is False
    assert "p2" in result.details["regressed_probe_ids"]


def test_qualify_fails_safe_with_no_shared_probes():
    gate = make_gate()
    request = make_request()
    baseline = {"p1": True}
    candidate = {"p2": True}

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.regression_detected is True
    assert result.qualified is False


def test_qualify_fails_on_prompt_digest_mismatch():
    gate = make_gate()
    request = make_request(prompt_digest="prompt-stale")
    baseline = {"p1": True}
    candidate = {"p1": True}

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.qualified is False
    assert result.details["prompt_digest_matches_target"] is False


def test_qualify_fails_on_constitution_digest_mismatch():
    gate = make_gate()
    request = make_request(metadata={"constitution_digest": "const-stale"})
    baseline = {"p1": True}
    candidate = {"p1": True}

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.qualified is False
    assert result.details["constitution_digest_matches_target"] is False


def test_qualify_fails_below_minimum_pass_rate():
    gate = make_gate(min_pass_rate=0.9)
    request = make_request()
    baseline = {"p1": True, "p2": True}
    candidate = {"p1": True, "p2": True, "p3": False}

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.regression_detected is False
    assert result.pass_rate < 0.9
    assert result.qualified is False


def test_activate_refuses_unqualified_result():
    gate = make_gate()
    request = make_request()
    gate.qualify(request, {"p1": True}, {"p1": False}, "prompt-abc", "const-abc")

    with pytest.raises(ValueError):
        gate.activate(request.adapter_id, "prompt-abc", "const-abc")
    assert gate.active.version == "base-v1"


def test_activate_then_rollback_restores_incumbent_atomically():
    gate = make_gate()
    request = make_request()
    result = gate.qualify(request, {"p1": True}, {"p1": True}, "prompt-abc", "const-abc")
    assert result.qualified is True

    activated = gate.activate(request.adapter_id, "prompt-abc", "const-abc")
    assert activated.version == "candidate-v2"
    assert activated.rollback_pointer == "base-v1"
    assert gate.active.version == "candidate-v2"

    restored = gate.rollback()
    assert restored.version == "base-v1"
    assert gate.active.version == "base-v1"


def test_rollback_without_prior_activation_raises():
    gate = make_gate()
    with pytest.raises(ValueError):
        gate.rollback()


def test_rollback_cannot_be_called_twice():
    gate = make_gate()
    request = make_request()
    gate.qualify(request, {"p1": True}, {"p1": True}, "prompt-abc", "const-abc")
    gate.activate(request.adapter_id, "prompt-abc", "const-abc")
    gate.rollback()

    with pytest.raises(ValueError):
        gate.rollback()


# ---------------------------------------------------------------------------
# Fix round (P0-2, orchestration/PHASE_06/FIX_PLAN.md): qualify() must fail
# closed on incomplete baseline probe coverage, and activate() must trust
# only its own internally registered qualification record -- never a
# caller-supplied result or an unverified digest pair.
# ---------------------------------------------------------------------------


def test_qualify_fails_closed_on_missing_baseline_probe():
    """A candidate that silently drops a formerly-passing probe from its
    held-out run must not qualify: a missing result is not evidence of "no
    regression," it is an absence of evidence."""
    gate = make_gate()
    request = make_request()
    baseline = {"p1": True, "p2": True}
    candidate = {"p1": True}  # p2 silently dropped, not merely failed

    result = gate.qualify(request, baseline, candidate, "prompt-abc", "const-abc")

    assert result.qualified is False
    assert result.regression_detected is True
    assert result.details["missing_probe_ids"] == ["p2"]


def test_activate_refuses_mismatched_current_prompt_digest():
    """A persona/prompt change between qualify() and activate() must block
    activation rather than silently activating a now-stale qualification."""
    gate = make_gate()
    request = make_request()
    result = gate.qualify(request, {"p1": True}, {"p1": True}, "prompt-abc", "const-abc")
    assert result.qualified is True

    with pytest.raises(ValueError):
        gate.activate(request.adapter_id, "prompt-changed", "const-abc")
    assert gate.active.version == "base-v1"


def test_activate_refuses_mismatched_current_constitution_digest():
    gate = make_gate()
    request = make_request()
    result = gate.qualify(request, {"p1": True}, {"p1": True}, "prompt-abc", "const-abc")
    assert result.qualified is True

    with pytest.raises(ValueError):
        gate.activate(request.adapter_id, "prompt-abc", "const-changed")
    assert gate.active.version == "base-v1"


def test_activate_refuses_unregistered_adapter_id():
    """There is no path to activation for an adapter qualify() never saw --
    a caller cannot fabricate qualification by adapter id alone."""
    gate = make_gate()
    with pytest.raises(ValueError):
        gate.activate("never-qualified", "prompt-abc", "const-abc")


def test_activate_has_no_parameter_a_forged_result_could_reach():
    """activate() no longer accepts a request/result at all: a caller
    constructing a fabricated AdapterQualificationResult(qualified=True,
    ...) has nothing to hand it to. Only the internally registered record,
    written exclusively by qualify(), can ever drive activation."""
    gate = make_gate()
    forged = AdapterQualificationResult(
        adapter_id="never-qualified",
        qualified=True,
        pass_rate=1.0,
        regression_detected=False,
    )
    assert forged.qualified is True  # the forged object itself is well-formed...
    with pytest.raises(ValueError):
        # ...but activate() has no parameter that could ever receive it.
        gate.activate(forged.adapter_id, "prompt-abc", "const-abc")


def test_requalifying_the_same_adapter_replaces_its_registered_record():
    """A second qualify() call for the same adapter_id must supersede the
    first record, not accumulate stale qualified state alongside it."""
    gate = make_gate()
    request = make_request()
    gate.qualify(request, {"p1": True}, {"p1": False}, "prompt-abc", "const-abc")
    with pytest.raises(ValueError):
        gate.activate(request.adapter_id, "prompt-abc", "const-abc")

    result = gate.qualify(request, {"p1": True}, {"p1": True}, "prompt-abc", "const-abc")
    assert result.qualified is True
    activated = gate.activate(request.adapter_id, "prompt-abc", "const-abc")
    assert activated.version == "candidate-v2"


def test_compute_prompt_digest_is_stable_and_content_sensitive():
    a = compute_prompt_digest("You are a warm, honest friend.")
    b = compute_prompt_digest("You are a warm, honest friend.")
    c = compute_prompt_digest("You are a cold, dishonest friend.")
    assert a == b
    assert a != c


def test_compute_constitution_digest_changes_with_constitutional_field():
    baseline_persona = PersonaProfile.from_config()
    changed_persona = baseline_persona.model_copy(update={"mood_decay_rate": 0.2})

    baseline_digest = compute_constitution_digest(baseline_persona)
    changed_digest = compute_constitution_digest(changed_persona)

    assert baseline_digest != changed_digest


def test_compute_constitution_digest_ignores_adaptive_field():
    """Only IMMUTABLE_CORE + CONSTITUTIONAL fields belong in the
    constitution digest -- an adaptive field like `relationship` changing
    (which reflection is allowed to do routinely) must not force every
    adapter qualified before that change to look stale."""
    baseline_persona = PersonaProfile.from_config()
    changed_persona = baseline_persona.model_copy(update={"relationship": "Trusted Friend"})

    assert compute_constitution_digest(baseline_persona) == compute_constitution_digest(
        changed_persona
    )
