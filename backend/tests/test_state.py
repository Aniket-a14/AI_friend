import pytest
from datetime import datetime, timedelta
from app.cognitive.state import StateService

@pytest.fixture
def state_service(mock_graph_db):
    return StateService(graph_store=mock_graph_db)

@pytest.mark.asyncio
async def test_state_hydration(state_service, mock_graph_db):
    mock_graph_db.execute_query.return_value = [{"a": {
        "mood": 0.5,
        "energy": 0.9,
        "trust": 0.7,
        "attachment": 0.3
    }}]
    
    await state_service.hydrate_state()
    assert state_service.current_state.mood == 0.5
    assert state_service.current_state.energy == 0.9

@pytest.mark.asyncio
async def test_mood_evolution(state_service):
    # Set positive valence event
    state_service.current_state.mood = 0.0
    state_service.current_state.last_update = datetime.now() - timedelta(hours=1)
    
    # 1.0 valence event should pull mood up
    await state_service.update_from_event(event_valence=1.0)
    
    assert state_service.current_state.mood > 0.0
    assert state_service.current_state.mood < 1.0
    assert state_service.current_state.energy < 0.8 # Energy should have decreased

@pytest.mark.asyncio
async def test_idle_decay(state_service):
    # Set high mood and energy
    state_service.current_state.mood = 0.8
    state_service.current_state.energy = 0.2
    
    # Evolve via system tick (10 hours gap)
    tick = {"timestamp": 123456789.0, "interval": 36000} # 10h
    await state_service.handle_system_tick(tick)
    
    # Mood should decay toward 0
    assert state_service.current_state.mood < 0.8
    # Energy should recover during rest
    assert state_service.current_state.energy > 0.2

@pytest.mark.asyncio
async def test_bounds_enforcement(state_service):
    await state_service.update_from_event(event_valence=5.0) # Impossible high
    assert state_service.current_state.mood <= 1.0
    
    await state_service.update_from_event(event_valence=-5.0) # Impossible low
    assert state_service.current_state.mood >= -1.0

def test_emotion_label(state_service):
    state_service.current_state.mood = 0.5
    assert state_service.get_emotion_label() == "happy"
    
    state_service.current_state.mood = -0.5
    assert state_service.get_emotion_label() == "sad"
    
    state_service.current_state.mood = 0.0
    state_service.current_state.energy = 0.9
    assert state_service.get_emotion_label() == "excited"
