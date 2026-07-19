"""
Findings from the second audit pass.

The two that matter are a camera endpoint anyone on the LAN could flip, and
per-turn blocking calls sitting on the event loop. The rest are small, but each
one is a case where the code claimed something it did not do.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.metrics import SubjectMetrics
from app.state.memory_store import _cached_ln, _ln

# --------------------------------------------------------------------------
# the camera endpoint is not a preference
# --------------------------------------------------------------------------


def test_vision_toggle_requires_the_same_auth_as_token_issuance():
    """A guest on the WiFi must not be able to point the camera at you.

    `require_lan_client` only restricts *where* a caller connects from, which
    with LAN_ONLY on is still any device on the network. `/token` and
    `/start-session` both add `require_session_auth`; `/vision/toggle` did not,
    while being the one endpoint that switches the vision source to `camera`.

    Asserted on the route's own dependencies rather than by driving a request,
    because the failure being guarded is *the dependency being absent* — a live
    request from loopback passes either way, which is exactly why this went
    unnoticed.
    """
    import main

    routes = {r.path: r for r in main.app.routes if hasattr(r, "dependencies")}

    def dep_names(path):
        return {
            d.dependency.__name__
            for d in routes[path].dependencies
            if getattr(d, "dependency", None)
        }

    assert "require_session_auth" in dep_names("/vision/toggle")
    # Pinned against a peer so the test states a rule rather than a constant:
    # whatever guards token issuance must also guard the camera.
    assert dep_names("/token") <= dep_names("/vision/toggle")


# --------------------------------------------------------------------------
# blocking work off the loop
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_persistence_does_not_block_the_event_loop():
    """`persist_state` ran a synchronous Redis write and a synchronous sqlite3
    write directly on the loop, from five call sites including the per-turn
    path.

    The loop stalled for a network round trip plus a disk write in the middle of
    a conversation — precisely when latency is felt. Asserted by checking the
    loop stays responsive while a deliberately slow backend is persisting.
    """
    from app.state.agent_state import StateService

    service = object.__new__(StateService)
    service.db_path = ":memory:"
    service.publish_cb = None
    service.redis_client = None

    ticks_when_write_finished = []

    def slow_write(_params):
        time.sleep(0.2)
        # Sampled at the moment the blocking work ends. Off the loop, the
        # heartbeat below has been running throughout and this is non-zero;
        # inline, the loop was pinned and the heartbeat has not ticked once.
        #
        # Asserting on the *final* tick count instead would pass either way:
        # `gather` waits for both coroutines regardless of whether they
        # overlapped, so it measures completion, not concurrency. That version
        # of this test survived a mutant that put the write back on the loop.
        ticks_when_write_finished.append(ticks)

    service._write_state_row = slow_write

    class _Model:
        inferred_valence = 0.0
        inferred_arousal = 0.5
        implied_goals = []
        known_concepts = []

    class _State:
        mood = energy = dominance = 0.5
        trust_benevolence = trust_competence = trust_integrity = trust = 0.5
        attachment = fatigue = last_user_interaction = 0.0
        interaction_count = 0
        baseline_valence = baseline_arousal = baseline_dominance = 0.0
        user_mental_model = _Model()

    service.current_state = _State()

    ticks = 0

    async def heartbeat():
        nonlocal ticks
        for _ in range(10):
            await asyncio.sleep(0.01)
            ticks += 1

    await asyncio.gather(service.persist_state("friend"), heartbeat())

    assert ticks_when_write_finished, "the sqlite writer never ran"
    assert ticks_when_write_finished[0] > 0, (
        "the event loop made no progress while the state write ran, so the "
        "write is back on the loop"
    )


@pytest.mark.asyncio
async def test_hydration_holds_the_same_lock_as_every_other_mutation():
    """`hydrate_state` wrote ~20 state fields without `_state_lock`.

    It is startup-only today, so nothing races it — but it was the single
    mutation path not holding the lock, and a later caller re-hydrating
    mid-session would interleave with the fire-and-forget System-2 appraisal
    and leave a state that is half restored and half appraised.
    """
    from app.state.agent_state import StateService

    service = object.__new__(StateService)
    service._state_lock = asyncio.Lock()
    observed = []

    async def fake_hydrate(_name):
        observed.append(service._state_lock.locked())

    service._hydrate_locked = fake_hydrate
    await service.hydrate_state("friend")

    assert observed == [True], "hydration ran without holding the state lock"


# --------------------------------------------------------------------------
# small things that lied
# --------------------------------------------------------------------------


def test_activation_log_is_deterministic_regardless_of_call_order():
    """The old cache keyed on the rounded value but stored the log of the *raw*
    one, so the result depended on which float reached it first.

    Two runs with identical inputs in a different order could produce different
    ACT-R activations, and therefore a different memory ranking, with nothing
    to indicate why.
    """
    _cached_ln.cache_clear()
    first = _ln(2.00001)
    _cached_ln.cache_clear()
    second = _ln(2.00049)

    # Both round to 2.0, so both must return log(2.0) exactly.
    assert first == second


def test_activation_log_cache_cannot_grow_without_bound():
    """It was a module-level dict that was never evicted (A6).

    Keys are memory ages, so a long-lived process with a wide spread of
    timestamps kept adding entries for the life of the process.
    """
    _cached_ln.cache_clear()
    for i in range(9000):
        _ln(1.0 + i * 0.01)

    assert _cached_ln.cache_info().currsize <= 4096


def test_metrics_join_gives_up_instead_of_hanging_forever():
    """`join()` spun on `while buffer or processing` with no exit.

    A dead worker thread presented as a frozen test run or a hung shutdown,
    which is a long way from where the fault actually was.
    """
    import threading

    metrics = SubjectMetrics(tracked_subjects={"chat.input"})
    metrics.shutdown()

    # A buffer that will never drain, because the worker is stopped.
    metrics._buffer = ["never drains"]
    metrics._is_processing = True

    result = []

    # Driven from a watchdog thread rather than called directly. If the bound
    # is ever removed, `join` spins forever -- called inline that hangs the
    # whole suite, and a test that pins CI is worse than one that fails. This
    # way the regression shows up as a failed assertion in about a second.
    worker = threading.Thread(
        target=lambda: result.append(metrics._queue.join(timeout=0.2)), daemon=True
    )
    worker.start()
    worker.join(timeout=3.0)

    assert not worker.is_alive(), "join() never returned; its timeout is gone"
    assert result == [False], "join() reported success on a buffer that never drained"


def test_a_failed_vision_call_is_logged_not_silently_empty(caplog, monkeypatch):
    """`except Exception: pass` then `return ""`.

    An empty description is indistinguishable from "the model saw nothing worth
    describing", so a vision backend that is down looked exactly like a quiet
    room — and the agent narrates that difference to the user as if it were
    real.
    """
    from app import config as config_module
    from app.llm.ollama_client import OllamaClient

    # `describe_image` short-circuits to a canned string under MOCK_LLM_TEXT,
    # which the suite enables globally. The real HTTP path is the one under
    # test. Patched on `config_instance`, since `Config.FOO` delegates there.
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)

    client = object.__new__(OllamaClient)
    client.model = "llava"

    failing = MagicMock()
    failing.post = AsyncMock(side_effect=RuntimeError("connection refused"))
    client._get_client = AsyncMock(return_value=failing)

    with caplog.at_level("WARNING"):
        result = asyncio.run(client.describe_image("b64", "what is here"))

    assert result == ""
    assert any("connection refused" in r.getMessage() for r in caplog.records), (
        "a failed vision call returned empty with nothing in the log"
    )
