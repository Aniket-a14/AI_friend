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
    
    event = CognitiveEvent(event_id="1", event_type="USER_MESSAGE", raw_content="Remember my birthday", metadata={})
    state = {"emotion": "neutral", "mood": 0.0}
    
    await decision_service.decide(event, state)
    
    assert event.intent == "REMEMBER"
    assert event.metadata["suggested_goal"] == "RECALL"

@pytest.mark.asyncio
async def test_bt_traversal_chat(decision_service, mock_llm_service):
    # Mock CHAT intent
    mock_llm_service.generate.return_value = '{"intent": "CHAT", "goal": "TEASE"}'
    
    event = CognitiveEvent(event_id="2", event_type="USER_MESSAGE", raw_content="You are funny", metadata={})
    state = {"emotion": "happy", "mood": 0.5}
    
    plan = await decision_service.decide(event, state)
    
    assert plan.action_type == "RESPOND_CHAT"
    assert plan.goal == "TEASE"
    assert plan.payload["emotion_state"] == "happy"

@pytest.mark.asyncio
async def test_bt_traversal_reflect(decision_service, mock_llm_service):
    # SYSTEM_TICK usually has REFLECT intent from Perception
    event = CognitiveEvent(event_id="3", event_type="SYSTEM_TICK", raw_content="Tick", metadata={})
    event.intent = "REFLECT"
    state = {"emotion": "neutral", "mood": 0.0}
    
    plan = await decision_service.decide(event, state)
    
    assert plan.action_type == "BACKGROUND_CONSOLIDATION"
    assert plan.goal == "REFLECT"

@pytest.mark.asyncio
async def test_classification_failure_fallback(decision_service, mock_llm_service):
    # LLM returns garbage
    mock_llm_service.generate.return_value = "I don't know what you mean"
    
    event = CognitiveEvent(event_id="4", event_type="USER_MESSAGE", raw_content="What is up?", metadata={})
    event.intent = "CHAT" # Default from perception
    state = {"emotion": "neutral", "mood": 0.0}
    
    plan = await decision_service.decide(event, state)
    
    # Should fallback to default RESPOND_CHAT
    assert plan.action_type == "RESPOND_CHAT"
    assert plan.goal == "ENGAGE" # Default goal in fallback
