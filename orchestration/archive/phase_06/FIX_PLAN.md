# Phase 06 Peer Review Arbitration and Fix Plan

Phase: PHASE_06
Arbitrator: Antigravity Orchestration Lead
Date: 2026-09-04
Target Branches: `codex/phase-06` and `claude/phase-06`

---

## 1. Arbitration Summary

Both peer reviews were rigorous, identifying critical P0 bypasses, soundness bugs, and schema/isolation gaps with concrete, runnable reproductions.

All P0 and P1 findings from both reviews are sustained and must be resolved before integration:

### Package A (Codex) - Sustained Findings:
1. **P0-1 (Fallback Loop Guard Race & Silent Success):** `DeterministicPlanExecutor._execute_chain` loop guard exits prematurely when revisiting nodes in `completed`, failing to flag execution fallback cycles and reporting `succeeded=True` with `errors=[]` when every step fails. Must fix loop cycle detection, ensure failed executions never report success, and ensure `simulate_plan` rejects invalid plans or handles failures cleanly.
2. **P0-2 (Simulation Quarantine & Action Callback Context):** `EpisodicSimulator.simulate_plan` provides no simulation context to caller-supplied `action` callbacks, allowing unflagged side effects. Must provide explicit `SimulationContext` / `is_simulation=True` signaling, document purity requirements, and tag all execution products.
3. **P1-1 (False-Positive Cycle Detection on Redundant Effects):** `DeterministicPlanVerifier._dependency_graph` generates spurious cycle errors when later steps redundantly re-affirm flags needed by earlier steps, and `_effect_can_establish` disagrees with `precondition_holds` regarding `DELETE`/`NOT_EQUAL`. Must make causal cycle detection order-aware and align `DELETE` semantics.
4. **P1-2 (Self-Referential Fallback Step):** `PlanArtifact` validator allows a step to name itself as its own fallback (`fallback_step_id == step_id`). Must reject self-referential fallback references.
5. **P1-3 (Missing Test Coverage for Retries, Budget & Operators):** Add unit tests for retry-then-succeed, retry exhaustion, effect operators (`INCREMENT`, `APPEND`, `DELETE`), and step budget limits.

### Package B (Claude) - Sustained Findings:
1. **P0-1 (Protected Domain & Value Hard Invariant Bypasses):** `check_targets_protected_domain` only inspects `target_domain` and misses `proposed_value` and `rollback_value` keys; tokenizer misses braces, parens, commas, backslashes, and joined/camelCase tokens; and no re-check occurs before activation/rollback state mutations. Must inspect all domains and value keys recursively, expand tokenization to all delimiters and camelCase, freeze/deep-copy proposals, and re-validate before state writes.
2. **P0-2 (Adapter Qualification Probe Coverage & Unforgeable Activation):** `OfflineAdapterGate.qualify` checks only probe intersection rather than full baseline probe coverage; `activate` accepts arbitrary unverified caller arguments. Must require complete baseline probe coverage (fail-closed on dropped probes), register qualification records internally, and verify target digests at activation.
3. **P1-1 (Section 21 Schema Completeness):** Add `training_provenance` and `post_activation_measurement` fields to `LearningProposal` per Section 21.
4. **P1-2 (Atomicity & Error Handling during State Writes):** Ensure failures during state application in `activate()` or `rollback()` do not leave proposal status out of sync with actual state.
5. **P1-3 (Curiosity Noise & Non-finite Robustness):** Reject `NaN`/`inf` inputs in `LearningProgressCuriosity.record()`, and add variance/stability filtering so steady progress reliably outranks random noise.

---

## 2. Action Items

- Codex executes `orchestration/PHASE_06/CODEX_FIX_TASK.md` in `/Users/aniketsaha/Projects/ai-friend-codex`.
- Claude executes `orchestration/PHASE_06/CLAUDE_FIX_TASK.md` in `/Users/aniketsaha/Projects/ai-friend-claude`.
- Both packages must maintain 100% pure 7-bit ASCII, 0 ruff errors, and 0 radon D/E/F cyclomatic complexity findings.
