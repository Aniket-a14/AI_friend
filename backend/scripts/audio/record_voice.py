"""
Voice enrollment -- Phase 2.3 of the community roadmap.

    cd backend
    ../.venv/bin/python -m scripts.audio.record_voice          # macOS/Linux
    ../.venv/Scripts/python.exe -m scripts.audio.record_voice  # Windows

Records a short reference clip for voice cloning, transcribes it automatically
(no hand-typed `REF_TEXT` to get out of sync with the clip), checks the
recording is actually usable, and writes `REF_AUDIO_PATH`/`REF_TEXT` into
`.env` -- replacing the bundled placeholder from Phase 1.1. Optionally
continues on to the four emotional variants (`REF_*_{CALM,WARM,CONCERNED,
EXCITED}`), reachable since Phase 1.4 wired them through Compose.

Transcription shells out to the `stt-agent` Rust binary's offline
`--transcribe-file` mode (built as part of this same phase) rather than
requiring the whole NATS mesh to be running just to record a voice sample.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

try:
    import sounddevice as sd
except (ImportError, OSError) as exc:
    # The enrollment CLI needs a microphone, but the API and its tests only
    # need the validator/transcriber. Importing this module must therefore be
    # safe on headless hosts where PortAudio is not installed.
    sd = None
    _SOUNDDEVICE_IMPORT_ERROR = exc
else:
    _SOUNDDEVICE_IMPORT_ERROR = None

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import set_key

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
VOICE_SAMPLES_DIR = BACKEND_ROOT / "voice_samples"
ENV_PATH = REPO_ROOT / ".env"
SAMPLE_RATE = 22_050  # GPT-SoVITS's expected input rate.

# The four emotional variants Phase 1.4 wired through Compose. Key: the .env
# suffix; value: a short spoken-line prompt so the recording actually carries
# that emotion rather than being read flat.
EMOTIONAL_VARIANTS = {
    "CALM": "Read a sentence slowly, in a calm, relaxed voice.",
    "WARM": "Say something warm and affectionate, like greeting a close friend.",
    "CONCERNED": "Say something in a concerned, worried tone, like checking on someone.",
    "EXCITED": "Say something excitedly, like sharing good news.",
}

CONSENT_NOTICE = """
This records your voice to clone it. Please only use your own voice, or a
voice you have the right to use -- someone else's likeness deserves their
consent, not just yours.
"""


def record_audio(duration: float, samplerate: int = SAMPLE_RATE) -> np.ndarray:
    """Record `duration` seconds from the default microphone. Returns mono
    float32 samples in [-1, 1]."""
    if sd is None:
        raise RuntimeError(
            "Microphone recording requires sounddevice and a system PortAudio library"
        ) from _SOUNDDEVICE_IMPORT_ERROR

    print(f"Recording for {duration:.0f}s -- speak naturally after the countdown.")
    for n in (3, 2, 1):
        print(f"{n}...")
        time.sleep(1)
    print("GO")

    audio = sd.rec(
        int(duration * samplerate), samplerate=samplerate, channels=1, dtype="float32"
    )
    sd.wait()
    print("Recording complete.")
    return audio.reshape(-1)


def validate_clip(
    audio: np.ndarray,
    samplerate: int,
    *,
    min_duration_s: float = 3.0,
    max_duration_s: float = 30.0,
    max_clipping_ratio: float = 0.001,
    max_silence_ratio: float = 0.6,
    min_peak_amplitude: float = 0.02,
) -> list[str]:
    """Cheap, fast checks a bad recording fails often enough to be worth
    catching before it becomes a permanent voice clone: too short/long, mostly
    silence, clipped, or too quiet to have registered speech at all.

    Deliberately NOT checking for a single speaker -- that needs real speaker
    diarization, which this script does not have, and a check that always
    passes is worse than no check: it would look like verification while
    verifying nothing.
    """
    problems: list[str] = []
    if audio.size == 0:
        return ["recording is empty"]

    duration_s = len(audio) / samplerate
    if duration_s < min_duration_s:
        problems.append(f"only {duration_s:.1f}s long (minimum {min_duration_s:.0f}s)")
    if duration_s > max_duration_s:
        problems.append(
            f"{duration_s:.1f}s long (maximum {max_duration_s:.0f}s for a reference clip)"
        )

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < min_peak_amplitude:
        problems.append(
            f"peak amplitude {peak:.4f} is very low -- check your microphone level"
        )

    clipping_ratio = float(np.mean(np.abs(audio) >= 0.99))
    if clipping_ratio > max_clipping_ratio:
        problems.append(
            f"{clipping_ratio * 100:.2f}% of samples are clipped (too loud)"
        )

    window = max(1, int(0.02 * samplerate))  # 20ms windows
    trimmed = audio[: len(audio) - (len(audio) % window)] if window else audio
    if trimmed.size:
        windows = trimmed.reshape(-1, window)
        rms = np.sqrt(np.mean(windows.astype(np.float64) ** 2, axis=1))
        silence_ratio = float(np.mean(rms < 0.01))
        if silence_ratio > max_silence_ratio:
            problems.append(
                f"{silence_ratio * 100:.0f}% of the clip is silence -- speak "
                "throughout the recording"
            )

    return problems


def _find_stt_agent_binary() -> Path | None:
    for candidate in (
        BACKEND_ROOT / "target" / "release" / "stt-agent",
        BACKEND_ROOT / "target" / "debug" / "stt-agent",
    ):
        if candidate.exists():
            return candidate
    return None


def transcribe(wav_path: Path) -> str | None:
    """Runs the stt-agent binary's offline mode. Returns the transcript, or
    `None` if the binary isn't built or the call failed -- the caller falls
    back to asking the person to type it themselves rather than blocking
    enrollment on a Rust build."""
    binary = _find_stt_agent_binary()
    if binary is None:
        print(
            "stt-agent binary not found (looked in target/release and "
            "target/debug). Build it with:\n"
            "    cargo build --release --package stt-agent\n"
            "Falling back to manual transcription for now."
        )
        return None

    # Local (non-Docker) default for the offline transcriber's model cache.
    # The Rust binary's own default (`/app/models/whisper`) assumes the
    # container layout and is not writable when this runs directly on a
    # host; `ensure_model` creates this directory itself if it's missing.
    env = dict(os.environ)
    env.setdefault("STT_MODEL_DIR", str(BACKEND_ROOT / "models" / "whisper"))

    print("Transcribing (first run downloads the Whisper model, ~75MB)...")
    try:
        result = subprocess.run(
            [str(binary), "--transcribe-file", str(wav_path)],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("Transcription timed out.")
        return None

    if result.returncode != 0:
        print(f"Transcription failed:\n{result.stderr[-2000:]}")
        return None

    transcript = result.stdout.strip()
    return transcript or None


def _record_and_validate(duration: float, prompt: str | None = None) -> np.ndarray:
    """Records, validates, and lets the person re-record on request. Returns
    the accepted clip (a person may accept a flawed clip deliberately)."""
    if prompt:
        print(f"\n{prompt}")
    while True:
        audio = record_audio(duration)
        problems = validate_clip(audio, SAMPLE_RATE)
        if problems:
            print("This clip may not be great for voice cloning:")
            for p in problems:
                print(f"  - {p}")
            choice = (
                input("[r]e-record, [u]se it anyway, [s]kip this clip: ")
                .strip()
                .lower()
            )
            if choice == "r":
                continue
            if choice == "s":
                return np.array([], dtype=np.float32)
        return audio


def _get_transcript(wav_path: Path) -> str:
    transcript = transcribe(wav_path)
    if transcript:
        print(f'Transcript: "{transcript}"')
        choice = input("[a]ccept, [e]dit, [r]etype: ").strip().lower()
        if choice == "e" or choice == "r":
            edited = input("Transcript: ").strip()
            return edited or transcript
        return transcript
    return input("Type exactly what was said in the clip: ").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration", type=float, default=8.0, help="Seconds to record (default 8)."
    )
    parser.add_argument(
        "--skip-emotional",
        action="store_true",
        help="Skip the four emotional variant clips.",
    )
    args = parser.parse_args()

    print(CONSENT_NOTICE)
    if input("Continue? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 1

    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    reference_audio = _record_and_validate(
        args.duration,
        "Recording your reference clip -- speak naturally, as if talking to a friend.",
    )
    if reference_audio.size == 0:
        print("No usable reference clip recorded; nothing was saved.")
        return 1

    reference_path = VOICE_SAMPLES_DIR / "sample_en_gold.wav"
    sf.write(reference_path, reference_audio, SAMPLE_RATE)
    reference_text = _get_transcript(reference_path)

    set_key(str(ENV_PATH), "REF_AUDIO_PATH", f"output/{reference_path.name}")
    set_key(str(ENV_PATH), "REF_TEXT", reference_text)
    print(f"Saved {reference_path} and updated REF_AUDIO_PATH/REF_TEXT in .env.")

    if args.skip_emotional:
        return 0

    if input("\nRecord the four emotional variants too? [y/N] ").strip().lower() != "y":
        return 0

    for suffix, cue in EMOTIONAL_VARIANTS.items():
        audio = _record_and_validate(args.duration, cue)
        if audio.size == 0:
            print(f"Skipped {suffix}.")
            continue
        path = VOICE_SAMPLES_DIR / f"{suffix.lower()}.wav"
        sf.write(path, audio, SAMPLE_RATE)
        text = _get_transcript(path)
        set_key(str(ENV_PATH), f"REF_AUDIO_PATH_{suffix}", f"output/{path.name}")
        set_key(str(ENV_PATH), f"REF_TEXT_{suffix}", text)
        print(f"Saved {path} and updated REF_AUDIO_PATH_{suffix}/REF_TEXT_{suffix}.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
