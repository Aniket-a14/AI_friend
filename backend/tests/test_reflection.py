import logging
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

    # Updated assertion to handle dynamic properties (extracted_at, confidence).
    # P3-11: canonicalization (LOVES -> LIKES) now happens inside
    # GraphDB.consolidate_relationship itself (see test_regressions.py's
    # test_consolidate_relationship_canonicalizes_synonyms), not in
    # ReflectionService -- mock_graph_db stands in for GraphDB here, so it
    # never runs that real code and this only confirms the safety-normalized
    # ("LOVES", uppercased) relation is what gets passed downstream.
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
async def test_identity_evolution_survives_a_list_of_non_dict_elements(
    reflection_service, mock_llm_service, caplog
):
    """A list-shaped identity suggestion whose first element isn't itself a
    dict (e.g. the LLM returns `["Logical"]` instead of `[{"new_traits": ...}]`)
    used to crash `_consolidate` with `'str' object has no attribute 'get'`,
    found via a real concurrent-load run (roadmap Phase 6.2) where contention
    made the reflection call more likely to return this malformed shape. The
    sibling fact-parsing block already re-validates each unwrapped list
    element; this asserts the identity-suggestion block does the same instead
    of crashing the whole consolidation pass."""
    mock_llm_service.generate.side_effect = [
        "[]",  # Facts (empty)
        '["Logical"]',  # Malformed: a list of strings, not of dicts
    ]

    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()

    with caplog.at_level(logging.ERROR, logger="reflection"):
        await reflection_service._consolidate(
            [{"content": "Let's build a reactor", "response": "Logic first."}]
        )

    reflection_service.identity.evolve_persona.assert_not_called()
    # The crash this regression guards against is caught by _consolidate's
    # own try/except, so evolve_persona not being called is true either way
    # (bug or fix) -- the log line is the only observable difference between
    # "cleanly skipped a malformed suggestion" and "crashed and swallowed it".
    assert not any(
        "Identity evolution failure" in record.message for record in caplog.records
    ), (
        "malformed identity suggestion crashed _consolidate instead of being skipped cleanly"
    )


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


@pytest.mark.asyncio
async def test_repeated_fact_is_reinforced_not_skipped(
    reflection_service, mock_llm_service, mock_graph_db
):
    """P2-13: `_consolidate` used to MATCH for an existing relationship and
    `continue` on a hit, logging "Fact RESOLVED" and never writing anything -
    so a restated fact never reinforced its edge weight, while
    `decay_relationships` still pushed every edge toward the prune threshold
    regardless of repetition. `create_triplet` must be called every time the
    same fact is extracted, so `consolidate_relationship`'s own `ON MATCH SET
    r.weight = coalesce(r.weight, 1) + 1` actually runs on a repeat instead
    of being unreachable.
    """
    # _consolidate makes three sequential self.llm.generate calls per
    # invocation (facts, identity suggestion, episodic summary) - all six
    # must be supplied since the mock's side_effect iterator is shared
    # across both calls below.
    mock_llm_service.generate.side_effect = [
        '[{"subject": "User", "relation": "LIKES", "object": "Tea", "confidence": 0.9}]',
        "{}",
        "We talked about tea.",
        '[{"subject": "User", "relation": "LIKES", "object": "Tea", "confidence": 0.9}]',
        "{}",
        "We talked about tea again.",
    ]

    await reflection_service._consolidate(
        [{"content": "I like tea", "response": "Noted."}]
    )
    await reflection_service._consolidate(
        [{"content": "I still like tea", "response": "Noted again."}]
    )

    assert mock_graph_db.create_triplet.call_count == 2
    mock_graph_db.create_triplet.assert_called_with(
        "User",
        "LIKES",
        "Tea",
        properties=ANY,
        subject_label="Entity",
        target_label="Entity",
    )


@pytest.mark.asyncio
async def test_unsafe_relation_is_skipped_and_logged_before_reaching_the_graph(
    reflection_service, mock_llm_service, mock_graph_db, caplog
):
    """The pre-flight `GraphDB._safe_relation` check in `_consolidate` exists
    so an unsafe relation string is skipped-and-logged here, rather than
    raising ValueError from deep inside consolidate_relationship with no
    context about which extracted fact caused it. P3-11 moved
    canonicalization (LIKES/ENJOYS/LOVES -> one type) to
    GraphDB.consolidate_relationship itself -- see test_regressions.py's
    test_consolidate_relationship_canonicalizes_synonyms for that guarantee;
    this test covers what's still this layer's job: rejecting an unsafe
    relation before any graph write is attempted.
    """
    mock_llm_service.generate.return_value = (
        '[{"subject": "User", "relation": "LIKES`) DETACH DELETE n //", '
        '"object": "Tea", "confidence": 0.9}]'
    )

    with caplog.at_level("WARNING"):
        await reflection_service._consolidate(
            [{"content": "I really enjoy tea", "response": "Noted."}]
        )

    mock_graph_db.create_triplet.assert_not_called()
    assert any("unsafe graph fact" in r.getMessage().lower() for r in caplog.records)


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
