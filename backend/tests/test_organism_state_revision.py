"""Phase 2A: `AgentState.revision`/`writer_id` and the compare-and-swap guard
in `apply_external_state`.

Two `StateService` instances exist per deployment (brain_agent, subconscious_
agent), each mutating its own `AgentState` and syncing via `state.broadcast`.
Before this, `apply_external_state` applied every broadcast unconditionally,
so a broadcast that arrived out of order (no ordering guarantee across NATS
delivery) could silently overwrite a fresher local appraisal with a stale one.
"""

import pytest

from app.state.agent_state import StateService


@pytest.fixture
def state_service(mock_graph_db):
    service = StateService(
        graph_store=mock_graph_db, db_path=":memory:", writer_id="brain_agent"
    )
    service.redis_client = None
    return service


@pytest.mark.asyncio
async def test_persist_state_increments_revision_monotonically(state_service):
    assert state_service.current_state.revision == 0

    await state_service.persist_state()
    assert state_service.current_state.revision == 1
    assert state_service.current_state.writer_id == "brain_agent"

    await state_service.persist_state()
    assert state_service.current_state.revision == 2


@pytest.mark.asyncio
async def test_apply_external_state_rejects_stale_broadcast(state_service):
    """A broadcast carrying an older revision than what this process already
    has must not overwrite the newer local state -- this is the actual
    failure a naive unconditional-apply would produce under out-of-order
    delivery."""
    state_service.current_state.revision = 5
    state_service.current_state.mood = 0.9

    await state_service.apply_external_state(
        {"revision": 3, "writer_id": "subconscious_agent", "mood": -0.9}
    )

    # Rejected wholesale: mood is untouched, not partially merged.
    assert state_service.current_state.mood == 0.9
    assert state_service.current_state.revision == 5


@pytest.mark.asyncio
async def test_apply_external_state_accepts_newer_broadcast(state_service):
    state_service.current_state.revision = 2
    state_service.current_state.mood = 0.1

    await state_service.apply_external_state(
        {"revision": 3, "writer_id": "subconscious_agent", "mood": 0.7}
    )

    assert state_service.current_state.mood == 0.7
    assert state_service.current_state.revision == 3
    assert state_service.current_state.writer_id == "subconscious_agent"


@pytest.mark.asyncio
async def test_apply_external_state_equal_revision_different_writer_logs_and_applies(
    state_service, caplog
):
    """§18 Experiment 3's ambiguous case: two writers producing the same
    revision number. Not silently resolved -- applied, but logged distinctly
    so the ambiguity is visible rather than hidden."""
    state_service.current_state.revision = 4
    state_service.current_state.writer_id = "brain_agent"
    state_service.current_state.mood = 0.1

    with caplog.at_level("WARNING"):
        await state_service.apply_external_state(
            {"revision": 4, "writer_id": "subconscious_agent", "mood": 0.5}
        )

    assert state_service.current_state.mood == 0.5
    assert any(
        "Equal-revision write conflict" in record.message for record in caplog.records
    )


@pytest.mark.asyncio
async def test_apply_external_state_missing_revision_is_backward_compatible(
    state_service,
):
    """A broadcast with no `revision` key at all (e.g. from code that hasn't
    picked up this change, or a hand-built test payload) must still apply --
    this is not a case the CAS guard has evidence to reject."""
    state_service.current_state.revision = 5
    state_service.current_state.mood = 0.1

    await state_service.apply_external_state({"mood": 0.6})

    assert state_service.current_state.mood == 0.6
    # revision/writer_id untouched when the broadcast doesn't carry them
    assert state_service.current_state.revision == 5


@pytest.mark.asyncio
async def test_persist_state_writer_id_defaults_empty_when_unset(mock_graph_db):
    """A `StateService` built without an explicit `writer_id` (tests, ad hoc
    scripts) still increments revision and stamps an empty writer_id, rather
    than erroring."""
    service = StateService(graph_store=mock_graph_db, db_path=":memory:")
    service.redis_client = None

    await service.persist_state()

    assert service.current_state.revision == 1
    assert service.current_state.writer_id == ""
