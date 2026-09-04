# Phase 07 Codex Task: Runtime Composition Root, Action Realization & State Integrity

**Auditor Reference:** CODEX_FINAL_SYSTEM_AUDIT.md & FINAL_SYSTEM_VALIDATION_REPORT.md
**Assigned Package:** Package A (Engineering / Runtime Composition)
**Target Worktree:** `/Users/aniketsaha/Projects/ai-friend-codex`
**Target Branch:** `codex/phase-07`
**Architecture Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (Sections 1-41)
**Quality Standards:** Pure 7-bit ASCII, 0 ruff errors, 0 radon D/E/F cyclomatic complexity findings, full test pass rate.

---

## 1. Context & Objectives

In the Final System Audit, Codex identified that while Phase 01-06 components were built and unit-tested in isolation, they were never composed into the production runtime:
- `CognitiveService.__init__` instantiates only legacy services and passes `scheduler=None` and no workspace.
- `BrainAgent` passes `percept` but no `workspace` to `process_event`, causing `ActionIntent` to fall back to `(0, 0)`.
- When `CandidateSelector` selects `WAIT`, `decision.py` fails to map it to an executable action type, causing `action.py` to fall through to `_execute_respond_chat` and speak.

Your objective in Package A is to refactor the production composition root and action realization so the accepted architecture actually runs in production.

---

## 2. Owned Files

1. `backend/app/cognitive/core.py`
2. `backend/app/cognitive/pipeline.py`
3. `backend/app/cognitive/decision.py`
4. `backend/app/cognitive/action.py`
5. `backend/app/agents/brain_agent.py`
6. `backend/app/state/session_state.py`
7. `backend/tests/test_runtime_composition.py` (NEW)

Do NOT edit files assigned to Package B (`subconscious_agent.py`, `memory_activation.py`, `memory_store.py`, `config.py`, `learning.py`).

---

## 3. Specific Implementation Tasks

### Task A1: Refactor Production Composition Root (`core.py` & `pipeline.py`)
- In `CognitiveService.__init__`:
  - Instantiate and compose the completed Phase 01-06 services:
    - `WorkspaceStore` (e.g. `SQLiteWorkspaceStore` or in-memory fallback)
    - `TemporalMemoryStore`
    - `BackgroundScheduler`
    - `DeterministicPlanVerifier` and `DeterministicPlanExecutor`
    - `EpisodicSimulator`
    - `LearningGovernor` and `OfflineAdapterGate`
    - `ProviderCapabilityNegotiator`
    - `ExternalActionDispatcher`
  - Pass `scheduler=self.scheduler`, `workspace_store=self.workspace_store`, etc., to `CognitivePipeline` so `pipeline.scheduler` is non-None and background preemption works.

### Task A2: Causal Workspace Pass-Through (`brain_agent.py`)
- In `BrainAgent`:
  - Provide access to an authoritative `WorkspaceStore` (either instantiated directly or accessed via `cognitive_core`).
  - In `_handle_chat_turn` / `process_event`, obtain the current workspace snapshot and pass `workspace=workspace_snapshot` into `self.cognitive_core.process_event(...)`.
  - Ensure that `ActionIntent` committed in Stage 6 of `pipeline.py` records the actual `(epoch, revision)` of the workspace instead of `(0, 0)`.

### Task A3: Action Realization for WAIT (`decision.py` & `action.py`)
- In `backend/app/cognitive/decision.py:848-863`:
  - Add mapping for `selected_kind == "WAIT"`: set `action_type = "WAIT"`.
- In `backend/app/cognitive/action.py:1793-1833`:
  - Add a dedicated handler for `plan.action_type == "WAIT"`.
  - `_execute_wait(plan)` must yield `{"type": "done", "data": ""}` without emitting any speech/content chunks.
  - Also ensure fail-closed safe execution for `EXTERNAL_ACT` or unknown action kinds (yielding error or done, never unhandled exception).

### Task A4: Session State Workspace Authority (`session_state.py`)
- Update `session_state.py` so `_workspace_authoritative_enabled()` gracefully reads `WORKSPACE_AUTHORITATIVE` from `Config` (defaults to False if not present, but respects True when declared).

### Task A5: Comprehensive Composition Tests (`test_runtime_composition.py`)
- Create `backend/tests/test_runtime_composition.py` with tests verifying:
  1. `CognitiveService` instantiates and composes all Phase 01-06 services without error.
  2. `CognitivePipeline` holds non-None references to `scheduler` and `session_store`.
  3. `BrainAgent` passes a valid `workspace` to `process_event`, and `ActionIntent` is committed with non-zero `(epoch, revision)`.
  4. When `WAIT` candidate is selected, `action.py:execute` yields only `{"type": "done", "data": ""}` with zero content chunks.

---

## 4. Verification Bar
- Run pytest on `tests/test_runtime_composition.py`, `tests/test_causal_slice.py`, `tests/test_action_selection.py`.
- Ensure pure 7-bit ASCII, 0 ruff errors, and 0 radon D/E/F findings.
- Produce `orchestration/PHASE_07/CODEX_RESULT.md` with full verification evidence.
