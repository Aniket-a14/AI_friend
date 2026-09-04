# Phase 07 Claude Task: Epistemic Quarantine, Memory Truth Bridge & Governance

**Auditor Reference:** CLAUDE_FINAL_COGNITIVE_AUDIT.md & FINAL_SYSTEM_VALIDATION_REPORT.md
**Assigned Package:** Package B (Cognitive / Memory Truth / Governance)
**Target Worktree:** `/Users/aniketsaha/Projects/ai-friend-claude`
**Target Branch:** `claude/phase-07`
**Architecture Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (Sections 1-41)
**Quality Standards:** Pure 7-bit ASCII, 0 ruff errors, 0 radon D/E/F cyclomatic complexity findings, full test pass rate.

---

## 1. Context & Objectives

In the Final System Audit, Claude identified critical epistemic, behavioral, and governance gaps:
- `SubconsciousAgent._run_dream_sequence` directly writes ungrounded dream text into `MemoryStore` as `subconscious_dream`, contaminating autobiographical memory.
- `PHASE_02_MEMORY_TRUTH` and `PHASE_03_AFFECT_CONTROL` default to `False`. When enabled, legacy test mocks break.
- The legacy memory bridge (`memories_to_activations`) hardcodes `contradiction_state="NONE"` and `outage_flag=False`, blinding the agent to contradictions and outages.
- `LEARNING_REVIEW_REQUIRED` defaults to `False`, allowing uncalibrated reflection LLM suggestions to directly mutate persona traits.
- The provider independence benchmark (`BM-GPU-P5-01`) was a same-provider tautology.

Your objective in Package B is to implement epistemic quarantine for dreams, bridge memory truth into candidate selection, enable active configuration flags with test compatibility, wire governed learning, and provide genuine cross-provider validation.

---

## 2. Owned Files

1. `backend/app/agents/subconscious_agent.py`
2. `backend/app/cognitive/memory_activation.py`
3. `backend/app/state/memory_store.py`
4. `backend/app/cognitive/learning.py`
5. `backend/app/config.py`
6. `backend/tests/test_phase5_tom.py`
7. `backend/tests/test_context_assembly.py`
8. `backend/tests/test_action_selection.py`
9. `backend/tests/test_phase6_advanced_cognition.py`
10. `backend/tests/test_provider_portability_validation.py` (NEW)

Do NOT edit files assigned to Package A (`core.py`, `pipeline.py`, `decision.py`, `action.py`, `brain_agent.py`).

---

## 3. Specific Implementation Tasks

### Task B1: Epistemic Dream Memory Quarantine (`subconscious_agent.py`)
- In `backend/app/agents/subconscious_agent.py`:
  - In `_run_dream_sequence`, remove the direct call to `memory_store.add_memory(..., source="subconscious_dream")`.
  - In accordance with Sections 19, 37, and Invariant 12 ("Generated background content cannot self-promote to truth"), dream text must NEVER be added to autobiographical memory.
  - Log dream insight as an ephemeral subconscious event:
    `logger.info("[Subconscious] Dream insight generated (ephemeral quarantine): '%s'", dream_text)`
  - In `backend/tests/test_phase6_advanced_cognition.py`:
    - Update `test_dream_sequence_query_is_linear` so it verifies that `add_memory` is NOT called with `source="subconscious_dream"`.

### Task B2: Memory Truth Bridge (`memory_activation.py` & `memory_store.py`)
- In `backend/app/cognitive/memory_activation.py`:
  - Update `memories_to_activations`:
    - If `mem_dict` carries `contradiction_state` (or a linked `BeliefRecord`), propagate that state (`CONFLICT`, `UPDATE`, `CORRECTION`, `ELABORATION`).
    - If `mem_dict` carries `outage_flag` or error status, propagate `outage_flag=True`.
- In `backend/app/state/memory_store.py`:
  - Ensure `search_memories` records errors in `self.last_search_error` and surfaces degraded status rather than silently returning `[]` on outages.

### Task B3: Active Configuration Defaults & Test Compatibility
- In `backend/app/config.py`:
  - Set `PHASE_02_MEMORY_TRUTH: bool = True`.
  - Set `PHASE_03_AFFECT_CONTROL: bool = True`.
  - Declare `WORKSPACE_AUTHORITATIVE: bool = True`.
  - Set `LEARNING_REVIEW_REQUIRED: bool = True`.
- In `backend/tests/test_phase5_tom.py`:
  - Update `mock_decide` in `test_pipeline_tom_integration` to accept `**kwargs` so it cleanly accepts `global_controls`.
- In `backend/tests/test_context_assembly.py`:
  - In `test_instruction_shaped_memory_stays_inside_the_markers`, accommodate the active `AntiInjectionGate` which replaces injected text with `[UNTRUSTED_CONTENT_FILTERED]`.
- In `backend/tests/test_action_selection.py`:
  - In `TestBackwardCompatibility`, ensure tests explicitly monkeypatch `PHASE_02_MEMORY_TRUTH` and `PHASE_03_AFFECT_CONTROL` to `False` to verify the backward compatibility branches.

### Task B4: Governed Learning Wiring (`learning.py`)
- In `backend/app/cognitive/learning.py`:
  - Wire `LearningGovernor` into `ReflectionService`:
    - When reflection produces persona trait suggestions, construct a `LearningProposal`.
    - When `LEARNING_REVIEW_REQUIRED=True`, submit the proposal to `LearningGovernor` / review queue instead of calling `identity.evolve_persona` directly.

### Task B5: Genuine Cross-Provider Portability Test (`test_provider_portability_validation.py`)
- Create `backend/tests/test_provider_portability_validation.py`:
  - Validate that persona prompt assembly and response processing work identically across distinct provider clients (`OllamaClient` vs `AnthropicClient` / simulated provider conforming to `LLMClient`).
  - Assert that identity boundaries and prompt invariants are preserved regardless of provider backend.

---

## 4. Verification Bar
- Run pytest on `tests/test_provider_portability_validation.py`, `tests/test_phase5_tom.py`, `tests/test_context_assembly.py`, `tests/test_action_selection.py`, `tests/test_phase6_advanced_cognition.py`.
- Ensure pure 7-bit ASCII, 0 ruff errors, and 0 radon D/E/F findings.
- Produce `orchestration/PHASE_07/CLAUDE_RESULT.md` with full verification evidence.
