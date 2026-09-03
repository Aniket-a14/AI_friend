"""Tests for the Phase 3A speech-expression contract."""

import cognitive_rust
import pytest

from app.cognitive.expression import SpeechExpression, derive_speech_expression


@pytest.mark.parametrize(
    "state",
    [
        {
            "valence": 0.2,
            "arousal": 0.6,
            "dominance": 0.4,
            "fatigue": 0.1,
            "cortisol": 0.2,
            "dopamine": 0.3,
            "adrenaline": 0.0,
        },
        {
            "valence": -0.5,
            "arousal": 0.8,
            "dominance": 0.2,
            "fatigue": 0.0,
            "cortisol": 0.7,
            "dopamine": 0.0,
            "adrenaline": 0.4,
        },
    ],
)
def test_trajectory_is_identical_to_the_authoritative_apra_generator(state):
    expected = cognitive_rust.generate_apra_trajectory(
        state["valence"],
        state["arousal"],
        state["dominance"],
        state["fatigue"],
        state["cortisol"],
        state["dopamine"],
        state["adrenaline"],
    )

    expression = derive_speech_expression(state)

    assert expression.trajectory == expected
    assert repr(expression.trajectory) == repr(expected)


@pytest.mark.parametrize(
    "valence,arousal,affect_label,breath",
    [
        (-0.9, 0.9, "concerned", 1.0),  # <breath_fast>
        (-0.2, 0.2, "calm", 0.5),  # <sigh_soft>
        (0.9, 0.9, "excited", 0.0),
        (0.5, 0.5, "warm", 0.0),
        (0.0, 0.5, "neutral", 0.0),
    ],
)
def test_affect_and_breath_follow_existing_thresholds(
    valence, arousal, affect_label, breath
):
    expression = derive_speech_expression(
        {"valence": valence, "arousal": arousal, "dominance": 0.5}
    )

    assert expression.affect_label == affect_label
    assert expression.breath == breath


@pytest.mark.parametrize("dominance,expected", [(0.39, 1.0), (0.4, 0.0)])
def test_low_dominance_enables_hesitation(dominance, expected):
    expression = derive_speech_expression(
        {"valence": 0.0, "arousal": 0.5, "dominance": dominance}
    )

    assert expression.hesitation == expected


def test_empty_snapshot_uses_neutral_defaults():
    expression = derive_speech_expression({})

    assert expression.affect_label == "neutral"
    assert expression.breath == 0.0
    assert expression.hesitation == 0.0
    assert expression.style == "natural"
    assert len(expression.trajectory) == 60


def test_expression_model_bounds_and_defaults():
    expression = SpeechExpression(
        affect_label="warm",
        breath=0.25,
        hesitation=0.75,
        trajectory=[(0, 1.0, 1.0, 0.5)],
    )

    assert expression.style == "natural"
    assert expression.trajectory == [(0, 1.0, 1.0, 0.5)]
