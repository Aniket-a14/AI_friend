"""Phase 1 causal slice (§7, §38): the unified `PerceptEnvelope` every
mesh-sourced modality event normalizes into before it enters cognition.

`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` §7 describes `PerceptEnvelope` as the
contract every perception adapter emits so the attention arbiter and workspace
authority never have to special-case a raw NATS payload shape. This module is
the Phase 1 slice of that: one Pydantic envelope plus one converter per
existing modality event (`chat.input`, `vision.description`,
`vision.facial_reflex`, `audio.stop`, `system.tick`,
`audio.playback.progress`). It does not yet change what those events cause --
that is later-phase attention/workspace work -- it only gives every event one
common, lossless shape so a later stage can be written once instead of six
times.

Each converter is deliberately narrow: it reads the wire dict a specific
handler in `agents/brain_agent.py` already receives (already validated against
its own `contracts.py` model there) and copies it into `raw_payload` verbatim,
so nothing about the original event is lost even though only a few fields are
promoted to typed top-level attributes.
"""

from __future__ import annotations

import math
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Modality = Literal["text", "audio", "vision", "reflex", "system", "playback"]


class PerceptEnvelope(BaseModel):
    """Normalized shape for any incoming sensor/mesh event, per
    `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` §7. `raw_payload` is the original
    wire dict, preserved for anything downstream that needs a field this
    envelope does not promote -- normalization must not be lossy."""

    percept_id: str
    modality: Modality
    source: str
    observed_at: float = Field(default_factory=time.time)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    text_content: str | None = None
    provenance: str = "nats"


def _new_percept_id(modality: str) -> str:
    return f"{modality}-{uuid.uuid4().hex}"


def _percept_id(modality: str, data: dict[str, Any]) -> str:
    """Deterministic when the source event carries its own identity
    (`utterance_id`/`event_id`/`id`/`turn_id`); random otherwise.

    JetStream redelivers an event whenever its handler is slow to ack (see
    CLAUDE.md's finding A1), and a `percept_id` that changed on every
    redelivery would make idempotency at any downstream consumer -- a
    workspace commit, outcome attribution -- impossible: the same real-world
    event would mint a second, distinct percept each time. Deriving the id
    from the wire event's own identity instead means redelivery of the exact
    same message produces the exact same `percept_id`.
    """
    source_id = (
        data.get("utterance_id")
        or data.get("event_id")
        or data.get("id")
        or data.get("turn_id")
    )
    if source_id:
        return f"percept:{modality}:{source_id}"
    return _new_percept_id(modality)


def _clamp_confidence(value: Any, default: float = 1.0) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(confidence):
        return default
    return max(0.0, min(1.0, confidence))


def from_chat_input(data: dict[str, Any]) -> PerceptEnvelope:
    """`chat.input` (STTAgent's final transcription -- `contracts.ChatInput`)."""
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return PerceptEnvelope(
        percept_id=_percept_id("text", data),
        modality="text",
        source=str(metadata.get("source") or "chat_input"),
        observed_at=time.time(),
        confidence=_clamp_confidence(metadata.get("confidence"), default=0.9),
        raw_payload=dict(data),
        text_content=data.get("text"),
    )


def from_vision_description(data: dict[str, Any]) -> PerceptEnvelope:
    """`vision.description` (VLM appraisal -- `contracts.VisionDescription`).

    Mirrors `BrainAgent._on_vision_description`'s own confidence rule for
    `last_visual_evidence`: a frame that cleared habituation (`is_novel`) is a
    fresh observation, a cached repeat is worth less -- one definition of that
    judgment, not two that can drift apart.
    """
    return PerceptEnvelope(
        percept_id=_new_percept_id("vision"),
        modality="vision",
        source=str(data.get("source") or "screen"),
        observed_at=float(data.get("timestamp", time.time())),
        confidence=1.0 if data.get("is_novel", True) else 0.5,
        raw_payload=dict(data),
        text_content=data.get("description"),
    )


def from_facial_reflex(data: dict[str, Any]) -> PerceptEnvelope:
    """`vision.facial_reflex` (CPU-only reflex channel --
    `contracts.FacialReflexEvent`). Already a scored expression onset, not raw
    pixels -- confidence stays at the model default (1.0): the reflex channel
    does not report a graded confidence of its own, only signed deltas."""
    return PerceptEnvelope(
        percept_id=_new_percept_id("reflex"),
        modality="reflex",
        source=str(data.get("source") or "camera"),
        observed_at=float(data.get("timestamp", time.time())),
        raw_payload=dict(data),
        text_content=data.get("evidence"),
    )


def from_audio_stop(data: dict[str, Any]) -> PerceptEnvelope:
    """`audio.stop` (confirmed or speculative interrupt -- `contracts.AudioStop`)."""
    return PerceptEnvelope(
        percept_id=_percept_id("audio", data),
        modality="audio",
        source=str(data.get("intent_type") or "VOICE_INTERRUPTION"),
        observed_at=time.time(),
        confidence=_clamp_confidence(data.get("confidence"), default=0.0),
        raw_payload=dict(data),
        text_content=data.get("perception_text") or data.get("command_text"),
    )


def from_system_tick(data: dict[str, Any]) -> PerceptEnvelope:
    """`system.tick` (heartbeat -- `SystemAgent._pulse_loop`'s `tick_data`)."""
    return PerceptEnvelope(
        percept_id=_new_percept_id("system"),
        modality="system",
        source=str(data.get("source") or "system_agent"),
        observed_at=float(data.get("timestamp", time.time())),
        raw_payload=dict(data),
    )


def from_playback_progress(data: dict[str, Any]) -> PerceptEnvelope:
    """`audio.playback.progress` (transport_agent's relayed PCM progress --
    `contracts.AudioPlaybackProgress`)."""
    return PerceptEnvelope(
        percept_id=_percept_id("playback", data),
        modality="playback",
        source="transport_agent",
        observed_at=time.time(),
        raw_payload=dict(data),
    )
