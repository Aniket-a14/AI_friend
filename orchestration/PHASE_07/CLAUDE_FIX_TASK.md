# Phase 07 Claude Fix Task: Package B Fix Round

Worktree: `/Users/aniketsaha/Projects/ai-friend-claude`
Branch: `claude/phase-07`
Reference: `orchestration/PHASE_07/FIX_PLAN.md`

---

## Assigned Fix Items

### 1. Fix `test_scenario_hostile_interaction_drift` (`backend/tests/test_scenarios.py`)
- The failure in `test_scenario_hostile_interaction_drift` must be resolved so the full test suite passes unconditionally:
  - Ensure the test uses `monkeypatch` (or exception-safe `try...finally`) for all modified configuration variables (`LEARNING_REVIEW_REQUIRED`, `PHASE_02_MEMORY_TRUTH`, `PHASE_03_AFFECT_CONTROL`, `REFLECTION_MIN_INTERVAL_SECONDS`).
  - Investigate why `Strained` relationship wasn't reached: ensure reflection triggers properly or that interval limits don't suppress the hostile reflection step.
  - Verify that `test_scenarios.py` passes both in isolation and when running after other tests.

### 2. Accept Injected Governor & Eliminate Key Renaming Hack (`backend/app/cognitive/learning.py`)
- In `ReflectionService.__init__`:
  - Accept `governor: LearningGovernor | None = None`.
  - Set `self.governor = governor if governor is not None else LearningGovernor()`.
- Eliminate the `new_traits` -> `new_trait_additions` artificial renaming:
  - In `_governed_persona_proposal`, keep the exact `suggestions` payload without renaming `new_traits`.
  - In `backend/app/cognitive/learning_governance.py` (or within the proposal validation logic), ensure `new_traits` is recognized as an allowed ADAPTIVE trait addition key, while strictly rejecting protected fields like `mood_decay_rate`, `baseline_valence`, `traits` (when passed as a direct field), and `IMMUTABLE_CORE`.
  - Ensure the proposal payload registered in `LearningGovernor` strictly matches the applied queue suggestions.

### 3. Surface Retrieval Outage on Empty Error Result (`backend/app/cognitive/memory_activation.py`)
- In `memories_to_activations`:
  - If a memory dict has `metadata` containing `outage_flag` or `contradiction_state`, inspect `metadata` as well.
  - If `last_search_error` or outage indicator is present in the memory list or passed context, ensure an activation with `outage_flag=True` is emitted so `pipeline.py` marks `retrieval_degraded=True`.

---

## Verification
- Run: `../.venv/bin/python -m pytest tests/test_scenarios.py tests/test_learning_review.py tests/test_action_selection.py tests/test_provider_portability_validation.py`
- Run: `../.venv/bin/python -m ruff check .`
- Run: `../.venv/bin/python -m radon cc app/ -s -n D`
- Ensure pure 7-bit ASCII on all edits.
- Commit to `claude/phase-07` with message: "fix(phase-07): resolve scenario drift test, unify governor injection, and preserve exact proposal payload"
