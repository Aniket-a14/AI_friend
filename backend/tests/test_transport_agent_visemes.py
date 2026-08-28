"""
Phase 5.3: `audio.playback.visemes` has been published by voice-agent (four
call sites in its playback loop) since the wiring audit, and
`check_subject_wiring.py`'s whitelist has documented it as "consumed by the
frontend voice UI" the entire time -- but nothing ever delivered it there.
`transport_agent` is the only process with an open LiveKit room to deliver it
through, so this is that delivery: one NATS subscription, forwarded onto the
room's data channel.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.transport_agent import TransportAgent


class _FakeRoom:
    def __init__(self, local_participant=None):
        self.local_participant = local_participant


def _transport_agent(local_participant=None) -> TransportAgent:
    # Mirrors test_transport_agent_presence.py's own helper -- rtc.Room()'s
    # real constructor needs a running event loop, hence @pytest.mark.asyncio.
    with patch("app.agents.transport_agent.Config") as mock_config:
        mock_config.NATS_URL = "nats://127.0.0.1:4222"
        mock_config.LIVEKIT_URL = "ws://127.0.0.1:7880"
        mock_config.LIVEKIT_API_KEY = "k"
        mock_config.LIVEKIT_API_SECRET = "s"
        mock_config.SAMPLE_RATE = 16000
        mock_config.TRANSPORT_AUDIO_QUEUE_SIZE = 8
        agent = TransportAgent()
    agent.room = _FakeRoom(local_participant=local_participant)
    agent.publish = AsyncMock()
    return agent


@pytest.mark.asyncio
async def test_a_valid_viseme_is_forwarded_to_the_room_data_channel():
    participant = MagicMock()
    agent = _transport_agent(local_participant=participant)

    await agent._on_viseme({"target_level": 0.42, "viseme_id": "AA", "timestamp": 1.0})

    participant.publish_data.assert_called_once()
    (payload,), kwargs = participant.publish_data.call_args
    body = json.loads(payload)
    assert body["target_level"] == 0.42
    assert body["viseme_id"] == "AA"
    assert kwargs["reliable"] is False
    assert kwargs["topic"] == "visemes"


@pytest.mark.asyncio
async def test_a_malformed_payload_is_dropped_not_raised():
    """`target_level`/`viseme_id` are required fields on `PlaybackVisemes` --
    a payload missing them must not crash the subscription's callback (which
    would nak-and-redeliver the same poison message forever)."""
    participant = MagicMock()
    agent = _transport_agent(local_participant=participant)

    await agent._on_viseme({"unexpected": "shape"})

    participant.publish_data.assert_not_called()


@pytest.mark.asyncio
async def test_no_local_participant_does_not_raise():
    """Before the room's initial connect (or after a disconnect), there is
    no local_participant to publish through -- this must be a no-op, not an
    AttributeError from `None.publish_data`."""
    agent = _transport_agent(local_participant=None)

    await agent._on_viseme({"target_level": 0.1, "viseme_id": "sil", "timestamp": 1.0})
    # No exception raised is the assertion; nothing else to check on a no-op.


@pytest.mark.asyncio
async def test_a_publish_data_failure_is_swallowed():
    """A data-channel publish can fail (e.g. no subscriber yet) -- this is a
    best-effort animation signal, not audio itself, so a failure here must
    not take down the NATS subscription's callback."""
    participant = MagicMock()
    participant.publish_data.side_effect = RuntimeError("no data channel")
    agent = _transport_agent(local_participant=participant)

    await agent._on_viseme({"target_level": 0.9, "viseme_id": "O", "timestamp": 1.0})
    # No exception raised is the assertion.
