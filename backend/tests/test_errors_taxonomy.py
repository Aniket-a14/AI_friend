"""AgentError taxonomy (Phase 1D, §15 item 12). Covers the new base/leaf
classes in errors.py and the regression guard that every pre-existing
bespoke exception still satisfies its OLD `except <Base>` call sites after
gaining AgentError as an additional base."""

import pytest

from app.errors import (
    AgentError,
    PerceptionError,
    PolicyError,
    RealizationError,
    RetrievalError,
    StateConflictError,
    TransportError,
)

_LEAVES = [
    PerceptionError,
    RetrievalError,
    StateConflictError,
    PolicyError,
    RealizationError,
    TransportError,
]


@pytest.mark.parametrize("leaf", _LEAVES)
def test_every_leaf_is_an_agent_error(leaf):
    assert issubclass(leaf, AgentError)


@pytest.mark.parametrize("leaf", _LEAVES)
def test_a_leaf_instance_is_catchable_as_agent_error(leaf):
    with pytest.raises(AgentError):
        raise leaf("boom")


def test_agent_error_itself_is_a_plain_exception():
    """A caller with only `except Exception` (no taxonomy awareness) must
    keep working unchanged."""
    assert issubclass(AgentError, Exception)


# --------------------------------------------------------------------------
# Existing bespoke exceptions: gained AgentError, must not lose their old base
# --------------------------------------------------------------------------


def test_metacognitive_exception_is_now_also_an_agent_error():
    from app.cognitive.action import MetacognitiveException

    exc = MetacognitiveException("leaked scaffolding")
    assert isinstance(exc, AgentError)
    assert isinstance(exc, Exception)
    assert exc.reason == "leaked scaffolding"


def test_stream_reconciliation_error_keeps_its_runtime_error_base():
    """A pre-1D `except RuntimeError` call site around stream reconciliation
    must keep catching this -- losing RuntimeError as a base would silently
    stop it."""
    from app.nats_streams import StreamReconciliationError

    assert issubclass(StreamReconciliationError, RuntimeError)
    assert issubclass(StreamReconciliationError, AgentError)
    with pytest.raises(RuntimeError):
        raise StreamReconciliationError("no convergence")
    with pytest.raises(AgentError):
        raise StreamReconciliationError("no convergence")


def test_jetstream_publish_failed_keeps_its_runtime_error_base():
    from app.agents.base import JetStreamPublishFailed

    assert issubclass(JetStreamPublishFailed, RuntimeError)
    assert issubclass(JetStreamPublishFailed, AgentError)
    with pytest.raises(RuntimeError):
        raise JetStreamPublishFailed("publish failed")


def test_persona_compilation_error_is_now_also_an_agent_error():
    from app.persona.compiler import PersonaCompilationError

    assert issubclass(PersonaCompilationError, AgentError)
    assert issubclass(PersonaCompilationError, Exception)
    with pytest.raises(AgentError):
        raise PersonaCompilationError("could not compile")
