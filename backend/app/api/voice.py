"""Voice enrollment over HTTP (roadmap Phase 5.1).

Mirrors `scripts/audio/record_voice.py`'s validate -> transcribe -> commit
flow, minus the microphone capture itself (a browser records; this only
receives the resulting clip). Accepts WAV uploads only, matching what the
CLI script already produces (and what a plain `<input type=file>` gives
without needing a server-side codec). A browser `MediaRecorder` upload
(webm/opus, and not necessarily at GPT-SoVITS's expected 22050 Hz) needs a
decode/resample step this endpoint does not yet have -- left for when the
Phase 5.2 web flow that would actually drive it exists.
"""

import asyncio
import tempfile
from pathlib import Path

import soundfile as sf
from dotenv import set_key
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from scripts.audio.record_voice import (
    EMOTIONAL_VARIANTS,
    SAMPLE_RATE,
    VOICE_SAMPLES_DIR,
    transcribe,
    validate_clip,
)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# A reference clip is short, so accepting arbitrarily large multipart bodies
# only creates an easy memory-exhaustion path for a LAN client. The limit is
# deliberately generous for WAV while bounding the request before decoding it.
MAX_VOICE_UPLOAD_BYTES = 10 * 1024 * 1024

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = REPO_ROOT / ".env"


class ValidateResponse(BaseModel):
    problems: list[str]
    transcript: str | None
    duration_s: float
    samplerate: int


async def _read_wav(upload: UploadFile) -> tuple:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        temp_path = Path(handle.name)
        total = 0
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_VOICE_UPLOAD_BYTES:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Uploaded clip exceeds the {MAX_VOICE_UPLOAD_BYTES // (1024 * 1024)} MiB limit",
                )
            handle.write(chunk)
    try:
        audio, samplerate = await asyncio.to_thread(
            sf.read, str(temp_path), dtype="float32", always_2d=False
        )
        if samplerate != SAMPLE_RATE:
            raise HTTPException(
                status_code=422,
                detail=f"Reference clips must use a {SAMPLE_RATE} Hz sample rate",
            )
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio, samplerate, temp_path
    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400, detail=f"Could not read the uploaded clip as WAV audio: {exc}"
        ) from exc


@router.post("/validate", response_model=ValidateResponse)
async def validate_voice_endpoint(file: UploadFile = File(...)):
    """Runs the same checks `record_voice.py::validate_clip` runs on a live
    recording, plus a best-effort transcription -- nothing is saved yet."""
    audio, samplerate, temp_path = await _read_wav(file)
    try:
        problems = await asyncio.to_thread(validate_clip, audio, samplerate)
        transcript = await asyncio.to_thread(transcribe, temp_path) if not problems else None
        duration_s = len(audio) / samplerate if samplerate else 0.0
        return ValidateResponse(
            problems=problems,
            transcript=transcript,
            duration_s=duration_s,
            samplerate=samplerate,
        )
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/commit")
async def commit_voice_endpoint(
    file: UploadFile = File(...),
    transcript: str = Form(..., max_length=10_000),
    variant: str | None = Form(default=None),
    force: bool = Form(default=False),
):
    """Saves an already-validated clip and points `.env` at it. `variant` is
    one of the four emotional suffixes (`CALM`/`WARM`/`CONCERNED`/`EXCITED`)
    to save an emotional reference instead of the main one; omit it for the
    primary reference clip. No overwrite guard here -- matches
    `record_voice.py`, which always replaces the previous reference on a
    fresh recording. `force` mirrors that same CLI's "[u]se it anyway"
    choice -- validation still runs and is still reported, it just stops
    being a hard rejection."""
    if variant is not None and variant not in EMOTIONAL_VARIANTS:
        raise HTTPException(
            status_code=400,
            detail=f"variant must be one of {sorted(EMOTIONAL_VARIANTS)} or omitted",
        )
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="transcript is empty")

    audio, samplerate, temp_path = await _read_wav(file)
    try:
        problems = await asyncio.to_thread(validate_clip, audio, samplerate)
        if problems and not force:
            raise HTTPException(
                status_code=422,
                detail={"message": "Clip failed validation; nothing was saved.", "problems": problems},
            )

        VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        filename = "sample_en_gold.wav" if variant is None else f"{variant.lower()}.wav"
        dest_path = VOICE_SAMPLES_DIR / filename
        await asyncio.to_thread(sf.write, dest_path, audio, samplerate)

        env_audio_key = "REF_AUDIO_PATH" if variant is None else f"REF_AUDIO_PATH_{variant}"
        env_text_key = "REF_TEXT" if variant is None else f"REF_TEXT_{variant}"
        await asyncio.to_thread(
            set_key, str(ENV_PATH), env_audio_key, f"output/{dest_path.name}"
        )
        await asyncio.to_thread(set_key, str(ENV_PATH), env_text_key, transcript.strip())

        return {
            "status": "saved",
            "path": f"voice_samples/{dest_path.name}",
            "env_audio_key": env_audio_key,
            "env_text_key": env_text_key,
        }
    finally:
        temp_path.unlink(missing_ok=True)
