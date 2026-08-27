"""
Phase 3.1: `transport_agent` is the only component with direct visibility
into who is actually in the LiveKit room. These test the edge-triggered
`session.presence` publish this file's own account (`__init__`'s comment on
`self.room.on("participant_connected", ...)`) explains the need for --
`subconscious_agent` runs as a separate process and has no other way to know
whether a proactive thought has anyone to reach.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.transport_agent import TransportAgent
from app.contracts import Topics


class _FakeRoom:
    """A stand-in for `rtc.Room` exposing only what these handlers read --
    `remote_participants`, mutated directly to simulate join/leave order."""

    def __init__(self):
        self.remote_participants: dict[str, object] = {}


def _transport_agent() -> TransportAgent:
    # `rtc.Room()`'s own constructor needs a running event loop -- matches
    # every other test in this repo that builds a real TransportAgent (see
    # test_playback_progress.py), which is why this helper is only ever
    # called from an `@pytest.mark.asyncio` test.
    with patch("app.agents.transport_agent.Config") as mock_config:
        mock_config.NATS_URL = "nats://127.0.0.1:4222"
        mock_config.LIVEKIT_URL = "ws://127.0.0.1:7880"
        mock_config.LIVEKIT_API_KEY = "k"
        mock_config.LIVEKIT_API_SECRET = "s"
        mock_config.SAMPLE_RATE = 16000
        mock_config.TRANSPORT_AUDIO_QUEUE_SIZE = 8
        agent = TransportAgent()
    agent.room = _FakeRoom()
    agent.publish = AsyncMock()
    agent.spawn = MagicMock(side_effect=lambda coro: coro.close())
    return agent


@pytest.mark.asyncio
async def test_first_participant_joining_publishes_connected_true():
    agent = _transport_agent()
    agent.room.remote_participants["p1"] = object()  # LiveKit adds before emitting

    agent._on_participant_connected(participant=object())

    agent.publish.assert_called_once()
    topic, payload = agent.publish.call_args[0]
    assert topic == Topics.SESSION_PRESENCE
    assert payload["connected"] is True
    assert payload["participant_count"] == 1


@pytest.mark.asyncio
async def test_a_second_participant_joining_does_not_republish():
    """Only the 0 -> 1 edge matters -- subconscious_agent only needs to know
    "is anyone here at all", not track a headcount."""
    agent = _transport_agent()
    agent.room.remote_participants["p1"] = object()
    agent._on_participant_connected(participant=object())
    agent.publish.reset_mock()

    agent.room.remote_participants["p2"] = object()
    agent._on_participant_connected(participant=object())

    agent.publish.assert_not_called()


@pytest.mark.asyncio
async def test_last_participant_leaving_publishes_connected_false():
    agent = _transport_agent()
    # LiveKit has already removed the leaving participant by the time this
    # callback fires (see room.py's _on_participant_disconnected).
    agent.room.remote_participants.clear()

    agent._on_participant_disconnected(participant=object())

    agent.publish.assert_called_once()
    topic, payload = agent.publish.call_args[0]
    assert topic == Topics.SESSION_PRESENCE
    assert payload["connected"] is False
    assert payload["participant_count"] == 0


@pytest.mark.asyncio
async def test_one_of_several_participants_leaving_does_not_republish():
    agent = _transport_agent()
    agent.room.remote_participants["p1"] = object()  # p2 already left, p1 remains

    agent._on_participant_disconnected(participant=object())

    agent.publish.assert_not_called()
