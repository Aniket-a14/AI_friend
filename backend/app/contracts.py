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
from pydantic import BaseModel, Field


# ─── chat.input ──────────────────────────────────────────────
class ChatInputMetadata(BaseModel):
    source: str = "whisper"
    confidence: float = 0.9
    utterance_id: Optional[str] = None


class ChatInput(BaseModel):
    """Published by STTAgent on `chat.input` after final transcription."""

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


class ChatOutput(BaseModel):
    """Published by BrainAgent on `chat.output` for each speech chunk or done signal."""

    content: Optional[str] = None
    done: bool = False
    turn_id: Optional[str] = None
    affect: Optional[ChatOutputAffect] = None

    # Prosody control
    confidence: float = 1.0
    intensity: float = 0.0
    speaking_rate: float = 1.0
    pause_bias: float = 0.0

    # Metadata
    timestamp: float = Field(default_factory=time.time)
    full_response: Optional[str] = None
    generation_error: Optional[str] = None
    proactive: bool = False


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
    keywords: List[str] = Field(default_factory=list)
    confidence: float = 0.0
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
class SurfacedMemory(BaseModel):
    content: str
    score: float = 0.0
    valence: float = 0.0
    created_at: Optional[str] = None
    recall_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemorySurfaced(BaseModel):
    """Published by SurfacingAgent on `memory.surfaced`."""

    memories: List[SurfacedMemory] = Field(default_factory=list)
    source: str = "episodic"
    context: Optional[str] = None


# ─── state.update ────────────────────────────────────────────
class StateUpdate(BaseModel):
    """Published on `state.update` when agent state changes."""

    mood: float = 0.0
    energy: float = 0.5
    dominance: float = 0.5
    trust: float = 0.5
    attachment: float = 0.1
    emotion: str = "neutral"
    interaction_count: int = 0
