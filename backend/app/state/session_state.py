"""Phase 2B (§15 item 7): per-turn session state.

Before this, "is this turn speculative", "which turn/utterance", and
"is playback mid-interruption" lived as ad hoc dict keys threaded through
three different unfunneled paths -- `event_metadata`/`event.metadata`,
`raw_event`, and `plan.payload` -- each stage of `CognitivePipeline.execute`
reading and writing whichever of those happened to be in scope for it.
`SessionState` is the collection point: constructed once per turn at stage 1,
threaded through `event.metadata["session_state"]` for any stage that wants
one shared object instead of re-deriving the same facts from three places.

Backed by `WorkingMemoryStore` (Redis + SQLite fallback) rather than a new
store -- session state is exactly what that store already models: sub-turn,
volatile, single-most-recent-value data. `WorkingMemoryStore` had a real,
tested API but no production caller before this; persisting `SessionState`
through it is that store's first real producer.

Scope note: this phase gives every turn a real, populated `SessionState` and
makes stage 2 (turn-taking conflict resolution) a real reader/writer of
`active_interruption` -- it does not rip out the existing dict-key threading
elsewhere in the pipeline, which stays the source of truth for today's
speculative/turn-taking behavior. Migrating every remaining stage onto
`SessionState` as the sole source is future work, not attempted here, to
keep this change additive on the hottest path in the codebase.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from ..config import Config
from .workspace import CognitiveWorkspaceSnapshot, WorkspaceCommand

if TYPE_CHECKING:
    from .workspace_store import WorkspaceStore

InterruptionState = Literal["none", "duck", "stop"]


@dataclass
class SessionState:
    turn_id: str
    utterance_id: str | None = None
    speculative: bool = False
    active_interruption: InterruptionState = "none"
    started_at: float = field(default_factory=time.time)

    @classmethod
    def start_turn(
        cls,
        turn_id: str | None = None,
        utterance_id: str | None = None,
        speculative: bool = False,
    ) -> SessionState:
        """One call per turn, at `CognitivePipeline.execute` stage 1.

        `turn_id` defaults to a fresh uuid4 when the caller (today, nothing
        upstream reliably assigns one) doesn't supply one -- every turn gets
        an identity, not just the ones some future producer remembers to
        stamp.
        """
        return cls(
            turn_id=turn_id or uuid.uuid4().hex,
            utterance_id=utterance_id,
            speculative=speculative,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def persist_session_state(
    store: Any,
    session_state: SessionState,
    workspace_store: WorkspaceStore | None = None,
    workspace_session_id: str | None = None,
) -> None:
    """Persist legacy state and optionally mirror it into the workspace.

    The workspace write runs first when it is authoritative, so a rejected CAS
    cannot leave a newer legacy value beside an older authoritative value.
    ``store=None`` remains a supported no-op when no workspace is supplied.
    """
    if workspace_store is not None and _workspace_authoritative_enabled():
        await _persist_workspace_session_state(
            workspace_store,
            workspace_session_id or session_state.turn_id,
            session_state,
        )
    if store is not None:
        await store.set_state_var("session_state", session_state.to_dict())


async def load_session_state(
    store: Any,
    workspace_store: WorkspaceStore | None = None,
    workspace_session_id: str | None = None,
) -> SessionState | None:
    """Load authoritative state when enabled, otherwise retain legacy behavior.

    A process resuming from workspace-only state must supply
    ``workspace_session_id`` because legacy ``SessionState`` has no session ID.
    """
    data = await store.get_state_var("session_state") if store is not None else None
    legacy_state = SessionState(**data) if data else None
    if workspace_store is None or not _workspace_authoritative_enabled():
        return legacy_state

    session_id = workspace_session_id or (
        legacy_state.turn_id if legacy_state is not None else None
    )
    if session_id is None:
        return legacy_state
    snapshot = await workspace_store.get_snapshot(session_id)
    workspace_state = _session_state_from_workspace(snapshot)
    return workspace_state or legacy_state


def _workspace_authoritative_enabled() -> bool:
    """Read the migration flag from the process-level configuration facade."""
    return bool(getattr(Config, "WORKSPACE_AUTHORITATIVE", False))


async def _persist_workspace_session_state(
    workspace_store: WorkspaceStore,
    session_id: str,
    session_state: SessionState,
) -> None:
    snapshot = await workspace_store.get_snapshot(session_id)
    await workspace_store.commit_transition(
        WorkspaceCommand(
            session_id=session_id,
            expected_epoch=snapshot.epoch,
            expected_revision=snapshot.revision,
            percept_id=session_state.utterance_id,
            focus_update=session_state.turn_id,
            pending_action={"legacy_session_state": session_state.to_dict()},
            command_source="session_state.dual_write",
        )
    )


def _session_state_from_workspace(
    snapshot: CognitiveWorkspaceSnapshot,
) -> SessionState | None:
    pending_action = snapshot.pending_action
    if not isinstance(pending_action, dict):
        return None
    data = pending_action.get("legacy_session_state")
    if not isinstance(data, dict):
        return None
    try:
        return SessionState(**data)
    except (TypeError, ValueError):
        return None
