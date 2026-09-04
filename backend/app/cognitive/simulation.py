"""Sandboxed prospective episodic simulation with strict write quarantine."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from .planning import (
    DeterministicPlanExecutor,
    DeterministicPlanVerifier,
    PlanArtifact,
    PlanExecutionContext,
    PlanExecutionResult,
    StepAction,
)


class SimulationQuarantineViolationError(RuntimeError):
    """Raised when a simulated record attempts to reach production state."""


class EpisodicSimulationResult(BaseModel):
    """The ephemeral trace and cloned state produced by one prospective rollout."""

    workspace_state: dict[str, Any]
    succeeded: bool = False
    errors: list[str] = Field(default_factory=list)
    percepts: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


SimulationPolicy = Callable[[dict[str, Any], dict[str, Any]], Mapping[str, Any] | None]
OutcomeResolver = Callable[
    [dict[str, Any], dict[str, Any]], Mapping[str, Any] | None
]
ProductionCommit = Callable[[Any], Any]


class EpisodicSimulator:
    """Run bounded what-if traces on copies that cannot write production state."""

    def rollout(
        self,
        workspace_state: Mapping[str, Any],
        percepts: Iterable[Mapping[str, Any]],
        policy: SimulationPolicy,
        outcome_resolver: OutcomeResolver | None = None,
    ) -> EpisodicSimulationResult:
        """Evaluate percepts prospectively without mutating the caller workspace."""
        sandbox = copy.deepcopy(dict(workspace_state))
        simulated_percepts: list[dict[str, Any]] = []
        simulated_actions: list[dict[str, Any]] = []
        simulated_outcomes: list[dict[str, Any]] = []
        for percept in percepts:
            tagged_percept = self._tag(percept)
            action = self._tag(policy(tagged_percept, sandbox) or {})
            outcome = self._resolve_outcome(action, sandbox, outcome_resolver)
            simulated_percepts.append(tagged_percept)
            simulated_actions.append(action)
            simulated_outcomes.append(outcome)
        return EpisodicSimulationResult(
            workspace_state=sandbox,
            succeeded=True,
            percepts=simulated_percepts,
            actions=simulated_actions,
            outcomes=simulated_outcomes,
        )

    def simulate_plan(
        self,
        plan: PlanArtifact,
        workspace_state: Mapping[str, Any],
        action: StepAction | None = None,
    ) -> EpisodicSimulationResult:
        """Execute a plan prospectively with pure, side-effect-free callbacks.

        Callbacks receive ``PlanExecutionContext(is_simulation=True)`` and must
        not write production state, memory, network services, or external devices.
        """
        verification = DeterministicPlanVerifier().verify(plan, workspace_state)
        if not verification.valid:
            return self._invalid_plan_result(workspace_state, verification.errors)
        execution = DeterministicPlanExecutor().execute(
            plan,
            workspace_state,
            action,
            execution_context=PlanExecutionContext(is_simulation=True),
        )
        return self._plan_result(execution)

    def commit_to_production_memory(
        self, record: Any, commit: ProductionCommit | None = None
    ) -> Any:
        """Reject simulated records before a production-memory callback can run."""
        self.assert_production_safe(record)
        return self._call_commit(commit, record)

    def commit_to_production_state(
        self, record: Any, commit: ProductionCommit | None = None
    ) -> Any:
        """Reject simulated records before a persistent-state callback can run."""
        self.assert_production_safe(record)
        return self._call_commit(commit, record)

    @staticmethod
    def assert_production_safe(record: Any) -> None:
        """Enforce the quarantine invariant at every production write boundary."""
        if _is_simulation_record(record):
            raise SimulationQuarantineViolationError(
                "simulated records cannot be committed to production memory or state"
            )

    @staticmethod
    def _tag(record: Mapping[str, Any]) -> dict[str, Any]:
        """Return a detached record whose simulation provenance cannot be omitted."""
        tagged = copy.deepcopy(dict(record))
        tagged["is_simulation"] = True
        return tagged

    def _resolve_outcome(
        self,
        action: dict[str, Any],
        sandbox: dict[str, Any],
        outcome_resolver: OutcomeResolver | None,
    ) -> dict[str, Any]:
        """Create a tagged default outcome when the policy has no resolver."""
        if outcome_resolver is None:
            return self._tag({"status": "SIMULATED", "action": copy.deepcopy(action)})
        return self._tag(outcome_resolver(action, sandbox) or {})

    def _plan_result(self, execution: PlanExecutionResult) -> EpisodicSimulationResult:
        """Translate an execution trace to independently tagged simulated records."""
        actions = [
            self._tag(
                {
                    "step_id": entry.step_id,
                    "status": entry.status.value,
                    "attempt_count": entry.attempt_count,
                }
            )
            for entry in execution.step_executions
        ]
        outcomes = [
            self._tag(
                {
                    "succeeded": execution.succeeded,
                    "errors": list(execution.errors),
                }
            )
        ]
        return EpisodicSimulationResult(
            workspace_state=copy.deepcopy(execution.workspace_state),
            succeeded=execution.succeeded,
            errors=list(execution.errors),
            percepts=[],
            actions=actions,
            outcomes=outcomes,
        )

    def _invalid_plan_result(
        self, workspace_state: Mapping[str, Any], errors: list[str]
    ) -> EpisodicSimulationResult:
        """Return a tagged failure without executing an invalid simulated plan."""
        return EpisodicSimulationResult(
            workspace_state=copy.deepcopy(dict(workspace_state)),
            succeeded=False,
            errors=list(errors),
            outcomes=[self._tag({"succeeded": False, "errors": list(errors)})],
        )

    @staticmethod
    def _call_commit(commit: ProductionCommit | None, record: Any) -> Any:
        """Call an explicit production boundary only after the quarantine check."""
        if commit is None:
            return None
        result = commit(record)
        if inspect.isawaitable(result):
            raise TypeError("use an explicit async wrapper for asynchronous commits")
        return result


def _is_simulation_record(record: Any) -> bool:
    """Recognize tagged mappings, Pydantic models, and nested raw payloads."""
    if isinstance(record, BaseModel):
        return _is_simulation_record(record.model_dump())
    if not isinstance(record, Mapping):
        return bool(getattr(record, "is_simulation", False))
    if record.get("is_simulation") is True:
        return True
    return any(
        _is_simulation_record(record.get(key))
        for key in ("raw_payload", "metadata", "record", "payload")
        if record.get(key) is not None
    )
