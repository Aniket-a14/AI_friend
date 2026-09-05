# Phase 02 Fix Plan: Arbitration and Resolution

Date: 2026-09-04
Phase: 02 (Memory Truth and General Action Selection)
Status: IN_PROGRESS (Fix Round)

## 1. Executive Summary

Both reciprocal peer reviews have completed with substantive technical rigor:
- Claude reviewed Codex: 9 findings (2 High, 5 Medium, 2 Low).
- Codex reviewed Claude: 8 findings (2 Blocker, 3 High, 3 Medium).

Gemini (Orchestrator) has arbitrated all findings. This document records the final verdict for each finding and the required fixes for Codex (Package A) and Claude (Package B).

---

## 2. Arbitration of Claude Review of Codex (Package A)

### F1 [HIGH] Bi-temporal `as_of` query bug
- Verdict: ACCEPT
- Rationale: `query_current_beliefs(as_of=t)` hardcoding `status = 'ACTIVE'` fails when querying past valid intervals of superseded records.
- Action: When `as_of` is provided, query records where `valid_from <= as_of AND (valid_until IS NULL OR valid_until > as_of)` with `status IN ('ACTIVE', 'SUPERSEDED')`. When `as_of` is None, query `status = 'ACTIVE'`.

### F2 [HIGH] `classify_contradiction` defaults to CONFLICT
- Verdict: ACCEPT WITH MODIFICATION
- Rationale: Slot updates with matching subject and predicate (e.g., "city = Seoul" superseding "city = Tokyo") should default to `UPDATE` when the new assertion has equal or higher confidence and no conflicting temporal interval, rather than falling through to `CONFLICT`.
- Action: When `existing.predicate == incoming.predicate` and `existing.subject == incoming.subject`, if `incoming.confidence >= existing.confidence` and the new record does not specify an overlapping contradictory interval, classify as `UPDATE`. Reserve `CONFLICT` for cases where confidence is ambiguous or both assert simultaneous contradictory truths.

### F3 [MEDIUM] Backdated update interval inversion
- Verdict: ACCEPT
- Rationale: If `new_record.valid_from < existing.valid_from`, setting `existing.valid_until = new_record.valid_from` creates an inverted interval (`valid_until < valid_from`).
- Action: Validate in `apply_contradiction` that `new_record.valid_from >= existing.valid_from`. Raise `InvalidIntervalError` (subclass of `ValueError`) if violated.

### F4 [MEDIUM] Raw SQLite exceptions leak
- Verdict: ACCEPT
- Rationale: Callers should catch domain-specific errors rather than raw `sqlite3.OperationalError` or `sqlite3.IntegrityError`.
- Action: Introduce domain exceptions in `backend/app/state/memory_records.py`:
  - `MemoryStoreError` (base)
  - `DuplicateRecordError(MemoryStoreError)`
  - `RecordNotFoundError(MemoryStoreError)`
  - `InvalidIntervalError(MemoryStoreError, ValueError)`
  Wrap SQLite operations to raise these exceptions.

### F5 [MEDIUM] ProcedureRecord unpersisted
- Verdict: ACCEPT
- Rationale: While `ProcedureRecord` was defined, `TemporalMemoryStore` omitted a `procedures` table.
- Action: Add a `procedures` table schema and CRUD methods (`store_procedure`, `get_procedure`) in `TemporalMemoryStore` to make the storage interface complete.

### F6 [MEDIUM] Concurrency test missing for `apply_contradiction`
- Verdict: ACCEPT
- Rationale: Multiple threads or transactions applying contradictions on the same record must maintain consistency.
- Action: Add concurrency test in `test_memory_truth.py` demonstrating thread-safe or serialized contradiction handling.

### F7 [MEDIUM] Boundary test at exact timestamps
- Verdict: ACCEPT
- Rationale: Edge cases where `as_of == valid_from` or `as_of == valid_until` need explicit test verification.
- Action: Add tests verifying `as_of == valid_from` returns the record (inclusive) and `as_of == valid_until` excludes it (exclusive).

### F8 & F9 [LOW] SQL filtering and docstring cleanups
- Verdict: ACCEPT
- Rationale: Good hygiene.
- Action: Ensure all queries use SQL WHERE clauses instead of Python in-memory post-filtering where feasible.

---

## 3. Arbitration of Codex Review of Claude (Package B)

### B1 [BLOCKER] Production turns cannot supply MemoryActivation tokens
- Verdict: ACCEPT WITH MODIFICATION
- Rationale: While cross-package integration between `TemporalMemoryStore` and `CognitivePipeline` is finalized at integration, `CognitivePipeline` and `CognitiveService.process_event` must bridge surfaced memories into `MemoryActivation` tokens when `Config.PHASE_02_MEMORY_TRUTH` is enabled.
- Action:
  1. Add an adapter helper `memories_to_activations(surfaced_memories)` that converts legacy memory dicts or records to `list[MemoryActivation]`.
  2. Update `CognitiveService.process_event` in `core.py` to accept optional `memory_activations: list[MemoryActivation] | None = None`. If None and `Config.PHASE_02_MEMORY_TRUTH` is True, adapt `self.surfaced_memories`.
  3. Forward `memory_activations` into `self.pipeline.run_pipeline(...)`.
  4. Add an end-to-end test in `test_action_selection.py` testing `process_event()` producing an ASK or constrained selection with `PHASE_02_MEMORY_TRUTH=True`.

### B2 [BLOCKER] ASK is committed in trace but never becomes executed action
- Verdict: ACCEPT
- Rationale: If `intent.kind == ActionKind.ASK`, the executed plan must reflect clarification behavior rather than a generic `RESPOND_CHAT`.
- Action:
  1. When `intent.kind == ActionKind.ASK`, set `plan.action_type = "CLARIFY"` (or configure `ActionPlan` with an explicit clarification directive).
  2. In `ActionService.execute` (or social response execution), when action is `CLARIFY` / `ASK`, constrain the prompt or produce a deterministic clarification question (e.g. asking which statement is accurate).
  3. Assert in tests that the emitted response or action plan reflects clarification rather than generic chat.

### B3 [HIGH] Constraint-first filtering is inert for generated candidates
- Verdict: ACCEPT
- Rationale: `_build_candidates()` creates candidates with empty `constraint_claims`, so `filter_constraints()` never filters generated candidates.
- Action:
  1. Populate `constraint_claims` on generated candidates based on the action kind and context (e.g., SPEAK includes proposed topic claims, ASK includes clarification claims).
  2. Map forbidden claims from `state_snapshot` or identity boundaries to filter candidate actions.
  3. Add a test showing a candidate being rejected by `filter_constraints` during a decision cycle.

### B4 [HIGH] AntiInjectionGate has no live enforcement point
- Verdict: ACCEPT
- Rationale: `AntiInjectionGate.sanitize_memory_text()` was defined but never called in prompt assembly.
- Action:
  1. Wire `AntiInjectionGate.sanitize_memory_text()` into the memory prompt assembly path (e.g. in `_format_memory_context` or `MemoryActivation` rendering in `action.py` / `pipeline.py`).
  2. Verify that injected memory strings are sanitized before being added to LLM prompts.

### B5 [HIGH] AntiInjectionGate misses common instruction & role-hijack variants
- Verdict: ACCEPT
- Rationale: Codex proved bypasses with "Ignore the previous instructions", zero-width spaces, "System:", "[INST]", etc. Partial redaction also leaves imperative payloads.
- Action:
  1. Apply Unicode normalization (NFKC) and strip zero-width characters (`\u200b`, `\u200c`, `\u200d`, `\ufeff`).
  2. Expand regex to match "ignore (the|all|any|previous) instructions", role labels (`System:`, `User:`, `Assistant:`, `[INST]`, `[/INST]`, `<|im_start|>`), and system prompt exfiltration directives.
  3. When an injection attempt is detected, quarantine/redact the entire untrusted memory field (replace with `[UNTRUSTED_CONTENT_FILTERED]`) rather than merely stripping the trigger phrase.
  4. Add adversarial tests covering all reported bypasses.

### B6 [MEDIUM] Bidirectional substring matching in `_claims_overlap`
- Verdict: ACCEPT
- Rationale: `c in f or f in c` causes false positives ("body" in "somebody") and false negatives.
- Action: Use word-boundary regex (`\b`) or normalized token set intersection for claim matching rather than raw substring containment.

### B7 [MEDIUM] Schema is partial subset of architecture section 22
- Verdict: ACCEPT
- Rationale: `ActionKind` should include the full section 22 set to avoid future schema churn.
- Action: Add `UPDATE_STATE`, `EXTERNAL_ACT`, `INTERRUPT`, `CONTINUE` to `ActionKind` enum.

### B8 [MEDIUM] Default-off pipeline compatibility breaks 2-argument stubs
- Verdict: ACCEPT
- Rationale: Legacy `decision.decide(event, state_snapshot)` mocks fail if 3 arguments are passed unconditionally.
- Action: In `pipeline.py`, check if `decision.decide` accepts `memory_activations` (via `inspect.signature` or arity check) before passing it, or only pass it when `PHASE_02_MEMORY_TRUTH` is True and supported. Add a test with a legacy 2-arg mock.

---

## 4. Next Steps
1. Issue `CODEX_FIX_TASK.md` to Codex worktree.
2. Issue `CLAUDE_FIX_TASK.md` to Claude worktree.
3. Update `peer_review_prompts` artifact with single-paragraph execution prompts for both agents.

