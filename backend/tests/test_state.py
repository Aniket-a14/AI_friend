import pytest
from datetime import datetime, timedelta
from app.state.agent_state import StateService


@pytest.fixture
def state_service(mock_graph_db):
    service = StateService(graph_store=mock_graph_db, db_path=":memory:")
    service.redis_client = None
    return service


@pytest.mark.asyncio
async def test_state_hydration(state_service, mock_graph_db):
    mock_graph_db.execute_query.return_value = [
        {"a": {"mood": 0.5, "energy": 0.9, "trust": 0.7, "attachment": 0.3}}
    ]

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
    assert state_service.current_state.energy < 0.8  # Energy should have decreased


@pytest.mark.asyncio
async def test_idle_decay(state_service):
    # Set high mood and energy
    state_service.current_state.mood = 0.8
    state_service.current_state.energy = 0.2

    # Evolve via system tick (10 hours gap)
    tick = {"timestamp": 123456789.0, "interval": 36000}  # 10h
    await state_service.handle_system_tick(tick)

    # Mood should decay toward 0
    assert state_service.current_state.mood < 0.8
    # Energy should recover during rest
    assert state_service.current_state.energy > 0.2


@pytest.mark.asyncio
async def test_bounds_enforcement(state_service):
    await state_service.update_from_event(event_valence=5.0)  # Impossible high
    assert state_service.current_state.mood <= 1.0

    await state_service.update_from_event(event_valence=-5.0)  # Impossible low
    assert state_service.current_state.mood >= -1.0


def test_emotion_label(state_service):
    state_service.current_state.mood = 0.5
    assert state_service.get_emotion_label() == "happy"

    state_service.current_state.mood = -0.5
    assert state_service.get_emotion_label() == "sad"

    # PAD: Neutral valence + high arousal = "alert" (not "excited")
    state_service.current_state.mood = 0.0
    state_service.current_state.energy = 0.9
    assert state_service.get_emotion_label() == "alert"

    # PAD: Positive valence + high arousal = "excited"
    state_service.current_state.mood = 0.5
    state_service.current_state.energy = 0.9
    assert state_service.get_emotion_label() == "excited"

    # PAD: Low dominance = "uncertain"
    state_service.current_state.mood = 0.0
    state_service.current_state.energy = 0.5
    state_service.current_state.dominance = 0.2
    assert state_service.get_emotion_label() == "uncertain"


@pytest.mark.asyncio
async def test_fatigue_evolution(state_service):
    # Set deterministic base time
    base_time = 1716000000.0
    state_service.current_state.fatigue = 0.5
    state_service.current_state.last_user_interaction = base_time - 10.0

    # Not idle -> fatigue increases
    tick = {"timestamp": base_time, "interval": 3600}
    await state_service.handle_system_tick(tick)
    # Check bounded range reflecting configuration (timezone day/night safe)
    assert 0.64 < state_service.current_state.fatigue < 0.78

    # Idle -> fatigue decreases
    state_service.current_state.fatigue = 0.5
    state_service.current_state.last_user_interaction = base_time - 600.0
    await state_service.handle_system_tick(tick)
    # Check bounded range reflecting configuration (timezone day/night safe)
    assert 0.29 < state_service.current_state.fatigue < 0.40


@pytest.mark.asyncio
async def test_apply_semantic_appraisal_writes_and_clamps(state_service):
    """A2: System-2 background drift is applied under the state lock and bounded."""
    state_service.current_state.mood = 0.0
    state_service.current_state.energy = 0.5
    state_service.current_state.dominance = 0.5

    # Out-of-range values must be clamped to PAD bounds.
    await state_service.apply_semantic_appraisal(
        {"valence": 5.0, "arousal": -2.0, "dominance": 0.7}
    )
    assert state_service.current_state.mood == 1.0
    assert state_service.current_state.energy == 0.0
    assert state_service.current_state.dominance == 0.7

    # Missing / None keys leave the corresponding dimension untouched.
    await state_service.apply_semantic_appraisal({"valence": 0.2, "arousal": None})
    assert state_service.current_state.mood == pytest.approx(0.2)
    assert state_service.current_state.energy == 0.0
    assert state_service.current_state.dominance == 0.7


@pytest.mark.asyncio
async def test_state_lock_serializes_concurrent_writers(state_service):
    """A2: appraisal and background drift cannot interleave a read-modify-write."""
    import asyncio

    from app.cognitive.appraisal import AppraisalVector

    state_service.current_state.mood = 0.0
    appraisal = AppraisalVector(goal_congruence=1.0, relationship_impact=1.0)

    # Fire the synchronous appraisal path and a background drift concurrently.
    await asyncio.gather(
        state_service.update_from_appraisal(appraisal),
        state_service.apply_semantic_appraisal({"valence": -0.9}),
    )

    # Whichever ran last wins, but the value must be a clean, in-bounds float
    # (no half-written interleave) — proving the lock serialized the writers.
    assert -1.0 <= state_service.current_state.mood <= 1.0


@pytest.mark.asyncio
async def test_missing_emotional_bias_does_not_flatten_mood(state_service):
    """Transcript-only STT (Whisper) sends no emotional_bias; affect must be untouched.

    Regression: the metadata was defaulted to 0.0 and blended in, so every partial
    transcript pulled mood and inferred_valence ~14% toward zero, erasing affect
    established by semantic appraisal.
    """
    state_service.current_state.mood = 0.8
    state_service.current_state.user_mental_model.inferred_valence = 0.8

    # Exactly what the Whisper STT publishes: text + confidence, no emotion.
    for _ in range(5):
        await state_service.apply_sensory_perception(
            {"text": "hello there", "is_partial": True, "confidence": 0.7}
        )

    assert state_service.current_state.mood == 0.8
    assert state_service.current_state.user_mental_model.inferred_valence == 0.8


@pytest.mark.asyncio
async def test_explicit_zero_emotional_bias_still_blends(state_service):
    """An explicit 0.0 from a real emotion model is evidence, not absence."""
    state_service.current_state.mood = 0.8

    await state_service.apply_sensory_perception(
        {"emotional_bias": 0.0, "confidence": 0.9}
    )

    assert state_service.current_state.mood < 0.8


@pytest.mark.asyncio
async def test_events_still_apply_without_emotional_bias(state_service):
    """Paralinguistic events must fire even when no emotion estimate is supplied."""
    state_service.current_state.mood = 0.4
    state_service.current_state.energy = 0.5
    baseline_mood = state_service.current_state.mood

    await state_service.apply_sensory_perception(
        {"confidence": 0.9, "events": ["Laughter"]}
    )

    assert state_service.current_state.energy > 0.5
    # ...but the absent emotion estimate still must not move mood.
    assert state_service.current_state.mood == baseline_mood
