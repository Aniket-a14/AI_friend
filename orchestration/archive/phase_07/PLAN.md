# Phase 07 Implementation Plan: Production Runtime Consolidation

Phase: PHASE_07
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 1-41)
Audit Reference: FINAL_SYSTEM_VALIDATION_REPORT.md (2026-09-04)
Baseline Git Commit: c474470
Status: READY_FOR_DISPATCH

---

## 1. Executive Objective

Phase 07 directly resolves the blocker and high-severity findings of the Final System Audit. It transitions the Humanoid Brain Architecture from component-complete libraries to a fully composed, runtime-integrated production system:
1. Compose all Phase 01-06 services into the production runtime (`CognitiveService.__init__` and `BrainAgent`).
2. Supply authoritative workspace instances to live turns, eliminating the `(0, 0)` fallback for `ActionIntent`.
3. Enable `PHASE_02_MEMORY_TRUTH`, `PHASE_03_AFFECT_CONTROL`, and `WORKSPACE_AUTHORITATIVE` as active production defaults.
4. Quarantine dream memory generation in `SubconsciousAgent`, eliminating autobiographical memory contamination.
5. Implement faithful action execution for `WAIT`, ensuring that selecting silence produces no spoken utterance.
6. Connect `MemoryStore` to `TemporalMemoryStore`, propagating real contradiction states and explicit outage flags.
7. Enforce governed learning reviews (`LEARNING_REVIEW_REQUIRED=True`) via `LearningGovernor`.
8. Provide genuine cross-provider behavioral evaluation.

---

## 2. Package Decomposition and Ownership

### Package A: Codex (Runtime Composition Root, Action Realization, State Integrity)
- Target Directory: `/Users/aniketsaha/Projects/ai-friend-codex`
- Branch: `codex/phase-07`
- Owned Files:
  - `backend/app/cognitive/core.py` (Compose Phase 1-6 services in CognitiveService)
  - `backend/app/cognitive/pipeline.py` (Ensure clean forwarding of composed services)
  - `backend/app/cognitive/decision.py` (Map WAIT candidate to action_type="WAIT")
  - `backend/app/cognitive/action.py` (Implement silent execution for WAIT action)
  - `backend/app/agents/brain_agent.py` (Pass authoritative workspace to process_event)
  - `backend/app/state/session_state.py` (Support WORKSPACE_AUTHORITATIVE in configuration)
  - `backend/tests/test_runtime_composition.py` (NEW: comprehensive composition tests)

### Package B: Claude (Epistemic Quarantine, Memory Truth Bridge, Background & Learning Governance)
- Target Directory: `/Users/aniketsaha/Projects/ai-friend-claude`
- Branch: `claude/phase-07`
- Owned Files:
  - `backend/app/agents/subconscious_agent.py` (Quarantine dream memory insertion)
  - `backend/app/cognitive/memory_activation.py` (Bridge real contradiction states & outage flags)
  - `backend/app/state/memory_store.py` (Surface explicit retrieval outages)
  - `backend/app/cognitive/learning.py` (Wire LearningGovernor into ReflectionService)
  - `backend/app/config.py` (Enable PHASE_02_MEMORY_TRUTH, PHASE_03_AFFECT_CONTROL, LEARNING_REVIEW_REQUIRED, WORKSPACE_AUTHORITATIVE)
  - `backend/tests/test_phase5_tom.py` (Update mock_decide signature for global_controls)
  - `backend/tests/test_context_assembly.py` (Update prompt injection test expectations under active gate)
  - `backend/tests/test_provider_portability_validation.py` (NEW: genuine cross-provider evaluation)

---

## 3. Implementation Workflow

1. Create isolated worktrees for Codex (`ai-friend-codex`), Claude (`ai-friend-claude`), and Integration (`ai-friend-integration`).
2. Dispatch Package A to Codex and Package B to Claude.
3. Conduct reciprocal peer review (`CLAUDE_REVIEW_OF_CODEX.md` and `CODEX_REVIEW_OF_CLAUDE.md`).
4. Reconcile findings into `orchestration/PHASE_07/FIX_PLAN.md` and execute targeted fix round.
5. Merge both packages into `integration/phase-07` and verify the full regression suite (2,332+ tests).
6. Execute Phase 07 local micro-benchmarks and remote GPU benchmarks on NVIDIA RTX 2060 Super.
7. Evaluate all Phase 07 Acceptance Criteria in `orchestration/PHASE_07/PHASE_GATE.md`.
8. Merge to `main`, re-run the Final System Release Gate, and certify the architecture as fully integrated.
