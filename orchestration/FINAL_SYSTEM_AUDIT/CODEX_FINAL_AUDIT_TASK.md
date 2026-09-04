Perform an independent final engineering audit of the fully integrated six-phase humanoid brain architecture.

Do not read Claude's final audit before completing your own initial report.

Read:

* `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`
* `orchestration/MASTER_STATE.md`
* all six phase gates
* all six phase acceptance criteria
* relevant benchmark results
* the final integrated repository

Your role is:

**engineering truth**

Do not assume that because every phase passed independently, the combined system is correct.

Audit the repository as one integrated runtime system.

Focus on:

## 1. Architecture Conformance

Trace whether the final code actually implements the accepted architecture.

Verify:

* perception integration
* salience/attention
* persistent mental state
* memory
* appraisal
* affect/emotional state
* global control / neuromodulation
* goals
* world model
* self model
* social state
* reasoning
* fast cognition
* slow cognition
* background cognition
* action selection
* learning/reflection
* voice boundary
* vision boundary
* provider abstraction

For important claims, reference actual files, classes, functions, schemas and runtime paths.

## 2. End-to-End Runtime Flow

Trace actual runtime execution for scenarios such as:

* normal user interaction
* memory retrieval
* emotional-state change
* high-salience event
* interruption
* fast reaction
* slow reasoning
* background cognition
* action selection
* speech intent generation
* learning/reflection
* restart/state restoration

Identify broken or bypassed paths.

## 3. Cross-Phase Integration

Look specifically for problems caused by independently implemented phases:

* duplicated state
* competing sources of truth
* stale APIs
* incompatible assumptions
* duplicated logic
* dead code
* disconnected features
* circular dependencies
* phase-specific adapters that no longer belong
* inconsistent schemas
* unnecessary compatibility layers

## 4. State Integrity

Inspect persistent and transient state ownership.

Verify:

* no important state is duplicated unsafely
* update paths are deterministic where required
* concurrency does not create inconsistent mental state
* persistence/recovery works
* failures do not corrupt state
* ordering-sensitive events are handled correctly

## 5. Action Selection

Verify that action selection genuinely exists independently from language generation.

Check whether the system can represent/select actions such as:

* speak
* wait
* stay silent
* retrieve memory
* observe
* reason further
* update internal state
* change goal
* interrupt
* perform external action

Flag any path where generated text still implicitly becomes the decision.

## 6. Fast / Slow Path

Verify the distinction is real.

Measure/inspect:

* what bypasses expensive reasoning
* what uses deterministic logic
* latency-critical paths
* interruption handling
* propagation from fast path to slower cognition
* race conditions between pathways

## 7. Memory Engineering

Audit:

* storage
* retrieval
* ranking
* consolidation
* forgetting
* contradiction handling
* provenance
* relationship state
* autobiographical continuity
* recovery after restart

Check whether architecture-specific memory behavior is actually used rather than merely stored.

## 8. Learning / Reflection

Verify:

* what actually changes
* durable persistence
* approval/review
* rollback
* failure behavior
* regression protection
* whether incorrect learning can propagate

Do not call storage "learning."

## 9. Provider Independence

Inspect coupling to:

* LLM provider
* TTS
* STT
* vision model
* embedding model
* databases/infrastructure

Verify provider-specific logic does not leak into core cognition beyond adapters.

## 10. Error Handling and Recovery

Test or inspect:

* provider failures
* model timeout
* malformed model output
* database failure
* queue failure
* missing memory
* corrupted state
* interrupted background task
* restart
* partial external-service availability

## 11. Tests

Run the complete relevant test suite.

Also inspect test quality.

Identify:

* missing integration tests
* weak assertions
* tests that only verify mocks
* untested critical paths
* flaky tests
* stale tests
* accidental test coupling

Add no production changes during the initial audit.

## 12. Static / Structural Quality

Inspect:

* cyclomatic complexity
* dead code
* duplication
* module boundaries
* dependency direction
* type safety
* lint/static analysis
* architectural drift

Do not recommend cosmetic refactors unless they materially improve reliability or architecture.

## 13. Performance

Run local measurements where appropriate.

Prepare GPU-dependent tests where required by the final audit task.

Measure relevant:

* end-to-end latency
* fast-path latency
* slow-path latency
* memory retrieval latency
* throughput
* CPU/RAM
* model calls
* queue behavior
* background processing overhead

## 14. Architecture Invariants

Verify every invariant in `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`.

For each invariant mark:

* PASS
* PARTIAL
* FAIL
* NOT TESTABLE

## 15. Severity

Classify findings:

* BLOCKER
* HIGH
* MEDIUM
* LOW

Do not inflate severity.

Provide evidence for each finding.

Create:

`orchestration/FINAL_SYSTEM_AUDIT/CODEX_FINAL_SYSTEM_AUDIT.md`

Use this structure:

# Codex Final System Audit

## Executive Verdict

## Repository State

## Architecture Conformance

## End-to-End Runtime Flow

## Cross-Phase Integration

## State Integrity

## Memory

## Fast/Slow Cognition

## Action Selection

## Learning/Reflection

## Provider Independence

## Failure Recovery

## Tests

## Static/Structural Quality

## Performance

## Architecture Invariants

## Findings

## Recommended Fixes

## Remaining Engineering Risks

## Final Engineering Verdict

Do not implement fixes yet.

Finish the audit first.

After writing the report, stop and wait for Gemini's arbitration/fix assignment.

Do not merge or push.
