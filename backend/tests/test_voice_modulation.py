import pytest
from pydantic import ValidationError
from app.contracts import AgentVoiceModulation, ProsodyFrame


def test_valid_voice_modulation():
    modulation = AgentVoiceModulation(
        trajectory=[
            ProsodyFrame(time_offset_ms=0, rate=1.0, pitch=1.0, volume=0.5),
            ProsodyFrame(time_offset_ms=50, rate=1.1, pitch=1.05, volume=0.6),
            ProsodyFrame(time_offset_ms=100, rate=1.2, pitch=1.1, volume=0.7),
        ],
        timestamp=123456789.0,
    )
    assert len(modulation.trajectory) == 3
    assert modulation.trajectory[0].time_offset_ms == 0
    assert modulation.trajectory[1].time_offset_ms == 50
    assert modulation.trajectory[2].time_offset_ms == 100


def test_invalid_voice_modulation_empty():
    with pytest.raises(ValidationError):
        AgentVoiceModulation(trajectory=[])


def test_invalid_voice_modulation_negative_offset():
    with pytest.raises(ValidationError):
        AgentVoiceModulation(
            trajectory=[
                ProsodyFrame(time_offset_ms=-50, rate=1.0, pitch=1.0, volume=0.5),
            ]
        )


def test_invalid_voice_modulation_unordered():
    with pytest.raises(ValidationError):
        AgentVoiceModulation(
            trajectory=[
                ProsodyFrame(time_offset_ms=50, rate=1.0, pitch=1.0, volume=0.5),
                ProsodyFrame(time_offset_ms=0, rate=1.1, pitch=1.0, volume=0.6),
            ]
        )


def test_invalid_voice_modulation_wrong_cadence():
    with pytest.raises(ValidationError):
        AgentVoiceModulation(
            trajectory=[
                ProsodyFrame(time_offset_ms=0, rate=1.0, pitch=1.0, volume=0.5),
                ProsodyFrame(time_offset_ms=40, rate=1.1, pitch=1.0, volume=0.6),
            ]
        )
