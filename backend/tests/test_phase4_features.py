"""
Comprehensive tests for Phase 4: Dynamic Continuous Prosody Mapping, verifying Python-side PAD formulas.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.utils.speech import SpeechCoordinator
from app.utils.segmentation import HybridSegmenter
from app.contracts import ChatOutput, ChatOutputAffect
from app.agents.brain_agent import BrainAgent


def test_speech_coordinator_continuous_formulas():
    """Verify that SpeechCoordinator computes correct continuous PAD formulas with fatigue slowdown."""
    coordinator = SpeechCoordinator(segmenter=HybridSegmenter(target_size=8))

    # 1. Baseline/Neutral state
    state_snap = {
        "valence": 0.0,
        "arousal": 0.5,
        "dominance": 0.5,
        "fatigue": 0.0,
    }
    prosody = coordinator.map_affect_to_prosody(state_snap)
    # Sr = 1.0 + 0.20 * Ar - 0.10 * V - 0.25 * F = 1.0 + 0.20*0.5 - 0.0 - 0.0 = 1.10
    assert abs(prosody["speaking_rate"] - 1.10) < 1e-5
    assert abs(prosody["pause_bias"] - 0.5) < 1e-5
    assert abs(prosody["intensity"] - 0.0) < 1e-5

    # 2. Excited/Positive state
    state_snap_excited = {
        "valence": 0.8,
        "arousal": 0.9,
        "dominance": 0.7,
        "fatigue": 0.0,
    }
    prosody_excited = coordinator.map_affect_to_prosody(state_snap_excited)
    # Sr = 1.0 + 0.20 * 0.9 - 0.10 * 0.8 - 0.0 = 1.0 + 0.18 - 0.08 = 1.10
    assert abs(prosody_excited["speaking_rate"] - 1.10) < 1e-5
    assert abs(prosody_excited["pause_bias"] - 0.1) < 1e-5
    assert abs(prosody_excited["intensity"] - 0.72) < 1e-5

    # 3. Fatigued/Stressed state
    state_snap_tired = {
        "valence": -0.4,
        "arousal": 0.8,
        "dominance": 0.3,
        "fatigue": 0.8,
    }
    prosody_tired = coordinator.map_affect_to_prosody(state_snap_tired)
    # Sr = 1.0 + (0.20 * arousal) - (0.10 * valence) - (0.25 * fatigue) = 1.0 + 0.16 + 0.04 - 0.20 = 1.00
    assert abs(prosody_tired["speaking_rate"] - 1.00) < 1e-5
    assert abs(prosody_tired["pause_bias"] - 0.2) < 1e-5
    assert abs(prosody_tired["intensity"] - 0.32) < 1e-5

    # (1) Max fatigue (fatigue=1.0) with high arousal (arousal=0.9)
    # Sr = 1.0 + 0.20 * Ar - 0.10 * V - 0.25 * F = 1.0 + 0.20 * 0.9 - 0.10 * 0.5 - 0.25 * 1.0 = 0.88
    # Intensity = |V| * Ar = |0.5| * 0.9 = 0.45
    # Pause Bias = clamp(1.0 - Ar, 0, 1) = clamp(1.0 - 0.9, 0, 1) = 0.10
    state_snap_max_fatigue = {
        "valence": 0.5,
        "arousal": 0.9,
        "dominance": 0.5,
        "fatigue": 1.0,
    }
    prosody_fatigue = coordinator.map_affect_to_prosody(state_snap_max_fatigue)
    assert abs(prosody_fatigue["speaking_rate"] - 0.880) < 1e-5
    assert abs(prosody_fatigue["pause_bias"] - 0.100) < 1e-5
    assert abs(prosody_fatigue["intensity"] - 0.450) < 1e-5

    # (2) Zero arousal (arousal=0.0) combined with varying valence
    # Case A: Positive valence (valence=0.5)
    # Sr = 1.0 + 0.20 * 0.0 - 0.10 * 0.5 - 0.25 * 0.0 = 0.95
    # Intensity = |V| * Ar = |0.5| * 0.0 = 0.00
    # Pause Bias = clamp(1.0 - Ar, 0, 1) = clamp(1.0 - 0.0, 0, 1) = 1.00
    state_snap_zero_arousal_pos = {
        "valence": 0.5,
        "arousal": 0.0,
        "dominance": 0.5,
        "fatigue": 0.0,
    }
    prosody_zero_ar_pos = coordinator.map_affect_to_prosody(state_snap_zero_arousal_pos)
    assert abs(prosody_zero_ar_pos["speaking_rate"] - 0.950) < 1e-5
    assert abs(prosody_zero_ar_pos["pause_bias"] - 1.000) < 1e-5
    assert abs(prosody_zero_ar_pos["intensity"] - 0.000) < 1e-5

    # Case B: Negative valence (valence=-0.8)
    # Sr = 1.0 + 0.20 * 0.0 - 0.10 * -0.8 - 0.25 * 0.0 = 1.08
    # Intensity = |V| * Ar = |-0.8| * 0.0 = 0.00
    # Pause Bias = clamp(1.0 - Ar, 0, 1) = clamp(1.0 - 0.0, 0, 1) = 1.00
    state_snap_zero_arousal_neg = {
        "valence": -0.8,
        "arousal": 0.0,
        "dominance": 0.5,
        "fatigue": 0.0,
    }
    prosody_zero_ar_neg = coordinator.map_affect_to_prosody(state_snap_zero_arousal_neg)
    assert abs(prosody_zero_ar_neg["speaking_rate"] - 1.080) < 1e-5
    assert abs(prosody_zero_ar_neg["pause_bias"] - 1.000) < 1e-5
    assert abs(prosody_zero_ar_neg["intensity"] - 0.000) < 1e-5

    # (3) Negative/edge dominance values (e.g. dominance=-1.0)
    # Sr = 1.0 + 0.20 * 0.6 - 0.10 * 0.4 - 0.25 * 0.2 = 1.03
    # Intensity = |V| * Ar = |0.4| * 0.6 = 0.24
    # Pause Bias = clamp(1.0 - Ar, 0, 1) = clamp(1.0 - 0.6, 0, 1) = 0.40
    state_snap_neg_dom = {
        "valence": 0.4,
        "arousal": 0.6,
        "dominance": -1.0,
        "fatigue": 0.2,
    }
    prosody_neg_dom = coordinator.map_affect_to_prosody(state_snap_neg_dom)
    assert abs(prosody_neg_dom["speaking_rate"] - 1.030) < 1e-5
    assert abs(prosody_neg_dom["pause_bias"] - 0.400) < 1e-5
    assert abs(prosody_neg_dom["intensity"] - 0.240) < 1e-5

    # (4) Out-of-range input (e.g., arousal=1.5, valence=-1.5)
    # Sr = max(0.6, min(1.8, 1.0 + 0.20 * 1.5 - 0.10 * -1.5)) = max(0.6, min(1.8, 1.45)) = 1.45
    # Intensity = |V| * Ar = |-1.5| * 1.5 = 2.25
    # Pause Bias = clamp(1.0 - Ar, 0, 1) = clamp(1.0 - 1.5, 0, 1) = 0.00
    state_snap_out_of_range = {
        "valence": -1.5,
        "arousal": 1.5,
        "dominance": 0.5,
        "fatigue": 0.0,
    }
    prosody_out_of_range = coordinator.map_affect_to_prosody(state_snap_out_of_range)
    assert abs(prosody_out_of_range["speaking_rate"] - 1.450) < 1e-5
    assert abs(prosody_out_of_range["pause_bias"] - 0.000) < 1e-5
    assert abs(prosody_out_of_range["intensity"] - 2.250) < 1e-5


def test_speech_coordinator_create_chunk_payload():
    """Verify that SpeechCoordinator creates a fully compliant ChatOutput with affect fields."""
    coordinator = SpeechCoordinator(segmenter=HybridSegmenter(target_size=8))

    state_snap = {
        "valence": 0.5,
        "arousal": 0.7,
        "dominance": 0.6,
        "trust": 0.8,
        "attachment": 0.4,
        "emotion": "happy",
        "fatigue": 0.2,
    }

    payload = coordinator.create_chunk_payload(
        words=["hello", "there"],
        state_snap=state_snap,
        turn_id="turn-4",
        done=False,
        user_distance=1.2,
    )

    assert isinstance(payload, ChatOutput)
    assert payload.content == "hello there"
    assert payload.turn_id == "turn-4"
    assert payload.done is False

    # Check top-level prosody fields (rounded to 3 decimal places)
    # Sr = 1.0 + 0.20*0.7 - 0.10*0.5 - 0.25*0.2 = 1.0 + 0.14 - 0.05 - 0.05 = 1.04
    assert abs(payload.speaking_rate - 1.04) < 1e-5
    assert abs(payload.pause_bias - 0.3) < 1e-5

    # Check affect payload details
    assert payload.affect is not None
    assert isinstance(payload.affect, ChatOutputAffect)
    assert payload.affect.valence == 0.5
    assert payload.affect.arousal == 0.7
    assert payload.affect.dominance == 0.6
    assert payload.affect.trust == 0.8
    assert payload.affect.attachment == 0.4
    assert payload.affect.emotion == "happy"
    assert payload.affect.fatigue == 0.2
    assert payload.affect.user_distance == 1.2


@pytest.mark.asyncio
async def test_brain_agent_prosody_calculation_publishing():
    """Verify that BrainAgent correctly computes prosody and publishes compliant JSON to NATS."""
    # Instantiating a mock/stub BrainAgent
    agent = BrainAgent(
        ollama_url="http://localhost:11434",
        graph_db=MagicMock(),
        memory_store=MagicMock(),
        conversation_store=MagicMock(),
    )

    # Mock cognitive core context snapshot
    state_snap = {
        "valence": -0.2,
        "arousal": 0.6,
        "dominance": 0.4,
        "trust": 0.7,
        "attachment": 0.2,
        "emotion": "sad",
        "fatigue": 0.4,
    }
    agent.cognitive_core = MagicMock()
    agent.cognitive_core.state.get_context_snapshot.return_value = state_snap
    agent.last_user_distance = 1.8

    # Mock publish
    agent.publish = AsyncMock()

    # Call the speech publishing method
    await agent._publish_speech_chunk(
        words=["testing", "continuous", "prosody"], turn_id="turn-5"
    )

    # Assert publish was called once
    agent.publish.assert_called_once()
    nats_topic, nats_payload = agent.publish.call_args[0]

    assert nats_topic == "chat.output"
    assert isinstance(nats_payload, dict)

    # Validate published payload
    parsed = ChatOutput.model_validate(nats_payload)
    assert parsed.content == "testing continuous prosody"
    assert parsed.done is False
    assert parsed.turn_id == "turn-5"

    # Sr = 1.0 + 0.20*0.6 - 0.10*(-0.2) - 0.25*0.4 = 1.0 + 0.12 + 0.02 - 0.10 = 1.04
    assert abs(parsed.speaking_rate - 1.04) < 1e-5
    assert abs(parsed.pause_bias - 0.4) < 1e-5

    assert parsed.affect.valence == -0.2
    assert parsed.affect.arousal == 0.6
    assert parsed.affect.dominance == 0.4
    assert parsed.affect.fatigue == 0.4
    assert parsed.affect.user_distance == 1.8
