import time
from unittest.mock import AsyncMock, patch

import pytest

from app.cognitive.core import CognitiveService


@pytest.fixture
def cognitive_service(mock_llm_service, mock_graph_db, mock_memory_store, tmp_path):
    with patch(
        "app.state.agent_state.StateService.persist_state", new_callable=AsyncMock
    ):
        # AI Friend Core: Isolation Hardening - use temp directory for persona/history persistence
        base_path = str(tmp_path)

        def mock_load_json(path):
            if "personality.json" in path:
                return {
                    "name": "my friend",
                    "core_personality": {
                        "traits": ["Warm"],
                        "immutable": {
                            "values": ["Honesty"],
                            "base_tone": "Warm",
                            "boundaries": [],
                        },
                    },
                    "conversation_rules": {"avoid": []},
                    "speaking_style": {"style_description": "Hinglish"},
                }
            elif "history.json" in path:
                return {"relationship": "Friend", "memories": []}
            return {}

        with patch(
            "app.cognitive.identity.IdentityManager._load_json",
            side_effect=mock_load_json,
        ):
            svc = CognitiveService(
                llm_service=mock_llm_service,
                memory_store=mock_memory_store,
                graph_db=mock_graph_db,
                base_path=base_path,
            )
            return svc


@pytest.mark.asyncio
async def test_scenario_hostile_interaction_drift(cognitive_service, mock_llm_service):
    """
    Scenario: User is consistently mean. The agent should drift toward guarded/reserved.
    """
    # 1. Explicitly disable intent classification so generate() is only called for:
    #   1. Reflection - Fact Extraction
    #   2. Reflection - Identity Suggestion (REQUIRED: confidence >= 0.8)
    # This avoids fragile coupling with the autouse fixture's .env interaction.
    from app.config import Config

    original_val = Config.LLM_INTENT_CLASSIFICATION_ENABLED
    Config.LLM_INTENT_CLASSIFICATION_ENABLED = False
    # Phase 07: LEARNING_REVIEW_REQUIRED now defaults True, which routes a
    # high-confidence persona suggestion into the governed review queue
    # instead of applying it directly -- this scenario is specifically
    # about the legacy direct-apply drift actually landing in
    # identity.history, so it pins the flag back to False for its duration
    # (mirrors test_reflection.py::test_identity_evolution_trigger).
    original_review_required = Config.LEARNING_REVIEW_REQUIRED
    Config.LEARNING_REVIEW_REQUIRED = False

    async def mock_generate(prompt, **kwargs):
        if "deep appraisal" in prompt or "goal_congruence" in prompt:
            return (
                '{"goal_congruence": -0.8, "norm_alignment": -0.5, "expectedness": 0.2}'
            )
        elif "Determine if" in prompt and "evolve" in prompt:
            return '{"new_traits": ["Reserved"], "relationship": "Strained", "confidence": 0.9}'
        elif "People, Preferences" in prompt or "Facts about the User" in prompt:
            return "[]"
        return '{"intent": "CHAT", "goal": "ENGAGE", "confidence": 0.9}'

    mock_llm_service.generate.side_effect = mock_generate

    # 2. Process 5 hostile events
    for _ in range(5):
        # Reset task tracker (Optional, keeping for compatibility but Event is primary)
        cognitive_service.last_reflection_task = None

        raw_event = {"text": "I hate you, you are just a machine"}
        async for _ in cognitive_service.process_event(raw_event):
            pass

        # AI Friend Core: ABSOLUTE DETERMINISM - ensure semantic consolidation is 100% complete
        await cognitive_service.learning.reflection_done.wait()

    # 3. Verify Evolutionary adaptive variables
    # Core Traits (Immutable) should NOT contain 'Reserved'
    core_traits = cognitive_service.identity.personality["core_personality"].get(
        "traits", []
    )
    assert "Reserved" not in core_traits

    # Relationship (Adaptive) should have evolved
    assert cognitive_service.identity.history["relationship"] == "Strained"

    # Cleanup
    Config.LLM_INTENT_CLASSIFICATION_ENABLED = original_val
    Config.LEARNING_REVIEW_REQUIRED = original_review_required


@pytest.mark.asyncio
async def test_scenario_energy_exhaustion_rest(cognitive_service):
    """
    Scenario: Many interactions drain energy, idle time restores it.
    """
    # 1. Drain energy via 10 interactions
    cognitive_service.state.current_state.baseline_arousal = 0.8
    cognitive_service.state.current_state.energy = 0.8
    initial_energy = cognitive_service.state.current_state.energy
    for _ in range(10):
        # Trigger an event
        await cognitive_service.state.update_from_event(event_valence=0.0)

    exhausted_energy = cognitive_service.state.current_state.energy
    assert exhausted_energy < initial_energy

    # 2. Simulate 24 hours of rest via mesh heartbeat
    tick = {"timestamp": time.time(), "interval": 86400}  # 24h
    await cognitive_service.state.handle_system_tick(tick)

    rested_energy = cognitive_service.state.current_state.energy
    assert rested_energy > exhausted_energy
    assert rested_energy <= 1.0  # Should be bounded at 1.0
    assert rested_energy > 0.6  # Should recover significantly in 24h
