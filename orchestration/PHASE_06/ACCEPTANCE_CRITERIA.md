# Phase 06 Acceptance Criteria: Optional Advanced Learning and Planning

Phase: PHASE_06
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 16, 17, 19, 20, 21, 38, 40)
Baseline Git Commit: 9203f55
Status: READY_FOR_DISPATCH

---

## 1. Functional and Structural Criteria

| Criteria ID | Component | Requirement | Verification Target |
|---|---|---|---|
| **AC-P6-01** | Planning | PlanArtifact and PlanStep formalization with typed preconditions, effects, invariants, budget, and fallback steps | Schema validation tests pass 100% |
| **AC-P6-02** | Planning | DeterministicPlanVerifier sound verification: acyclicity, step reachability, precondition satisfiability, invariant preservation, budget limits | 0% false acceptance on malformed/cyclic plans |
| **AC-P6-03** | Simulation | EpisodicSimulator sandboxed rollouts: prospective execution of plan steps over cloned workspace state | Rollout succeeds and computes prospective outcome |
| **AC-P6-04** | Simulation | Simulation Quarantine Invariant: 100% of simulated percepts, actions, and outcomes tagged `is_simulation=True`; live memory commit attempts raise SimulationQuarantineViolationError | 0% simulated records leak into live memory/state |
| **AC-P6-05** | Learning | LearningProposal schema completeness per Section 21: source records, target domain, proposed value, expected effect, risk class, counterfactual baseline, rollback value, status | Schema validation tests pass 100% |
| **AC-P6-06** | Learning | Immutable Core & Safety Hard Gate: proposals targeting IMMUTABLE_CORE, safety invariants, or constitutional boundaries rejected immediately | 100% rejection rate for core/safety modifications |
| **AC-P6-07** | Learning | Risk-tiered approval & 1-step reversible rollback: LOW risk threshold, MEDIUM/HIGH gatekeeper required, CRITICAL blocked; atomic rollback restores previous state | 100% accurate approval enforcement and state restoration |
| **AC-P6-08** | Curiosity | LearningProgressCuriosity engine: computes learning progress delta over sliding windows; scores learnable novelty above flat noise or mastered routine | Rank ordering: Progress > Mastery and Progress > Random Noise |
| **AC-P6-09** | Adapters | OfflineAdapterGate qualification: checks held-out eval suite for zero regressions, validates prompt digest match, snapshots incumbent adapter for atomic rollback | Adapter rejected on any regression; rollback restores baseline |
| **AC-P6-10** | Quality | Code hygiene & CI compliance: pure 7-bit ASCII, 0 ruff errors, 0 radon D/E/F cyclomatic complexity findings, 100% test pass rate | CI gates pass locally and on remote home-gpu |

---

## 2. Invariant Checklist

1. **Deterministic Plan Soundness:**
   - A plan with a cycle in its dependency graph must NEVER be marked valid.
   - A step requiring precondition P that is never satisfied by initial state or preceding step effects must be flagged as unfulfilled.
   - A plan exceeding `max_steps` (default 20) must be rejected for budget violation.

2. **Simulation Quarantine Invariant:**
   - Simulated percepts, actions, and outcomes are tagged with `is_simulation=True`.
   - `MemoryStore.save_memory` or state mutations must raise `SimulationQuarantineViolationError` if invoked with simulated records.
   - Simulation state is isolated to ephemeral memory or sandbox containers and destroyed after rollout evaluation.

3. **Immutable Identity Invariant:**
   - Identity core (`IMMUTABLE_CORE`, safety invariants, constitutional bounds) is strictly non-targetable by `LearningProposal`.
   - Any proposal whose `target_domain` or `proposed_value` intersects with immutable fields is hard-rejected with `SecurityViolationError` or `LearningApprovalRejectedError`.

4. **Reversible Adaptation:**
   - No learning update or adapter activation is irrevocable.
   - The prior state snapshot must be recorded in `rollback_value` before applying activation.
   - `rollback_proposal()` must restore the previous value bit-for-bit.
