"""
L5: pydantic-settings validates type on load (a non-numeric env value fails
to parse) but not range - a negative timeout or a zero halflife loaded fine
and only broke something later, at runtime, far from the misconfiguration.
"""

import pytest
from pydantic import ValidationError

from app.config import AppSettings


def _settings(**overrides):
    return AppSettings(_env_file=None, **overrides)


@pytest.mark.parametrize(
    "field",
    [
        "DOPAMINE_PHASIC_HALFLIFE_S",
        "CORTISOL_PHASIC_HALFLIFE_S",
        "TOKEN_RATE_LIMIT_WINDOW_SECONDS",
        "LLM_STREAM_MAX_SECONDS",
    ],
)
def test_zero_or_negative_rejected_for_positive_float_fields(field):
    """A zero halflife divides by zero in decay math; a zero/negative
    timeout produces nonsensical (instant or infinite) behavior."""
    with pytest.raises(ValidationError):
        _settings(**{field: 0})
    with pytest.raises(ValidationError):
        _settings(**{field: -1})


def test_negative_decay_rate_rejected():
    """A negative ACTR_DECAY_RATE would make memories strengthen with time
    instead of decaying - an inversion of the intended model, not just an
    edge case."""
    with pytest.raises(ValidationError):
        _settings(ACTR_DECAY_RATE=-0.1)


def test_zero_decay_rate_is_allowed():
    """Zero is a legitimate (if unusual) choice - 'never decay' - unlike
    negative, which inverts the model."""
    settings = _settings(ACTR_DECAY_RATE=0.0)
    assert settings.ACTR_DECAY_RATE == 0.0


@pytest.mark.parametrize(
    "field",
    [
        "SYSTEM_TICK_INTERVAL",
        "TOKEN_RATE_LIMIT_MAX_REQUESTS",
        "MAX_VOICE_QUEUE_SIZE",
        "VOICE_SYNTH_CONCURRENCY",
        "TRANSPORT_AUDIO_QUEUE_SIZE",
        "STT_WHISPER_QUEUE_SIZE",
        "STT_PERCEPTION_QUEUE_SIZE",
    ],
)
def test_zero_or_negative_rejected_for_positive_int_fields(field):
    """A zero SYSTEM_TICK_INTERVAL busy-loops; a zero queue/concurrency size
    is a store nothing can ever pass through."""
    with pytest.raises(ValidationError):
        _settings(**{field: 0})
    with pytest.raises(ValidationError):
        _settings(**{field: -1})


def test_qdrant_port_out_of_range_rejected():
    with pytest.raises(ValidationError):
        _settings(QDRANT_PORT=0)
    with pytest.raises(ValidationError):
        _settings(QDRANT_PORT=70000)


def test_default_settings_load_without_error():
    """Sanity check that the new validator doesn't reject the shipped
    defaults themselves."""
    settings = _settings()
    assert settings.SYSTEM_TICK_INTERVAL > 0
