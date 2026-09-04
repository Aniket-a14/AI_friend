"""Deterministic plan contracts, verification, and fallback execution.

This module is deliberately state-store agnostic.  A caller supplies a
workspace mapping, and verification or execution returns a separate mapping.
Production persistence remains outside this planning boundary.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

_MISSING = object()
MAX_PLAN_STEPS = 20


class PreconditionOp(str, Enum):
    """Supported deterministic predicates over a workspace value."""

    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    CONTAINS = "CONTAINS"
    NOT_EMPTY = "NOT_EMPTY"


class PlanPrecondition(BaseModel):
    """A predicate which must hold before a plan transition."""

    key: str
    op: PreconditionOp
    value: Any

    @field_validator("key")
    @classmethod
    def key_must_not_be_blank(cls, value: str) -> str:
        """Reject ambiguous empty workspace paths."""
        if not value.strip():
            raise ValueError("precondition key must not be blank")
        return value


class PlanEffectOp(str, Enum):
    """Supported deterministic workspace transitions."""

    SET = "SET"
    INCREMENT = "INCREMENT"
    APPEND = "APPEND"
    DELETE = "DELETE"


class PlanEffect(BaseModel):
    """A bounded state transition performed after a successful step."""

    key: str
    op: PlanEffectOp
    value: Any

    @field_validator("key")
    @classmethod
    def key_must_not_be_blank(cls, value: str) -> str:
        """Reject ambiguous empty workspace paths."""
        if not value.strip():
            raise ValueError("effect key must not be blank")
        return value


class PlanStep(BaseModel):
    """One typed action with declarative transition and fallback metadata."""

    step_id: str
    name: str
    action_type: str
    preconditions: list[PlanPrecondition] = Field(default_factory=list)
    effects: list[PlanEffect] = Field(default_factory=list)
    fallback_step_id: str | None = None
    timeout_s: float = Field(default=5.0, gt=0.0)
    max_retries: int = Field(default=1, ge=0)

    @field_validator("step_id", "name", "action_type")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        """Reject identifiers that cannot be safely addressed or displayed."""
        if not value.strip():
            raise ValueError("plan step text fields must not be blank")
        return value


class PlanArtifact(BaseModel):
    """A bounded, declarative plan suitable for deterministic verification."""

    plan_id: str
    goal_id: str
    version: int = Field(default=1, ge=1)
    steps: list[PlanStep] = Field(min_length=1)
    initial_preconditions: list[PlanPrecondition] = Field(default_factory=list)
    terminal_conditions: list[PlanPrecondition] = Field(default_factory=list)
    invariants: list[PlanPrecondition] = Field(default_factory=list)
    budget_max_steps: int = Field(default=MAX_PLAN_STEPS, ge=1)
    estimated_cost: float = Field(default=0.0, ge=0.0)

    @field_validator("plan_id", "goal_id")
    @classmethod
    def identifiers_must_not_be_blank(cls, value: str) -> str:
        """Reject plans without stable identifiers."""
        if not value.strip():
            raise ValueError("plan identifiers must not be blank")
        return value

    @model_validator(mode="after")
    def validate_step_references(self) -> PlanArtifact:
        """Require unique ids and fallback references that exist in this plan."""
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("plan step ids must be unique")
        if any(
            step.fallback_step_id == step.step_id
            for step in self.steps
            if step.fallback_step_id is not None
        ):
            raise ValueError("a plan step cannot use itself as its fallback")
        unknown_fallbacks = [
            step.fallback_step_id
            for step in self.steps
            if step.fallback_step_id is not None
            and step.fallback_step_id not in step_ids
        ]
        if unknown_fallbacks:
            raise ValueError("fallback step ids must reference a plan step")
        return self


class PlanVerificationResult(BaseModel):
    """The complete deterministic verdict for a plan and initial workspace."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    cycle_detected: bool = False
    unreachable_steps: list[str] = Field(default_factory=list)
    invariant_violations: list[str] = Field(default_factory=list)


class PlanStepStatus(str, Enum):
    """Terminal status of an attempted step."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PlanStepExecution(BaseModel):
    """An auditable execution attempt and any fallback transition taken."""

    step_id: str
    status: PlanStepStatus
    attempt_count: int = 0
    fallback_step_id: str | None = None
    error: str | None = None


class PlanExecutionResult(BaseModel):
    """The detached state and trace produced by deterministic plan execution."""

    succeeded: bool
    workspace_state: dict[str, Any]
    step_executions: list[PlanStepExecution] = Field(default_factory=list)
    fallback_transitions: list[tuple[str, str]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def precondition_holds(
    precondition: PlanPrecondition, workspace_state: Mapping[str, Any]
) -> bool:
    """Evaluate one predicate without coercing missing values or types."""
    actual = workspace_state.get(precondition.key, _MISSING)
    if precondition.op is PreconditionOp.EQUAL:
        return actual is not _MISSING and actual == precondition.value
    if precondition.op is PreconditionOp.NOT_EQUAL:
        return actual is not _MISSING and actual != precondition.value
    if precondition.op is PreconditionOp.NOT_EMPTY:
        return actual is not _MISSING and bool(actual)
    return _compare_precondition(actual, precondition)


def _compare_precondition(actual: Any, precondition: PlanPrecondition) -> bool:
    """Evaluate comparisons that can fail for heterogeneous state values."""
    if actual is _MISSING:
        return False
    try:
        if precondition.op is PreconditionOp.GREATER_EQUAL:
            return actual >= precondition.value
        if precondition.op is PreconditionOp.LESS_EQUAL:
            return actual <= precondition.value
        if precondition.op is PreconditionOp.CONTAINS:
            return precondition.value in actual
    except TypeError:
        return False
    return False


def apply_effect(effect: PlanEffect, workspace_state: dict[str, Any]) -> None:
    """Apply one supported effect to a caller-owned detached workspace map."""
    if effect.op is PlanEffectOp.SET:
        workspace_state[effect.key] = copy.deepcopy(effect.value)
        return
    if effect.op is PlanEffectOp.DELETE:
        workspace_state.pop(effect.key, None)
        return
    if effect.op is PlanEffectOp.INCREMENT:
        _increment(effect, workspace_state)
        return
    _append(effect, workspace_state)


def _increment(effect: PlanEffect, workspace_state: dict[str, Any]) -> None:
    """Increment a numeric state value while rejecting silent coercion."""
    current = workspace_state.get(effect.key, 0)
    if isinstance(current, bool) or isinstance(effect.value, bool):
        raise TypeError(f"effect {effect.key!r} requires numeric values")
    if not isinstance(current, (int, float)) or not isinstance(effect.value, (int, float)):
        raise TypeError(f"effect {effect.key!r} requires numeric values")
    workspace_state[effect.key] = current + effect.value


def _append(effect: PlanEffect, workspace_state: dict[str, Any]) -> None:
    """Append to a list state value without sharing mutable plan values."""
    current = workspace_state.get(effect.key, [])
    if not isinstance(current, list):
        raise TypeError(f"effect {effect.key!r} requires a list value")
    workspace_state[effect.key] = [*current, copy.deepcopy(effect.value)]


class DeterministicPlanVerifier:
    """Verify bounded plans by replaying their declared transitions in order."""

    def verify(
        self,
        plan: PlanArtifact,
        initial_state: Mapping[str, Any] | None = None,
    ) -> PlanVerificationResult:
        """Return all detected plan errors without mutating the initial state."""
        state = copy.deepcopy(dict(initial_state or {}))
        errors = self._budget_errors(plan)
        errors.extend(self._initial_errors(plan, state))
        invariant_violations = self._invariant_errors(plan, state, None)
        cycle_detected = self._has_cycle(plan, state)
        if cycle_detected:
            errors.append("plan contains a circular dependency")
        unreachable, transition_errors, transition_invariant_violations = self._replay(
            plan, state
        )
        invariant_violations.extend(transition_invariant_violations)
        errors.extend(transition_errors)
        errors.extend(invariant_violations)
        return PlanVerificationResult(
            valid=not errors,
            errors=errors,
            cycle_detected=cycle_detected,
            unreachable_steps=unreachable,
            invariant_violations=invariant_violations,
        )

    @staticmethod
    def _budget_errors(plan: PlanArtifact) -> list[str]:
        """Reject both a plan's declared and actual work above the fixed ceiling."""
        errors: list[str] = []
        if plan.budget_max_steps > MAX_PLAN_STEPS:
            errors.append(f"budget_max_steps exceeds {MAX_PLAN_STEPS}")
        if len(plan.steps) > plan.budget_max_steps:
            errors.append("plan step count exceeds budget_max_steps")
        return errors

    @staticmethod
    def _initial_errors(plan: PlanArtifact, state: Mapping[str, Any]) -> list[str]:
        """Report plan-level predicates that the supplied workspace does not meet."""
        return [
            f"initial precondition is unfulfilled: {condition.key}"
            for condition in plan.initial_preconditions
            if not precondition_holds(condition, state)
        ]

    def _replay(
        self, plan: PlanArtifact, state: dict[str, Any]
    ) -> tuple[list[str], list[str], list[str]]:
        """Replay reachable effects and validate invariants after each transition."""
        unreachable: list[str] = []
        errors: list[str] = []
        invariant_violations: list[str] = []
        for step in plan.steps:
            if not self._step_is_reachable(step, state, unreachable, errors):
                continue
            if not self._apply_step(step, state, errors):
                continue
            invariant_violations.extend(self._invariant_errors(plan, state, step))
        errors.extend(self._terminal_errors(plan, state))
        return unreachable, errors, invariant_violations

    @staticmethod
    def _step_is_reachable(
        step: PlanStep,
        state: Mapping[str, Any],
        unreachable: list[str],
        errors: list[str],
    ) -> bool:
        """Require every step predicate to be established before this step."""
        missing = [
            condition.key
            for condition in step.preconditions
            if not precondition_holds(condition, state)
        ]
        if not missing:
            return True
        unreachable.append(step.step_id)
        errors.append(f"step {step.step_id} has unfulfilled preconditions: {', '.join(missing)}")
        return False

    @staticmethod
    def _apply_step(step: PlanStep, state: dict[str, Any], errors: list[str]) -> bool:
        """Apply all effects or preserve the pre-step state if one is invalid."""
        before = copy.deepcopy(state)
        try:
            for effect in step.effects:
                apply_effect(effect, state)
        except TypeError as error:
            state.clear()
            state.update(before)
            errors.append(f"step {step.step_id} has invalid effect: {error}")
            return False
        return True

    @staticmethod
    def _invariant_errors(
        plan: PlanArtifact, state: Mapping[str, Any], step: PlanStep | None
    ) -> list[str]:
        """Name each invariant broken by a reachable state transition."""
        location = "initial state" if step is None else f"after step {step.step_id}"
        return [
            f"invariant violated {location}: {condition.key}"
            for condition in plan.invariants
            if not precondition_holds(condition, state)
        ]

    @staticmethod
    def _terminal_errors(plan: PlanArtifact, state: Mapping[str, Any]) -> list[str]:
        """Require terminal predicates after all reachable effects are replayed."""
        return [
            f"terminal condition is unfulfilled: {condition.key}"
            for condition in plan.terminal_conditions
            if not precondition_holds(condition, state)
        ]

    def _has_cycle(self, plan: PlanArtifact, initial_state: Mapping[str, Any]) -> bool:
        """Detect cycles from fallback edges and causal producer dependencies."""
        graph = self._dependency_graph(plan, initial_state)
        return self._graph_has_cycle(graph)

    @staticmethod
    def _dependency_graph(
        plan: PlanArtifact, initial_state: Mapping[str, Any]
    ) -> dict[str, set[str]]:
        """Build a graph whose edges run from a step to what it depends on."""
        graph = {step.step_id: set() for step in plan.steps}
        for index, step in enumerate(plan.steps):
            if step.fallback_step_id is not None:
                graph[step.step_id].add(step.fallback_step_id)
            for condition in step.preconditions:
                if precondition_holds(condition, initial_state):
                    continue
                graph[step.step_id].update(
                    _causal_producer_ids(plan.steps, index, condition)
                )
        return graph

    @staticmethod
    def _graph_has_cycle(graph: Mapping[str, set[str]]) -> bool:
        """Use depth-first colors so every back-edge is a deterministic failure."""
        visiting: set[str] = set()
        visited: set[str] = set()
        return any(
            _visit_for_cycle(node, graph, visiting, visited) for node in graph
        )


def _effect_can_establish(effect: PlanEffect, condition: PlanPrecondition) -> bool:
    """Conservatively identify effects that could establish a predicate key."""
    if effect.key != condition.key:
        return False
    if effect.op is PlanEffectOp.DELETE:
        return False
    if effect.op is PlanEffectOp.SET:
        return precondition_holds(condition, {effect.key: effect.value})
    if effect.op is PlanEffectOp.INCREMENT:
        return condition.op in {PreconditionOp.GREATER_EQUAL, PreconditionOp.LESS_EQUAL}
    return condition.op in {PreconditionOp.CONTAINS, PreconditionOp.NOT_EMPTY}


def _causal_producer_ids(
    steps: list[PlanStep], consumer_index: int, condition: PlanPrecondition
) -> set[str]:
    """Prefer preceding producers so later redundant effects do not form cycles."""
    preceding = _producer_ids(steps[:consumer_index], condition)
    if preceding:
        return preceding
    return _producer_ids(steps[consumer_index + 1 :], condition)


def _producer_ids(
    steps: list[PlanStep], condition: PlanPrecondition
) -> set[str]:
    """Return declared steps whose effects could establish one predicate."""
    return {
        step.step_id
        for step in steps
        if any(_effect_can_establish(effect, condition) for effect in step.effects)
    }


def _visit_for_cycle(
    node: str,
    graph: Mapping[str, set[str]],
    visiting: set[str],
    visited: set[str],
) -> bool:
    """Return true only when a DFS edge returns to the active recursion path."""
    if node in visited:
        return False
    if node in visiting:
        return True
    visiting.add(node)
    if any(_visit_for_cycle(next_node, graph, visiting, visited) for next_node in graph[node]):
        return True
    visiting.remove(node)
    visited.add(node)
    return False


@dataclass(frozen=True, slots=True)
class PlanExecutionContext:
    """Execution mode supplied to every action callback."""

    is_simulation: bool = False


StepAction = Callable[[PlanStep, dict[str, Any], PlanExecutionContext], bool | None]


class DeterministicPlanExecutor:
    """Execute steps deterministically and record every fallback transition."""

    def execute(
        self,
        plan: PlanArtifact,
        workspace_state: Mapping[str, Any],
        action: StepAction | None = None,
        execution_context: PlanExecutionContext | None = None,
    ) -> PlanExecutionResult:
        """Execute declared steps once, redirecting failures to declared fallbacks."""
        state = copy.deepcopy(dict(workspace_state))
        context = execution_context or PlanExecutionContext()
        steps = {step.step_id: step for step in plan.steps}
        trace: list[PlanStepExecution] = []
        transitions: list[tuple[str, str]] = []
        errors: list[str] = []
        completed: set[str] = set()
        for step in plan.steps:
            self._execute_chain(
                step,
                steps,
                state,
                action,
                context,
                completed,
                trace,
                transitions,
                errors,
            )
        return PlanExecutionResult(
            succeeded=not errors,
            workspace_state=state,
            step_executions=trace,
            fallback_transitions=transitions,
            errors=errors,
        )

    def _execute_chain(
        self,
        first_step: PlanStep,
        steps: Mapping[str, PlanStep],
        state: dict[str, Any],
        action: StepAction | None,
        execution_context: PlanExecutionContext,
        completed: set[str],
        trace: list[PlanStepExecution],
        transitions: list[tuple[str, str]],
        errors: list[str],
    ) -> None:
        """Follow one failure path, stopping deterministically on a repeat."""
        step = first_step
        chain: set[str] = set()
        while True:
            if step.step_id in chain:
                errors.append(f"execution fallback cycle at step {step.step_id}")
                return
            if step.step_id in completed:
                return
            chain.add(step.step_id)
            execution = self._attempt_step(step, state, action, execution_context)
            trace.append(execution)
            completed.add(step.step_id)
            if execution.status is PlanStepStatus.SUCCEEDED:
                return
            if step.fallback_step_id is None:
                errors.append(execution.error or f"step {step.step_id} failed")
                return
            transitions.append((step.step_id, step.fallback_step_id))
            execution.fallback_step_id = step.fallback_step_id
            step = steps[step.fallback_step_id]

    @staticmethod
    def _attempt_step(
        step: PlanStep,
        state: dict[str, Any],
        action: StepAction | None,
        execution_context: PlanExecutionContext,
    ) -> PlanStepExecution:
        """Run one action at most retry-count plus one times before applying effects."""
        if not all(precondition_holds(condition, state) for condition in step.preconditions):
            return PlanStepExecution(
                step_id=step.step_id,
                status=PlanStepStatus.FAILED,
                error="step preconditions are unfulfilled",
            )
        for attempt in range(1, step.max_retries + 2):
            try:
                successful = (
                    action(step, state, execution_context) if action is not None else True
                )
            except Exception as error:  # action adapters are an execution boundary
                successful = False
                failure = str(error)
            else:
                failure = "step action reported failure"
            if successful is not False:
                before = copy.deepcopy(state)
                try:
                    for effect in step.effects:
                        apply_effect(effect, state)
                except TypeError as error:
                    state.clear()
                    state.update(before)
                    return PlanStepExecution(
                        step_id=step.step_id,
                        status=PlanStepStatus.FAILED,
                        attempt_count=attempt,
                        error=str(error),
                    )
                return PlanStepExecution(
                    step_id=step.step_id,
                    status=PlanStepStatus.SUCCEEDED,
                    attempt_count=attempt,
                )
        return PlanStepExecution(
            step_id=step.step_id,
            status=PlanStepStatus.FAILED,
            attempt_count=step.max_retries + 1,
            error=failure,
        )


PlanStepTracker = DeterministicPlanExecutor
