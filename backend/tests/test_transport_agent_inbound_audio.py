"""
#173: `_process_remote_audio` used to `await self.publish("audio.inbound",
...)` directly inside LiveKit's `AudioStream` iteration loop. If NATS
publishing stalls (network delay, JetStream backpressure), that await stalls
right there, delaying every subsequent frame the WebRTC stack hands over.
These tests cover the fix: capture is decoupled from publish via a bounded
queue and a dedicated worker.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.transport_agent import TransportAgent


def _make_agent(queue_size: int = 4) -> TransportAgent:
    with patch("app.agents.transport_agent.Config") as mock_config:
        mock_config.NATS_URL = "nats://127.0.0.1:4222"
        mock_config.LIVEKIT_URL = "ws://127.0.0.1:7880"
        mock_config.LIVEKIT_API_KEY = "k"
        mock_config.LIVEKIT_API_SECRET = "s"
        mock_config.SAMPLE_RATE = 16000
        mock_config.TRANSPORT_AUDIO_QUEUE_SIZE = queue_size
        agent = TransportAgent()
    return agent


def _fake_frame_event(sample_rate=16000, channels=1, data=b"\x00\x01"):
    frame = SimpleNamespace(data=data, sample_rate=sample_rate, num_channels=channels)
    return SimpleNamespace(frame=frame)


class _FakeAudioStream:
    """Minimal async-iterable standing in for `rtc.AudioStream(track)`."""

    def __init__(self, events):
        self._events = list(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


@pytest.mark.asyncio
async def test_capture_does_not_await_publish_directly():
    """A blocked/slow `publish` must not stall frame capture - only enqueue,
    never await the network call inline, is what makes this true."""
    agent = _make_agent()
    agent.publish = AsyncMock(side_effect=Exception("should never be called here"))

    events = [_fake_frame_event() for _ in range(3)]
    with patch("app.agents.transport_agent.rtc.AudioStream", return_value=_FakeAudioStream(events)):
        await agent._process_remote_audio(track=SimpleNamespace(sid="track-1"))

    agent.publish.assert_not_awaited()
    assert agent.inbound_audio_queue.qsize() == 3


@pytest.mark.asyncio
async def test_queue_overflow_drops_the_oldest_frame_not_the_newest():
    agent = _make_agent(queue_size=32)  # constructor floors below 32; override after
    agent.inbound_audio_queue = asyncio.Queue(maxsize=2)

    events = [
        _fake_frame_event(data=b"first"),
        _fake_frame_event(data=b"second"),
        _fake_frame_event(data=b"third"),
    ]
    with patch("app.agents.transport_agent.rtc.AudioStream", return_value=_FakeAudioStream(events)):
        await agent._process_remote_audio(track=SimpleNamespace(sid="track-1"))

    assert agent.inbound_audio_queue.qsize() == 2
    remaining = []
    while not agent.inbound_audio_queue.empty():
        data, _meta = agent.inbound_audio_queue.get_nowait()
        remaining.append(data)
    assert remaining == [b"second", b"third"]
    assert agent.dropped_inbound_audio_frames == 1


@pytest.mark.asyncio
async def test_inbound_worker_drains_the_queue_and_publishes():
    agent = _make_agent()
    agent.publish = AsyncMock()

    await agent.inbound_audio_queue.put((b"pcm-bytes", {"sample_rate": 16000}))

    worker = asyncio.create_task(agent._inbound_audio_worker())
    try:
        await asyncio.wait_for(agent.inbound_audio_queue.join(), timeout=2.0)
    finally:
        worker.cancel()
        try:
            await worker
        except Exception:
            pass

    agent.publish.assert_awaited_once_with(
        "audio.inbound", b"pcm-bytes", metadata={"sample_rate": 16000}
    )


@pytest.mark.asyncio
async def test_stop_cancels_the_inbound_worker_task():
    agent = _make_agent()
    agent.room = SimpleNamespace(disconnect=AsyncMock())
    agent.nc = None

    async def never_ending():
        await asyncio.Event().wait()

    task = asyncio.create_task(never_ending())
    agent.inbound_audio_worker_task = task
    agent.audio_worker_task = None

    await agent.stop()

    assert task.cancelled()
