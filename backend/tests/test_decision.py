import pytest

from app.cognitive.decision import DecisionService
from app.cognitive.perception import CognitiveEvent


@pytest.fixture
def decision_service(mock_llm_service, mock_memory_store):
    return DecisionService(llm_service=mock_llm_service, memory_store=mock_memory_store)


@pytest.mark.asyncio
async def test_intent_classification_cleaning(decision_service, mock_llm_service):
    # Test DeepSeek style response with thoughts
    mock_llm_service.generate.return_value = """
    <think>
    User wants to remember something.
    </think>
    ```json
    {"intent": "REMEMBER", "goal": "RECALL"}
    ```
    """

    event = CognitiveEvent(
        event_id="1",
        event_type="USER_MESSAGE",
        raw_content="Remember my birthday",
        metadata={},
    )
    state = {"emotion": "neutral", "mood": 0.0}

    await decision_service.decide(event, state)

    assert event.intent == "REMEMBER"
    assert event.metadata["suggested_goal"] == "RECALL"


@pytest.mark.asyncio
async def test_bt_traversal_chat(decision_service, mock_llm_service):
    # Mock CHAT intent
    mock_llm_service.generate.return_value = '{"intent": "CHAT", "goal": "TEASE"}'

    event = CognitiveEvent(
        event_id="2",
        event_type="USER_MESSAGE",
        raw_content="You are funny",
        metadata={},
    )
    state = {"emotion": "happy", "mood": 0.5}

    plan = await decision_service.decide(event, state)

    assert plan.action_type == "RESPOND_CHAT"
    assert plan.goal == "TEASE"
    assert plan.payload["emotion_state"] == "happy"


@pytest.mark.asyncio
async def test_bt_traversal_reflect(decision_service, mock_llm_service):
    # SYSTEM_TICK usually has REFLECT intent from Perception
    event = CognitiveEvent(
        event_id="3", event_type="SYSTEM_TICK", raw_content="Tick", metadata={}
    )
    event.intent = "REFLECT"
    state = {"emotion": "neutral", "mood": 0.0}

    plan = await decision_service.decide(event, state)

    assert plan.action_type == "BACKGROUND_CONSOLIDATION"
    assert plan.goal == "REFLECT"


@pytest.mark.asyncio
async def test_classification_failure_fallback(decision_service, mock_llm_service):
    # LLM returns garbage
    mock_llm_service.generate.return_value = "I don't know what you mean"

    event = CognitiveEvent(
        event_id="4", event_type="USER_MESSAGE", raw_content="What is up?", metadata={}
    )
    event.intent = "CHAT"  # Default from perception
    state = {"emotion": "neutral", "mood": 0.0}

    plan = await decision_service.decide(event, state)

    # Should fallback to default RESPOND_CHAT
    assert plan.action_type == "RESPOND_CHAT"
    assert plan.goal == "ENGAGE"  # Default goal in fallback


@pytest.mark.asyncio
async def test_intent_classification_ignores_a_second_json_block_in_the_response(
    decision_service, mock_llm_service
):
    """H1 regression: a greedy `\\{.*\\}` regex spans from the response's
    first `{` to its LAST `}`, so a model that appends a second, unrelated
    JSON-looking aside after the real answer used to produce an invalid
    combined span that failed json.loads and silently kept whatever the
    cheap keyword heuristic had already guessed instead of the LLM's actual
    classification.

    Raw content is deliberately chosen to NOT contain "remember"/"memorize",
    so the heuristic pre-classifier (`_apply_heuristic_intent_and_goal`)
    defaults to CHAT/ENGAGE - only a successfully parsed LLM response can
    produce COMMAND/TASK here, so this fails if the parse silently breaks.
    """
    mock_llm_service.generate.return_value = (
        '{"intent": "COMMAND", "goal": "TASK"}\n'
        'By the way, an example of a chat object looks like {"intent": "CHAT"}.'
    )

    event = CognitiveEvent(
        event_id="5",
        event_type="USER_MESSAGE",
        raw_content="please set a timer for five minutes",
        metadata={},
    )
    state = {"emotion": "neutral", "mood": 0.0}

    await decision_service.decide(event, state)

    assert event.intent == "COMMAND"
    assert event.metadata["suggested_goal"] == "TASK"


# --------------------------------------------------------------------------
# Phase 1B: CommunicativeIntent / BehaviorDecision attached to every plan
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_plan_carries_a_behavior_decision(decision_service, mock_llm_service):
    mock_llm_service.generate.return_value = '{"intent": "CHAT", "goal": "TEASE"}'

    event = CognitiveEvent(
        event_id="6",
        event_type="USER_MESSAGE",
        raw_content="You are funny",
        metadata={},
    )
    state = {"emotion": "happy", "mood": 0.5, "trust": 0.5, "attachment": 0.1}

    plan = await decision_service.decide(event, state)

    assert plan.behavior_decision is not None
    assert plan.behavior_decision.intent.goal == "TEASE"
    assert plan.behavior_decision.intent.act == "CHAT"


@pytest.mark.asyncio
async def test_reflect_plan_carries_a_behavior_decision(
    decision_service, mock_llm_service
):
    event = CognitiveEvent(
        event_id="7", event_type="SYSTEM_TICK", raw_content="Tick", metadata={}
    )
    event.intent = "REFLECT"
    state = {"emotion": "neutral", "mood": 0.0}

    plan = await decision_service.decide(event, state)

    assert plan.behavior_decision is not None
    assert plan.behavior_decision.intent.act == "REFLECT"


def test_relational_stance_rises_with_trust_attachment_and_mood():
    from app.cognitive.decision import _bucket_relational_stance

    cold = _bucket_relational_stance(trust=0.0, attachment=0.0, mood=-1.0)
    warm = _bucket_relational_stance(trust=1.0, attachment=1.0, mood=1.0)
    assert cold == "distant"
    assert warm == "close"


def test_relational_stance_bucketing_is_monotonic_in_trust():
    """A regression guard against a future edit that makes the bucket
    function non-monotonic (e.g. an off-by-one in the index clamp) --
    higher trust must never produce a colder-or-equal bucket ranked lower."""
    from app.cognitive.decision import _RELATIONAL_STANCES, _bucket_relational_stance

    stances = [
        _bucket_relational_stance(trust=t / 10, attachment=0.5, mood=0.0)
        for t in range(11)
    ]
    indices = [_RELATIONAL_STANCES.index(s) for s in stances]
    assert indices == sorted(indices)


def test_build_communicative_intent_reads_tom_urgency_and_state():
    from app.cognitive.decision import _build_communicative_intent

    event = CognitiveEvent(
        event_id="8",
        event_type="USER_MESSAGE",
        raw_content="help now",
        metadata={
            "suggested_goal": "PROTECT",
            "tom_inferences": {"inferred_arousal": 0.9},
        },
    )
    event.intent = "CHAT"
    blackboard = {
        "event": event,
        "state": {"trust": 0.5, "attachment": 0.1, "mood": 0.0},
    }

    intent = _build_communicative_intent(event, blackboard)

    assert intent.goal == "PROTECT"
    assert intent.urgency == pytest.approx(0.9)
    assert intent.interruption_policy == "reflex"


def test_build_communicative_intent_defaults_to_deliberative_below_threshold():
    from app.cognitive.decision import _build_communicative_intent

    event = CognitiveEvent(
        event_id="9",
        event_type="USER_MESSAGE",
        raw_content="hey",
        metadata={"tom_inferences": {"inferred_arousal": 0.3}},
    )
    event.intent = "CHAT"
    blackboard = {"event": event, "state": {}}

    intent = _build_communicative_intent(event, blackboard)

    assert intent.interruption_policy == "deliberative"
