"""
audit/ROADMAP.md P1-3: a confirmed barge-in stops the agent from generating
*more* audio (voice-agent's abort_flag), but everything already queued in
transport_agent (buffer 3) and already handed to LiveKit's native send
buffer (buffer 4) used to keep playing regardless -- transport_agent never
even subscribed to audio.stop. These tests cover the fix: a confirmed stop
drains the local queue and rotates the published track, scoped to the turn
it names the same way voice-agent's own `stop_applies_to_active_turn` is.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.transport_agent import TransportAgent


def _make_agent(queue_size: int = 8) -> TransportAgent:
    with patch("app.agents.transport_agent.Config") as mock_config:
        mock_config.NATS_URL = "nats://127.0.0.1:4222"
        mock_config.LIVEKIT_URL = "ws://127.0.0.1:7880"
        mock_config.LIVEKIT_API_KEY = "k"
        mock_config.LIVEKIT_API_SECRET = "s"
        mock_config.SAMPLE_RATE = 16000
        mock_config.TRANSPORT_AUDIO_QUEUE_SIZE = queue_size
        agent = TransportAgent()
    return agent


def _wire_fake_room(agent: TransportAgent, publish_track=None) -> AsyncMock:
    """Replace `agent.room` with a stand-in whose `local_participant` records
    publish/unpublish calls without touching a real LiveKit connection."""
    unpublish_track = AsyncMock()

    async def _default_publish_track(track):
        return SimpleNamespace(sid=f"pub-{id(track)}")

    publish_track_mock = AsyncMock(side_effect=publish_track or _default_publish_track)
    agent.room = SimpleNamespace(
        local_participant=SimpleNamespace(
            publish_track=publish_track_mock,
            unpublish_track=unpublish_track,
        )
    )
    agent.audio_publication = SimpleNamespace(sid="pub-original")
    return unpublish_track


def _stop(speculative=False, turn_id=None):
    return {"interrupt": True, "speculative": speculative, "turn_id": turn_id}


@pytest.mark.asyncio
async def test_speculative_stop_does_not_flush_anything():
    """A duck has not cancelled anything yet -- nothing here to flush."""
    agent = _make_agent()
    unpublish_track = _wire_fake_room(agent)
    await agent.audio_queue.put((b"pcm", 16000, 1))

    await agent._on_audio_stop(_stop(speculative=True))

    assert agent.audio_queue.qsize() == 1
    unpublish_track.assert_not_awaited()
    assert agent.room.local_participant.publish_track.await_count == 0


@pytest.mark.asyncio
async def test_confirmed_stop_with_no_turn_id_drains_the_queue_and_rotates_the_track():
    agent = _make_agent()
    unpublish_track = _wire_fake_room(agent)
    for _ in range(3):
        await agent.audio_queue.put((b"pcm", 16000, 1))
    old_source = agent.audio_source
    old_track = agent.audio_track

    await agent._on_audio_stop(_stop(speculative=False, turn_id=None))

    assert agent.audio_queue.qsize() == 0
    agent.room.local_participant.publish_track.assert_awaited_once()
    unpublish_track.assert_awaited_once_with("pub-original")
    assert agent.audio_source is not old_source
    assert agent.audio_track is not old_track
    assert agent.audio_publication.sid != "pub-original"


@pytest.mark.asyncio
async def test_confirmed_stop_for_the_active_turn_flushes():
    agent = _make_agent()
    unpublish_track = _wire_fake_room(agent)
    await agent._on_nats_audio(b"pcm", metadata={"turn_id": "turn-1"})
    await agent.audio_queue.get()  # drain what _on_nats_audio itself queued
    agent.audio_queue.task_done()
    await agent.audio_queue.put((b"pcm", 16000, 1))

    await agent._on_audio_stop(_stop(speculative=False, turn_id="turn-1"))

    assert agent.audio_queue.qsize() == 0
    unpublish_track.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirmed_stop_for_a_stale_turn_is_ignored():
    """A stop delayed in the mesh for a turn that already finished must not
    flush audio queued for the turn playing now -- the exact race
    voice-agent's own `stop_applies_to_active_turn` was built to close."""
    agent = _make_agent()
    unpublish_track = _wire_fake_room(agent)
    await agent._on_nats_audio(b"pcm", metadata={"turn_id": "turn-2"})
    await agent.audio_queue.get()
    agent.audio_queue.task_done()
    await agent.audio_queue.put((b"pcm", 16000, 1))

    await agent._on_audio_stop(_stop(speculative=False, turn_id="turn-1"))

    assert agent.audio_queue.qsize() == 1
    unpublish_track.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_nats_audio_tracks_the_active_turn_from_metadata():
    agent = _make_agent()
    assert agent._active_turn_id is None

    await agent._on_nats_audio(b"pcm", metadata={"turn_id": "turn-9"})

    assert agent._active_turn_id == "turn-9"


@pytest.mark.asyncio
async def test_missing_turn_id_in_metadata_leaves_the_active_turn_unchanged():
    agent = _make_agent()
    agent._active_turn_id = "turn-9"

    await agent._on_nats_audio(b"pcm", metadata=None)
    await agent._on_nats_audio(b"pcm", metadata={})

    assert agent._active_turn_id == "turn-9"


@pytest.mark.asyncio
async def test_flush_publishes_the_new_track_before_unpublishing_the_old_one():
    """The overlap is deliberate (see `_flush_downstream_audio`'s docstring):
    it costs a brief renegotiation, not a gap in what the client receives."""
    agent = _make_agent()
    order = []

    async def _publish_track(track):
        order.append("publish")
        return SimpleNamespace(sid="pub-new")

    async def _unpublish_track(sid):
        order.append("unpublish")

    agent.room = SimpleNamespace(
        local_participant=SimpleNamespace(
            publish_track=AsyncMock(side_effect=_publish_track),
            unpublish_track=AsyncMock(side_effect=_unpublish_track),
        )
    )
    agent.audio_publication = SimpleNamespace(sid="pub-original")

    await agent._flush_downstream_audio()

    assert order == ["publish", "unpublish"]


@pytest.mark.asyncio
async def test_flush_before_any_track_was_ever_published_does_not_unpublish():
    """`audio_publication` is only set once `start()` runs; a flush before
    that (or in a test double) must not call unpublish_track(None)."""
    agent = _make_agent()
    agent.audio_publication = None
    unpublish_track = _wire_fake_room(agent)
    agent.audio_publication = None  # _wire_fake_room sets a fake one back

    await agent._flush_downstream_audio()

    unpublish_track.assert_not_awaited()
