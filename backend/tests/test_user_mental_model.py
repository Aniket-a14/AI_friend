from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.appraisal import AppraisalVector
from app.cognitive.decision import ActionPlan, CognitiveEvent, DecisionService
from app.cognitive.pipeline import CognitivePipeline
from app.cognitive.tom import MAX_KNOWN_CONCEPTS, UserMentalModel, update_known_concepts
from app.state.agent_state import StateService


def test_vocabulary_tracker():
    """Verifies stop-word filtering and case-insensitive word matching."""
    current = ["learning", "concept"]

    # "their", "there", "with" are stop words and should be filtered out.
    # "quantum" and "physics" are significant (> 3 chars) and should be added uniquely.
    # Words < 4 or > 15 characters should be ignored.
    user_input = "Tell me about quantum physics with their there code aaaaaaaaaaaaaaaaa"

    updated = update_known_concepts(current, user_input)

    assert "quantum" in updated
    assert "physics" in updated
    assert "learning" in updated  # retained
    assert "concept" in updated  # retained

    # Stop words
    assert "their" not in updated
    assert "there" not in updated
    assert "with" not in updated
    assert "about" not in updated

    # Length boundaries
    assert "me" not in updated  # < 4
    assert "code" in updated  # 4 chars, valid
    assert "aaaaaaaaaaaaaaaaa" not in updated  # > 15 chars


def test_vocabulary_tracker_evicts_oldest_once_the_cap_is_exceeded():
    """M7: a multi-hour session used to grow `known_concepts` without bound,
    inflating the state payload serialized on every persist. Once the cap is
    hit, the oldest entries must fall off so the tracker reflects recent
    vocabulary rather than everything ever said.
    """
    current = [f"conceptword{i}" for i in range(MAX_KNOWN_CONCEPTS)]

    updated = update_known_concepts(current, "brandnewword")

    assert len(updated) == MAX_KNOWN_CONCEPTS
    assert "conceptword0" not in updated  # oldest, evicted
    assert "conceptword1" in updated  # next-oldest, retained
    assert "brandnewword" in updated  # newest, retained


def test_vocabulary_tracker_filters_conversational_filler_words():
    """L8: high-frequency filler/connector words ('also', 'even', 'still',
    'well', etc.) used to pass the length filter and get tracked as if they
    were distinctive user vocabulary, diluting the concept list with noise.
    """
    current = []
    user_input = "well i also think it was still quite good actually"

    updated = update_known_concepts(current, user_input)

    assert "well" not in updated
    assert "also" not in updated
    assert "still" not in updated
    assert "actually" not in updated
    # A genuine content word in the same sentence must survive the filter.
    assert "think" in updated
    assert "good" in updated


@pytest.mark.asyncio
async def test_state_tom_update_and_bounds(mock_graph_db):
    """Validates that update_theory_of_mind parses concepts and enforces bounds."""
    state_service = StateService(graph_store=mock_graph_db, db_path=":memory:")

    # Verify initial state
    assert state_service.current_state.user_mental_model.inferred_valence == 0.0
    assert state_service.current_state.user_mental_model.inferred_arousal == 0.5
    assert not state_service.current_state.user_mental_model.known_concepts

    # 1. Update ToM with valid inferences
    tom_inferences = {
        "inferred_valence": 0.8,
        "inferred_arousal": 0.9,
        "implied_goals": ["seek_help"],
    }

    await state_service.update_theory_of_mind(
        "I want assistance with science.", tom_inferences
    )

    assert state_service.current_state.user_mental_model.inferred_valence == 0.8
    assert state_service.current_state.user_mental_model.inferred_arousal == 0.9
    assert "assistance" in state_service.current_state.user_mental_model.known_concepts
    assert "science" in state_service.current_state.user_mental_model.known_concepts
    assert state_service.current_state.user_mental_model.implied_goals == ["seek_help"]

    # 2. Check bounds enforcement
    out_of_bounds_inferences = {
        "inferred_valence": 3.5,  # Needs clamping to 1.0
        "inferred_arousal": -1.2,  # Needs clamping to 0.0
        "implied_goals": ["reassurance"],
    }

    await state_service.update_theory_of_mind(
        "Calm down please.", out_of_bounds_inferences
    )
    assert state_service.current_state.user_mental_model.inferred_valence == 1.0
    assert state_service.current_state.user_mental_model.inferred_arousal == 0.0
    assert state_service.current_state.user_mental_model.implied_goals == [
        "reassurance"
    ]


@pytest.mark.asyncio
async def test_acoustic_tom_drift(mock_graph_db):
    """Validates that SenseVoice acoustic updates correctly shift inferred user valence."""
    state_service = StateService(graph_store=mock_graph_db, db_path=":memory:")
    state_service.current_state.user_mental_model.inferred_valence = 0.0

    # Perception metadata from voice agent
    perception_metadata = {"emotional_bias": 0.8, "confidence": 0.9, "events": []}

    # This should drift the inferred user valence
    await state_service.apply_sensory_perception(perception_metadata)

    # Ensure inferred valence is drifted positively (emotional_bias is 0.8)
    assert state_service.current_state.user_mental_model.inferred_valence > 0.0
    assert state_service.current_state.user_mental_model.inferred_valence < 0.8


@pytest.mark.asyncio
async def test_state_hydration_persistence(mock_graph_db):
    """Mocks SQLite cache hydration/persistence and Neo4j fallback to ensure user mental model fields are cleanly read and saved."""
    import json
    import os
    import sqlite3
    import tempfile

    # Create unique temp file
    fd, db_file = tempfile.mkstemp(suffix=".db", prefix="test_tom_state_")
    os.close(fd)  # Close the file descriptor, we'll use the path

    try:
        state_service = StateService(graph_store=mock_graph_db, db_path=db_file)

        # 1. Test Persist State
        state_service.current_state.user_mental_model.inferred_valence = -0.5
        state_service.current_state.user_mental_model.inferred_arousal = 0.4
        state_service.current_state.user_mental_model.implied_goals = ["vent"]
        state_service.current_state.user_mental_model.known_concepts = [
            "anger",
            "frustration",
        ]

        await state_service.persist_state("test_agent")

        # Query SQLite directly to assert it was saved successfully
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agent_state WHERE agent_name = ?", ("test_agent",)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["inferred_valence"] == -0.5
        assert row["inferred_arousal"] == 0.4
        assert json.loads(row["implied_goals"]) == ["vent"]
        assert json.loads(row["known_concepts"]) == ["anger", "frustration"]

        # 2. Test Hydrate State from SQLite cache
        new_service = StateService(graph_store=mock_graph_db, db_path=db_file)
        await new_service.hydrate_state("test_agent")

        assert new_service.current_state.user_mental_model.inferred_valence == -0.5
        assert new_service.current_state.user_mental_model.inferred_arousal == 0.4
        assert new_service.current_state.user_mental_model.implied_goals == ["vent"]
        assert new_service.current_state.user_mental_model.known_concepts == [
            "anger",
            "frustration",
        ]
    finally:
        # Guaranteed cleanup in finally block
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_llm_tom_inference_extraction():
    """Asserts that _classify_intent_and_goal parses ToM schemas and populates model variables."""
    # Mock LLM response for classification
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value="""
    {
      "intent": "CHAT",
      "goal": "ENGAGE",
      "inferred_valence": -0.4,
      "inferred_arousal": 0.8,
      "implied_goals": ["express_frustration", "seek_comfort"]
    }
    """
    )

    decision_service = DecisionService(llm_service=mock_llm)

    event = CognitiveEvent(
        event_id="evt-123",
        event_type="USER_MESSAGE",
        raw_content="I am so annoyed with this program",
        metadata={},
    )

    state_snapshot = {"emotion": "happy", "mood": 0.1}

    await decision_service._classify_intent_and_goal(event, state_snapshot)

    assert event.intent == "CHAT"
    assert event.metadata["suggested_goal"] == "ENGAGE"
    assert "tom_inferences" in event.metadata

    tom = event.metadata["tom_inferences"]
    assert tom["inferred_valence"] == -0.4
    assert tom["inferred_arousal"] == 0.8
    assert "express_frustration" in tom["implied_goals"]
    assert "seek_comfort" in tom["implied_goals"]


@pytest.mark.asyncio
async def test_pipeline_tom_integration():
    """Validates the full cognitive event flow, ensuring user_mental_model is injected into action payloads."""
    state = MagicMock()
    state.update_from_appraisal = AsyncMock()
    state.update_theory_of_mind = AsyncMock()
    state.last_speculative_intent = (
        None  # Crucial to prevent interruption conflict fallback
    )

    tom_model = UserMentalModel(
        inferred_valence=0.5,
        inferred_arousal=0.3,
        implied_goals=["chat_socially"],
        known_concepts=["python", "programming"],
    )

    state.get_context_snapshot = MagicMock(
        return_value={
            "mood": 0.1,
            "cortisol": 0.3,
            "dopamine": 0.5,
            "fatigue": 0.0,
            "user_mental_model": tom_model.model_dump(),
        }
    )
    state.get_behavioral_directive = MagicMock(return_value="be happy")

    perception = AsyncMock()
    perception.perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="I love writing python code",
        intent="CHAT",
        event_id="evt-1",
        metadata={},
    )

    appraisal = MagicMock()
    appraisal.appraise.return_value = AppraisalVector(
        relevance=1.0,
        novelty=0.5,
        goal_congruence=0.2,
        agency=0.8,
        norm_alignment=1.0,
        relationship_impact=0.1,
    )

    # Mock decision to return custom ToM metadata
    async def mock_decide(event, snapshot, memory_activations=None, **kwargs):
        # Phase 07: AFFECT_CONTROL_ENABLED now defaults True, so the
        # pipeline also passes `global_controls` (and possibly other
        # keyword-only extras) to `decide()` -- accepted and ignored here
        # since this test only cares about the ToM metadata path.
        event.metadata["tom_inferences"] = {
            "inferred_valence": 0.9,
            "inferred_arousal": 0.4,
            "implied_goals": ["learn_concept"],
        }
        return ActionPlan(
            action_type="RESPOND_CHAT",
            goal="ENGAGE",
            payload={"message": "python code"},
        )

    decision = MagicMock()
    decision.decide.side_effect = mock_decide

    action = MagicMock()

    async def mock_execute(plan):
        # Assert that action payload has the user mental model
        assert "user_mental_model" in plan.payload
        assert plan.payload["user_mental_model"]["inferred_valence"] == 0.5
        assert "python" in plan.payload["user_mental_model"]["known_concepts"]
        yield {"type": "content", "data": "Awesome!"}

    action.execute.side_effect = mock_execute

    identity = MagicMock()
    identity.validate_response = AsyncMock(return_value=(True, ""))
    identity.get_persona_prompt.return_value = "System prompt"

    pipeline = CognitivePipeline(
        perception=perception,
        appraisal=appraisal,
        state=state,
        decision=decision,
        action=action,
        learning=AsyncMock(),
        identity=identity,
    )

    # Run loop
    results = []
    async for chunk in pipeline.execute(
        {"type": "USER_MESSAGE", "content": "I love writing python code"}
    ):
        results.append(chunk)

    assert any(r["type"] == "content" and r["data"] == "Awesome!" for r in results)

    # Ensure pre-decision update is called
    assert state.update_theory_of_mind.call_count == 2


@pytest.mark.asyncio
async def test_llm_tom_inference_invalid_type_graceful():
    """Asserts that _classify_intent_and_goal gracefully handles invalid implied_goals types (e.g. dict, int) and falls back to an empty list."""
    # Mock LLM response for classification with invalid implied_goals type (integer instead of list)
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value="""
    {
      "intent": "CHAT",
      "goal": "ENGAGE",
      "inferred_valence": 0.3,
      "inferred_arousal": 0.6,
      "implied_goals": 12345
    }
    """
    )

    decision_service = DecisionService(llm_service=mock_llm)

    event = CognitiveEvent(
        event_id="evt-456",
        event_type="USER_MESSAGE",
        raw_content="This is a test case",
        metadata={},
    )

    state_snapshot = {"emotion": "neutral", "mood": 0.0}

    await decision_service._classify_intent_and_goal(event, state_snapshot)

    assert event.intent == "CHAT"
    assert event.metadata["suggested_goal"] == "ENGAGE"
    assert "tom_inferences" in event.metadata

    tom = event.metadata["tom_inferences"]
    assert tom["inferred_valence"] == 0.3
    assert tom["inferred_arousal"] == 0.6
    assert tom["implied_goals"] == []
