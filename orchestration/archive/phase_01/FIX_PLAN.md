# Phase 01: Peer Review Arbitration & Fix Plan

**Phase:** `PHASE_01` - Authoritative Causal Slice  
**Arbiter:** Gemini (Orchestrator)  
**Date:** 2026-09-04  
**Input Reviews:**
- `orchestration/PHASE_01/CLAUDE_REVIEW_OF_CODEX.md` (by Claude)
- `orchestration/PHASE_01/CODEX_REVIEW_OF_CLAUDE.md` (by Codex)

---

## 1. Executive Arbitration Summary

Both peer reviews were rigorous, identifying real architectural seams and edge cases.
- **Claude's Review of Codex:** 7 findings (0 Blocker, 1 High, 3 Medium, 1 Low, 2 Nit). Core store is sound; defects are in the dual-write adapter and contract clear-semantics.
- **Codex's Review of Claude:** 7 findings (3 Blocker, 2 High, 2 Medium). Identified critical live-wiring gaps: missing percept/workspace threading in `core.py`, transport-agent missing `completed=True` playback events, non-persistent outcome records, and NaN confidence clamping.

All valid findings are arbitrated below and assigned back to their original owners.

---

## 2. Itemized Arbitration & Fix Assignments

### Part A: Fixes Assigned to Codex (in `ai-friend-codex`)

| ID | Origin | Severity | Finding Summary | Decision | Required Fix | Validation Requirement |
|---|---|---|---|---|---|---|
| **FIX-CDX-01** | Claude Finding 1 | MEDIUM | `WorkspaceCommand` cannot clear `focus` or `pending_action` to `None` | **ACCEPT** | In `backend/app/state/workspace.py` and `workspace_store.py`: Add `clear_focus: bool = False` and `clear_pending_action: bool = False` to `WorkspaceCommand`. In `_apply_command`, if `clear_pending_action` is True, set `pending_action = None`. | Add test in `test_workspace_store.py` verifying clearing fields to None. |
| **FIX-CDX-02** | Claude Finding 2 | HIGH | `session_state.py` dual-write CAS race raises unhandled `StaleWorkspaceError` | **ACCEPT** | In `backend/app/state/session_state.py`: Wrap `_persist_workspace_session_state` in a bounded retry loop (up to 3 attempts) that re-fetches the latest snapshot and retries before logging warning and falling back. | Add concurrency test in `test_workspace_store.py` simulating race during dual-write. |
| **FIX-CDX-03** | Claude Finding 3 | MEDIUM | `pending_action["legacy_session_state"]` clobbers real `ActionIntent` | **ACCEPT** | In `session_state.py` and `workspace_store.py`: Namespace legacy payload under a dedicated dict key `legacy_session_state` and preserve existing keys in `pending_action` rather than replacing the entire dictionary. | Add test verifying `pending_action` with existing `action_intent` preserves it during session state sync. |
| **FIX-CDX-04** | Claude Finding 4 | MEDIUM | `workspace_session_id` falls back to per-turn `turn_id` silently | **ACCEPT** | In `session_state.py`: If `workspace_session_id` is not passed, log a warning and use a designated session identifier rather than silently creating a fresh single-turn workspace row every turn. | Unit test verifying warning and stable session ID handling. |
| **FIX-CDX-05** | Claude Finding 6 | NIT | Epoch-restart test omits non-empty `affect_snapshot` | **ACCEPT** | In `backend/tests/test_workspace_store.py`: In `test_workspace_epoch_increment_rejects_prior_epoch`, populate `affect_update={"valence": 0.5, "arousal": 0.8}` and assert it survives the restart. | Test passes with non-empty affect assertions. |
| **FIX-CDX-06** | Claude Finding 7 | NIT | Untyped `RuntimeError` on epoch divergence | **ACCEPT** | In `backend/app/state/workspace.py`: Define `WorkspaceDivergenceError(StaleWorkspaceError)` and raise it instead of bare `RuntimeError`. | Catchable by `StaleWorkspaceError`. |

---

### Part B: Fixes Assigned to Claude (in `ai-friend-claude`)

| ID | Origin | Severity | Finding Summary | Decision | Required Fix | Validation Requirement |
|---|---|---|---|---|---|---|
| **FIX-CLD-01** | Codex Finding 1 | BLOCKER | Production turns never thread percept or workspace revision into `pipeline.execute()` | **ACCEPT** | In `backend/app/cognitive/core.py`: Update `CognitiveService.process_event` to accept `percept: PerceptEnvelope | None = None` and `workspace: WorkspaceSnapshotLike | None = None`, and forward them to `self.pipeline.execute()`. In `brain_agent.py`: Pass `self.last_percept` into `process_event`. | Test in `test_causal_slice.py` verifying end-to-end turn receives non-zero epoch/revision. |
| **FIX-CLD-02** | Codex Finding 3 | BLOCKER | Normal playback path in `transport_agent.py` never emits `completed=True` | **ACCEPT** | In `backend/app/agents/transport_agent.py`: When the NATS audio stream finishes (at line 406), publish a terminal `AudioPlaybackProgress(completed=True, character_offset=...)` event so `BrainAgent` receives completion. | Test verifying transport stream end triggers `COMPLETED` OutcomeRecord. |
| **FIX-CLD-03** | Codex Finding 2 | BLOCKER | `ActionIntent` and `OutcomeRecord` are diagnostic-only, never persisted | **ACCEPT** | In `backend/app/agents/brain_agent.py`: When `_emit_outcome_record` is called, append the record to an in-memory/store history ledger (`self._outcome_history: list[OutcomeRecord]`) and provide `get_outcome_history(turn_id)` for retrieval and evaluation. | Test asserting outcome records can be queried by turn ID after completion. |
| **FIX-CLD-04** | Codex Finding 4 | HIGH | Completed outcome uses `len(delivered)` instead of playback offset | **ACCEPT** | In `backend/app/agents/brain_agent.py::_on_audio_playback_progress`: Use `progress.character_offset` (or full text length if progress offset matches/exceeds text) rather than blindly assuming full length. | Test verifying character offset matches progress marker. |
| **FIX-CLD-05** | Codex Finding 5 | HIGH | Cancellation in `_replace_active_generation` bypasses outcome recording | **ACCEPT** | In `backend/app/agents/brain_agent.py::_replace_active_generation`: If replacing an active generation task with an active intent, emit `OutcomeRecord(status="CANCELLED")` before resetting. | Test in `test_causal_slice.py` simulating turn replacement. |
| **FIX-CLD-06** | Codex Finding 6 | MEDIUM | `_clamp_confidence("nan")` returns 1.0 | **ACCEPT** | In `backend/app/cognitive/percept.py::_clamp_confidence`: Use `math.isfinite(val)` check; if not finite, fallback to `default`. | Unit test verifying NaN and Inf fall back to default. |
| **FIX-CLD-07** | Codex Finding 7 | MEDIUM | Percept IDs are not stable across redelivery | **ACCEPT** | In `backend/app/cognitive/percept.py`: If raw event has `utterance_id` or `id`, derive a deterministic percept ID (e.g. `f"percept:{source_id}"`) so replays have stable IDs. | Unit test verifying identical raw event produces identical percept ID. |

---

## 3. Fix Verification Pipeline

Each agent must run:
1. Focused test suite:
   - Codex: `../.venv/bin/python -m pytest tests/test_workspace_store.py tests/test_session_state.py -q`
   - Claude: `../.venv/bin/python -m pytest tests/test_causal_slice.py tests/test_pipeline.py -q`
2. Full backend regression suite: `../.venv/bin/python -m pytest -q`
3. Static tooling: `ruff check .`, `radon cc app/ --min D -s`, `mypy app`
4. Commit fixes to their respective branches (`codex/phase-01`, `claude/phase-01`).
5. Update `CODEX_RESULT.md` and `CLAUDE_RESULT.md` with the fix verification details.

