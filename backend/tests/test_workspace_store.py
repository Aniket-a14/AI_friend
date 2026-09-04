"""Authoritative workspace persistence, CAS, and restart fencing tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.config import Config
from app.state.session_state import (
    SessionState,
    load_session_state,
    persist_session_state,
)
from app.state.workspace import (
    StaleWorkspaceError,
    WorkspaceCommand,
    WorkspaceDivergenceError,
)
from app.state.workspace_store import SQLiteWorkspaceStore


class _MemorySessionStore:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    async def set_state_var(self, key: str, value: Any) -> None:
        self.values[key] = value

    async def get_state_var(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


@pytest.mark.asyncio
async def test_workspace_initialization():
    """A new session must begin at epoch one and revision zero."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        snapshot = await store.get_snapshot("session-a")

        assert snapshot.session_id == "session-a"
        assert snapshot.epoch == 1
        assert snapshot.revision == 0
        assert snapshot.focus is None
        assert snapshot.active_goals == []
        assert snapshot.pending_action is None
        assert snapshot.affect_snapshot == {}
        assert snapshot.last_percept_id is None
        assert snapshot.updated_at > 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_cas_success():
    """Sequential commands must apply bounded deltas and advance one revision."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        initial = await store.get_snapshot("session-a")
        first = await store.commit_transition(
            WorkspaceCommand(
                session_id="session-a",
                expected_epoch=initial.epoch,
                expected_revision=initial.revision,
                percept_id="percept-1",
                focus_update="listen",
                add_goals=["help", "clarify", "help"],
                pending_action={"kind": "ASK"},
                affect_update={"valence": 0.2, "arousal": 0.4},
                command_source="test.first",
            )
        )
        second = await store.commit_transition(
            WorkspaceCommand(
                session_id="session-a",
                expected_epoch=first.epoch,
                expected_revision=first.revision,
                percept_id="percept-2",
                remove_goals=["clarify"],
                add_goals=["answer"],
                affect_update={"valence": 0.5},
                command_source="test.second",
            )
        )

        assert first.revision == 1
        assert second.revision == 2
        assert second.epoch == 1
        assert second.focus == "listen"
        assert second.active_goals == ["help", "answer"]
        assert second.pending_action == {"kind": "ASK"}
        assert second.affect_snapshot == {"valence": 0.5, "arousal": 0.4}
        assert second.last_percept_id == "percept-2"
        assert second.updated_at >= first.updated_at
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_cas_stale_revision_rejected():
    """A delayed writer must not overwrite or audit newer workspace state."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        initial = await store.get_snapshot("session-a")
        current = await store.commit_transition(
            WorkspaceCommand(
                session_id="session-a",
                expected_epoch=initial.epoch,
                expected_revision=initial.revision,
                focus_update="current",
            )
        )

        with pytest.raises(StaleWorkspaceError, match="revision is stale"):
            await store.commit_transition(
                WorkspaceCommand(
                    session_id="session-a",
                    expected_epoch=initial.epoch,
                    expected_revision=initial.revision,
                    focus_update="stale",
                )
            )

        after_rejection = await store.get_snapshot("session-a")
        transitions = await store.list_transitions("session-a")
        assert after_rejection == current
        assert len(transitions) == 1
        assert transitions[0].to_revision == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_command_can_clear_focus_and_pending_action():
    """Terminal transitions must be able to clear fields, not only retain them."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        initial = await store.get_snapshot("session-a")
        populated = await store.commit_transition(
            WorkspaceCommand(
                "session-a",
                initial.epoch,
                initial.revision,
                focus_update="active turn",
                pending_action={"action_intent": {"id": "intent-1"}},
            )
        )

        cleared = await store.commit_transition(
            WorkspaceCommand(
                "session-a",
                populated.epoch,
                populated.revision,
                clear_focus=True,
                clear_pending_action=True,
            )
        )

        assert cleared.focus is None
        assert cleared.pending_action is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_epoch_increment_rejects_prior_epoch(tmp_path):
    """A restarted owner must fence commands retained by the prior process."""
    db_path = tmp_path / "workspace.db"
    prior_store = SQLiteWorkspaceStore(db_path)
    restarted_store = SQLiteWorkspaceStore(db_path)
    try:
        initial = await prior_store.get_snapshot("session-a")
        before_restart = await prior_store.commit_transition(
            WorkspaceCommand(
                session_id="session-a",
                expected_epoch=initial.epoch,
                expected_revision=initial.revision,
                percept_id="percept-before-restart",
                focus_update="unfinished work",
                add_goals=["resume me"],
                pending_action={"intent_id": "intent-1"},
                affect_update={"valence": 0.5, "arousal": 0.8},
            )
        )
        stale_command = WorkspaceCommand(
            session_id="session-a",
            expected_epoch=before_restart.epoch,
            expected_revision=before_restart.revision,
            focus_update="old worker overwrite",
        )

        restarted = await restarted_store.increment_epoch("session-a")

        assert restarted.epoch == before_restart.epoch + 1
        assert restarted.revision == 0
        assert restarted.focus == "unfinished work"
        assert restarted.active_goals == ["resume me"]
        assert restarted.pending_action == {"intent_id": "intent-1"}
        assert restarted.affect_snapshot == {"valence": 0.5, "arousal": 0.8}
        assert restarted.last_percept_id == "percept-before-restart"
        with pytest.raises(StaleWorkspaceError, match="epoch is stale"):
            await prior_store.commit_transition(stale_command)
        assert await restarted_store.get_snapshot("session-a") == restarted
    finally:
        await prior_store.close()
        await restarted_store.close()


@pytest.mark.asyncio
async def test_workspace_epoch_metadata_divergence_is_typed_as_stale():
    """Epoch metadata corruption must remain catchable as a stale workspace error."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        await store.get_snapshot("session-a")
        with store._lock:
            store._connection.execute(
                "UPDATE workspace_epoch SET current_epoch = 2 WHERE session_id = ?",
                ("session-a",),
            )
            store._connection.commit()

        with pytest.raises(WorkspaceDivergenceError):
            await store.get_snapshot("session-a")
        assert issubclass(WorkspaceDivergenceError, StaleWorkspaceError)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_first_startup_epoch_is_one():
    """Startup on an unseen session must create epoch one, not skip a generation."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        started = await store.increment_epoch("session-a")

        assert started.epoch == 1
        assert started.revision == 0
        assert await store.get_snapshot("session-a") == started
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_concurrency_race():
    """Twenty writers on one revision must produce one winner, never lost updates."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        initial = await store.get_snapshot("session-a")
        commands = [
            WorkspaceCommand(
                session_id="session-a",
                expected_epoch=initial.epoch,
                expected_revision=initial.revision,
                focus_update=f"writer-{index}",
                command_source=f"race.{index}",
            )
            for index in range(20)
        ]

        results = await asyncio.gather(
            *(store.commit_transition(command) for command in commands),
            return_exceptions=True,
        )

        successes = [result for result in results if not isinstance(result, Exception)]
        stale = [
            result for result in results if isinstance(result, StaleWorkspaceError)
        ]
        final = await store.get_snapshot("session-a")
        transitions = await store.list_transitions("session-a")
        assert len(successes) == 1
        assert len(stale) == 19
        assert final.revision == 1
        assert final.focus == successes[0].focus
        assert len(transitions) == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_two_connections_share_atomic_cas(tmp_path):
    """SQLite, not only an object-local lock, must fence a second process handle."""
    db_path = tmp_path / "workspace.db"
    left = SQLiteWorkspaceStore(db_path)
    right = SQLiteWorkspaceStore(db_path)
    try:
        initial = await left.get_snapshot("session-a")
        left_command = WorkspaceCommand(
            "session-a", initial.epoch, initial.revision, focus_update="left"
        )
        right_command = WorkspaceCommand(
            "session-a", initial.epoch, initial.revision, focus_update="right"
        )

        results = await asyncio.gather(
            left.commit_transition(left_command),
            right.commit_transition(right_command),
            return_exceptions=True,
        )

        assert sum(not isinstance(result, Exception) for result in results) == 1
        assert sum(isinstance(result, StaleWorkspaceError) for result in results) == 1
        assert (await left.get_snapshot("session-a")).revision == 1
    finally:
        await left.close()
        await right.close()


@pytest.mark.asyncio
async def test_workspace_transition_audit():
    """Every accepted command must retain its exact revision and causal metadata."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        snapshot = await store.get_snapshot("session-a")
        for revision in range(2):
            snapshot = await store.commit_transition(
                WorkspaceCommand(
                    session_id="session-a",
                    expected_epoch=snapshot.epoch,
                    expected_revision=snapshot.revision,
                    percept_id=f"percept-{revision}",
                    command_source=f"source-{revision}",
                )
            )

        transitions = await store.list_transitions("session-a")

        assert [item.from_revision for item in transitions] == [0, 1]
        assert [item.to_revision for item in transitions] == [1, 2]
        assert [item.epoch for item in transitions] == [1, 1]
        assert [item.command_source for item in transitions] == [
            "source-0",
            "source-1",
        ]
        assert [item.percept_id for item in transitions] == [
            "percept-0",
            "percept-1",
        ]
        assert len({item.transition_id for item in transitions}) == 2
        assert all(item.timestamp > 0 for item in transitions)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_snapshot_mutation_cannot_change_persisted_state():
    """Mutable containers in the frozen contract must still be detached values."""
    store = SQLiteWorkspaceStore(":memory:")
    try:
        initial = await store.get_snapshot("session-a")
        snapshot = await store.commit_transition(
            WorkspaceCommand(
                "session-a",
                initial.epoch,
                initial.revision,
                add_goals=["original"],
                pending_action={"nested": {"value": "original"}},
                affect_update={"valence": 0.1},
            )
        )

        snapshot.active_goals.append("injected")
        assert snapshot.pending_action is not None
        snapshot.pending_action["nested"]["value"] = "injected"
        snapshot.affect_snapshot["valence"] = 1.0

        persisted = await store.get_snapshot("session-a")
        assert persisted.active_goals == ["original"]
        assert persisted.pending_action == {"nested": {"value": "original"}}
        assert persisted.affect_snapshot == {"valence": 0.1}
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_session_state_dual_write_flag_off_preserves_legacy_behavior(monkeypatch):
    """Supplying a workspace store must be inert while migration is disabled."""
    monkeypatch.setattr(Config, "WORKSPACE_AUTHORITATIVE", False, raising=False)
    legacy_store = _MemorySessionStore()
    workspace_store = SQLiteWorkspaceStore(":memory:")
    session_state = SessionState.start_turn("turn-a", "utterance-a", speculative=True)
    try:
        await persist_session_state(legacy_store, session_state, workspace_store)

        assert await load_session_state(legacy_store, workspace_store) == session_state
        snapshot = await workspace_store.get_snapshot("turn-a")
        assert snapshot.revision == 0
        assert await workspace_store.list_transitions("turn-a") == []
    finally:
        await workspace_store.close()


@pytest.mark.asyncio
async def test_session_state_dual_write_flag_on_round_trips_workspace(monkeypatch):
    """Enabled migration must persist legacy state under an explicit workspace ID."""
    monkeypatch.setattr(Config, "WORKSPACE_AUTHORITATIVE", True, raising=False)
    legacy_store = _MemorySessionStore()
    workspace_store = SQLiteWorkspaceStore(":memory:")
    session_state = SessionState.start_turn("turn-a", "utterance-a", speculative=True)
    session_state.active_interruption = "duck"
    try:
        await persist_session_state(
            legacy_store,
            session_state,
            workspace_store,
            workspace_session_id="conversation-a",
        )
        legacy_store.values.clear()

        loaded = await load_session_state(
            legacy_store,
            workspace_store,
            workspace_session_id="conversation-a",
        )
        snapshot = await workspace_store.get_snapshot("conversation-a")

        assert loaded == session_state
        assert snapshot.revision == 1
        assert snapshot.focus == "turn-a"
        assert snapshot.last_percept_id == "utterance-a"
        assert snapshot.pending_action == {
            "legacy_session_state": session_state.to_dict()
        }
        transitions = await workspace_store.list_transitions("conversation-a")
        assert len(transitions) == 1
        assert transitions[0].command_source == "session_state.dual_write"
    finally:
        await workspace_store.close()


@pytest.mark.asyncio
async def test_session_state_dual_write_preserves_existing_action_intent(monkeypatch):
    """Mirroring legacy state must not erase the authoritative action namespace."""
    monkeypatch.setattr(Config, "WORKSPACE_AUTHORITATIVE", True, raising=False)
    legacy_store = _MemorySessionStore()
    workspace_store = SQLiteWorkspaceStore(":memory:")
    try:
        initial = await workspace_store.get_snapshot("conversation-a")
        await workspace_store.commit_transition(
            WorkspaceCommand(
                "conversation-a",
                initial.epoch,
                initial.revision,
                pending_action={"action_intent": {"id": "intent-1"}},
            )
        )
        session_state = SessionState.start_turn("turn-a", "utterance-a")

        await persist_session_state(
            legacy_store,
            session_state,
            workspace_store,
            workspace_session_id="conversation-a",
        )

        snapshot = await workspace_store.get_snapshot("conversation-a")
        assert snapshot.pending_action == {
            "action_intent": {"id": "intent-1"},
            "legacy_session_state": session_state.to_dict(),
        }
    finally:
        await workspace_store.close()


@pytest.mark.asyncio
async def test_session_state_dual_write_retries_after_cas_race(monkeypatch):
    """A concurrent workspace writer must be retried before legacy fallback."""
    monkeypatch.setattr(Config, "WORKSPACE_AUTHORITATIVE", True, raising=False)

    class _RaceOnceWorkspaceStore:
        def __init__(self, inner: SQLiteWorkspaceStore) -> None:
            self.inner = inner
            self.get_count = 0
            self.commit_count = 0
            self.raced = False

        async def get_snapshot(self, session_id: str):
            self.get_count += 1
            return await self.inner.get_snapshot(session_id)

        async def commit_transition(self, command: WorkspaceCommand):
            self.commit_count += 1
            if not self.raced:
                self.raced = True
                current = await self.inner.get_snapshot(command.session_id)
                await self.inner.commit_transition(
                    WorkspaceCommand(
                        command.session_id,
                        current.epoch,
                        current.revision,
                        pending_action={"action_intent": {"id": "intent-1"}},
                        command_source="test.concurrent-writer",
                    )
                )
                raise StaleWorkspaceError("simulated CAS race")
            return await self.inner.commit_transition(command)

    legacy_store = _MemorySessionStore()
    inner_store = SQLiteWorkspaceStore(":memory:")
    workspace_store = _RaceOnceWorkspaceStore(inner_store)
    session_state = SessionState.start_turn("turn-a", "utterance-a")
    try:
        await persist_session_state(
            legacy_store,
            session_state,
            workspace_store,
            workspace_session_id="conversation-a",
        )

        snapshot = await inner_store.get_snapshot("conversation-a")
        assert workspace_store.get_count == 2
        assert workspace_store.commit_count == 2
        assert snapshot.revision == 2
        assert snapshot.pending_action == {
            "action_intent": {"id": "intent-1"},
            "legacy_session_state": session_state.to_dict(),
        }
        assert legacy_store.values["session_state"] == session_state.to_dict()
    finally:
        await inner_store.close()


@pytest.mark.asyncio
async def test_session_state_workspace_fallback_uses_stable_id_and_warns(
    monkeypatch, caplog
):
    """Missing IDs must be visible and must not create one workspace per turn."""
    monkeypatch.setattr(Config, "WORKSPACE_AUTHORITATIVE", True, raising=False)
    legacy_store = _MemorySessionStore()
    workspace_store = SQLiteWorkspaceStore(":memory:")
    try:
        with caplog.at_level("WARNING", logger="app.state.session_state"):
            first = SessionState.start_turn("turn-a")
            second = SessionState.start_turn("turn-b")
            await persist_session_state(legacy_store, first, workspace_store)
            await persist_session_state(legacy_store, second, workspace_store)

        assert caplog.text.count("workspace_session_id was not supplied") == 2
        stable = await workspace_store.get_snapshot("default")
        assert stable.revision == 2
        assert stable.focus == "turn-b"
        assert await workspace_store.list_transitions("turn-a") == []
        assert await workspace_store.list_transitions("turn-b") == []
    finally:
        await workspace_store.close()
