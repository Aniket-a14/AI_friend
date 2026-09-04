# Phase 07 Codex Package A Completion Summary

Date: 2026-09-04
Branch: `codex/phase-07`

## Fix round update

Applied the accepted Phase 07 arbitration fixes:

- `CognitiveService` now passes its `learning_governor` into
  `ReflectionService`, and the reflection constructor accepts and stores that
  shared instance.
- `ActionService` now builds an `ExternalActionIntent` and invokes a configured
  dispatcher for `EXTERNAL_ACT`. Successful dispatch emits one terminal done
  chunk; missing dispatchers, dispatcher failures, and invalid results fail
  closed with an error and terminal done chunk.
- `_on_memory_surfaced` now preserves `contradiction_state`, `outage_flag`,
  `metadata`, and `belief_record` for both list and single-memory payloads.
- Added regression coverage for governor identity, external dispatch success
  and failure, and epistemic memory metadata preservation.

## Fix round verification

- Focused command: **122 passed, 0 failures, 0 errors, 0 skipped** for
  `test_runtime_composition.py`, `test_action_selection.py`, and
  `test_causal_slice.py`.
- Full backend suite in the restricted sandbox: **2,332 passed, 0 failures,
  8 environment errors, 0 skipped**. All 8 errors were NATS loopback socket
  setup failures with `PermissionError: [Errno 1] Operation not permitted`.
- Socket-permitted rerun: **8 passed, 0 failures, 0 errors, 0 skipped** for
  `test_nats_accounts_enforcement.py`; together with the sandbox run, all
  2,340 collected tests passed.
- `ruff check .`: passed.
- `radon cc app/ -s -n D`: passed with no rank D, E, or F findings.
- All added and modified lines in this fix round are pure 7-bit ASCII.
- The requested `../.venv/bin/python` path does not exist in this worktree;
  verification used the repository-shared interpreter at
  `/Users/aniketsaha/Projects/AI_friend/.venv/bin/python`.

## Implemented

- Composed `SQLiteWorkspaceStore`, `TemporalMemoryStore`,
  `BackgroundScheduler`, deterministic plan verifier and executor,
  `EpisodicSimulator`, `LearningGovernor`, `OfflineAdapterGate`,
  `ProviderCapabilityNegotiator`, and `ExternalActionDispatcher` in
  `CognitiveService`.
- Forwarded the composed services through `CognitivePipeline`. Session state
  uses the workspace store when workspace authority is enabled and refreshes
  the snapshot before Stage 6.
- Updated `BrainAgent` to read the authoritative workspace snapshot and pass it
  into `CognitiveService.process_event`, with compatibility for older injected
  process-event doubles.
- Mapped selected `WAIT` candidates to `action_type="WAIT"` and added a silent
  WAIT handler that emits exactly `{"type": "done", "data": ""}`.
- Added dispatcher-backed EXTERNAL_ACT handling with fail-closed errors and
  composition regression tests.
- `session_state.py` already contained the required graceful
  `Config.WORKSPACE_AUTHORITATIVE` lookup at the Phase 07 baseline; no change
  was needed there.

## Verification evidence

- Requested focused command: 119 passed, 0 failures, 0 errors, 0 skipped.
- Full backend suite: 2,337 passed, 0 failures, 0 errors, 0 skipped in the
  loopback-socket-permitted rerun. The sandboxed run had 8 NATS setup errors
  caused by `PermissionError: [Errno 1] Operation not permitted`; it had no
  assertion failures.
- `../.venv/bin/python -m ruff check .`: passed.
- `../.venv/bin/python -m radon cc app/ -s -n D`: no D, E, or F findings.
- New source, test, ledger entry, and this result document contain only 7-bit
  ASCII. Pre-existing non-ASCII bytes in untouched legacy source remain.

## Scope note

Package B behavior was not changed: configuration default activation, memory
activation outage handling, dream quarantine, cross-provider evaluation, and
GPU benchmarks remain outside this package. The minimal `ReflectionService`
constructor contract was added because the accepted governor injection cannot
instantiate otherwise. No push or merge was performed.
