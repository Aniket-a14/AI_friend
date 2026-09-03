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
from typing import Any, Literal

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


async def persist_session_state(store: Any, session_state: SessionState) -> None:
    """Best-effort by construction: `WorkingMemoryStore` already swallows and
    logs its own Redis/SQLite failures, so nothing here needs its own
    try/except. `store=None` (a `CognitivePipeline` built without one, as
    most unit tests do) is a deliberate no-op, not an error -- session
    persistence is an enhancement, not a requirement for the pipeline to run.
    """
    if store is None:
        return
    await store.set_state_var("session_state", session_state.to_dict())


async def load_session_state(store: Any) -> SessionState | None:
    """The `WorkingMemoryStore` counterpart to `persist_session_state` --
    used by a process resuming mid-turn (e.g. a restart) rather than by the
    normal per-turn path, which always starts a fresh `SessionState`."""
    if store is None:
        return None
    data = await store.get_state_var("session_state")
    if not data:
        return None
    return SessionState(**data)
