"""Failure taxonomy (Phase 1D, §15 item 12).

Today, a caller that wants to catch "something this agent raised, as opposed
to a stray `ValueError` from a library" has no such type to catch -- each
subsystem invented its own bespoke exception (`MetacognitiveException`,
`StreamReconciliationError`, `JetStreamPublishFailed`,
`PersonaCompilationError`, ...) with no common ancestor narrower than
`Exception` itself. `AgentError` is that ancestor.

Existing exceptions gain `AgentError` as an *additional* base via multiple
inheritance rather than being redefined under it -- every existing
``except StreamReconciliationError`` or ``except RuntimeError`` call site
keeps working unchanged, while new code gets the option of
``except AgentError`` to catch any of them uniformly.
"""

from __future__ import annotations


class AgentError(Exception):
    """Base for every error the agent mesh itself raises deliberately, as
    opposed to an unexpected exception from a library or the runtime."""


class PerceptionError(AgentError):
    """Turning a raw event into a `CognitiveEvent` failed."""


class RetrievalError(AgentError):
    """Memory/graph/vector retrieval failed in a way the caller must react
    to, distinct from "found nothing" (which is a normal, empty result)."""


class StateConflictError(AgentError):
    """A state mutation was rejected because it conflicted with a newer or
    concurrent write -- see `AgentState`'s revision guard (Phase 2A)."""


class PolicyError(AgentError):
    """A persona/identity boundary check rejected a plan or a response."""


class RealizationError(AgentError):
    """Stage 8 (turning an approved decision into spoken/written text)
    failed in a way distinct from a raw LLM transport/network error."""


class TransportError(AgentError):
    """Delivering a turn's output to the user-facing transport (chat/audio
    session) failed. TTS-specific synthesis failures are a Rust concern
    (voice-agent's own error types) -- this covers the Python-side
    publish/session boundary only.
    """
