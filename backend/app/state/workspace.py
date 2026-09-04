"""Domain models for the authoritative foreground cognitive workspace."""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any


class StaleWorkspaceError(Exception):
    """Raised when a workspace update fails CAS validation (stale epoch or revision)."""


class WorkspaceDivergenceError(StaleWorkspaceError):
    """Raised when epoch metadata and the persisted workspace disagree."""


@dataclass
class CognitiveWorkspace:
    """Mutable persistence model owned exclusively by ``WorkspaceStore``."""

    session_id: str
    epoch: int
    revision: int
    focus: str | None
    active_goals: list[str]
    pending_action: dict[str, Any] | None
    affect_snapshot: dict[str, float]
    last_percept_id: str | None
    updated_at: float

    @classmethod
    def fresh(cls, session_id: str, epoch: int = 1) -> CognitiveWorkspace:
        """Create the revision-zero state for a session and restart epoch."""
        return cls(
            session_id=session_id,
            epoch=epoch,
            revision=0,
            focus=None,
            active_goals=[],
            pending_action=None,
            affect_snapshot={},
            last_percept_id=None,
            updated_at=time.time(),
        )

    def to_snapshot(self) -> CognitiveWorkspaceSnapshot:
        """Return a detached value so consumers cannot mutate store state."""
        return CognitiveWorkspaceSnapshot(
            session_id=self.session_id,
            epoch=self.epoch,
            revision=self.revision,
            focus=self.focus,
            active_goals=list(self.active_goals),
            pending_action=copy.deepcopy(self.pending_action),
            affect_snapshot=dict(self.affect_snapshot),
            last_percept_id=self.last_percept_id,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class CognitiveWorkspaceSnapshot:
    """Immutable view of workspace state exposed to cognitive consumers."""

    session_id: str
    epoch: int
    revision: int
    focus: str | None
    active_goals: list[str]
    pending_action: dict[str, Any] | None
    affect_snapshot: dict[str, float]
    last_percept_id: str | None
    updated_at: float


@dataclass
class WorkspaceCommand:
    """Mutation command submitted to WorkspaceStore.commit_transition."""

    session_id: str
    expected_epoch: int
    expected_revision: int
    percept_id: str | None = None
    focus_update: str | None = None
    add_goals: list[str] = field(default_factory=list)
    remove_goals: list[str] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    affect_update: dict[str, float] | None = None
    command_source: str = "pipeline"
    clear_focus: bool = False
    clear_pending_action: bool = False


@dataclass
class WorkspaceTransitionRecord:
    """Audit log entry capturing the transition history."""

    transition_id: str
    session_id: str
    from_revision: int
    to_revision: int
    epoch: int
    command_source: str
    percept_id: str | None
    timestamp: float
