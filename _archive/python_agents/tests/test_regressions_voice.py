import asyncio
import re
from unittest.mock import AsyncMock, MagicMock
from app.config import Config
from archive.voice.agent import VoiceAgent, VoicePlaybackState

def test_voice_temporal_renderer_keeps_timing_tags_out_of_tts():
    agent = VoiceAgent()
    agent.playback_queue = asyncio.Queue()
    agent.sovits.synthesize_stream = MagicMock()

    async def _stream(**kwargs):
        yield b"pcm:" + kwargs["text"].encode()

    agent.sovits.synthesize_stream.side_effect = _stream

    item = {
        "turn_id": "turn-1",
        "generation": agent.system.generation,
        "metadata": {"turn_id": "turn-1"},
    }
    prosody = {"rate": 1.0, "pitch": 1.0, "volume": 1.0}

    asyncio.run(agent._enqueue_temporal_audio("hello<pause=20ms>there", item, prosody))

    calls = agent.sovits.synthesize_stream.call_args_list
    assert [call.kwargs["text"] for call in calls] == ["hello", "there"]
    queued = []
    while not agent.playback_queue.empty():
        queued.append(agent.playback_queue.get_nowait()["pcm"])

    assert queued[0] == b"pcm:hello"
    assert queued[1] == agent._silence_pcm(20)
    assert queued[2] == b"pcm:there"


def test_voice_done_flushes_residual_phrase_buffer():
    agent = VoiceAgent()
    agent.ingestion_queue = asyncio.PriorityQueue()
    agent._phrase_buffer = "small phrase"

    asyncio.run(agent._handle_input({"done": True, "turn_id": "turn-1"}))

    assert agent._phrase_buffer == ""
    assert agent.ingestion_queue.qsize() == 1


def test_voice_final_stop_fences_old_synthesis_generation():
    agent = VoiceAgent()
    agent.set_state = AsyncMock()

    stale_item = {"turn_id": "turn-1", "generation": agent.system.generation}
    assert agent._is_current_item(stale_item)

    asyncio.run(agent._on_audio_stop({"speculative": False, "turn_id": "turn-1"}))

    assert not agent._is_current_item(stale_item)
    assert agent._is_current_item({"turn_id": "turn-2", "generation": agent.system.generation})


def test_voice_resume_ignores_stale_utterance_id():
    agent = VoiceAgent()
    agent.set_state = AsyncMock()
    agent.system.state = VoicePlaybackState.SPECULATIVE_PAUSE
    agent.system.paused_utterance_id = "utt-current"

    asyncio.run(agent._on_audio_resume({"utterance_id": "utt-old"}))

    assert agent.system.state == VoicePlaybackState.SPECULATIVE_PAUSE
    agent.set_state.assert_not_awaited()


def test_voice_silence_uses_configured_sample_rate():
    agent = VoiceAgent()
    agent.sample_rate = 16000

    assert len(agent._silence_pcm(10)) == 320


def test_voice_warm_start_sets_warning_when_weights_unavailable():
    agent = VoiceAgent()
    agent.set_state = AsyncMock()
    agent.sovits.set_gpt_weights = AsyncMock(return_value=False)
    agent.sovits.set_sovits_weights = AsyncMock(return_value=False)

    original_gpt = Config.CUSTOM_GPT_PATH
    original_sovits = Config.CUSTOM_SOVITS_PATH
    original_retries = Config.VOICE_WEIGHT_LOAD_RETRIES

    Config.CUSTOM_GPT_PATH = "GPT_weights/missing.ckpt"
    Config.CUSTOM_SOVITS_PATH = "SoVITS_weights/missing.pth"
    Config.VOICE_WEIGHT_LOAD_RETRIES = 1

    try:
        ready = asyncio.run(agent._warm_start_identity())
    finally:
        Config.CUSTOM_GPT_PATH = original_gpt
        Config.CUSTOM_SOVITS_PATH = original_sovits
        Config.VOICE_WEIGHT_LOAD_RETRIES = original_retries

    assert ready is False
    agent.set_state.assert_awaited_once_with("warning_no_weights")


def test_voice_warm_start_succeeds_when_both_weights_load():
    agent = VoiceAgent()
    agent.set_state = AsyncMock()
    agent.sovits.set_gpt_weights = AsyncMock(return_value=True)
    agent.sovits.set_sovits_weights = AsyncMock(return_value=True)

    original_gpt = Config.CUSTOM_GPT_PATH
    original_sovits = Config.CUSTOM_SOVITS_PATH
    original_retries = Config.VOICE_WEIGHT_LOAD_RETRIES

    Config.CUSTOM_GPT_PATH = "GPT_weights/ok.ckpt"
    Config.CUSTOM_SOVITS_PATH = "SoVITS_weights/ok.pth"
    Config.VOICE_WEIGHT_LOAD_RETRIES = 1

    try:
        ready = asyncio.run(agent._warm_start_identity())
    finally:
        Config.CUSTOM_GPT_PATH = original_gpt
        Config.CUSTOM_SOVITS_PATH = original_sovits
        Config.VOICE_WEIGHT_LOAD_RETRIES = original_retries

    assert ready is True
    agent.set_state.assert_not_awaited()
