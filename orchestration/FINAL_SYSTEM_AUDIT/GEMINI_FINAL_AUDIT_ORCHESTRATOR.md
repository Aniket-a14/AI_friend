You are now performing the final system-level validation and release gate for the completed six-phase humanoid brain architecture implementation.

All six implementation phases are complete.

Your architectural source of truth is:

`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`

Your job is NOT to perform the entire audit yourself.

Your role is to coordinate two independent final audits:

* Codex = engineering/runtime/integration audit
* Claude = cognitive/behavioral/research audit

Then you will reconcile both reports, verify unresolved claims where necessary, run or coordinate final benchmarks, and decide whether the complete architecture passes as a coherent system.

Start by reading:

* `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`
* `orchestration/MASTER_STATE.md`
* all six phase `PHASE_GATE.md` files
* all six phase acceptance criteria
* benchmark results
* major review/fix records
* current Git state and final integrated branch

Do not assume that six individually passing phases automatically mean the complete system is correct.

The central question is:

**Do the six completed phases now form one coherent, measurable, provider-independent humanoid brain architecture that matches the final architectural specification?**

Create:

`orchestration/FINAL_SYSTEM_AUDIT/`

Use it for the final audit state.

At minimum prepare:

* `CODEX_FINAL_AUDIT_TASK.md`
* `CLAUDE_FINAL_AUDIT_TASK.md`
* `FINAL_BENCHMARK_PLAN.md`

Codex should independently inspect the final integrated repository and produce:

`CODEX_FINAL_SYSTEM_AUDIT.md`

Claude should independently inspect the final integrated system and produce:

`CLAUDE_FINAL_COGNITIVE_AUDIT.md`

Do not allow either agent to read the other's final audit before completing its own initial assessment.

After both reports are complete:

1. Read both fully.
2. Compare their findings.
3. Classify every major issue as:

   * BLOCKER
   * HIGH
   * MEDIUM
   * LOW
   * INVALID
   * NEEDS_EXPERIMENT
4. Resolve disagreements using:

   * code evidence
   * architecture requirements
   * behavioral evidence
   * benchmarks
   * research evidence
5. Create:
   `FINAL_FIX_PLAN.md`
6. Assign accepted engineering fixes primarily to Codex.
7. Assign accepted cognitive/behavioral fixes primarily to Claude.
8. Use cross-review where a fix materially affects the other agent's domain.
9. Run only necessary fix rounds. Do not enter an endless review loop.

After fixes are integrated, run final full-system validation.

Validate at least:

* complete end-to-end cognitive flow
* architecture invariants
* memory/state persistence
* action selection separate from language generation
* fast vs slow cognition
* interruption handling
* background cognition
* emotion/appraisal causal influence
* global-control/neuromodulatory causal influence
* learning and reflection
* rollback/reviewability
* self-model consistency
* personality/identity persistence
* social/relationship continuity
* foundation-model independence
* voice-provider independence
* vision-provider independence
* error/failure recovery
* concurrency/state integrity
* regression suite
* static analysis
* complexity
* resource usage
* latency
* GPU-dependent benchmarks
* ablation experiments required by the architecture

Do not accept subjective demonstrations as proof of cognitive mechanisms where measurable tests are possible.

For important cognitive mechanisms, use ablation where feasible:

architecture with mechanism
versus
architecture without mechanism

If disabling a supposedly important mechanism produces no measurable behavioral or system difference, flag that mechanism.

Run the final benchmarks on the designated GPU server where relevant and record:

* hardware
* software/model versions
* final commit SHA
* configuration
* number of runs
* measurements
* variance
* baselines
* interpretation
* limitations

Create:

`FINAL_SYSTEM_VALIDATION_REPORT.md`

The report should contain:

# Final System Validation Report

## 1. Executive Verdict

## 2. Final Repository State

## 3. Architecture Conformance

## 4. Codex Engineering Audit Summary

## 5. Claude Cognitive Audit Summary

## 6. Reconciled Findings

## 7. Fixes Applied

## 8. End-to-End Cognitive Flow Validation

## 9. Architecture Invariants

## 10. Memory and Persistent State

## 11. Emotion/Appraisal

## 12. Global Control / Neuromodulation

## 13. Fast and Slow Cognition

## 14. World/Self/Social Models

## 15. Learning and Metacognition

## 16. Action Selection

## 17. Voice and Vision Boundaries

## 18. Provider Independence

## 19. Regression and Integration Results

## 20. GPU and Runtime Benchmarks

## 21. Ablation Results

## 22. Remaining Weaknesses

## 23. Research Claims Currently Supported

## 24. Research Claims Not Yet Supported

## 25. Final Release Gate

The final gate must be exactly one of:

### PASS

The complete architecture is coherent, validated, and no critical unresolved findings remain.

### PASS_WITH_LIMITATIONS

The architecture is fundamentally valid, but specific non-critical limitations remain and are explicitly documented.

### FAIL

Critical architectural, behavioral, integration, or evaluation problems remain.

Do not lower standards to obtain PASS.

If the final system passes, update `orchestration/MASTER_STATE.md` to mark all six implementation phases and the final system gate complete.

Do not begin new architecture phases or add new features during this audit.

Do not push unless explicitly authorized.

Your final response should contain only:

* final audit status
* Codex audit status
* Claude audit status
* final system gate
* number of BLOCKER/HIGH issues remaining
* final validation report filename
* next recommended stage
