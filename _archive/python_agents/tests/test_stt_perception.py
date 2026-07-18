import pytest
import numpy as np
import sys
import types
from unittest.mock import AsyncMock, patch
from app.stt.agent import STTAgent
from app.contracts import Topics


@pytest.fixture
def stt_agent():
    fake_whisper_module = types.ModuleType("app.stt.whisper_service")
    fake_sensevoice_module = types.ModuleType("app.stt.sensevoice_service")

    class _FakeWhisperSTTService:
        def __init__(self, *args, **kwargs):
            pass

    class _FakeSenseVoiceSTTService:
        def __init__(self, *args, **kwargs):
            pass

    fake_whisper_module.WhisperSTTService = _FakeWhisperSTTService
    fake_sensevoice_module.SenseVoiceSTTService = _FakeSenseVoiceSTTService

    with patch.dict(
        sys.modules,
        {
            "app.stt.whisper_service": fake_whisper_module,
            "app.stt.sensevoice_service": fake_sensevoice_module,
        },
    ):
        agent = STTAgent()
        agent.publish = AsyncMock()
        agent.connect = AsyncMock()
        return agent


@pytest.mark.asyncio
async def test_stt_agent_extracts_paralinguistics_and_snr(stt_agent):
    # Mock perception data from SenseVoice
    # One silent chunk to establish noise floor, one with speech + laughter
    silent_audio = np.random.normal(0, 0.001, 1600).astype(np.float32)
    speech_audio = np.random.normal(0, 0.1, 1600).astype(np.float32)

    perception_data_silent = {"text": "", "events": [], "audio_np": silent_audio}

    perception_data_speech = {
        "text": "Hello!",
        "events": ["Laughter"],
        "audio_np": speech_audio,
    }

    # 1. Process silent chunk to calibrate noise floor
    await stt_agent._handle_perception_result(perception_data_silent, {})
    initial_noise_floor = stt_agent.noise_floor
    assert initial_noise_floor > 0

    # 2. Process speech chunk
    await stt_agent._handle_perception_result(perception_data_speech, {})

    # Verify publication
    assert stt_agent.publish.called
    args, kwargs = stt_agent.publish.call_args_list[-1]
    assert args[0] == Topics.AUDIO_PERCEPTION

    payload = args[1]
    assert "Laughter" in payload["paralinguistic_events"]
    assert payload["snr"] > 0  # Speech should be louder than noise floor
    assert payload["text"] == "Hello!"


@pytest.mark.asyncio
async def test_noise_floor_tracking_ema(stt_agent):
    # Baseline noise floor
    stt_agent.noise_floor = 0.1

    # Very quiet chunk
    quiet_audio = np.zeros(1600, dtype=np.float32)
    perception_data = {"text": "", "events": [], "audio_np": quiet_audio}

    await stt_agent._handle_perception_result(perception_data, {})

    # Noise floor should decrease (EMA: 0.95 * 0.1 + 0.05 * 0.0)
    assert stt_agent.noise_floor < 0.1
    assert stt_agent.noise_floor == pytest.approx(0.095, rel=1e-2)
