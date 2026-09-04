# Final Fix Plan and Finding Reconciliation

Date: 2026-09-04
Orchestrator: Gemini (Antigravity)
Audited Revision: main (f0333fc)

---

## 1. Finding Reconciliation & Classification

| Finding ID | Source | Summary | Severity | Status | Resolution |
|---|---|---|---|---|---|
| **F-01** | Codex F-01, Claude F1 | The 6-phase architecture is component-complete but not composed in the production runtime (`CognitiveService`, `BrainAgent`). | **BLOCKER** | **ACCEPTED (DOCUMENTED)** | Cannot perform a complete architectural rewrite during final release gate; must be explicitly documented in Release Gate and classified under PASS_WITH_LIMITATIONS. |
| **F-02** | Claude F2, Codex F-05 | `SubconsciousAgent._run_dream_sequence` persists ungrounded dream text directly into `memory_store` as `subconscious_dream`, violating Invariant 12 and Section 19/37. | **BLOCKER** | **FIXED IN ROUND 1** | Remove direct dream memory insertion. Replace with quarantined logging so dreams cannot contaminate autobiographical memory. |
| **F-03** | Claude F3, Codex F-08 | Provider independence benchmark (`BM-GPU-P5-01`) tested two Ollama models on the same provider with a local variable tautology. Genuine cross-provider independence unproven. | **HIGH** | **ACCEPTED (DOWNGRADED CLAIM)** | Reclassify "Provider Independence" from fully verified to NOT YET SUPPORTED in release documentation. Retain real LLM abstraction evidence. |
| **F-04** | Claude F10, Codex F-03 | `WAIT` candidate selected by `CandidateSelector` is not mapped to an executable `action_type`, causing `ActionService` to fall through to `RESPOND_CHAT` and speak. | **HIGH** | **FIXED IN ROUND 1** | Map `WAIT` to `action_type="WAIT"` in `decision.py` and handle `WAIT` in `action.py` as a silent, non-utterance completion. |
| **F-05** | Claude F4, Codex F-05 | `BackgroundScheduler` (Phase 04) is never instantiated in production composition; `SubconsciousAgent` runs older ungoverned monologue loop. | **HIGH** | **ACCEPTED (DOCUMENTED)** | Document as an architectural limitation for future production runtime consolidation. |
| **F-06** | Claude F5, Codex F-01 | Phase 06 planning (`DeterministicPlanVerifier`), simulation (`EpisodicSimulator`), and learning governance (`LearningGovernor`) have no production callers in live loop. | **HIGH** | **ACCEPTED (DOCUMENTED)** | Document as verified modular substrate ready for live dispatch integration. |
| **F-07** | Claude F7, Codex F-06 | `LEARNING_REVIEW_REQUIRED` defaults to False, allowing uncalibrated reflection LLM suggestions to directly mutate persona traits. | **HIGH** | **FIXED IN ROUND 1** | Set `LEARNING_REVIEW_REQUIRED: bool = True` as default in `config.py` so traits are never mutated without review. |
| **F-08** | Claude F6, Codex F-09 | Metacognitive directive permanently defaults to "PROCEED"; calibration engine has no live observation callers. | **HIGH** | **ACCEPTED (DOWNGRADED CLAIM)** | Accurately report Metacognition as SCAFFOLD / NOT YET SUPPORTED in the release report. |
| **F-09** | Claude F8, F9, Codex F-09 | "Operational self-model" and "World model" do not exist as claimed (only a narrow affect-valence prediction loop exists). | **HIGH** | **ACCEPTED (DOWNGRADED CLAIM)** | Reclassify as RESEARCH CLAIMS NOT YET SUPPORTED. |
| **F-10** | Codex F-02, Claude F11 | `PersonModel` rich fields (knowledge, disclosures, obligations) unread by decision logic; collapsed to single scalar trust average. | **MEDIUM** | **ACCEPTED (DOCUMENTED)** | Document as limitation of current social decision logic. |
| **F-11** | Codex F-11 | Mypy reports 17 errors in 7 files; 80 files have formatting drift; C-grade complexity at state hydration. | **MEDIUM** | **ACCEPTED (TECHNICAL DEBT)** | Fix high-risk type errors if trivial; track remainder as technical debt. |
| **F-12** | Codex F-12 | Phase 06 learning governance microbenchmark is sensitive to concurrent CPU load. | **LOW** | **MONITORED** | Isolated runs pass with 45.4 us (< 50.0 us target). |

---

## 2. Fix Assignments

### Engineering Fixes (Codex Domain)
1. **Action Execution Fidelity for WAIT (F-04):**
   - Update `decision.py` to map `selected_kind == "WAIT"` to `action_type = "WAIT"`.
   - Update `action.py:execute` to handle `action_type == "WAIT"` by yielding `{"type": "done", "data": ""}`.
2. **Safe Configuration Defaults & Declarations (F-07, F-01):**
   - Declare `WORKSPACE_AUTHORITATIVE: bool = False` in `AppSettings` (`backend/app/config.py`).
   - Set `LEARNING_REVIEW_REQUIRED: bool = True` in `backend/app/config.py`.

### Cognitive / Safety Fixes (Claude Domain)
1. **Epistemic Memory Quarantine for Dreams (F-02):**
   - In `backend/app/agents/subconscious_agent.py`, remove the direct call to `memory_store.add_memory(source="subconscious_dream")`.
   - Replace with logging or quarantined ephemeral insight so dream text never pollutes the autobiographical memory corpus.

---

## 3. Verification Protocol
1. Re-run affected unit tests (`test_decision.py`, `test_action_selection.py`, `test_subconscious_agent.py`).
2. Run full test suite to ensure 0 regressions.
3. Run `ruff check .` and `radon cc app/ -s -n D`.
4. Proceed to `FINAL_SYSTEM_VALIDATION_REPORT.md` evaluation.
