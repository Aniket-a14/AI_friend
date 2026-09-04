"""Capability-aware compilers from ``SpeechIntent`` to voice payloads.

The compilers deliberately return descriptions rather than contact a vendor.
That keeps provider integration at the adapter boundary and makes every lossy
translation inspectable before a renderer is allowed to synthesize audio.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.cognitive.speech_intent import (
    SpeechAffect,
    SpeechDelivery,
    SpeechIntent,
    SpeechTimelineMarker,
    TimelineMarkerKind,
    build_speech_intent,
)


class VoiceCapability(BaseModel):
    """Explicit declaration of the controls a voice provider can honor."""

    supports_pitch: bool
    supports_rate: bool
    supports_timeline_pause: bool
    supports_timeline_emphasis: bool
    supports_affect_modulation: bool
    supports_ssml: bool
    supports_epistemic_modulation: bool = False
    supports_relationship_modulation: bool = False
    supported_styles: list[str] = Field(default_factory=list)


class CompiledVoicePayload(BaseModel):
    """Provider-ready, but transport-independent, synthesis request."""

    compiler_id: str
    intent_id: str
    audio_text: str
    synthesis_parameters: dict[str, Any]
    ssml_or_tags: str | None = None


class IntentLossRecord(BaseModel):
    """Audit record for dimensions a compiler dropped or substituted."""

    compiler_id: str
    intent_id: str
    dropped_dimensions: list[str] = Field(default_factory=list)
    substituted_dimensions: dict[str, Any] = Field(default_factory=dict)
    fidelity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""


@runtime_checkable
class VoiceCompilerProtocol(Protocol):
    """Structural interface all voice providers must satisfy."""

    compiler_id: str
    capabilities: VoiceCapability

    def compile(self, intent: SpeechIntent) -> tuple[CompiledVoicePayload, IntentLossRecord]:
        """Compile an intent and disclose every unsupported dimension."""


def _loss_record(
    compiler_id: str,
    intent_id: str,
    dropped: list[str],
    substituted: dict[str, Any],
) -> IntentLossRecord:
    """Build deterministic telemetry with a bounded, comparable fidelity score."""
    loss_count = len(dropped) + len(substituted)
    fidelity = 1.0 if loss_count == 0 else 1.0 / (loss_count + 1)
    reasons: list[str] = []
    if dropped:
        reasons.append("dropped " + ", ".join(dropped))
    if substituted:
        reasons.append("substituted " + ", ".join(sorted(substituted)))
    return IntentLossRecord(
        compiler_id=compiler_id,
        intent_id=intent_id,
        dropped_dimensions=dropped,
        substituted_dimensions=substituted,
        fidelity_score=fidelity,
        reason="; ".join(reasons),
    )


def _markers_of_kind(
    intent: SpeechIntent,
    kind: TimelineMarkerKind,
) -> list[SpeechTimelineMarker]:
    return [marker for marker in intent.timeline if marker.kind == kind]


def _unrenderable_social_dimensions(
    intent: SpeechIntent,
    capabilities: VoiceCapability,
) -> list[str]:
    """Return non-default intent dimensions that this compiler cannot render."""
    dropped: list[str] = []
    if not capabilities.supports_epistemic_modulation:
        if intent.epistemics.confidence != 1.0:
            dropped.append("epistemics.confidence")
        if intent.epistemics.uncertainty != 0.0:
            dropped.append("epistemics.uncertainty")
        if intent.epistemics.hedge_required:
            dropped.append("epistemics.hedge_required")
    if not capabilities.supports_relationship_modulation:
        if intent.relationship.stance != "WARM":
            dropped.append("relationship.stance")
        if intent.relationship.familiarity != 0.5:
            dropped.append("relationship.familiarity")
        if intent.relationship.register != "CASUAL":
            dropped.append("relationship.register")
    return dropped


def _unrenderable_affect_dimensions(
    intent: SpeechIntent,
    capabilities: VoiceCapability,
) -> list[str]:
    """Return intentional affect modulation a compiler cannot represent."""
    if capabilities.supports_affect_modulation:
        return []

    dropped: list[str] = []
    if intent.affect.valence != 0.0:
        dropped.append("affect.valence")
    if intent.affect.arousal != 0.0:
        dropped.append("affect.arousal")
    if intent.affect.dominance != 0.0:
        dropped.append("affect.dominance")
    if intent.affect.intensity != 0.5:
        dropped.append("affect.intensity")
    if intent.affect.optional_label_hint:
        dropped.append("affect.optional_label_hint")
    return dropped


class ElevenLabsVoiceCompiler:
    """Cloud-oriented compiler for style, affect, rate, and pause controls."""

    compiler_id = "elevenlabs"
    capabilities = VoiceCapability(
        supports_pitch=False,
        supports_rate=True,
        supports_timeline_pause=True,
        supports_timeline_emphasis=False,
        supports_affect_modulation=True,
        supports_ssml=False,
        supported_styles=["neutral", "warm", "calm", "excited", "conversational"],
    )

    def compile(self, intent: SpeechIntent) -> tuple[CompiledVoicePayload, IntentLossRecord]:
        """Produce cloud controls without leaking provider markup into cognition."""
        dropped = _unrenderable_social_dimensions(intent, self.capabilities)
        substituted: dict[str, Any] = {}
        style = intent.delivery.style
        if style and style not in self.capabilities.supported_styles:
            substituted["delivery.style"] = {"requested": style, "applied": "neutral"}
            style = "neutral"
        if intent.delivery.relative_pitch != 1.0:
            dropped.append("delivery.relative_pitch")
        if _markers_of_kind(intent, TimelineMarkerKind.EMPHASIS):
            dropped.append("timeline.emphasis")
        if _markers_of_kind(intent, TimelineMarkerKind.VOCALIZATION):
            dropped.append("timeline.vocalization")

        parameters: dict[str, Any] = {
            "rate": intent.delivery.relative_rate,
            "urgency": intent.delivery.urgency,
            "energy": intent.delivery.relative_energy,
            "style": style,
            "affect": intent.affect.model_dump(),
            "pauses": [
                {"duration_s": marker.strength_or_duration, "reason": marker.reason}
                for marker in _markers_of_kind(intent, TimelineMarkerKind.PAUSE)
            ],
        }
        payload = CompiledVoicePayload(
            compiler_id=self.compiler_id,
            intent_id=intent.intent_id,
            audio_text=intent.semantic_text,
            synthesis_parameters=parameters,
        )
        return payload, _loss_record(self.compiler_id, intent.intent_id, dropped, substituted)


class GPTSoVITSVoiceCompiler:
    """Local compiler for pitch/rate controls and SSML-compatible tags."""

    compiler_id = "gpt-sovits"
    capabilities = VoiceCapability(
        supports_pitch=True,
        supports_rate=True,
        supports_timeline_pause=True,
        supports_timeline_emphasis=True,
        supports_affect_modulation=False,
        supports_ssml=True,
    )

    def compile(self, intent: SpeechIntent) -> tuple[CompiledVoicePayload, IntentLossRecord]:
        """Emit local SSML tags and disclose cloud-only style loss."""
        dropped = _unrenderable_social_dimensions(intent, self.capabilities)
        if intent.delivery.style:
            dropped.append("delivery.style")
        dropped.extend(_unrenderable_affect_dimensions(intent, self.capabilities))

        tags = _gpt_sovits_tags(intent)
        payload = CompiledVoicePayload(
            compiler_id=self.compiler_id,
            intent_id=intent.intent_id,
            audio_text=intent.semantic_text,
            synthesis_parameters={
                "rate": intent.delivery.relative_rate,
                "pitch": intent.delivery.relative_pitch,
                "energy": intent.delivery.relative_energy,
                "urgency": intent.delivery.urgency,
            },
            ssml_or_tags=tags,
        )
        return payload, _loss_record(self.compiler_id, intent.intent_id, dropped, {})


def _gpt_sovits_tags(intent: SpeechIntent) -> str:
    """Render only adapter-owned tags; the original semantic text stays intact."""
    replacements: list[tuple[int, int, str]] = []
    for marker in _markers_of_kind(intent, TimelineMarkerKind.EMPHASIS):
        if not marker.text_span:
            continue
        start = 0
        while True:
            start = intent.semantic_text.find(marker.text_span, start)
            if start < 0:
                break
            end = start + len(marker.text_span)
            if all(end <= used_start or start >= used_end for used_start, used_end, _ in replacements):
                emphasized = (
                    f'<emphasis level="{marker.strength_or_duration}">'
                    f"{marker.text_span}</emphasis>"
                )
                replacements.append((start, end, emphasized))
                break
            start += 1
    speech = intent.semantic_text
    for start, end, emphasized in sorted(replacements, reverse=True):
        speech = f"{speech[:start]}{emphasized}{speech[end:]}"
    pauses = "".join(
        f'<break time="{marker.strength_or_duration}s"/>'
        for marker in _markers_of_kind(intent, TimelineMarkerKind.PAUSE)
    )
    return (
        f'<prosody rate="{intent.delivery.relative_rate}" '
        f'pitch="{intent.delivery.relative_pitch}" '
        f'volume="{intent.delivery.relative_energy}">{speech}</prosody>{pauses}'
    )


def _legacy_trajectory(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Normalize legacy frame dictionaries while tolerating early wire payloads."""
    raw_trajectory = data.get("trajectory", [])
    if not isinstance(raw_trajectory, list):
        return []
    return [frame for frame in raw_trajectory if isinstance(frame, Mapping)]


def _legacy_relative_energy(frames: list[Mapping[str, Any]]) -> float:
    """Use post-fade-in frames so legacy migration does not violate schema bounds."""
    steady_frames: list[Mapping[str, Any]] = []
    for frame in frames:
        try:
            time_offset_ms = float(frame.get("time_offset_ms", 0.0))
        except (TypeError, ValueError):
            continue
        if time_offset_ms >= 150.0:
            steady_frames.append(frame)
    volumes: list[float] = []
    for frame in steady_frames or frames:
        try:
            volume = float(frame.get("volume", 1.0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(volume):
            volumes.append(volume)
    energy = sum(volumes) / len(volumes) if volumes else 1.0
    return min(2.0, max(0.5, energy))


def legacy_expression_to_speech_intent(data: dict[str, Any]) -> SpeechIntent:
    """Adapt an ``AgentVoiceModulation``-shaped payload into ``SpeechIntent``.

    The historic wire only carries acoustic frames, so fields it never knew
    about intentionally receive the stable schema defaults.
    """
    frames = _legacy_trajectory(data)
    first_frame = frames[0] if frames else {}
    affect_label = data.get("affect_label")
    style = data.get("style")
    affect = SpeechAffect(
        intensity=float(data.get("breath", 0.5)),
        optional_label_hint=affect_label if isinstance(affect_label, str) else None,
    )
    delivery = SpeechDelivery(
        relative_rate=float(first_frame.get("rate", 1.0)),
        relative_pitch=float(first_frame.get("pitch", 1.0)),
        relative_energy=_legacy_relative_energy(frames),
        style=style if isinstance(style, str) else None,
    )
    return build_speech_intent(
        turn_id=str(data.get("turn_id", "legacy-turn")),
        semantic_text=str(data.get("semantic_text", data.get("text", ""))),
        affect=affect,
        delivery=delivery,
    )


def speech_intent_to_legacy_modulation(intent: SpeechIntent) -> dict[str, Any]:
    """Produce a valid ``AgentVoiceModulation`` payload plus compatibility metadata."""
    return {
        "trajectory": [
            {
                "time_offset_ms": 0,
                "rate": intent.delivery.relative_rate,
                "pitch": intent.delivery.relative_pitch,
                "volume": intent.delivery.relative_energy,
            }
        ],
        "turn_id": intent.turn_id,
        "semantic_text": intent.semantic_text,
        "affect_label": intent.affect.optional_label_hint,
        "breath": intent.affect.intensity,
        "style": intent.delivery.style or "neutral",
    }
