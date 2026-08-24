"""P3-5 / P4-11b / P3-8 / P4-8 -- BaseAgent's mesh-semantics fixes (Stage 6).

Each test drives BaseAgent with hand-built fakes for `self.js`/`self.nc`
rather than the shared conftest NATS simulator, because these tests need
control the simulator's MockMessage doesn't expose (`.term()`,
`.metadata.num_delivered`, capturing the exact `deliver_policy` a subscribe
call was made with).
"""

import asyncio

import pytest

from app.agents.base import BaseAgent, JetStreamPublishFailed
from app.utils.background_tasks import spawn_background


class _FakeMeta:
    def __init__(self, num_delivered: int):
        self.num_delivered = num_delivered


class _FakeMsg:
    """Stands in for a JetStream message with configurable delivery count
    and headers, and records which disposition method was called."""

    def __init__(self, subject: str, data: bytes, num_delivered: int = 1):
        self.subject = subject
        self.data = data
        self.headers = None
        self.metadata = _FakeMeta(num_delivered)
        self.disposition: str | None = None

    async def ack(self):
        self.disposition = "ack"

    async def nak(self):
        self.disposition = "nak"

    async def term(self):
        self.disposition = "term"


class _FakeJS:
    """Captures the `cb`/`deliver_policy` a `subscribe()` call was made
    with, so a test can invoke the real `_handler` closure directly."""

    def __init__(self):
        self.subscribed_cb = None
        self.subscribed_kwargs = None

    async def subscribe(self, subject, **kwargs):
        self.subscribed_cb = kwargs["cb"]
        self.subscribed_kwargs = kwargs

    async def publish(self, subject, payload, timeout=None, headers=None):
        raise RuntimeError("JetStream publish failed (simulated)")


def _make_agent(name="mesh_semantics_agent") -> BaseAgent:
    agent = BaseAgent(name=name, nats_url="nats://127.0.0.1:4222")
    agent.js = _FakeJS()
    agent.nc = object()  # not exercised unless the core-NATS fallback fires
    return agent


async def _get_handler(agent: BaseAgent, subject: str, callback):
    """Drive real subscribe() far enough to capture its `_handler` closure,
    without needing a real JetStream connection."""
    await agent.subscribe(subject, callback)
    return agent.js.subscribed_cb


class _AlwaysFailCallback:
    async def __call__(self, data):
        raise ValueError("handler always fails (simulated poison message)")


@pytest.mark.asyncio
async def test_media_subject_is_not_discarded_on_first_failure():
    """Before P3-5, any subject outside chat./state. hit `await msg.ack()`
    unconditionally the moment its handler raised -- a poison media message
    (audio.*, vision.*, memory.*, ...) was silently discarded on attempt one,
    with no redelivery and no dead-letter record. Real system behavior this
    protects: a single malformed audio frame should not vanish without a
    trace just because its subject isn't chat.* or state.*.
    """
    agent = _make_agent()
    handler = await _get_handler(agent, "audio.stream", _AlwaysFailCallback())

    msg = _FakeMsg("audio.stream", b'{"x": 1}', num_delivered=1)
    await handler(msg)

    assert msg.disposition == "nak", (
        "a media-tier subject's first failure must be NAK'd for redelivery, "
        "not ack'd-and-discarded"
    )


@pytest.mark.asyncio
async def test_media_subject_dead_letters_after_its_own_bound(monkeypatch):
    """The media/control tier gets a smaller redelivery budget than
    chat./state. (MESH_MEDIA_MAX_DELIVER, default 2) -- it should still
    dead-letter (term, not silently ack) once that bound is reached."""
    monkeypatch.setenv("MESH_MEDIA_MAX_DELIVER", "2")
    agent = _make_agent()
    handler = await _get_handler(agent, "audio.stream", _AlwaysFailCallback())

    msg = _FakeMsg("audio.stream", b'{"x": 1}', num_delivered=2)
    await handler(msg)

    assert msg.disposition == "term", (
        "a media-tier subject that has exhausted MESH_MEDIA_MAX_DELIVER "
        "must be explicitly dead-lettered (term), not silently ack'd"
    )


@pytest.mark.asyncio
async def test_media_tier_bound_is_smaller_than_conversational_tier(monkeypatch):
    """chat./state. keep the full MESH_MAX_DELIVER (default 5) budget;
    everything else uses the smaller MESH_MEDIA_MAX_DELIVER (default 2) --
    a poison media frame should not sit in redelivery as long as a poison
    chat message legitimately can."""
    monkeypatch.delenv("MESH_MAX_DELIVER", raising=False)
    monkeypatch.delenv("MESH_MEDIA_MAX_DELIVER", raising=False)
    agent = _make_agent()

    chat_handler = await _get_handler(agent, "chat.input", _AlwaysFailCallback())
    media_handler = await _get_handler(agent, "audio.stream", _AlwaysFailCallback())

    # At delivery count 3: still under chat's bound of 5 (NAK), but already
    # at/over media's bound of 2 (dead-lettered).
    chat_msg = _FakeMsg("chat.input", b"{}", num_delivered=3)
    await chat_handler(chat_msg)
    media_msg = _FakeMsg("audio.stream", b"{}", num_delivered=3)
    await media_handler(media_msg)

    assert chat_msg.disposition == "nak"
    assert media_msg.disposition == "term"


@pytest.mark.asyncio
async def test_publish_propagates_jetstream_failure_when_fallback_disallowed():
    """P3-5: `allow_core_fallback=False` must make a JetStream publish
    failure visible to the caller, not silently downgrade to best-effort
    core NATS and return as if nothing happened."""
    agent = _make_agent()

    with pytest.raises(JetStreamPublishFailed):
        await agent.publish(
            "chat.output", {"x": 1}, allow_core_fallback=False
        )


@pytest.mark.asyncio
async def test_binary_publish_propagates_jetstream_failure_when_fallback_disallowed():
    """The strict durable-delivery contract also applies to raw audio."""
    agent = _make_agent()

    with pytest.raises(JetStreamPublishFailed):
        await agent.publish(
            "audio.stream", b"pcm", allow_core_fallback=False
        )


@pytest.mark.asyncio
async def test_publish_default_still_falls_back_to_core_nats():
    """Regression guard: the default (allow_core_fallback=True, unset) must
    keep today's best-effort downgrade behavior -- publish() should not
    raise, and the core-NATS path should have been used."""
    agent = _make_agent()
    calls = []

    async def fake_core_publish(subject, payload):
        calls.append((subject, payload))

    agent.nc = type("FakeNC", (), {"publish": staticmethod(fake_core_publish)})()

    await agent.publish("chat.output", {"x": 1})  # must not raise

    assert len(calls) == 1
    assert calls[0][0] == "chat.output"


@pytest.mark.asyncio
async def test_cache_sync_autosubscribe_uses_deliver_policy_new():
    """P3-8: before this fix, `cache.sync` subscribed with the default
    deliver_policy='all', so every agent restart replayed the subject's
    entire retained history. An invalidation from an hour ago says nothing
    about whether a freshly-started agent's (not-yet-built) local cache is
    stale now.

    Uses conftest's full NATS simulator for connect()/_bootstrap_mesh() (the
    same pattern test_mesh.py's test_agent_connection uses) and intercepts
    only `subscribe()` itself, since that is where deliver_policy is passed.
    """
    agent = BaseAgent(name="brain_agent")  # must NOT start with "test_"
    calls = []

    async def recording_subscribe(subject, callback, **kwargs):
        calls.append((subject, kwargs))

    agent.subscribe = recording_subscribe

    await agent.connect()

    cache_sync_calls = [c for c in calls if c[0] == "cache.sync"]
    assert len(cache_sync_calls) == 1, "cache.sync auto-subscribe did not fire"
    assert cache_sync_calls[0][1].get("deliver_policy") == "new", (
        "cache.sync must subscribe with deliver_policy='new' so a restarted "
        "agent does not replay the subject's entire retained history"
    )


@pytest.mark.asyncio
async def test_spawn_retains_a_strong_reference_until_the_task_completes():
    """P4-8: `asyncio.create_task(...)` with its result discarded is a
    documented GC pitfall. `spawn()`/`spawn_background()` must keep a task
    referenced in `_background_tasks` for as long as it is running, and
    release it once it finishes -- neither leaking forever nor losing the
    reference early."""
    agent = _make_agent()
    started = asyncio.Event()
    finish = asyncio.Event()

    async def work():
        started.set()
        await finish.wait()

    task = agent.spawn(work())
    await started.wait()

    assert task in agent._background_tasks, (
        "a still-running spawned task must be retained, or it could be "
        "garbage-collected and silently cancelled mid-execution"
    )

    finish.set()
    await task

    assert task not in agent._background_tasks, (
        "a finished spawned task must be released, or _background_tasks "
        "leaks forever"
    )


def test_spawn_background_helper_is_reusable_outside_baseagent():
    """P4-8: the same helper is used by non-BaseAgent classes (MemoryStore,
    StateService, IdentityCoreStore). A bare set() plus the free function
    must work identically to BaseAgent.spawn()."""

    async def _run():
        tasks: set = set()
        done = asyncio.Event()

        async def work():
            await done.wait()

        t = spawn_background(tasks, work())
        assert t in tasks
        done.set()
        await t
        assert t not in tasks

    asyncio.run(_run())
