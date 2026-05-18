import asyncio
import sys
from types import SimpleNamespace
from archive.stt.agent import STTAgent

def test_stt_rejects_non_pcm_payloads_and_downmixes_multichannel_pcm(monkeypatch):
    mock_vad = SimpleNamespace(
        create=lambda: object(),
        init=lambda _vad: None,
        set_mode=lambda _vad, _mode: None,
        process=lambda _vad, _sample_rate, _buf, _length: False,
        valid_rate_and_frame_length=lambda _rate, _frame_length: True,
    )
    monkeypatch.setitem(sys.modules, "_webrtcvad", mock_vad)

    agent = STTAgent.__new__(STTAgent)
    agent.target_sample_rate = 16000
    agent.whisper_queue = asyncio.Queue()
    agent.perception_queue = asyncio.Queue()
    agent.perception_buffer = []
    agent.perception_chunk_size = 999999

    enqueued = []

    def _capture_put(queue, item, label):
        enqueued.append((label, item))

    agent._put_latest = _capture_put

    asyncio.run(agent._on_audio_inbound({"audio": "legacy-json"}, metadata=None))
    assert enqueued == []

    stereo_samples = [1000, -1000, 3000, 1000]
    stereo_pcm = b"".join(
        int(sample).to_bytes(2, "little", signed=True) for sample in stereo_samples
    )
    asyncio.run(
        agent._on_audio_inbound(
            stereo_pcm,
            metadata={"sample_rate": 16000, "channels": 2},
        )
    )

    assert len(enqueued) == 1
    label, (pcm_16, _metadata) = enqueued[0]
    assert label == "whisper"
    assert len(pcm_16) == 4
