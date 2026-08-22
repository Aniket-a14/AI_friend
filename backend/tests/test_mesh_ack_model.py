"""
P1-1: long work must not run inside a NATS callback.

`BaseAgent.subscribe` acks only after the callback returns (base.py), and
`SubconsciousAgent._on_system_tick` used to await an LLM call, reflection,
graph writes and ACT-R decay inline -- MEASURED ~16s idle and ~28s under
the two-model contention HARDWARE.md §5 measured -- against a 30s default
AckWait with UNLIMITED MaxDeliver. A pass that outran the deadline was
redelivered mid-flight and ran again: duplicate graph writes, and the
symptom that actually surfaced it, duplicate proactive utterances.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Config


def _make_agent(monkeypatch, consolidation_gate=None):
    """A SubconsciousAgent wired far enough to reach the consolidation
    dispatch, with every external dependency mocked."""
    from app.agents.subconscious_agent import SubconsciousAgent

    state_service = MagicMock()
    state_service.check_proactive_eligibility.return_value = False
    state_service.get_context_snapshot.return_value = {"emotion": "calm", "energy": 0.5}
    # Long silence, so the 300s consolidation gate opens.
    state_service.current_state.last_user_interaction = 0.0

    agent = SubconsciousAgent(state_service=state_service, graph_db=MagicMock())
    agent.publish = AsyncMock()
    agent.engine = MagicMock()
    agent.engine.evaluate_and_think = AsyncMock(return_value=None)

    async def _episodes(*args, **kwargs):
        if consolidation_gate is not None:
            await consolidation_gate.wait()
        return []

    agent.memory_store = MagicMock()
    agent.memory_store.get_recent_unconsolidated_episodes = AsyncMock(
        side_effect=_episodes
    )
    agent.reflection_service = MagicMock()
    return agent


@pytest.mark.asyncio
async def test_tick_callback_returns_before_consolidation_completes(monkeypatch):
    """The whole point of the change: the callback must hand control back --
    so BaseAgent.subscribe can ack -- while consolidation is still running.
    If this regresses, the ack is held for the length of the consolidation
    again and JetStream redelivers the tick mid-pass."""
    gate = asyncio.Event()
    agent = _make_agent(monkeypatch, consolidation_gate=gate)

    # Bounded on purpose: if consolidation were awaited inline again this
    # would block on the gate forever, and a hang is a worse test failure
    # than an assertion -- it tells you nothing and stalls the suite.
    await asyncio.wait_for(agent._on_system_tick({"timestamp": 1.0}), timeout=5)

    # Returned already, but the work has not finished.
    assert agent._consolidation_task is not None
    assert not agent._consolidation_task.done()

    gate.set()
    await agent._consolidation_task
    assert agent._consolidation_task.done()


@pytest.mark.asyncio
async def test_two_overlapping_ticks_run_one_consolidation(monkeypatch):
    """`_is_consolidating` is set synchronously in the callback, before
    create_task schedules anything. If it were set inside the dispatched
    coroutine instead, two ticks arriving back-to-back would both pass the
    guard before either task body ran -- the exact duplicate-work bug this
    item exists to remove."""
    gate = asyncio.Event()
    agent = _make_agent(monkeypatch, consolidation_gate=gate)

    await asyncio.wait_for(agent._on_system_tick({"timestamp": 1.0}), timeout=5)
    first_task = agent._consolidation_task

    await asyncio.wait_for(agent._on_system_tick({"timestamp": 2.0}), timeout=5)

    # The second tick must not have dispatched a second pass.
    assert agent._consolidation_task is first_task
    assert agent.memory_store.get_recent_unconsolidated_episodes.await_count == 0

    gate.set()
    await first_task
    assert agent.memory_store.get_recent_unconsolidated_episodes.await_count == 1


@pytest.mark.asyncio
async def test_dispatched_consolidation_task_is_retained(monkeypatch):
    """M1-A13: a bare asyncio.create_task is only weakly referenced by the
    loop and can be garbage-collected mid-flight. The task must be held on
    the agent, not dropped on the floor."""
    gate = asyncio.Event()
    agent = _make_agent(monkeypatch, consolidation_gate=gate)

    await asyncio.wait_for(agent._on_system_tick({"timestamp": 1.0}), timeout=5)

    assert isinstance(agent._consolidation_task, asyncio.Task)
    gate.set()
    await agent._consolidation_task


@pytest.mark.asyncio
async def test_consolidation_guard_clears_even_when_the_pass_raises(monkeypatch):
    """If the guard leaked on failure, one failed pass would wedge
    consolidation off permanently -- silently, since the tick keeps
    arriving and keeps returning early."""
    agent = _make_agent(monkeypatch)
    agent.memory_store.get_recent_unconsolidated_episodes = AsyncMock(
        side_effect=RuntimeError("graph down")
    )

    await agent._on_system_tick({"timestamp": 1.0})
    await agent._consolidation_task

    assert agent._is_consolidating is False


@pytest.mark.asyncio
async def test_tick_subscription_states_its_ack_deadline_and_redelivery_bound():
    """Previously implicit: a 30s server-default ack_wait with UNLIMITED
    max_deliver. Unlimited redelivery is what turned one slow pass into an
    endless loop of duplicate proactive utterances."""
    from app.agents.subconscious_agent import SubconsciousAgent
    from app.contracts import Topics

    agent = SubconsciousAgent(state_service=MagicMock(), graph_db=MagicMock())
    agent.connect = AsyncMock()
    agent.subscribe = AsyncMock()
    agent.graph_db.initialize = AsyncMock()
    agent.state_service.hydrate_state = AsyncMock()
    agent.memory_store = MagicMock()
    agent.reflection_service = MagicMock()
    agent._continuous_monologue_loop = AsyncMock()

    await agent.start()

    tick_calls = [
        c for c in agent.subscribe.await_args_list if c.args[0] == Topics.SYSTEM_TICK
    ]
    assert len(tick_calls) == 1
    kwargs = tick_calls[0].kwargs
    assert kwargs["ack_wait"] == Config.MESH_CONTROL_ACK_WAIT_S
    assert kwargs["max_deliver"] == Config.MESH_CONTROL_MAX_DELIVER


# --------------------------------------------------------------------------
# Durable-consumer drift. Without this, sizing ack_wait is a no-op on every
# deployment that has run before -- correct in review, correct on a fresh
# mesh, silently inert in production.
# --------------------------------------------------------------------------


def _agent_with_js(existing_ack_wait, existing_max_deliver):
    from app.agents.base import BaseAgent

    agent = object.__new__(BaseAgent)
    agent.name = "subconscious"

    stored = MagicMock()
    stored.ack_wait = existing_ack_wait
    stored.max_deliver = existing_max_deliver
    info = MagicMock()
    info.config = stored

    jsm = MagicMock()
    jsm.consumer_info = AsyncMock(return_value=info)
    jsm.delete_consumer = AsyncMock()

    js = MagicMock()
    js.find_stream_name_by_subject = AsyncMock(return_value="AI_MESSAGES")
    js._jsm = jsm
    agent.js = js
    return agent, jsm


@pytest.mark.asyncio
async def test_drifted_durable_is_deleted_so_the_new_ack_wait_takes_effect():
    """JetStreamContext.subscribe does `config = consumer_info.config` when a
    durable already exists -- it DISCARDS the ConsumerConfig passed in and
    adopts the stored one (nats-py marks the spot `TODO: Detect
    configuration drift`). So without an explicit delete, the new deadline
    applies on a fresh mesh and in every test, and nowhere that matters,
    while still logging a successful subscribe."""
    agent, jsm = _agent_with_js(existing_ack_wait=30.0, existing_max_deliver=None)

    await agent._reconcile_consumer_config(
        subject="system.tick",
        durable="subconscious_system_tick",
        ack_wait=30.0,
        max_deliver=3,
    )

    jsm.delete_consumer.assert_awaited_once_with(
        "AI_MESSAGES", "subconscious_system_tick"
    )


@pytest.mark.asyncio
async def test_matching_durable_is_left_alone():
    """Deleting a durable discards its delivery cursor, so this must fire
    only on genuine drift -- not on every agent restart."""
    agent, jsm = _agent_with_js(existing_ack_wait=30.0, existing_max_deliver=3)

    await agent._reconcile_consumer_config(
        subject="system.tick",
        durable="subconscious_system_tick",
        ack_wait=30.0,
        max_deliver=3,
    )

    jsm.delete_consumer.assert_not_awaited()


@pytest.mark.asyncio
async def test_absent_durable_is_not_an_error():
    """The normal first-run path: no consumer exists yet, so there is
    nothing to reconcile and subscribe creates it correctly anyway."""
    from app.agents.base import BaseAgent

    agent = object.__new__(BaseAgent)
    agent.name = "subconscious"
    js = MagicMock()
    js.find_stream_name_by_subject = AsyncMock(return_value="AI_MESSAGES")
    js._jsm = MagicMock()
    js._jsm.consumer_info = AsyncMock(side_effect=Exception("not found"))
    js._jsm.delete_consumer = AsyncMock()
    agent.js = js

    await agent._reconcile_consumer_config(
        subject="system.tick",
        durable="subconscious_system_tick",
        ack_wait=30.0,
        max_deliver=3,
    )

    js._jsm.delete_consumer.assert_not_awaited()
