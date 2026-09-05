# Phase 04 Acceptance Criteria

Phase: PHASE_04
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 11, 13, 15, 19, 20, 21, 38, 40)
Baseline Git Commit: ea64b4b

---

## Acceptance Criteria Checklist

| ID | Category | Requirement | Target Metric | Verification Method |
|---|---|---|---|---|
| **AC-P4-01** | Social State | Event-grounded trust separation: `trust_competence` and `trust_benevolence` updated from reliance outcomes | Distinct dynamics on success vs failure | `test_social_metacognition.py` |
| **AC-P4-02** | Social State | Asymmetric rupture and repair: trust drops sharply on rupture and recovers gradually on repair | Drop magnitude > 2x repair gain | `test_social_metacognition.py` |
| **AC-P4-03** | Social State | Multi-person knowledge isolation: private facts owned by Person A cannot be disclosed to Person B | Zero leakage across all test cases | `test_social_metacognition.py`, `test_background_governed_learning.py` |
| **AC-P4-04** | Metacognition | Empirical domain calibration: Brier score tracking and calibration function for raw confidence | Valid Brier update, monotonic calibration | `test_social_metacognition.py` |
| **AC-P4-05** | Metacognition | Actionable directives: PROCEED, HEDGE, ASK_CLARIFICATION, VERIFY, ABSTAIN derived from calibrated confidence | 100% expected mapping across boundary fixtures | `test_social_metacognition.py` |
| **AC-P4-06** | Background | Background work scheduler: priority execution, token and time budget enforcement, idempotency | Timed out jobs cleanly aborted | `test_background_governed_learning.py` |
| **AC-P4-07** | Background | Immediate foreground preemption: background tasks abort immediately when user interaction begins | Preemption latency < 5ms | `test_background_governed_learning.py` |
| **AC-P4-08** | Goals | Time-watermarked due-goal review: GoalRecords evaluated against watermark; expired goals marked EXPIRED | Correct state transition & notification | `test_background_governed_learning.py` |
| **AC-P4-09** | Learning | Governed learning proposals with durable rollback: approved proposals can be cleanly rolled back | Exact restoration of previous state | `test_background_governed_learning.py` |
| **AC-P4-10** | Governance | Immutable core safety invariant: immutable persona core and safety boundaries can never be proposed or altered | ValueError raised on violation | `test_background_governed_learning.py` |
| **AC-P4-11** | Code Quality | Code hygiene & gate standards: pure 7-bit ASCII, zero ruff violations, zero radon D/E/F cyclomatic complexity | 0 errors, 0 rank D/E/F | `ruff check .`, `radon cc app --min D -s` |

