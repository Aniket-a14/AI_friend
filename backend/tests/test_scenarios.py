import pytest
import time
from unittest.mock import AsyncMock, patch
from app.cognitive.core import CognitiveService

@pytest.fixture
def cognitive_service(mock_llm_service, mock_graph_db, mock_memory_store, tmp_path):
    with patch("app.state.agent_state.StateService.persist_state", new_callable=AsyncMock):
        # CVS-1.0: Isolation Hardening - use temp directory for persona/history persistence
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
                            "boundaries": []
                        }
                    },
                    "conversation_rules": {"avoid": []},
                    "speaking_style": {"style_description": "Hinglish"}
                }
            elif "history.json" in path:
                return {"relationship": "Friend", "memories": []}
            return {}

        with patch("app.cognitive.identity.IdentityManager._load_json", side_effect=mock_load_json):
            svc = CognitiveService(
                llm_service=mock_llm_service,
                memory_store=mock_memory_store,
                graph_db=mock_graph_db,
                base_path=base_path
            )
            return svc

@pytest.mark.asyncio
async def test_scenario_hostile_interaction_drift(cognitive_service, mock_llm_service):
    """
    Scenario: User is consistently mean. The agent should drift toward guarded/reserved.
    """
    # 1. Setup Mock LLM to report negative valence and suggest 'Guarded' trait with CONFIDENCE
    mock_llm_service.generate.side_effect = [
        # Decision (Intent/Goal)
        '{"intent": "CHAT", "goal": "PROTECT", "confidence": 0.9}',
        # Action (Response) -> Already handled by streaming mock in conftest
        # Reflection - Fact Extraction
        '[]',
        # Reflection - Identity Suggestion (REQUIRED: confidence >= 0.8)
        '{"new_traits": ["Reserved"], "relationship": "Strained", "confidence": 0.9}'
    ] * 5 # Repeat for 5 cycles
    
    # 2. Process 5 hostile events
    for _ in range(5):
        # Reset task tracker (Optional, keeping for compatibility but Event is primary)
        cognitive_service.last_reflection_task = None
        
        raw_event = {"text": "I hate you, you are just a machine"}
        async for _ in cognitive_service.process_event(raw_event):
            pass
            
        # CVS-1.0: ABSOLUTE DETERMINISM - ensure semantic consolidation is 100% complete
        await cognitive_service.learning.reflection_done.wait()
    
    # 3. Verify Evolutionary adaptive variables
    # Core Traits (Immutable) should NOT contain 'Reserved'
    core_traits = cognitive_service.identity.personality["core_personality"].get("traits", [])
    assert "Reserved" not in core_traits
    
    # Relationship (Adaptive) should have evolved
    assert cognitive_service.identity.history["relationship"] == "Strained"

@pytest.mark.asyncio
async def test_scenario_energy_exhaustion_rest(cognitive_service):
    """
    Scenario: Many interactions drain energy, idle time restores it.
    """
    # 1. Drain energy via 10 interactions
    initial_energy = cognitive_service.state.current_state.energy
    for _ in range(10):
        # Trigger an event
        await cognitive_service.state.update_from_event(event_valence=0.0)
    
    exhausted_energy = cognitive_service.state.current_state.energy
    assert exhausted_energy < initial_energy
    
    # 2. Simulate 24 hours of rest via mesh heartbeat
    tick = {"timestamp": time.time(), "interval": 86400} # 24h
    await cognitive_service.state.handle_system_tick(tick)
    
    rested_energy = cognitive_service.state.current_state.energy
    assert rested_energy > exhausted_energy
    assert rested_energy == 1.0 # Should be capped at 1.0
