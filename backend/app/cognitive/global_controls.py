"""Bounded, derived engineering controls for cognitive modulation.

The controls are deliberately derived rather than authoritative state. They
may adjust rates, orderings, and budgets, but they cannot alter beliefs,
identity, safety constraints, or evidence provenance.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field


class GlobalControls(BaseModel):
    """Four non-redundant engineering control signals."""

    model_config = ConfigDict(frozen=True)

    urgency_gain: float = Field(default=0.1, ge=0.0, le=1.0)
    exploration_budget: float = Field(default=0.5, ge=0.0, le=1.0)
    effort_budget: float = Field(default=0.5, ge=0.0, le=1.0)
    learning_gain: float = Field(default=0.5, ge=0.0, le=1.0)


def _unit_interval(value: float) -> float:
    """Clamp a numeric control input to the closed unit interval."""
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return 0.0
    return max(0.0, min(1.0, numeric_value))


def _signed_unit_interval(value: float) -> float:
    """Clamp a signed PAD value to its declared range."""
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return 0.0
    return max(-1.0, min(1.0, numeric_value))


def _pad_value(affect_pad: dict[str, float], *names: str, default: float) -> float:
    """Read a PAD value without mutating the caller's mapping."""
    for name in names:
        value = affect_pad.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return default


def derive_global_controls(
    affect_pad: dict[str, float],
    load: float,
    urgency: float,
    prediction_error: float,
) -> GlobalControls:
    """Derive bounded controls from PAD affect, load, urgency, and surprise.

    ``prediction_error`` serves as the available uncertainty/novelty signal;
    ``urgency`` is both event stakes and salience. The calculations are pure so
    callers can audit or replay a control decision from its input snapshot.
    """
    valence = _signed_unit_interval(
        _pad_value(affect_pad, "valence", "pleasure", "mood", default=0.0)
    )
    arousal = _unit_interval(_pad_value(affect_pad, "arousal", "energy", default=0.5))
    bounded_load = _unit_interval(load)
    bounded_urgency = _unit_interval(urgency)
    bounded_prediction_error = _unit_interval(abs(float(prediction_error)))

    negative_valence = max(0.0, -valence)
    positive_valence = max(0.0, valence)
    positive_arousal = max(0.0, arousal)
    available_capacity = 1.0 - bounded_load
    salience = max(bounded_urgency, arousal, abs(valence))

    return GlobalControls(
        urgency_gain=_unit_interval(
            0.1
            + 0.55 * bounded_urgency
            + 0.20 * negative_valence
            + 0.15 * arousal
        ),
        exploration_budget=_unit_interval(
            0.15
            + 0.20 * positive_arousal
            + 0.20 * positive_valence
            + 0.25 * bounded_prediction_error
            + 0.20 * available_capacity
        ),
        effort_budget=_unit_interval(
            (0.25 + 0.75 * bounded_urgency) * available_capacity
        ),
        learning_gain=_unit_interval(
            0.10 + 0.60 * bounded_prediction_error + 0.30 * salience
        ),
    )


def endocrine_to_global_controls(
    cortisol: float, dopamine: float, fatigue: float
) -> GlobalControls:
    """Translate legacy endocrine readings to the four control dimensions.

    Cortisol maps to urgency, dopamine to exploration, and fatigue inversely
    maps to available effort. Learning gain preserves the available legacy
    salience signals without treating either hormone as a biological target.
    """
    bounded_cortisol = _unit_interval(cortisol)
    bounded_dopamine = _unit_interval(dopamine)
    bounded_fatigue = _unit_interval(fatigue)
    return GlobalControls(
        urgency_gain=bounded_cortisol,
        exploration_budget=bounded_dopamine,
        effort_budget=1.0 - bounded_fatigue,
        learning_gain=(bounded_cortisol + bounded_dopamine) / 2.0,
    )


def global_controls_to_endocrine(controls: GlobalControls) -> dict[str, float]:
    """Translate controls to the legacy names consumed by existing callers."""
    return {
        "cortisol": controls.urgency_gain,
        "dopamine": controls.exploration_budget,
        "fatigue": 1.0 - controls.effort_budget,
    }
