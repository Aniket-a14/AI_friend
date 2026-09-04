"""Governed boundary for high-level actions outside the cognitive process."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .action_intent import OutcomeRecord


class ActionReversibility(str, Enum):
    """Whether an action can be undone after an executor accepts it."""

    REVERSIBLE = "REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"


class ActionRiskLevel(str, Enum):
    """Risk classes used by the authorization gate."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExternalActionIntent(BaseModel):
    """A committed request for a tool or real-world actuator operation."""

    action_id: str
    turn_id: str
    tool_or_actuator: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    expected_effects: list[str] = Field(default_factory=list)
    reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    risk_level: ActionRiskLevel = ActionRiskLevel.LOW
    authorization_token: str | None = None
    timeout_s: float = Field(default=10.0, gt=0.0)


ActionExecutor = Callable[[ExternalActionIntent], dict[str, Any]]


class ExternalActionDispatcher:
    """Validates external action commitments before delegating to an executor.

    Unregistered tools are simulated. This makes the protocol safe to use in
    cognition and tests while keeping real actuator registration explicit.
    """

    def __init__(self, executors: Mapping[str, ActionExecutor] | None = None) -> None:
        self._executors = dict(executors or {})

    def validate_action(self, intent: ExternalActionIntent) -> tuple[bool, str | None]:
        """Return whether the request passes irreversible and risk authorization."""
        if not intent.tool_or_actuator.strip():
            return False, "tool_or_actuator must not be blank"
        authorization_required = (
            intent.risk_level in {ActionRiskLevel.HIGH, ActionRiskLevel.CRITICAL}
            or intent.reversibility == ActionReversibility.IRREVERSIBLE
        )
        if authorization_required and not _has_authorization(intent.authorization_token):
            return False, "authorization_token is required for this action"
        return True, None

    def dispatch(self, intent: ExternalActionIntent) -> dict[str, Any]:
        """Execute a registered adapter or return a safe simulation result."""
        valid, reason = self.validate_action(intent)
        if not valid:
            return {
                "action_id": intent.action_id,
                "executed": False,
                "status": "CANCELLED",
                "error": reason,
            }

        executor = self._executors.get(intent.tool_or_actuator)
        if executor is None:
            return {
                "action_id": intent.action_id,
                "executed": False,
                "simulated": True,
                "status": "COMPLETED",
                "tool_or_actuator": intent.tool_or_actuator,
                "message": f"simulated: no adapter registered for {intent.tool_or_actuator}",
            }
        executor_pool = ThreadPoolExecutor(max_workers=1)
        future = executor_pool.submit(executor, intent)
        try:
            result = dict(future.result(timeout=intent.timeout_s))
        except FuturesTimeoutError:
            future.cancel()
            return {
                "action_id": intent.action_id,
                "executed": False,
                "status": "FAILED",
                "error": f"Action timed out after {intent.timeout_s}s",
            }
        except Exception as exc:
            return {
                "action_id": intent.action_id,
                "executed": False,
                "status": "FAILED",
                "error": str(exc),
            }
        finally:
            executor_pool.shutdown(wait=False, cancel_futures=True)
        result.setdefault("action_id", intent.action_id)
        result.setdefault("executed", True)
        result.setdefault("status", "COMPLETED")
        return result

    def create_action_outcome(
        self,
        intent: ExternalActionIntent,
        result: dict[str, Any],
        elapsed_ms: float,
    ) -> OutcomeRecord:
        """Bind a dispatcher result to the existing terminal outcome contract."""
        return create_action_outcome(intent, result, elapsed_ms)


def _has_authorization(token: str | None) -> bool:
    return isinstance(token, str) and bool(token.strip())


def _outcome_status(result: Mapping[str, Any]) -> str:
    """Normalize untrusted executor statuses to valid terminal outcome states."""
    status = str(result.get("status", "COMPLETED")).upper()
    return status if status in {"COMPLETED", "TRUNCATED", "CANCELLED", "FAILED"} else "FAILED"


def create_action_outcome(
    intent: ExternalActionIntent,
    result: dict[str, Any],
    elapsed_ms: float,
) -> OutcomeRecord:
    """Create a terminal ``OutcomeRecord`` for an external action result."""
    status = _outcome_status(result)
    message = result.get("message")
    return OutcomeRecord(
        outcome_id=f"outcome-{uuid.uuid4().hex}",
        intent_id=intent.action_id,
        turn_id=intent.turn_id,
        status=status,
        actual_delivered_text=message if isinstance(message, str) else None,
        elapsed_ms=max(0.0, elapsed_ms),
        recorded_at=time.time(),
        error=str(result["error"]) if result.get("error") is not None else None,
    )
