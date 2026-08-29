"""Copies bundled default voice assets into backend/voice_samples/ if they are
not already there (roadmap Phase 1.1/1.5) -- both gpt-sovits and voice_agent
only see that directory via host bind mounts, never the built image, so this
has to run on the host before compose starts, not inside runtime_bootstrap.py."""

import shutil
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = BACKEND_ROOT / "assets" / "voice"
VOICE_SAMPLES_DIR = BACKEND_ROOT / "voice_samples"

DEFAULT_SOURCE = ASSETS_DIR / "default_voice.wav"
TARGET = VOICE_SAMPLES_DIR / "sample_en_gold.wav"

# (bundled asset filename, filename the running system looks for). The
# reference clip is renamed on copy (sample_en_gold.wav is the name
# REF_AUDIO_PATH/sovits_healthcheck.sh default to); the vocalization fallback
# keeps its name since load_vocalization_pcm looks it up by that name directly.
DEFAULT_ASSETS = [
    ("default_voice.wav", "sample_en_gold.wav"),
    ("voice_engine_unavailable.wav", "voice_engine_unavailable.wav"),
]


def ensure_default_voice_sample(
    source: Path = DEFAULT_SOURCE, target: Path = TARGET
) -> bool:
    """Copies `source` to `target` unless `target` already exists.

    Never overwrites -- a user who already recorded their own clip at this
    path must not silently lose it. Returns whether a copy happened.
    """
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def ensure_all_default_voice_assets(
    assets_dir: Path = ASSETS_DIR, voice_samples_dir: Path = VOICE_SAMPLES_DIR
) -> dict[str, bool]:
    """Runs `ensure_default_voice_sample` for every bundled default asset.

    Returns {target filename: whether it was copied}.
    """
    return {
        target_name: ensure_default_voice_sample(
            source=assets_dir / source_name, target=voice_samples_dir / target_name
        )
        for source_name, target_name in DEFAULT_ASSETS
    }


if __name__ == "__main__":
    for target_name, copied in ensure_all_default_voice_assets().items():
        target_path = VOICE_SAMPLES_DIR / target_name
        if copied:
            print(f"[voice] Copied bundled default asset to {target_path}")
        else:
            print(f"[voice] {target_path} already exists, leaving it untouched")
