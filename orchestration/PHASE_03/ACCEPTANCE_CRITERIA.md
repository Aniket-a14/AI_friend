# Phase 03: Acceptance Criteria & Gate Requirements

Phase: PHASE_03 -- Causal Affect and Global Control
Target Reference: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 9, 10, 21, 38)
Status: Formally Evaluated and Passed (11/11 PASS)

---

## 1. Local Acceptance Criteria (Mac Environment)

| ID | Category | Requirement | Validation Method | Threshold / Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-P3-01** | Global Controls | Four derived controls (urgency, exploration, effort, learning) strictly bounded in [0.0, 1.0]. | Unit tests in `test_causal_affect.py` | 100% boundary compliance; monotonic scaling with inputs. | **PASS** |
| **AC-P3-02** | Structured Appraisal | Event appraisal generates typed `AppraisalRecord` and affect deltas without side-effects. | Unit tests in `test_causal_affect.py` | Pure reducer behavior; goal congruence increases valence; novelty increases arousal. | **PASS** |
| **AC-P3-03** | Endocrine Compatibility | Bidirectional conversion between legacy hormones (cortisol, dopamine) and global controls. | Adapter tests in `test_causal_affect.py` | Zero regression on legacy endocrine callers. | **PASS** |
| **AC-P3-04** | Candidate Modulation | Global controls modulate candidate scoring (urgency favors fast/low-risk, exploration favors novelty). | Unit tests in `test_global_control_selection.py` | Statistically observable shift in winner ranking driven by controls. | **PASS** |
| **AC-P3-05** | Emotion Regulation | Distress triggers explicit regulation actions (`REAPPRAISE`, `REDIRECT_ATTENTION`) with safe execution. | Pipeline tests in `test_global_control_selection.py` | Regulation candidate wins under acute distress; outputs grounding response. | **PASS** |
| **AC-P3-06** | Constraint Invariant | High urgency or exploration gain CANNOT override boundary refusals or safety constraints. | Adversarial refusal tests in `test_global_control_selection.py` | 100% boundary violation rejection regardless of control values. | **PASS** |
| **AC-P3-07** | Content Isolation | Affect state changes and global controls cannot alter beliefs, truth records, or delete evidence. | Content isolation tests in `test_causal_affect.py` | Zero belief mutations induced by emotional state changes. | **PASS** |
| **AC-P3-08** | Full Regression | Entire test suite passes without regressions. | `../.venv/bin/python -m pytest` | 1,990+ tests passing cleanly (2,049 passed, 0 failures). | **PASS** |
| **AC-P3-09** | Quality Tooling Gate | Pure 7-bit ASCII and zero linter warnings. | `ruff check .` and ASCII byte scan | Clean Ruff check; 100% 7-bit ASCII compliance across Phase 3 diff. | **PASS** |

---

## 2. Remote GPU Acceptance Criteria (RTX 2060 Super 8GB)

| ID | Category | Requirement | Validation Method | Threshold / Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-GPU-P3-01** | Turn Latency Overhead | Appraisal and global control candidate scoring adds minimal latency to live Ollama turn. | 15 standardized turns on RTX 2060 Super with Candidate vs Baseline. | Mean TTFT delta <= 10.0 ms (-6.17 ms), p95 delta <= 20.0 ms (+8.99 ms). | **PASS** |
| **AC-GPU-P3-02** | Regulation & Affect Soak | 20-turn live dialog with acute distress injections tests regulation recovery and state stability. | 20-turn live dialog against Ollama on RTX 2060 Super. | 100.0% regulation trigger; recovery to baseline affect; VmRSS variance 0.0% (<= 5.0%). | **PASS** |

---

## 3. Architecture Invariant Gates (Non-Negotiable)

* **INV-P3-01:** Global controls are strictly read-only inputs to candidate selection; they can change gains and budgets, but NEVER write beliefs, identity, or bypass safety refusals. (**VERIFIED PASS**)
* **INV-P3-02:** Affect deltas cannot overwrite, delete, or mutate factual memory truth. (**VERIFIED PASS**)
* **INV-P3-03:** Emotion regulation is an explicit selectable candidate action, never a silent internal state hack. (**VERIFIED PASS**)

