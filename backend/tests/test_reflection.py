from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from app.cognitive.learning import ReflectionService


@pytest.fixture
def reflection_service(mock_llm_service, mock_graph_db):
    return ReflectionService(llm_service=mock_llm_service, graph_store=mock_graph_db)


@pytest.mark.asyncio
async def test_fact_consolidation(reflection_service, mock_llm_service, mock_graph_db):
    # Mock LLM returning facts with MANDATORY Confidence Gating (>0.8)
    mock_llm_service.generate.side_effect = [
        '[{"subject": "User", "relation": "LOVES", "object": "Coding", "type": "Interest", "confidence": 0.9, "reason": "Explicit stated preference"}]',  # Facts
        "{}",  # Identity suggestions (empty for this test)
    ]

    episodes = [{"content": "I love coding", "response": "That is cool"}]

    # We need to wait for the task to finish since it's an asyncio task
    # For testing, we can directly call _consolidate
    await reflection_service._consolidate(episodes)

    # Updated assertion to handle dynamic properties (extracted_at, confidence)
    mock_graph_db.create_triplet.assert_called_with(
        "User",
        "LOVES",
        "Coding",
        properties=ANY,
        subject_label="Entity",
        target_label="Entity",
    )


@pytest.mark.asyncio
async def test_identity_evolution_trigger(reflection_service, mock_llm_service):
    # Mock LLM suggesting a persona change with Confidence Gating
    mock_llm_service.generate.side_effect = [
        "[]",  # Facts (empty)
        '{"new_traits": ["Logical"], "relationship": "Technical Partner", "confidence": 0.9}',  # Suggestion
    ]

    # Mock the IdentityManager inside the service
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()

    await reflection_service._consolidate(
        [{"content": "Let's build a reactor", "response": "Logic first."}]
    )

    reflection_service.identity.evolve_persona.assert_called()
    args = reflection_service.identity.evolve_persona.call_args[0][0]
    assert "Logical" in args["new_traits"]
    assert args["relationship"] == "Technical Partner"


@pytest.mark.asyncio
async def test_fact_rejection_low_confidence(
    reflection_service, mock_llm_service, mock_graph_db
):
    """Verify that facts with confidence < 0.8 are mathematically rejected."""
    mock_llm_service.generate.return_value = '[{"subject": "User", "relation": "LIKES", "object": "Spam", "confidence": 0.3}]'

    await reflection_service._consolidate(
        [{"content": "Spam is okay i guess", "response": "?"}]
    )

    mock_graph_db.create_triplet.assert_not_called()


def test_json_extraction_robustness(reflection_service):
    # Test typical "Chatty" LLM response
    mixed_text = 'Here is the data: ```json\n{"key": "value"}\n``` Hope this helps!'
    data = reflection_service._extract_json(mixed_text)
    assert data["key"] == "value"

    # Test DeepSeek thought exclusion
    deepseek_text = '<think>Thoughts</think>{"a": 1}'
    data = reflection_service._extract_json(deepseek_text)
    assert data["a"] == 1


def test_json_extraction_does_not_fuse_two_separate_blocks(reflection_service):
    """H1 regression: a greedy `\\{.*\\}`/`\\[.*\\]` regex spans from the
    first opening bracket to the LAST closing bracket anywhere in the text,
    so a real answer followed by an unrelated second JSON-looking aside used
    to be fused into one invalid span and silently dropped."""
    text = '{"subject": "User"} and separately here is an example: {"unrelated": true}'
    data = reflection_service._extract_json(text)
    assert data == {"subject": "User"}
