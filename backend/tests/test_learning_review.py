from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.learning import ReflectionService
from app.cognitive.learning_review import LearningProposal, LearningReviewQueue
from app.config import Config


@pytest.fixture
def reflection_service(mock_llm_service, mock_graph_db):
    return ReflectionService(llm_service=mock_llm_service, graph_store=mock_graph_db)


def test_submit_adds_to_pending():
    queue = LearningReviewQueue()
    queue.submit({"relationship": "Trusted Friend"})
    assert len(queue.pending()) == 1


def test_contradicts_id_flags_the_proposal():
    """A proposal that conflicts with a confirmed memory must be visible to
    a reviewer as a contradiction, not silently mixed in with clean ones."""
    queue = LearningReviewQueue()
    queue.submit({"relationship": "Stranger"}, contradicts_id="mem-123")
    queue.submit({"relationship": "Friend"})

    flagged = queue.contradictions()
    assert len(flagged) == 1
    assert flagged[0].contradicts_id == "mem-123"
    assert flagged[0].is_contradiction


@pytest.mark.asyncio
async def test_approve_applies_via_identity_manager_and_stamps_evolved_learnings():
    queue = LearningReviewQueue()
    proposal = queue.submit({"relationship": "Trusted Friend"})
    identity = MagicMock()
    identity.evolve_persona = AsyncMock()
    identity.history = {}

    applied = await queue.approve(proposal.id, identity)

    identity.evolve_persona.assert_called_once_with({"relationship": "Trusted Friend"})
    assert applied.id == proposal.id
    assert queue.pending() == []
    assert "evolved_learnings" in identity.history


@pytest.mark.asyncio
async def test_approve_persists_evolved_learnings_before_evolve_persona_saves():
    """Codex Stage 2 blocker: stamping evolved_learnings AFTER evolve_persona()
    already saved/persisted lost the marker on restart. evolve_persona() must
    see the stamp already in history when it runs its own save."""
    queue = LearningReviewQueue()
    proposal = queue.submit({"relationship": "Trusted Friend"})
    identity = MagicMock()
    identity.history = {}
    seen = {}

    async def _evolve_persona(_suggestions):
        seen["evolved_learnings"] = identity.history.get("evolved_learnings")

    identity.evolve_persona = AsyncMock(side_effect=_evolve_persona)

    await queue.approve(proposal.id, identity)

    assert seen["evolved_learnings"] is not None


@pytest.mark.asyncio
async def test_approve_unknown_id_does_not_apply_anything():
    queue = LearningReviewQueue()
    identity = MagicMock()
    identity.evolve_persona = AsyncMock()

    assert await queue.approve("nonexistent", identity) is None
    identity.evolve_persona.assert_not_called()


def test_reject_removes_without_applying():
    queue = LearningReviewQueue()
    proposal = queue.submit({"relationship": "Trusted Friend"})

    rejected = queue.reject(proposal.id)

    assert rejected.id == proposal.id
    assert queue.pending() == []


def test_proposal_without_contradiction_is_not_flagged():
    proposal = LearningProposal(suggestions={"new_traits": ["Curious"]})
    assert proposal.contradicts_id is None
    assert not proposal.is_contradiction


@pytest.mark.asyncio
async def test_legacy_config_still_auto_applies_directly(
    reflection_service, mock_llm_service, monkeypatch
):
    """Regression guard: with LEARNING_REVIEW_REQUIRED explicitly False (no
    longer the Phase 07 default -- see test_review_required_routes_to_queue_
    instead_of_auto_applying for the now-default-True path), a
    high-confidence suggestion must still reach `evolve_persona` exactly as
    it did before this phase -- mirrors
    test_reflection.py::test_identity_evolution_trigger."""
    monkeypatch.setattr(Config, "LEARNING_REVIEW_REQUIRED", False)
    mock_llm_service.generate.side_effect = [
        "[]",
        '{"new_traits": ["Logical"], "relationship": "Technical Partner", "confidence": 0.9}',
    ]
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()

    await reflection_service._consolidate(
        [{"content": "Let's build a reactor", "response": "Logic first."}]
    )

    reflection_service.identity.evolve_persona.assert_called_once()
    assert reflection_service.review_queue.pending() == []


@pytest.mark.asyncio
async def test_review_required_routes_to_queue_instead_of_auto_applying(
    reflection_service, mock_llm_service, monkeypatch
):
    """When the gate is on, a matching suggestion must wait for review, and
    never touch the identity manager directly -- otherwise the review queue
    is decorative and the safety property it exists for does not hold."""
    monkeypatch.setattr(Config, "LEARNING_REVIEW_REQUIRED", True)
    mock_llm_service.generate.side_effect = [
        "[]",
        '{"new_traits": ["Logical"], "relationship": "Technical Partner", "confidence": 0.9}',
    ]
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()
    reflection_service.vector = None

    await reflection_service._consolidate(
        [{"content": "Let's build a reactor", "response": "Logic first."}]
    )

    reflection_service.identity.evolve_persona.assert_not_called()
    pending = reflection_service.review_queue.pending()
    assert len(pending) == 1
    assert pending[0].suggestions["relationship"] == "Technical Partner"


@pytest.mark.asyncio
async def test_review_required_records_a_governed_proposal_alongside_the_legacy_queue(
    reflection_service, mock_llm_service, monkeypatch
):
    """Phase 07: an ordinary, non-protected suggestion must also register
    as a real, approved `LearningGovernor` proposal (Section 21's audit
    trail) -- not just land in the legacy `review_queue` as before."""
    monkeypatch.setattr(Config, "LEARNING_REVIEW_REQUIRED", True)
    mock_llm_service.generate.side_effect = [
        "[]",
        '{"new_traits": ["Logical"], "relationship": "Technical Partner", "confidence": 0.9}',
    ]
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()
    reflection_service.vector = None

    await reflection_service._consolidate(
        [{"content": "Let's build a reactor", "response": "Logic first."}]
    )

    proposals = reflection_service.governor.list_proposals()
    assert len(proposals) == 1
    assert proposals[0].status.value == "APPROVED"
    assert proposals[0].target_domain == "identity.reflection_persona_suggestion"

    # Fix round (P7-FIX-05): the governor's audited payload must describe
    # exactly the value the review queue actually holds for approval/apply
    # -- a renamed or otherwise altered governor copy would make the audit
    # record inaccurate even though the queue applies something else.
    pending = reflection_service.review_queue.pending()
    assert len(pending) == 1
    assert proposals[0].proposed_value == pending[0].suggestions
    assert proposals[0].proposed_value["new_traits"] == ["Logical"]


@pytest.mark.asyncio
async def test_review_required_rejects_a_suggestion_smuggling_a_protected_field(
    reflection_service, mock_llm_service, monkeypatch
):
    """Section 21's hard invariant: a reflection suggestion that names a
    CONSTITUTIONAL-tier field (here `mood_decay_rate`) must never reach the
    human review queue at all, regardless of its confidence score -- the
    identity core and safety boundaries are never learned, by any source."""
    monkeypatch.setattr(Config, "LEARNING_REVIEW_REQUIRED", True)
    mock_llm_service.generate.side_effect = [
        "[]",
        '{"relationship": "Technical Partner", "mood_decay_rate": 0.0, "confidence": 0.9}',
    ]
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.evolve_persona = AsyncMock()
    reflection_service.vector = None

    await reflection_service._consolidate(
        [{"content": "Let's build a reactor", "response": "Logic first."}]
    )

    reflection_service.identity.evolve_persona.assert_not_called()
    assert reflection_service.review_queue.pending() == []
    assert reflection_service.governor.list_proposals() == []


@pytest.mark.asyncio
async def test_review_required_flags_a_contradicting_proposal(
    reflection_service, mock_llm_service, monkeypatch
):
    """Uses Phase 2C's find_contradiction to link a proposal that conflicts
    with an existing confirmed memory, so a reviewer sees it flagged rather
    than mixed in with ordinary proposals."""
    monkeypatch.setattr(Config, "LEARNING_REVIEW_REQUIRED", True)
    mock_llm_service.generate.side_effect = [
        "[]",
        '{"relationship": "Stranger", "confidence": 0.9}',
    ]
    reflection_service.identity = MagicMock()
    reflection_service.identity.personality = {"name": "my friend"}
    reflection_service.identity.history = {"relationship": "Friend"}
    reflection_service.identity.persona.name = "my friend"
    reflection_service.identity.evolve_persona = AsyncMock()
    reflection_service.vector = MagicMock()
    reflection_service.vector.find_contradiction = AsyncMock(
        return_value={"id": "mem-999"}
    )

    await reflection_service._consolidate(
        [{"content": "We're basically strangers now", "response": "I see."}]
    )

    flagged = reflection_service.review_queue.contradictions()
    assert len(flagged) == 1
    assert flagged[0].contradicts_id == "mem-999"
    reflection_service.vector.find_contradiction.assert_called_once_with(
        "Stranger", "my friend"
    )
