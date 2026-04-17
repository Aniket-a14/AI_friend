import pytest
from unittest.mock import MagicMock, AsyncMock
from app.cognitive.learning import ReflectionService

@pytest.fixture
def reflection_service(mock_llm_service, mock_graph_db):
    return ReflectionService(llm_service=mock_llm_service, graph_store=mock_graph_db)

@pytest.mark.asyncio
async def test_fact_consolidation(reflection_service, mock_llm_service, mock_graph_db):
    # Mock LLM returning facts
    mock_llm_service.generate.side_effect = [
        '[{"subject": "User", "relation": "LOVES", "object": "Coding", "type": "Interest"}]', # Facts
        '{}' # Identity suggestions (empty for this test)
    ]
    
    episodes = [{"content": "I love coding", "response": "That is cool"}]
    
    # We need to wait for the task to finish since it's an asyncio task
    # For testing, we can directly call _consolidate
    await reflection_service._consolidate(episodes)
    
    mock_graph_db.create_relationship.assert_called_with(
        "User", "Interest", "LOVES", "Coding", "Entity"
    )

@pytest.mark.asyncio
async def test_identity_evolution_trigger(reflection_service, mock_llm_service):
    # Mock LLM suggesting a persona change
    mock_llm_service.generate.side_effect = [
        '[]', # Facts (empty)
        '{"new_traits": ["Logical"], "relationship": "Technical Partner"}' # Suggestion
    ]
    
    # Mock the IdentityManager inside the service
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()
    
    await reflection_service._consolidate([{"content": "Let's build a reactor", "response": "Logic first."}])
    
    reflection_service.identity.evolve_persona.assert_called()
    args = reflection_service.identity.evolve_persona.call_args[0][0]
    assert "Logical" in args["new_traits"]
    assert args["relationship"] == "Technical Partner"

def test_json_extraction_robustness(reflection_service):
    # Test typical "Chatty" LLM response
    mixed_text = "Here is the data: ```json\n{\"key\": \"value\"}\n``` Hope this helps!"
    data = reflection_service._extract_json(mixed_text)
    assert data["key"] == "value"
    
    # Test DeepSeek thought exclusion
    deepseek_text = "<think>Thoughts</think>{\"a\": 1}"
    data = reflection_service._extract_json(deepseek_text)
    assert data["a"] == 1
