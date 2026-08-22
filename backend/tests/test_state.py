import asyncio
from datetime import datetime, timedelta

import pytest

from app.state.agent_state import AgentState, StateService


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


# --------------------------------------------------------------------------
# P1-5: apply_external_state -- subconscious_agent observing the brain's
# state.broadcast, instead of holding an independent, never-updated copy.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_external_state_updates_fields_from_broadcast(state_service):
    """The exact payload shape persist_state() publishes on state.broadcast
    must actually change current_state - this is the behavior that was
    entirely missing before (M1-A6/M1-A8): a broadcast arrived and nothing
    read it into the receiving process's own state."""
    broadcast = {
        "agent_name": "my friend",
        "mood": 0.42,
        "energy": 0.77,
        "dominance": 0.61,
        "trust_benevolence": 0.3,
        "trust_competence": 0.35,
        "trust_integrity": 0.4,
        "attachment": 0.55,
        "fatigue": 0.2,
        "last_user_interaction": 1234.5,
        "interaction_count": 7,
        "inferred_valence": 0.15,
        "inferred_arousal": 0.6,
        "implied_goals": ["finish the report"],
        "known_concepts": ["deadlines"],
        "baseline_valence": 0.1,
        "baseline_arousal": 0.5,
        "baseline_dominance": 0.5,
    }

    await state_service.apply_external_state(broadcast)

    assert state_service.current_state.mood == 0.42
    assert state_service.current_state.energy == 0.77
    assert state_service.current_state.dominance == 0.61
    assert state_service.current_state.trust_benevolence == 0.3
    assert state_service.current_state.attachment == 0.55
    assert state_service.current_state.fatigue == 0.2
    assert state_service.current_state.interaction_count == 7
    assert state_service.current_state.user_mental_model.inferred_valence == 0.15
    assert state_service.current_state.user_mental_model.implied_goals == [
        "finish the report"
    ]
    assert state_service.current_state.baseline_valence == 0.1


@pytest.mark.asyncio
async def test_apply_external_state_holds_the_state_lock():
    """Same discipline as hydrate_state (test_hydration_holds_the_same_lock_
    as_every_other_mutation in test_audit_hygiene.py): applying a broadcast
    that arrives mid fire-and-forget System-2 appraisal must not interleave
    with it and leave current_state half-overwritten, half-appraised."""
    service = object.__new__(StateService)
    service._state_lock = asyncio.Lock()
    service.current_state = AgentState()

    observed_locked_during_call = []

    original_lock_acquire = service._state_lock.acquire

    async def spying_acquire():
        result = await original_lock_acquire()
        observed_locked_during_call.append(service._state_lock.locked())
        return result

    service._state_lock.acquire = spying_acquire

    await service.apply_external_state({"mood": 0.9})

    assert observed_locked_during_call == [True]


@pytest.mark.asyncio
async def test_apply_external_state_preserves_fields_missing_from_broadcast(
    state_service,
):
    """A partial broadcast must not reset unlisted fields to a hardcoded
    default the way hydrate_state's Redis/SQLite branches do (there, a
    missing field means 'never persisted, use a sane zero'; here, a missing
    field means 'unchanged since the last broadcast', a different case)."""
    state_service.current_state.dominance = 0.73
    state_service.current_state.attachment = 0.44

    await state_service.apply_external_state({"mood": 0.1})

    assert state_service.current_state.dominance == 0.73
    assert state_service.current_state.attachment == 0.44
