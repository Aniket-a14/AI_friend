"""voice_agent never starts if backend/voice_samples/sample_en_gold.wav is
absent (roadmap Phase 1, "the blocker precisely"). This copy-in step is what
unblocks a fresh clone -- and must never clobber a voice someone already
recorded at that path."""

from pathlib import Path

from scripts.bootstrap.ensure_default_voice_sample import (
    DEFAULT_ASSETS,
    ensure_all_default_voice_assets,
    ensure_default_voice_sample,
)


def test_copies_bundled_clip_when_target_missing(tmp_path):
    source = tmp_path / "default_voice.wav"
    source.write_bytes(b"bundled-clip-bytes")
    target = tmp_path / "voice_samples" / "sample_en_gold.wav"

    copied = ensure_default_voice_sample(source=source, target=target)

    assert copied is True
    assert target.read_bytes() == b"bundled-clip-bytes"


def test_never_overwrites_an_existing_recording(tmp_path):
    """A user's own recorded clip at this path must survive re-running the
    bootstrap step, or every restart could silently replace their voice with
    the generic bundled default."""
    source = tmp_path / "default_voice.wav"
    source.write_bytes(b"bundled-clip-bytes")
    target = tmp_path / "voice_samples" / "sample_en_gold.wav"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"the-users-real-voice")

    copied = ensure_default_voice_sample(source=source, target=target)

    assert copied is False
    assert target.read_bytes() == b"the-users-real-voice"


def test_the_real_bundled_clip_exists_and_is_shipped():
    """Catches the asset itself going missing -- the copy step above can pass
    every test against a fake source and still fail on a real clone if
    backend/assets/voice/default_voice.wav was never committed."""
    repo_backend = Path(__file__).resolve().parents[1]
    clip = repo_backend / "assets" / "voice" / "default_voice.wav"
    assert clip.exists()
    assert clip.stat().st_size > 0


def test_ensure_all_default_voice_assets_copies_every_configured_asset(tmp_path):
    """load_vocalization_pcm's same-voice degradation (Phase 1.5) depends on
    voice_engine_unavailable.wav landing next to sample_en_gold.wav -- a
    regression here silently drops back to the plain reference-clip-only
    behavior with no error anywhere. Asserts hardcoded expected names, not
    names derived from DEFAULT_ASSETS itself, so shrinking that list can't
    pass this test by construction."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    voice_samples_dir = tmp_path / "voice_samples"
    for source_name, _ in DEFAULT_ASSETS:
        (assets_dir / source_name).write_bytes(source_name.encode())

    results = ensure_all_default_voice_assets(
        assets_dir=assets_dir, voice_samples_dir=voice_samples_dir
    )

    assert set(results) == {"sample_en_gold.wav", "voice_engine_unavailable.wav"}
    assert all(results.values())
    assert (voice_samples_dir / "sample_en_gold.wav").read_bytes() == b"default_voice.wav"
    assert (
        voice_samples_dir / "voice_engine_unavailable.wav"
    ).read_bytes() == b"voice_engine_unavailable.wav"


def test_the_real_vocalization_fallback_asset_exists_and_is_shipped():
    repo_backend = Path(__file__).resolve().parents[1]
    clip = repo_backend / "assets" / "voice" / "voice_engine_unavailable.wav"
    assert clip.exists()
    assert clip.stat().st_size > 0
