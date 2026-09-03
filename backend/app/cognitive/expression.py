"""Deterministic speech-expression derivation.

This module is the in-process expression boundary.  It owns the small amount
of semantic mapping that used to be split between ActionService's inline
breath tags and its stream hesitation injection; APRA trajectory generation
remains delegated to the Rust implementation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import cognitive_rust
from pydantic import BaseModel, Field

from .behavior_contracts import CommunicativeIntent

TrajectoryFrame = tuple[int, float, float, float]


class SpeechExpression(BaseModel):
    """The acoustic intent for one spoken turn.

    ``trajectory`` deliberately keeps cognitive-rust's native frame shape.
    Preserving the returned tuples is important: this object is a side
    channel, not a second prosody calculation or a lossy summary of APRA.
    """

    affect_label: str
    breath: float = Field(ge=0.0, le=1.0)
    hesitation: float = Field(ge=0.0, le=1.0)
    style: str = "natural"
    trajectory: list[TrajectoryFrame]


def _snapshot_value(
    snapshot: dict[str, Any] | Any,
    *names: str,
    default: float,
) -> float:
    """Read a numeric state value from mappings and state-like objects."""
    if isinstance(snapshot, Mapping):
        value = next((snapshot[name] for name in names if name in snapshot), default)
    else:
        model_dump = getattr(snapshot, "model_dump", None)
        if callable(model_dump):
            value = _snapshot_value(model_dump(), *names, default=default)
        else:
            value = next(
                (getattr(snapshot, name) for name in names if hasattr(snapshot, name)),
                default,
            )

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def _affect_label(valence: float, arousal: float) -> str:
    """Map the PAD dimensions to the stable labels used by the voice layer."""
    if valence < -0.3:
        return "concerned"
    if valence > 0.3 and arousal > 0.6:
        return "excited"
    if valence > 0.3:
        return "warm"
    if arousal < 0.4:
        return "calm"
    return "neutral"


def _breath_level(valence: float, arousal: float) -> float:
    """Encode ActionService's existing breath/sigh threshold rules."""
    if arousal > 0.6 and valence < -0.3:
        return 1.0
    if arousal < 0.4 and valence < 0.0:
        return 0.5
    return 0.0


def derive_speech_expression(
    state_snapshot: dict[str, Any] | Any,
    intent: CommunicativeIntent | None = None,
) -> SpeechExpression:
    """Derive one deterministic expression from a state snapshot.

    ``intent`` is accepted as part of the expression boundary and is
    intentionally not allowed to override affect or APRA state in this first
    contract slice.  The derivation is pure: it neither mutates the snapshot
    nor consults wall-clock time.
    """
    del intent

    valence = _snapshot_value(state_snapshot, "valence", "mood", default=0.0)
    arousal = _snapshot_value(state_snapshot, "arousal", "energy", default=0.5)
    dominance = _snapshot_value(state_snapshot, "dominance", default=0.5)
    fatigue = _snapshot_value(state_snapshot, "fatigue", default=0.0)
    cortisol = _snapshot_value(state_snapshot, "cortisol", default=0.0)
    dopamine = _snapshot_value(state_snapshot, "dopamine", default=0.0)
    adrenaline = _snapshot_value(state_snapshot, "adrenaline", default=0.0)

    trajectory = cognitive_rust.generate_apra_trajectory(
        valence,
        arousal,
        dominance,
        fatigue,
        cortisol,
        dopamine,
        adrenaline,
    )

    return SpeechExpression(
        affect_label=_affect_label(valence, arousal),
        breath=_breath_level(valence, arousal),
        hesitation=1.0 if dominance < 0.4 else 0.0,
        trajectory=trajectory,
    )
