# Phase 07 Codex Fix Task: Package A Fix Round

Worktree: `/Users/aniketsaha/Projects/ai-friend-codex`
Branch: `codex/phase-07`
Reference: `orchestration/PHASE_07/FIX_PLAN.md`

---

## Assigned Fix Items

### 1. Unify LearningGovernor Instance (`backend/app/cognitive/core.py`)
- In `CognitiveService.__init__`:
  - When constructing `self.learning = ReflectionService(...)`, pass `governor=self.learning_governor`.
  - This ensures `CognitiveService` and `ReflectionService` share the same unified proposal audit registry.

### 2. Wire ExternalActionDispatcher (`backend/app/cognitive/action.py`)
- In `ActionService.execute` under `plan.action_type == "EXTERNAL_ACT"`:
  - If `self.external_action_dispatcher is not None`:
    - Construct or obtain the `ExternalActionIntent` and call `await self.external_action_dispatcher.dispatch(...)`.
    - Yield a result chunk or completion (`yield {"type": "done", "data": ""}`), failing closed with `yield {"type": "error", "data": str(e)}` on exception.
  - If dispatcher is None, log warning and fail closed as before.

### 3. Preserve Epistemic Metadata in Memory Surfacing (`backend/app/cognitive/core.py`)
- In `CognitiveService._on_memory_surfaced`:
  - When extracting dictionary items from `data.get("memories", [])` or single items, copy `contradiction_state`, `outage_flag`, `belief_record`, and `metadata` into the stored dict in `self.surfaced_memories`:
    ```python
    "contradiction_state": mem_item.get("contradiction_state"),
    "outage_flag": mem_item.get("outage_flag", False),
    "metadata": mem_item.get("metadata", {}),
    "belief_record": mem_item.get("belief_record"),
    ```
  - This ensures `memories_to_activations` receives the rich truth metadata downstream.

---

## Verification
- Run: `../.venv/bin/python -m pytest tests/test_runtime_composition.py tests/test_action_selection.py tests/test_causal_slice.py`
- Run: `../.venv/bin/python -m ruff check .`
- Run: `../.venv/bin/python -m radon cc app/ -s -n D`
- Ensure pure 7-bit ASCII on all edits.
- Commit to `codex/phase-07` with message: "fix(phase-07): unify learning governor, wire external action dispatcher, and preserve truth metadata"
