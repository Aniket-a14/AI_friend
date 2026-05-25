"""
NATS Mesh Message Contracts — CVS-1.0

Typed Pydantic models for every inter-agent message on the NATS bus.
Using these at publish/subscribe boundaries catches key-rename and
type-mismatch bugs at runtime instead of silently dropping data.

Usage:
    # Publishing
    msg = ChatInput(text="hello", utterance_id="utt-1")
    await agent.publish("chat.input", msg.model_dump())

    # Receiving
    msg = ChatInput.model_validate(data)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


from enum import Enum


class Topics(str, Enum):
    CHAT_INPUT = "chat.input"
    CHAT_OUTPUT = "chat.output"
    VISION_CONTROL = "vision.control"
    VISION_FRAMES = "vision.frames"
    VISION_DESCRIPTION = "vision.description"
    AUDIO_PERCEPTION = "audio.perception"
    AUDIO_STOP = "audio.stop"
    AUDIO_RESUME = "audio.resume"
    AUDIO_INBOUND = "audio.inbound"
    AUDIO_STREAM = "audio.stream"
    VOICE_WARM = "voice.warm"
    VOICE_SEGMENTATION_FEEDBACK = "voice.segmentation_feedback"
    SYSTEM_TICK = "system.tick"
    MEMORY_SURFACED = "memory.surfaced"
    STATE_UPDATE = "state.update"
    STATE_SUBCONSCIOUS = "state.subconscious"
    USER_VOICE_PROPERTIES = "user.voice.properties"
    AGENT_VOICE_MODULATION = "agent.voice.modulation"
    AUDIO_PLAYBACK_VISEMES = "audio.playback.visemes"
    AUDIO_PLAYBACK_PROGRESS = "audio.playback.progress"
    AMBIENT_NOISE_TELEMETRY = "ambient.noise.telemetry"


# ─── chat.input ──────────────────────────────────────────────
class ChatInputMetadata(BaseModel):
    model_config = {"extra": "allow"}

    source: str = "whisper"
    confidence: float = 0.9
    utterance_id: Optional[str] = None


class ChatInput(BaseModel):
    """Published by STTAgent on `chat.input` after final transcription."""

    model_config = {"extra": "allow"}

    text: str
    utterance_id: Optional[str] = None
    turn_id: Optional[str] = None
    metadata: ChatInputMetadata = Field(default_factory=ChatInputMetadata)
    latency_metadata: Optional[Dict[str, Any]] = None


# ─── chat.output ─────────────────────────────────────────────
class ChatOutputAffect(BaseModel):
    """PAD and Relational affect vector attached to each speech chunk."""

    valence: float = 0.0
    arousal: float = 0.5
    dominance: float = 0.5
    trust: float = 0.5
    attachment: float = 0.1
    emotion: str = "neutral"
    fatigue: float = 0.0
    user_distance: Optional[float] = None


class ChatOutput(BaseModel):
    """Published by BrainAgent on `chat.output` for each speech chunk or done signal."""

    model_config = {"extra": "allow"}

    content: Optional[str] = None
    done: bool = False
    turn_id: Optional[str] = None
    affect: Optional[ChatOutputAffect] = None

    # Prosody & Signals
    confidence: float = 1.0
    intensity: float = 0.0
    speaking_rate: float = 1.0
    pause_bias: float = 0.0
    paralinguistic_tags: List[str] = Field(
        default_factory=list
    )  # [laughs], [sighs], etc.

    # Metadata
    timestamp: float = Field(default_factory=time.time)
    full_response: Optional[str] = None
    generation_error: Optional[str] = None
    proactive: bool = False
    metadata: Optional[Dict[str, Any]] = None
    latency_metadata: Optional[Dict[str, Any]] = None


# ─── audio.perception ────────────────────────────────────────
class SpeculativeIntent(BaseModel):
    name: str = "SPECULATIVE_STOP"
    keywords: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    text: str = ""
    timestamp: float = 0.0
    utterance_id: Optional[str] = None


class AudioPerception(BaseModel):
    """Published by STTAgent on `audio.perception` from the SenseVoice fast path."""

    text: str = ""
    intent: Optional[str] = None
    intent_type: str = "CONVERSATIONAL"  # COMMAND, PERCEPTION, CONVERSATIONAL
    keywords: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    snr: float = 0.0  # Signal-to-Noise Ratio
    paralinguistic_events: List[str] = Field(
        default_factory=list
    )  # [laughter], [cough], etc.
    speculative_intent: Optional[SpeculativeIntent] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = 0.0
    utterance_id: Optional[str] = None


# ─── audio.stop / audio.resume ───────────────────────────────
class AudioStop(BaseModel):
    """Published on `audio.stop` to halt voice playback."""

    interrupt: bool = True
    speculative: bool = False
    reason: Optional[str] = None
    command_text: Optional[str] = None
    intent: Optional[str] = None
    intent_type: str = (
        "VOICE_INTERRUPTION"  # VOICE_INTERRUPTION, VISION_INTERRUPTION, SYSTEM_HALT
    )
    keywords: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    perception_text: Optional[str] = None
    utterance_id: Optional[str] = None
    turn_id: Optional[str] = None


class AudioResume(BaseModel):
    """Published on `audio.resume` to resume voice playback after rejected stop."""

    reason: str = "conflict_rejected"
    perception_text: Optional[str] = None
    utterance_id: Optional[str] = None


# ─── memory.surfaced ─────────────────────────────────────────
class MemoryScope(BaseModel):
    """Hierarchical scope for memory items (Wings -> Rooms -> Drawers)."""

    wing: str = "personal"
    room: Optional[str] = None
    drawer_id: Optional[str] = None


class SurfacedMemory(BaseModel):
    content: str
    raw_content: str  # Verbatim Truth
    scope: MemoryScope = Field(default_factory=MemoryScope)
    score: float = 0.0
    valence: float = 0.0
    created_at: Optional[str] = None
    recall_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySurfaced(BaseModel):
    """Published by SurfacingAgent on `memory.surfaced`."""

    memories: List[SurfacedMemory] = Field(default_factory=list)
    source: str = "episodic"
    provenance: str = "pgvector_actr"  # cognitive source of the memory
    context: Optional[str] = None


# ─── vision.description ──────────────────────────────────────
class VisionDescription(BaseModel):
    """Published by VisionAgent on `vision.description` after VLM appraisal."""

    description: str
    source: str = "screen"
    timestamp: float = Field(default_factory=time.time)
    user_distance: Optional[float] = None


# ─── state.update ────────────────────────────────────────────
class StateUpdate(BaseModel):
    """Published on `state.update` when agent state changes."""

    model_config = {"extra": "allow"}

    mood: float = 0.0
    energy: float = 0.5
    dominance: float = 0.5
    trust: float = 0.5
    attachment: float = 0.1
    emotion: str = "neutral"
    interaction_count: int = 0
    cortisol: float = 0.0
    dopamine: float = 0.0
    fatigue: float = 0.0
    user_mental_model: Optional[Dict[str, Any]] = None


# ─── user.voice.properties ───────────────────────────────────
class UserVoiceProperties(BaseModel):
    model_config = {"extra": "allow"}

    pitch_f0: float
    energy_rms: float
    tempo_wpm: float
    timestamp: float = Field(default_factory=time.time)


# ─── agent.voice.modulation ───────────────────────────────────
class ProsodyFrame(BaseModel):
    model_config = {"extra": "allow"}

    time_offset_ms: int = Field(..., ge=0)
    rate: float
    pitch: float
    volume: float


class AgentVoiceModulation(BaseModel):
    model_config = {"extra": "allow"}

    trajectory: List[ProsodyFrame] = Field(..., min_length=1)
    timestamp: float = Field(default_factory=time.time)

    @field_validator("trajectory")
    @classmethod
    def validate_trajectory(cls, v: List[ProsodyFrame]) -> List[ProsodyFrame]:
        if not v:
            raise ValueError("Trajectory must not be empty.")
        if v[0].time_offset_ms < 0:
            raise ValueError("First offset must be >= 0.")
        for i in range(1, len(v)):
            if v[i].time_offset_ms < v[i - 1].time_offset_ms:
                raise ValueError(
                    "Trajectory must be ordered by time_offset_ms ascending."
                )
            if v[i].time_offset_ms - v[i - 1].time_offset_ms != 50:
                raise ValueError("Consecutive frames must differ by exactly 50 ms.")
        return v


# ─── audio.playback.visemes ───────────────────────────────────
class PlaybackVisemes(BaseModel):
    model_config = {"extra": "allow"}

    target_level: float
    viseme_id: str
    timestamp: float = Field(default_factory=time.time)


# ─── audio.playback.progress ───────────────────────────────────
class AudioPlaybackProgress(BaseModel):
    model_config = {"extra": "allow"}

    utterance_id: str
    character_offset: int = Field(..., ge=0)
    word_index: int = Field(..., ge=0)
    completed: bool
    timestamp: float = Field(default_factory=time.time)


# ─── ambient.noise.telemetry ───────────────────────────────────
class AmbientNoiseTelemetry(BaseModel):
    model_config = {"extra": "allow"}

    rms_energy: float
    noise_floor_db: float
    timestamp: float = Field(default_factory=time.time)
