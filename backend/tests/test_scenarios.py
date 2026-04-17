import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from app.cognitive.core import CognitiveService

@pytest.fixture
def cognitive_service(mock_llm_service, mock_graph_db, mock_memory_store):
    with patch("app.cognitive.state.StateService.persist_state", new_callable=AsyncMock):
        with patch("app.cognitive.identity.IdentityManager._load_json", return_value={
            "name": "my friend",
            "core_personality": {"traits": ["Warm"]},
            "history": {"relationship": "Friend", "memories": []},
            "conversation_rules": {"avoid": []},
            "speaking_style": {"style_description": "Hinglish"}
        }):
            svc = CognitiveService(
                llm_service=mock_llm_service,
                memory_store=mock_memory_store,
                graph_db=mock_graph_db
            )
            return svc

@pytest.mark.asyncio
async def test_scenario_hostile_interaction_drift(cognitive_service, mock_llm_service):
    """
    Scenario: User is consistently mean. The agent should drift toward guarded/reserved.
    """
    # 1. Setup Mock LLM to report negative valence and suggest 'Guarded' trait
    mock_llm_service.generate.side_effect = [
        # Decision (Intent/Goal)
        '{"intent": "CHAT", "goal": "PROTECT"}',
        # Action (Response) -> Already handled by streaming mock in conftest
        # Reflection - Fact Extraction
        '[]',
        # Reflection - Identity Suggestion
        '{"new_traits": ["Reserved"], "relationship": "Strained"}'
    ] * 5 # Repeat for 5 cycles
    
    # 2. Process 5 hostile events
    for _ in range(5):
        raw_event = {"text": "I hate you, you are just a machine"}
        async for _ in cognitive_service.process_event(raw_event):
            pass
        # Wait for background reflection to finish in each cycle
        await asyncio.sleep(0.1) 
    
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
