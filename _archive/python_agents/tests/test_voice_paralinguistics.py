import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.voice.agent import VoiceAgent


@pytest.fixture
def voice_agent():
    agent = VoiceAgent()
    agent.publish = AsyncMock()
    agent.connect = AsyncMock()
    return agent


@pytest.mark.asyncio
async def test_voice_agent_ingests_paralinguistic_tags(voice_agent):
    # Mock ChatOutput with tags
    data = {
        "content": "Hello world.",
        "paralinguistic_tags": ["[laughs]"],
        "affect": {"emotion": "happy", "valence": 0.8, "arousal": 0.7},
    }

    with patch(
        "app.voice.agent.vad_to_prosody",
        return_value={"rate": 1.0, "pitch": 1.0, "volume": 1.0},
    ):
        await voice_agent._handle_input(data)

    # Check ingestion queue
    assert voice_agent.ingestion_queue.qsize() == 1
    priority, seq, item = await voice_agent.ingestion_queue.get()
    assert "[laughs]" in item["paralinguistic_tags"]


@pytest.mark.asyncio
async def test_rendering_paralinguistic_tag_calls_filler_service(voice_agent):
    # Mock filler service
    voice_agent.filler_service.get_specific_filler = MagicMock(
        return_value=b"fake_pcm_data"
    )
    voice_agent.playback_queue = AsyncMock()

    item = {
        "text": "Hello",
        "paralinguistic_tags": ["[laughs]"],
        "generation": 0,
        "prosody": {"rate": 1.0, "pitch": 1.0, "volume": 1.0},
    }

    with patch.object(voice_agent, "_is_current_item", return_value=True):
        await voice_agent._enqueue_temporal_audio("Hello", item, item["prosody"])

    # Verify filler service was queried for the tag
    voice_agent.filler_service.get_specific_filler.assert_any_call("[laughs]")
    # Verify playback queue received the filler pcm
    assert voice_agent.playback_queue.put.called
