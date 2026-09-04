# Phase 07 Fix Plan and Peer Review Reconciliation

Phase: PHASE_07
Date: 2026-09-04
Orchestrator: Gemini (Antigravity)
Reviews Reconciled:
- `CLAUDE_REVIEW_OF_CODEX.md` (Reviewer: Claude)
- `CODEX_REVIEW_OF_CLAUDE.md` (Reviewer: Codex)

---

## 1. Finding Reconciliation and Arbitration

| Finding ID | Raised By | Target Package | Summary | Severity | Arbitration Decision |
|---|---|---|---|---|---|
| **P7-FIX-01** | Claude (P1) | Package A (Codex) | Two independent `LearningGovernor` instances created in one process (`core.py` and `learning.py`). | **HIGH** | **ACCEPTED**: `CognitiveService` must pass its `learning_governor` into `ReflectionService.__init__` so they share a single proposal registry. |
| **P7-FIX-02** | Claude (P2) | Package A (Codex) | `ExternalActionDispatcher` passed to `ActionService` but `action.py:1848` fails closed without calling `dispatcher.dispatch()`. | **MEDIUM** | **ACCEPTED**: In `action.py`, call `dispatcher.dispatch()` when `EXTERNAL_ACT` is executed, with fail-closed error handling. |
| **P7-FIX-03** | Codex (P1) | Package A (Codex) | `CognitiveService._on_memory_surfaced` drops `metadata`, `contradiction_state`, and `outage_flag` when projecting surfaced memory dicts. | **HIGH** | **ACCEPTED**: Update `_on_memory_surfaced` in `core.py` to preserve rich truth metadata so it reaches `memories_to_activations`. |
| **P7-FIX-04** | Codex (P1) | Package B (Claude) | `test_scenario_hostile_interaction_drift` in `test_scenarios.py` fails in the full test suite due to non-hermetic Config mutation. | **BLOCKER** | **ACCEPTED**: Fix test in `test_scenarios.py` using robust `monkeypatch` / `try...finally` to ensure hermetic execution across full-suite order. |
| **P7-FIX-05** | Codex (P0/P2) | Package B (Claude) | The `new_traits` -> `new_trait_additions` rename causes proposal payload to differ from queue payload; governor has no shared instance with core. | **HIGH** | **ACCEPTED**: Update protected-name matching to accurately distinguish constitutional `traits` from adaptive `new_traits`, ensuring proposal payload matches queue payload bit-for-bit. Accept `governor` parameter in `ReflectionService.__init__`. |
| **P7-FIX-06** | Codex (P1) | Package B (Claude) | When memory retrieval fails and returns `[]`, `pipeline.py` receives empty list and does not mark `retrieval_degraded=True`. | **MEDIUM** | **ACCEPTED**: When `memory_store.last_search_error` is active or error occurs, emit an outage activation or set `retrieval_degraded=True`. |
| **P7-FIX-07** | Claude (P0) | Shared / Ledger | 6 of 8 composed services are held as attributes on `CognitiveService` and `CognitivePipeline` but not called in live turns. | **DOCUMENTED** | **ACCEPTED (TRANSPARENT LEDGER ENTRY)**: Document clearly in CONTEXT.md and validation report that these services are composed in runtime root and available, with specific live turn call sites documented. |

---

## 2. Action Assignments

### Package A Fixes (Assigned to Codex):
1. **Pass `learning_governor` to `ReflectionService` (`backend/app/cognitive/core.py`):**
   Pass `governor=self.learning_governor` into `ReflectionService(...)` so the proposal registry is unified across `CognitiveService` and `ReflectionService`.
2. **Wire `ExternalActionDispatcher` in `action.py` (`backend/app/cognitive/action.py`):**
   In `ActionService.execute` for `plan.action_type == "EXTERNAL_ACT"`, call `await self.external_action_dispatcher.dispatch(action_intent)` if dispatcher is present, with safe fail-closed error handling.
3. **Preserve Truth Metadata in `_on_memory_surfaced` (`backend/app/cognitive/core.py`):**
   In `_on_memory_surfaced`, preserve `metadata`, `contradiction_state`, `outage_flag`, and `belief_record` from `mem_item` so that `memories_to_activations` receives full epistemic context.

### Package B Fixes (Assigned to Claude):
1. **Fix `test_scenario_hostile_interaction_drift` (`backend/tests/test_scenarios.py`):**
   Isolate and fix the test failure using `monkeypatch` or `try...finally` to ensure clean restoration of all Config flags (`LEARNING_REVIEW_REQUIRED`, `PHASE_02_MEMORY_TRUTH`, `PHASE_03_AFFECT_CONTROL`, `REFLECTION_MIN_INTERVAL_SECONDS`). Ensure full suite passes.
2. **Exact Proposal Matching & Governor Injection (`backend/app/cognitive/learning.py`):**
   Accept `governor: LearningGovernor | None = None` in `ReflectionService.__init__`. Eliminate artificial key renaming (`new_trait_additions`), ensuring the proposal payload strictly matches the applied suggestions. Update protected-name logic to recognize `new_traits` as adaptive while strictly rejecting protected fields.
3. **Outage Flag on Empty Retrieval Error (`backend/app/cognitive/memory_activation.py`):**
   Ensure that when retrieval encounters an error or when `last_search_error` is flagged, `memories_to_activations` or pipeline signals `retrieval_degraded=True`.
