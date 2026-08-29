"""
`app/api/voice.py` (roadmap Phase 5.1) mirrors `record_voice.py`'s
validate -> transcribe -> commit flow over HTTP. The two things worth real
scrutiny: `/commit` must actually run `validate_clip` before writing
anything (a silently-skipped check would defeat the whole point of Phase
2.3's "catch a bad recording before it becomes a permanent voice clone"),
and an unrecognized `variant` must be rejected rather than silently written
under a wrong `.env` key.
"""

import io
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from main import app
from scripts.audio.record_voice import SAMPLE_RATE

AUTH_HEADERS = {"x-backend-key": "test-key"}


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module.config_instance, "LAN_ONLY", False)
    monkeypatch.setattr(config_module.config_instance, "BACKEND_ACCESS_KEY", "test-key")


@pytest.fixture
def client():
    return TestClient(app)


def _tone_wav_bytes(
    duration_s: float, amplitude: float = 0.3, samplerate: int = SAMPLE_RATE
) -> bytes:
    t = np.linspace(0, duration_s, int(duration_s * samplerate), endpoint=False)
    audio = (amplitude * np.sin(2 * np.pi * 200.0 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, samplerate, format="WAV")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# /api/voice/validate
# ---------------------------------------------------------------------------


def test_validate_reports_no_problems_for_a_good_clip(client):
    wav = _tone_wav_bytes(8.0)
    with patch("app.api.voice.transcribe", return_value="hello there"):
        r = client.post(
            "/api/voice/validate",
            files={"file": ("clip.wav", wav, "audio/wav")},
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["problems"] == []
    assert body["transcript"] == "hello there"


def test_validate_reports_problems_for_a_too_short_clip_and_skips_transcription(client):
    wav = _tone_wav_bytes(1.0)
    with patch("app.api.voice.transcribe") as mock_transcribe:
        r = client.post(
            "/api/voice/validate",
            files={"file": ("clip.wav", wav, "audio/wav")},
            headers=AUTH_HEADERS,
        )
    assert r.status_code == 200
    body = r.json()
    assert any("short" in p or "only" in p for p in body["problems"])
    assert body["transcript"] is None
    mock_transcribe.assert_not_called()


def test_validate_rejects_a_non_audio_upload(client):
    r = client.post(
        "/api/voice/validate",
        files={"file": ("clip.wav", b"not a wav file", "audio/wav")},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400


def test_validate_rejects_an_unsupported_sample_rate(client):
    wav = _tone_wav_bytes(8.0, samplerate=16_000)
    r = client.post(
        "/api/voice/validate",
        files={"file": ("clip.wav", wav, "audio/wav")},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


def test_validate_rejects_an_oversized_upload_before_decoding(client, monkeypatch):
    import app.api.voice as voice_module

    monkeypatch.setattr(voice_module, "MAX_VOICE_UPLOAD_BYTES", 4)
    r = client.post(
        "/api/voice/validate",
        files={"file": ("clip.wav", b"12345", "audio/wav")},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# /api/voice/commit
# ---------------------------------------------------------------------------


def test_commit_rejects_an_unrecognized_variant(client):
    wav = _tone_wav_bytes(8.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", wav, "audio/wav")},
        data={"transcript": "hello", "variant": "FURIOUS"},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400


def test_commit_rejects_an_empty_transcript(client):
    wav = _tone_wav_bytes(8.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", wav, "audio/wav")},
        data={"transcript": "   "},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 400


def test_commit_rejects_an_unbounded_transcript(client):
    wav = _tone_wav_bytes(8.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", wav, "audio/wav")},
        data={"transcript": "x" * 10_001},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 422


def test_commit_refuses_to_save_a_clip_that_fails_validation(
    client, tmp_path, monkeypatch
):
    import app.api.voice as voice_module

    monkeypatch.setattr(voice_module, "VOICE_SAMPLES_DIR", tmp_path / "voice_samples")
    monkeypatch.setattr(voice_module, "ENV_PATH", tmp_path / ".env")

    too_short = _tone_wav_bytes(1.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", too_short, "audio/wav")},
        data={"transcript": "hello"},
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 422
    assert not (tmp_path / "voice_samples").exists()


def test_commit_saves_a_flawed_clip_when_forced(client, tmp_path, monkeypatch):
    import app.api.voice as voice_module

    voice_dir = tmp_path / "voice_samples"
    env_path = tmp_path / ".env"
    env_path.write_text("")
    monkeypatch.setattr(voice_module, "VOICE_SAMPLES_DIR", voice_dir)
    monkeypatch.setattr(voice_module, "ENV_PATH", env_path)

    too_short = _tone_wav_bytes(1.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", too_short, "audio/wav")},
        data={"transcript": "hello", "force": "true"},
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 200
    assert (voice_dir / "sample_en_gold.wav").exists()


def test_commit_writes_the_reference_clip_and_updates_env(
    client, tmp_path, monkeypatch
):
    import app.api.voice as voice_module

    voice_dir = tmp_path / "voice_samples"
    env_path = tmp_path / ".env"
    env_path.write_text("")
    monkeypatch.setattr(voice_module, "VOICE_SAMPLES_DIR", voice_dir)
    monkeypatch.setattr(voice_module, "ENV_PATH", env_path)

    wav = _tone_wav_bytes(8.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", wav, "audio/wav")},
        data={"transcript": "hello there"},
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 200
    body = r.json()
    assert body["env_audio_key"] == "REF_AUDIO_PATH"
    assert (voice_dir / "sample_en_gold.wav").exists()
    env_text = env_path.read_text()
    assert "REF_AUDIO_PATH" in env_text
    assert "REF_TEXT" in env_text


def test_commit_writes_an_emotional_variant_under_its_own_env_keys(
    client, tmp_path, monkeypatch
):
    import app.api.voice as voice_module

    voice_dir = tmp_path / "voice_samples"
    env_path = tmp_path / ".env"
    env_path.write_text("")
    monkeypatch.setattr(voice_module, "VOICE_SAMPLES_DIR", voice_dir)
    monkeypatch.setattr(voice_module, "ENV_PATH", env_path)

    wav = _tone_wav_bytes(8.0)
    r = client.post(
        "/api/voice/commit",
        files={"file": ("clip.wav", wav, "audio/wav")},
        data={"transcript": "so excited", "variant": "EXCITED"},
        headers=AUTH_HEADERS,
    )

    assert r.status_code == 200
    body = r.json()
    assert body["env_audio_key"] == "REF_AUDIO_PATH_EXCITED"
    assert body["env_text_key"] == "REF_TEXT_EXCITED"
    assert (voice_dir / "excited.wav").exists()
