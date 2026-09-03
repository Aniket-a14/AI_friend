"""Phase 2A / §18 Experiment 3: the state-conflict experiment.

`brain_agent` and `subconscious_agent` each own an independent `StateService`
over the same logical agent, connected only through NATS's `state.broadcast`
subject -- there is no shared process memory, so `AgentState.revision`/
`writer_id` (agent_state.py:127-137) and the compare-and-swap guard in
`apply_external_state` are the only thing standing between the two processes
and one silently overwriting the other's fresher appraisal with a stale one.

`test_organism_state_revision.py` already covers the CAS guard as a pure
function, calling `apply_external_state` with hand-built dicts. This file is
the thing the plan calls "§18 Experiment 3": the same guard exercised over
the actual mesh transport (mocked JetStream, real `BaseAgent.publish`/
`subscribe` wire path, real `orjson`/`json` (de)serialization), with two
independent `StateService` instances standing in for the two real OS
processes -- turning the design document's "hazard, not observed race" into
a reproducible, asserted-on result.

Two things this deliberately does NOT do:
- It does not claim `revision` is a global logical clock. It is a per-writer
  local counter (`persist_state` increments its own instance's field), so
  two independent writers racing to publish their first update both produce
  revision=1 -- an equal-revision-different-writer collision by construction,
  not a bug. `test_concurrent_first_writes_collide_on_revision_and_are_logged`
  reproduces exactly that.
- It does not claim restart safety. `revision` is explicitly not persisted
  across restarts (agent_state.py:131-135) precisely because a monotonic
  counter that *was* persisted would need cross-process coordination to
  reset correctly. The tradeoff: a restarted writer's revision counter goes
  back to zero, so its first few post-restart broadcasts carry a revision
  number a peer that saw its pre-restart history has already exceeded, and
  the CAS guard -- correctly, by its own rules -- rejects them as stale.
  `test_restart_resets_revision_so_peer_rejects_fresher_post_restart_state`
  makes that hazard concrete instead of leaving it as a design note.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import BaseAgent
from app.state.agent_state import StateService
from tests.conftest import MockNATSConnection

from .harness.nats_mesh_fixture import NatsMeshHarness

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_nats():
    """One shared in-memory NATS connection -- both simulated processes
    publish/subscribe on this, standing in for the real mesh between two
    separate OS processes."""
    return MockNATSConnection()


@pytest.fixture
def harness(mock_nats):
    h = NatsMeshHarness(mock_nats)
    h.start_recording()
    yield h
    h.stop_recording()


def _wire_agent(name: str, mock_nats: MockNATSConnection) -> BaseAgent:
    """A `BaseAgent` bound to the shared mock mesh without going through
    `connect()` -- `connect()` calls the real `nats.connect()`, which the
    test-suite-wide mock (conftest.py) satisfies by handing back a *new*
    `MockNATSConnection` per call, which would give brain and subconscious
    two disconnected mocks instead of one shared mesh. Setting `.nc`/`.js`
    directly is exactly what `connect()` itself does after the network
    round trip (see `BaseAgent.connect`), so `publish`/`subscribe` behave
    identically to production from here on.
    """
    agent = BaseAgent(name=name)
    agent.nc = mock_nats
    agent.js = mock_nats.jetstream()
    return agent


def _make_state_service(
    mock_graph_db, harness: NatsMeshHarness, writer_id: str
) -> StateService:
    """Publishing goes through `harness.inject` rather than `agent.publish`:
    the mock `MockJetStream.publish` (conftest.py) doesn't accept the
    `timeout=` kwarg `BaseAgent.publish` passes on the real client, so a
    real `agent.publish` call against this mock fails closed (falls through
    to a core-NATS path the mock also doesn't implement) and is silently
    swallowed by `publish`'s own broad `except Exception`. `harness.inject`
    calls `js.publish(subject, payload)` with no extra kwargs, which the
    mock does support, and is also how every other mesh integration test in
    this suite injects events -- consistent with the plan's "existing local
    NATS integration harness pattern."
    """
    service = StateService(
        graph_store=mock_graph_db,
        db_path=":memory:",
        writer_id=writer_id,
        publish_cb=harness.inject,
    )
    service.redis_client = None
    return service


async def _flush_background_publishes(service: StateService) -> None:
    """`persist_state` fires its `state.broadcast` publish via
    `spawn_background` (fire-and-forget) rather than awaiting it inline, so
    a caller that wants the broadcast to have actually landed on any
    subscriber before asserting has to wait for that task explicitly."""
    pending = list(service._background_tasks)
    if pending:
        await asyncio.gather(*pending)
    # `MockJetStream.publish` awaits `connection.drain()` itself, but give
    # the loop one more tick so subscriber-side `apply_external_state`
    # coroutines scheduled by `_trigger` have a chance to complete too.
    await asyncio.sleep(0)


@pytest.fixture
async def brain_and_subconscious(mock_graph_db, mock_nats, harness):
    """Two `StateService` instances, each behind its own `BaseAgent`,
    subscribed to each other's `state.broadcast` -- the symmetric wiring
    the experiment needs to observe a collision. (Production wiring is
    one-directional today -- only `subconscious_agent` subscribes to
    `state.broadcast`; `brain_agent` does not read it back. Symmetric
    wiring here is a deliberate widening to actually exercise the
    equal-revision-different-writer path the CAS guard already handles,
    not a claim about today's production topology.)
    """
    brain_agent = _wire_agent("brain_agent", mock_nats)
    subconscious_agent = _wire_agent("subconscious_agent", mock_nats)

    brain_state = _make_state_service(mock_graph_db, harness, "brain_agent")
    subconscious_state = _make_state_service(
        mock_graph_db, harness, "subconscious_agent"
    )

    await brain_agent.subscribe(
        "state.broadcast",
        brain_state.apply_external_state,
        durable="brain_agent_state_broadcast",
    )
    await subconscious_agent.subscribe(
        "state.broadcast",
        subconscious_state.apply_external_state,
        durable="subconscious_agent_state_broadcast",
    )

    return brain_state, subconscious_state


# ── Experiments ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_propagates_over_the_real_mesh_transport(
    brain_and_subconscious,
):
    """Sanity baseline before the conflict scenarios: a single write from
    one side reaches the other, through the actual JSON-over-JetStream wire
    path (not a direct dict call), with matching revision/writer_id."""
    brain_state, subconscious_state = brain_and_subconscious

    brain_state.current_state.mood = 0.42
    await brain_state.persist_state()
    await _flush_background_publishes(brain_state)

    assert subconscious_state.current_state.mood == 0.42
    assert subconscious_state.current_state.revision == 1
    assert subconscious_state.current_state.writer_id == "brain_agent"


@pytest.mark.asyncio
async def test_concurrent_first_writes_collide_on_revision_and_are_logged(
    brain_and_subconscious, caplog
):
    """§18 Experiment 3's central case: `revision` is a per-writer local
    counter, not a shared logical clock, so brain and subconscious writing
    concurrently for the first time both mint revision=1. Neither broadcast
    is "stale" by the CAS guard's own rule (`incoming < current`), so both
    apply -- last delivery wins -- but the collision is logged distinctly
    rather than silently resolved, exactly per `apply_external_state`'s
    "Equal-revision write conflict" branch.
    """
    brain_state, subconscious_state = brain_and_subconscious

    brain_state.current_state.mood = 0.6
    subconscious_state.current_state.mood = -0.3

    with caplog.at_level("WARNING"):
        # "Concurrent" here means neither side has yet observed the other's
        # revision=1 broadcast when it commits its own -- modeled by
        # persisting both before either's broadcast is flushed to the mesh.
        await brain_state.persist_state()
        await subconscious_state.persist_state()
        await _flush_background_publishes(brain_state)
        await _flush_background_publishes(subconscious_state)

    assert brain_state.current_state.revision == 1
    assert subconscious_state.current_state.revision == 1

    # Both broadcasts were revision=1 from different writers -- applied
    # (not rejected as stale), and each side ends up holding whichever
    # arrived last on ITS subscription, not necessarily the same value.
    # The property under test is not "who wins" (arbitrary, by design --
    # see apply_external_state's comment) but that the ambiguity is visible.
    conflict_logs = [
        r for r in caplog.records if "Equal-revision write conflict" in r.message
    ]
    assert len(conflict_logs) >= 1


@pytest.mark.asyncio
async def test_stale_broadcast_reordered_after_a_newer_one_is_rejected(
    brain_and_subconscious,
):
    """The ordering guarantee the CAS guard actually provides: once a peer
    has observed revision N from a writer, a revision < N broadcast from
    that same writer arriving later (out-of-order mesh delivery has no
    ordering guarantee across subjects -- see `apply_external_state`'s
    docstring) must not overwrite the newer state."""
    brain_state, subconscious_state = brain_and_subconscious

    brain_state.current_state.mood = 0.1
    await brain_state.persist_state()  # revision=1
    await _flush_background_publishes(brain_state)

    brain_state.current_state.mood = 0.9
    await brain_state.persist_state()  # revision=2
    await _flush_background_publishes(brain_state)

    assert subconscious_state.current_state.mood == 0.9
    assert subconscious_state.current_state.revision == 2

    # A delayed redelivery of the revision=1 broadcast (reordering under
    # JetStream redelivery/at-least-once semantics) arrives last.
    await subconscious_state.apply_external_state(
        {"revision": 1, "writer_id": "brain_agent", "mood": 0.1}
    )

    assert subconscious_state.current_state.mood == 0.9
    assert subconscious_state.current_state.revision == 2


@pytest.mark.asyncio
async def test_restart_resets_revision_so_peer_rejects_fresher_post_restart_state(
    mock_graph_db, mock_nats, harness
):
    """Restart-order variation: `revision` is explicitly NOT persisted
    across restarts (agent_state.py:131-135), so a writer that crashes and
    restarts begins its revision history over at 0 -- even though the state
    it now holds is the real, current one. A peer that had already seen
    that writer's pre-restart high-water mark rejects the writer's first
    post-restart broadcasts as stale, by the CAS guard's own correct logic,
    because the guard has no way to distinguish "an old message reordered
    in transit" from "a legitimately restarted process starting a new
    revision history." This is the accepted tradeoff the field's own
    comment names, made concrete rather than left as a design note.
    """
    subconscious_agent = _wire_agent("subconscious_agent", mock_nats)
    subconscious_state = _make_state_service(
        mock_graph_db, harness, "subconscious_agent"
    )
    await subconscious_agent.subscribe(
        "state.broadcast",
        subconscious_state.apply_external_state,
        durable="subconscious_agent_state_broadcast",
    )

    # Pre-restart brain_agent process reaches revision 5 before subconscious
    # last hears from it.
    pre_restart_brain = _make_state_service(mock_graph_db, harness, "brain_agent")
    for i in range(5):
        pre_restart_brain.current_state.mood = 0.1 * i
        await pre_restart_brain.persist_state()
        await _flush_background_publishes(pre_restart_brain)

    assert subconscious_state.current_state.revision == 5
    assert subconscious_state.current_state.mood == pytest.approx(0.4)

    # brain_agent crashes and restarts: a brand-new StateService, same
    # writer_id, revision starts back at 0. It picks up real, current
    # affect (e.g. rehydrated from Redis/SQLite) that happens to be
    # "happier" than anything subconscious has seen yet.
    restarted_brain = _make_state_service(mock_graph_db, harness, "brain_agent")
    restarted_brain.current_state.mood = 0.99
    await restarted_brain.persist_state()  # revision=1, writer_id=brain_agent
    await _flush_background_publishes(restarted_brain)

    # Rejected as stale (1 < 5) even though it is the genuinely fresher
    # real-world state -- the documented hazard, not a bug this phase fixes.
    assert subconscious_state.current_state.revision == 5
    assert subconscious_state.current_state.mood == pytest.approx(0.4)
    assert subconscious_state.current_state.mood != 0.99
