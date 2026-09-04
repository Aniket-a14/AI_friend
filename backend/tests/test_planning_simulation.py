"""Focused regression tests for verified planning and quarantined simulation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.cognitive.planning import (
    DeterministicPlanExecutor,
    DeterministicPlanVerifier,
    PlanArtifact,
    PlanEffect,
    PlanEffectOp,
    PlanPrecondition,
    PlanStep,
    PreconditionOp,
    _effect_can_establish,
)
from app.cognitive.simulation import (
    EpisodicSimulator,
    SimulationQuarantineViolationError,
)


def _condition(key: str, value: object) -> PlanPrecondition:
    return PlanPrecondition(key=key, op=PreconditionOp.EQUAL, value=value)


def _set_effect(key: str, value: object) -> PlanEffect:
    return PlanEffect(key=key, op=PlanEffectOp.SET, value=value)


def test_plan_artifact_rejects_duplicate_steps_and_unknown_fallbacks():
    """Duplicate ids or an absent fallback make deterministic tracking impossible."""
    step = PlanStep(step_id="one", name="one", action_type="ACT")
    with pytest.raises(ValidationError, match="unique"):
        PlanArtifact(plan_id="p", goal_id="g", steps=[step, step])
    with pytest.raises(ValidationError, match="fallback"):
        PlanArtifact(
            plan_id="p",
            goal_id="g",
            steps=[
                PlanStep(
                    step_id="one",
                    name="one",
                    action_type="ACT",
                    fallback_step_id="absent",
                )
            ],
        )


def test_plan_artifact_rejects_a_self_referential_fallback():
    """A self fallback would make failed action execution loop forever."""
    with pytest.raises(ValidationError, match="itself"):
        PlanArtifact(
            plan_id="self-fallback",
            goal_id="goal",
            steps=[
                PlanStep(
                    step_id="only",
                    name="only",
                    action_type="ACT",
                    fallback_step_id="only",
                )
            ],
        )


def test_verifier_rejects_cyclic_causal_dependencies():
    """A cycle cannot be accepted even when each step appears well formed alone."""
    plan = PlanArtifact(
        plan_id="cycle",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="first",
                name="first",
                action_type="ACT",
                preconditions=[_condition("second_done", True)],
                effects=[_set_effect("first_done", True)],
            ),
            PlanStep(
                step_id="second",
                name="second",
                action_type="ACT",
                preconditions=[_condition("first_done", True)],
                effects=[_set_effect("second_done", True)],
            ),
        ],
    )

    result = DeterministicPlanVerifier().verify(plan)

    assert result.valid is False
    assert result.cycle_detected is True
    assert result.unreachable_steps == ["first", "second"]


def test_verifier_accepts_a_dependency_already_satisfied_by_initial_state():
    """A future effect matching a true initial predicate is not a causal cycle."""
    plan = PlanArtifact(
        plan_id="initial-dependency",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="first",
                name="first",
                action_type="ACT",
                preconditions=[_condition("gate", True)],
                effects=[_set_effect("ready", True)],
            ),
            PlanStep(
                step_id="second",
                name="second",
                action_type="ACT",
                preconditions=[_condition("ready", True)],
                effects=[_set_effect("gate", True)],
            ),
        ],
    )

    result = DeterministicPlanVerifier().verify(plan, {"gate": True})

    assert result.valid is True
    assert result.cycle_detected is False


def test_verifier_ignores_later_redundant_effects_for_causal_dependencies():
    """A later re-affirmation must not make an ordered plan appear cyclic."""
    plan = PlanArtifact(
        plan_id="ordered-producers",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="prepare",
                name="prepare",
                action_type="ACT",
                effects=[_set_effect("ready", True)],
            ),
            PlanStep(
                step_id="use",
                name="use",
                action_type="ACT",
                preconditions=[_condition("ready", True)],
                effects=[_set_effect("used", True)],
            ),
            PlanStep(
                step_id="reaffirm",
                name="reaffirm",
                action_type="ACT",
                preconditions=[_condition("used", True)],
                effects=[_set_effect("ready", True)],
            ),
        ],
    )

    result = DeterministicPlanVerifier().verify(plan)

    assert result.valid is True
    assert result.cycle_detected is False


def test_delete_effect_cannot_establish_not_equal_when_key_is_missing():
    """NOT_EQUAL requires a present distinct value, so DELETE cannot establish it."""
    condition = PlanPrecondition(
        key="status", op=PreconditionOp.NOT_EQUAL, value="blocked"
    )
    effect = PlanEffect(key="status", op=PlanEffectOp.DELETE, value=None)

    assert _effect_can_establish(effect, condition) is False


def test_verifier_rejects_unfulfilled_precondition_and_invariant_violation():
    """A reachable transition may not silently cross a declared safety invariant."""
    plan = PlanArtifact(
        plan_id="unsafe",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="missing",
                name="missing",
                action_type="ACT",
                preconditions=[_condition("authorized", True)],
            ),
            PlanStep(
                step_id="breaks-invariant",
                name="breaks invariant",
                action_type="ACT",
                effects=[_set_effect("safe", False)],
            ),
        ],
        invariants=[_condition("safe", True)],
    )

    result = DeterministicPlanVerifier().verify(plan, {"safe": True})

    assert result.valid is False
    assert result.unreachable_steps == ["missing"]
    assert result.invariant_violations == [
        "invariant violated after step breaks-invariant: safe"
    ]


def test_verifier_rejects_declared_or_actual_step_budget_overrun():
    """The fixed twenty-step ceiling prevents unbounded deliberative plans."""
    steps = [
        PlanStep(step_id=f"step-{index}", name="step", action_type="ACT")
        for index in range(21)
    ]
    plan = PlanArtifact(
        plan_id="budget",
        goal_id="goal",
        steps=steps,
        budget_max_steps=21,
    )

    result = DeterministicPlanVerifier().verify(plan)

    assert result.valid is False
    assert "budget_max_steps exceeds 20" in result.errors


def test_verifier_rejects_more_steps_than_the_declared_budget():
    """The declared step budget must constrain the actual number of plan steps."""
    plan = PlanArtifact(
        plan_id="declared-budget",
        goal_id="goal",
        budget_max_steps=1,
        steps=[
            PlanStep(step_id="first", name="first", action_type="ACT"),
            PlanStep(step_id="second", name="second", action_type="ACT"),
        ],
    )

    result = DeterministicPlanVerifier().verify(plan)

    assert result.valid is False
    assert "plan step count exceeds budget_max_steps" in result.errors


def test_executor_tracks_failed_step_and_runs_declared_fallback():
    """A failed primary action must take its explicit fallback and preserve a trace."""
    plan = PlanArtifact(
        plan_id="fallback",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="primary",
                name="primary",
                action_type="ACT",
                fallback_step_id="fallback",
            ),
            PlanStep(
                step_id="fallback",
                name="fallback",
                action_type="ACT",
                effects=[_set_effect("recovered", True)],
            ),
        ],
    )

    result = DeterministicPlanExecutor().execute(
        plan,
        {},
        action=lambda step, _state, _context: step.step_id != "primary",
    )

    assert result.succeeded is True
    assert result.workspace_state == {"recovered": True}
    assert [(entry.step_id, entry.status.value) for entry in result.step_executions] == [
        ("primary", "FAILED"),
        ("fallback", "SUCCEEDED"),
    ]
    assert result.fallback_transitions == [("primary", "fallback")]


def test_executor_retries_then_succeeds_with_the_actual_attempt_count():
    """A transient action failure must retry before applying the step effects."""
    plan = PlanArtifact(
        plan_id="retry-success",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="retry",
                name="retry",
                action_type="ACT",
                max_retries=2,
                effects=[_set_effect("finished", True)],
            )
        ],
    )
    attempts: list[int] = []

    def transient_action(_step, _state, _context):
        attempts.append(1)
        return len(attempts) == 2

    result = DeterministicPlanExecutor().execute(plan, {}, transient_action)

    assert result.succeeded is True
    assert attempts == [1, 1]
    assert result.step_executions[0].attempt_count == 2
    assert result.workspace_state == {"finished": True}


def test_executor_reports_retry_exhaustion_as_a_plan_failure():
    """A step that exhausts every retry cannot silently leave the plan successful."""
    plan = PlanArtifact(
        plan_id="retry-failure",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="retry",
                name="retry",
                action_type="ACT",
                max_retries=1,
            )
        ],
    )

    result = DeterministicPlanExecutor().execute(
        plan, {}, lambda _step, _state, _context: False
    )

    assert result.succeeded is False
    assert result.step_executions[0].attempt_count == 2
    assert result.errors == ["step action reported failure"]


def test_executor_applies_increment_append_and_delete_effects():
    """Every supported non-SET effect must mutate only the detached workspace."""
    plan = PlanArtifact(
        plan_id="operators",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="transform",
                name="transform",
                action_type="ACT",
                effects=[
                    PlanEffect(key="count", op=PlanEffectOp.INCREMENT, value=2),
                    PlanEffect(key="items", op=PlanEffectOp.APPEND, value="new"),
                    PlanEffect(key="remove", op=PlanEffectOp.DELETE, value=None),
                ],
            )
        ],
    )

    result = DeterministicPlanExecutor().execute(
        plan, {"count": 3, "items": ["old"], "remove": True}
    )

    assert result.succeeded is True
    assert result.workspace_state == {"count": 5, "items": ["old", "new"]}


def test_executor_reports_fallback_cycles_as_failures():
    """Indirect fallback cycles must fail closed even after nodes enter completed."""
    plan = PlanArtifact(
        plan_id="fallback-cycle",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="first",
                name="first",
                action_type="ACT",
                fallback_step_id="second",
            ),
            PlanStep(
                step_id="second",
                name="second",
                action_type="ACT",
                fallback_step_id="first",
            ),
        ],
    )

    result = DeterministicPlanExecutor().execute(
        plan, {}, lambda _step, _state, _context: False
    )

    assert result.succeeded is False
    assert result.errors == ["execution fallback cycle at step first"]
    assert result.fallback_transitions == [("first", "second"), ("second", "first")]


def test_simulator_rollout_tags_every_record_and_does_not_mutate_workspace():
    """Prospective policy work must remain a tagged trace over a copied workspace."""
    original = {"counter": 1, "nested": {"values": ["live"]}}

    def policy(percept: dict[str, object], workspace: dict[str, object]):
        workspace["counter"] = int(workspace["counter"]) + 1
        return {"action": "RESPOND", "percept_id": percept["percept_id"]}

    result = EpisodicSimulator().rollout(
        original,
        [{"percept_id": "p-1", "text": "hello"}],
        policy,
    )

    assert original == {"counter": 1, "nested": {"values": ["live"]}}
    assert result.workspace_state["counter"] == 2
    assert all(
        record["is_simulation"] is True
        for records in (result.percepts, result.actions, result.outcomes)
        for record in records
    )


def test_simulator_executes_a_plan_on_a_cloned_workspace():
    """A simulated plan effect must appear only in the prospective workspace."""
    plan = PlanArtifact(
        plan_id="simulated-plan",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="advance",
                name="advance",
                action_type="ACT",
                effects=[_set_effect("phase", "prospective")],
            )
        ],
    )
    original = {"phase": "live"}

    result = EpisodicSimulator().simulate_plan(plan, original)

    assert original == {"phase": "live"}
    assert result.workspace_state == {"phase": "prospective"}
    assert result.succeeded is True
    assert result.actions[0]["is_simulation"] is True
    assert result.outcomes[0]["is_simulation"] is True


def test_simulator_marks_action_context_and_execution_failure_as_simulated():
    """Simulation callbacks see quarantine context and failed plans report failure."""
    plan = PlanArtifact(
        plan_id="simulated-failure",
        goal_id="goal",
        steps=[PlanStep(step_id="act", name="act", action_type="ACT")],
    )
    contexts: list[bool] = []

    def failing_action(_step, _state, context):
        contexts.append(context.is_simulation)
        return False

    result = EpisodicSimulator().simulate_plan(plan, {}, failing_action)

    assert contexts == [True, True]
    assert result.succeeded is False
    assert result.errors == ["step action reported failure"]
    assert result.actions[0]["is_simulation"] is True
    assert result.outcomes[0]["is_simulation"] is True


def test_simulator_rejects_invalid_plans_without_executing_actions():
    """Invalid plans must fail closed before a simulation callback can run."""
    plan = PlanArtifact(
        plan_id="invalid-simulation",
        goal_id="goal",
        steps=[
            PlanStep(
                step_id="first",
                name="first",
                action_type="ACT",
                fallback_step_id="second",
            ),
            PlanStep(
                step_id="second",
                name="second",
                action_type="ACT",
                fallback_step_id="first",
            ),
        ],
    )
    called: list[bool] = []

    def action(_step, _state, _context):
        called.append(True)
        return True

    result = EpisodicSimulator().simulate_plan(plan, {}, action)

    assert called == []
    assert result.succeeded is False
    assert "plan contains a circular dependency" in result.errors
    assert result.outcomes[0]["is_simulation"] is True


def test_simulated_records_cannot_reach_production_memory_or_state():
    """The quarantine guard must fire before either production callback runs."""
    simulator = EpisodicSimulator()
    record = {"record_id": "simulated", "is_simulation": True}
    committed: list[object] = []

    with pytest.raises(SimulationQuarantineViolationError):
        simulator.commit_to_production_memory(record, committed.append)
    with pytest.raises(SimulationQuarantineViolationError):
        simulator.commit_to_production_state(record, committed.append)

    assert committed == []


def test_phase_six_files_are_strictly_seven_bit_ascii():
    """Unicode in contracts, tests, or result docs can break constrained tooling."""
    repo_root = Path(__file__).resolve().parents[2]
    paths = [
        repo_root / "backend/app/cognitive/planning.py",
        repo_root / "backend/app/cognitive/simulation.py",
        repo_root / "backend/tests/test_planning_simulation.py",
        repo_root / "orchestration/PHASE_06/CODEX_RESULT.md",
    ]
    for path in paths:
        assert all(byte < 128 for byte in path.read_bytes()), path
