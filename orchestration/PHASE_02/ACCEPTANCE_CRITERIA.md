# Phase 02: Acceptance Criteria & Gate Requirements

**Phase:** `PHASE_02` -- Memory Truth and General Action Selection
**Target Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (Sections 8, 11, 22, 39)
**Status:** Frozen Criteria for Phase 02 Gate Evaluation

---

## 1. Local Acceptance Criteria (Mac Environment)

| ID | Category | Requirement | Validation Method | Threshold / Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-P2-01** | Bi-temporal Truth | As-of queries return only beliefs valid at specified timestamp; historical queries return complete succession. | Parametrized time-travel tests in `test_memory_truth.py` | 100% accuracy on historical vs current truth queries. | `PENDING_EXECUTION` |
| **AC-P2-02** | Contradiction Handling | Contradictory assertions are classified into ELABORATION, UPDATE, CORRECTION, or CONFLICT. | Unit tests in `test_memory_truth.py` | Exactly matching state transitions per contradiction type. | `PENDING_EXECUTION` |
| **AC-P2-03** | Episodic Immutability | `ExperienceRecord` is append-only and immutable upon creation. | Immutability and replay tests in `test_memory_truth.py` | Zero field mutations allowed after creation. | `PENDING_EXECUTION` |
| **AC-P2-04** | Structured Activation | Memory retrieval returns typed `MemoryActivation` tokens with validity and confidence. | Pipeline inspection tests in `test_action_selection.py` | 100% of activations conform to schema. | `PENDING_EXECUTION` |
| **AC-P2-05** | Typed Outage Reporting | Subsystem retrieval outage sets `outage_flag=True` rather than silently returning empty memories. | Simulated failure test in `test_action_selection.py` | Outage explicitly tagged; zero silent false-empty returns. | `PENDING_EXECUTION` |
| **AC-P2-06** | Constraint-First Filter | Hard identity boundaries and safety rules filter out action candidates before utility scoring. | Refusal boundary probe in `test_action_selection.py` | 100% of forbidden candidates rejected before scoring. | `PENDING_EXECUTION` |
| **AC-P2-07** | Action Diversification | Memory activation alters which `ActionCandidate` is selected (e.g. SPEAK vs ASK vs WAIT). | Planted-memory action ablation test in `test_action_selection.py` | Verifiable shift in action selection driven by active memory. | `PENDING_EXECUTION` |
| **AC-P2-08** | Anti-Injection Defense | Adversarial instructions embedded inside retrieved memory text are neutralized. | Injection probe suite in `test_action_selection.py` | Zero instruction leakage or unauthorized persona override. | `PENDING_EXECUTION` |
| **AC-P2-09** | Full Local Regression | Entire repository test suite passes cleanly. | `../.venv/bin/python -m pytest` | 1,909+ tests passing without regression. | `PENDING_EXECUTION` |
| **AC-P2-10** | Quality Tooling Gate | All quality gates, pre-commit hooks, and complexity checks pass cleanly. | `pre-commit run --files ...`, Radon CC, Radon MI, Mypy, Bandit, Codespell | Zero pre-commit errors; zero Radon D/E/F findings; zero Mypy errors; zero security warnings. | `PENDING_EXECUTION` |

---

## 2. Remote GPU Acceptance Criteria (RTX 2060 Super 8GB)

| ID | Category | Requirement | Validation Method | Threshold / Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-GPU-P2-01** | Selection Latency Overhead | Generating candidates, filtering constraints, and scoring adds minimal overhead to live Ollama turn. | 15 standardized turns on RTX 2060 Super with Candidate vs Baseline. | Candidate selection overhead $\le 10.0$ ms (p95). | `PENDING_GPU` |
| **AC-GPU-P2-02** | Multi-Turn Memory Truth | 20-turn live conversation with updating user facts accurately resolves latest facts and maintains stable state. | 20-turn live dialog test against Ollama on RTX 2060 Super. | 100% accuracy on updated facts; 0 stale state regressions; memory variance $\le 5.0\%$. | `PENDING_GPU` |

---

## 3. Architecture Invariant Gates (Non-Negotiable)

* **INV-P2-01:** Retrieved memory text is untrusted data and can never inject instructions or override identity boundaries.
* **INV-P2-02:** Hard safety and identity constraints filter before utility scoring; no affect or control parameter can override boundary refusals.
* **INV-P2-03:** Updating a belief supersedes its validity window; historical evidence is never erased or overwritten.
* **INV-P2-04:** A retrieval outage must be reported as a typed failure state, never silently equated with "no memories exist".

