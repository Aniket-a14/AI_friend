"""
`scripts/audio/record_voice.py` -- the parts with real logic to protect.

The interactive recording/menu loop isn't tested here, matching how this
repo already treats other `input()`-driven scripts (`show_persona.py`,
`reset_persona.py` have no dedicated test file either). `validate_clip` and
`transcribe`'s binary-lookup/subprocess handling are pure enough, and
consequential enough -- a validator that always passes would make the whole
"catch a bad recording" feature in Phase 2.3 a no-op -- to deserve real tests.
"""

import subprocess
from unittest.mock import MagicMock, patch

import numpy as np

from scripts.audio.record_voice import (
    SAMPLE_RATE,
    _find_stt_agent_binary,
    transcribe,
    validate_clip,
)


def _tone(duration_s: float, amplitude: float = 0.3, freq: float = 200.0, samplerate: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * samplerate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


# ---------------------------------------------------------------------------
# validate_clip
# ---------------------------------------------------------------------------


def test_a_reasonable_clip_passes_with_no_problems():
    audio = _tone(8.0)
    assert validate_clip(audio, SAMPLE_RATE) == []


def test_empty_recording_is_rejected():
    assert validate_clip(np.array([], dtype=np.float32), SAMPLE_RATE) == ["recording is empty"]


def test_too_short_clip_is_flagged():
    audio = _tone(1.0)
    problems = validate_clip(audio, SAMPLE_RATE, min_duration_s=3.0)
    assert any("only" in p and "long" in p for p in problems)


def test_too_long_clip_is_flagged():
    audio = _tone(40.0)
    problems = validate_clip(audio, SAMPLE_RATE, max_duration_s=30.0)
    assert any("maximum" in p for p in problems)


def test_silent_clip_is_flagged_for_both_peak_amplitude_and_silence():
    audio = np.zeros(int(8.0 * SAMPLE_RATE), dtype=np.float32)
    problems = validate_clip(audio, SAMPLE_RATE)
    assert any("peak amplitude" in p for p in problems)
    assert any("silence" in p for p in problems)


def test_clipped_clip_is_flagged():
    # A mutation that dropped the clipping check would let a recording that
    # is basically a square wave -- unusable for cloning -- through clean.
    audio = np.full(int(4.0 * SAMPLE_RATE), 0.999, dtype=np.float32)
    problems = validate_clip(audio, SAMPLE_RATE)
    assert any("clipped" in p for p in problems)


def test_mostly_silent_clip_with_a_brief_word_is_flagged():
    silence = np.zeros(int(7.0 * SAMPLE_RATE), dtype=np.float32)
    word = _tone(1.0, amplitude=0.3)
    audio = np.concatenate([silence, word])
    problems = validate_clip(audio, SAMPLE_RATE, max_silence_ratio=0.6)
    assert any("silence" in p for p in problems)


# ---------------------------------------------------------------------------
# _find_stt_agent_binary / transcribe
# ---------------------------------------------------------------------------


def test_find_stt_agent_binary_prefers_release_over_debug(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    release = tmp_path / "target" / "release"
    debug = tmp_path / "target" / "debug"
    release.mkdir(parents=True)
    debug.mkdir(parents=True)
    (release / "stt-agent").touch()
    (debug / "stt-agent").touch()

    found = _find_stt_agent_binary()
    assert found == release / "stt-agent"


def test_find_stt_agent_binary_falls_back_to_debug(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    debug = tmp_path / "target" / "debug"
    debug.mkdir(parents=True)
    (debug / "stt-agent").touch()

    assert _find_stt_agent_binary() == debug / "stt-agent"


def test_find_stt_agent_binary_returns_none_when_neither_exists(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    assert _find_stt_agent_binary() is None


def test_transcribe_returns_none_when_binary_is_missing(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    assert transcribe(tmp_path / "clip.wav") is None


def test_transcribe_returns_stripped_stdout_on_success(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    (tmp_path / "target" / "release").mkdir(parents=True)
    (tmp_path / "target" / "release" / "stt-agent").touch()

    fake_result = MagicMock(returncode=0, stdout="hello there\n", stderr="")
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        transcript = transcribe(tmp_path / "clip.wav")

    assert transcript == "hello there"
    mock_run.assert_called_once()


def test_transcribe_returns_none_on_nonzero_exit(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    (tmp_path / "target" / "release").mkdir(parents=True)
    (tmp_path / "target" / "release" / "stt-agent").touch()

    fake_result = MagicMock(returncode=1, stdout="", stderr="boom")
    with patch("subprocess.run", return_value=fake_result):
        assert transcribe(tmp_path / "clip.wav") is None


def test_transcribe_returns_none_on_timeout(tmp_path, monkeypatch):
    from scripts.audio import record_voice

    monkeypatch.setattr(record_voice, "BACKEND_ROOT", tmp_path)
    (tmp_path / "target" / "release").mkdir(parents=True)
    (tmp_path / "target" / "release" / "stt-agent").touch()

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="stt-agent", timeout=300)):
        assert transcribe(tmp_path / "clip.wav") is None
