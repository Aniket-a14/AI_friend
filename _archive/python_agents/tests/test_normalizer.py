from array import array

from app.voice.normalizer import AudioNormalizer


def _pcm_bytes(samples: list[int]) -> bytes:
    return array("h", samples).tobytes()


def test_process_returns_empty_for_empty_audio():
    normalizer = AudioNormalizer()
    assert normalizer.process(b"") == b""


def test_process_handles_odd_length_audio_bytes():
    normalizer = AudioNormalizer()
    result = normalizer.process(b"\x01")
    assert result == b""


def test_process_clips_and_updates_tail_rms(monkeypatch):
    normalizer = AudioNormalizer(target_peak=-1.0, sample_rate=10)
    # Force non-numpy path for deterministic branch coverage.
    monkeypatch.setattr("app.voice.normalizer.np", None)

    result = normalizer.process(_pcm_bytes([1000, -2000, 3000, -4000]))
    processed = array("h")
    processed.frombytes(result)

    assert len(processed) == 4
    assert normalizer.last_tail_rms is not None
    assert all(-32768 <= s <= 32767 for s in processed)
