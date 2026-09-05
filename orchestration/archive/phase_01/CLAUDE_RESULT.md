# Phase 01 Result: Claude  -  Perception Normalization & Causal Outcome Loop

**Agent:** Claude
**Worktree:** `/Users/aniketsaha/Projects/ai-friend-claude`
**Branch:** `claude/phase-01`
**Final commit SHA:** `5b4f4af59ec4d0daed8dbb1e920e96c70c1d9dab` (fix round; see Section 9). Initial implementation commit: `bad24de3c93b88cbeb52e6b556eda292d4e4c5ea`.
**Baseline SHA:** `bb5be86ba7c14ab7f8afa056707597a37d3bdd86`
**Status:** Local package complete, including the `FIX_PLAN.md` Part B fix round. Local verification suite green. GPU criteria remain `PENDING_GPU` (unchanged  -  no GPU-touching work was in this package).

---

## 1. Work Completed

Implemented the percept-normalization and causal-outcome half of the Phase 01 slice per `CLAUDE_TASK.md`:

1. **`PerceptEnvelope`** (`app/cognitive/percept.py`, new)  -  a unified, validated shape for every mesh-sourced event, with one converter per modality: `from_chat_input`, `from_vision_description`, `from_facial_reflex`, `from_audio_stop`, `from_system_tick`, `from_playback_progress`. Each converter reads the exact wire dict its corresponding `brain_agent.py` handler already receives and copies it into `raw_payload` verbatim, so normalization is lossless even though only a subset of fields is promoted to typed attributes.
2. **`ActionIntent` / `OutcomeRecord`** (`app/cognitive/action_intent.py`, new)  -  the frozen contract from `PLAN.md` Section 6, plus `build_action_intent`/`build_outcome_record` convenience constructors (`intent_id`/`outcome_id`/`committed_at`/`elapsed_ms` stamped automatically).
3. **Pipeline seam** (`app/cognitive/pipeline.py`)  -  `CognitivePipeline.execute()` gained two optional parameters, `percept: PerceptEnvelope | None` and `workspace: WorkspaceSnapshotLike | None`. Stage 6 (right after the BT decision, before Stage 7's action-payload prep) now always commits an `ActionIntent` and yields it as a new `{"type": "action_intent", ...}` chunk, using `workspace.epoch`/`workspace.revision` when supplied and `(0, 0)` when not  -  so every turn cites a tuple even before `WorkspaceStore` is wired in.
4. **BrainAgent causal loop** (`app/agents/brain_agent.py`)  -  all five specified handlers (`_on_chat_input`, `_on_vision_description`, `_on_facial_reflex`, `_on_audio_stop`, `_on_audio_playback_progress`) now build and stash a `PerceptEnvelope` (`self.last_percept`). The turn's committed `ActionIntent` is captured off the pipeline's new chunk type into `self._active_action_intent`. A new `_emit_outcome_record` helper binds a terminal `OutcomeRecord` to that intent from three sites:
   - `_on_audio_playback_progress`, when `progress.completed`  -  `status="COMPLETED"`.
   - `_truncate_interrupted_reply`, both branches (real offset known, and the "no progress, keep full text" branch)  -  `status="TRUNCATED"`.
   - `_cancel_active_generation`, only when nothing had streamed yet (`last_assistant_response` empty)  -  `status="CANCELLED"`, so a turn that never spoke still gets a terminal record, and a turn that partially spoke doesn't get *two* disagreeing records (cancellation defers to the truncation call that always follows it in the only production caller, `_on_audio_stop`).
5. **`test_causal_slice.py`** (new)  -  the five required tests plus supporting coverage (28 tests total): percept fidelity across all six modalities (each exercised both with and without its optional fields, to force real field-reads rather than coincidental matches with hardcoded defaults), `ActionIntent` commitment against a workspace revision (and the `(0,0)` fallback), and all three terminal-outcome paths (completed/truncated/cancelled), plus the "no active intent -> no-op" and "cancellation defers to truncation" edge cases.

## 2. Files Changed

| File | Change |
|---|---|
| `backend/app/cognitive/percept.py` | New |
| `backend/app/cognitive/action_intent.py` | New |
| `backend/app/cognitive/pipeline.py` | Modified  -  `WorkspaceSnapshotLike` Protocol, `_commit_action_intent`/`_derive_action_kind`, `execute()` signature |
| `backend/app/agents/brain_agent.py` | Modified  -  percept wiring, `_active_action_intent`/`last_percept`/`_last_outcome_record` state, `_emit_outcome_record`, outcome emission at 3 sites |
| `backend/tests/test_causal_slice.py` | New  -  28 tests |
| `backend/pyproject.toml` | Modified  -  added `app/cognitive/percept.py`/`action_intent.py` to the mutmut `only_mutate` allowlist and `test_causal_slice.py` to its scoped test selection, matching the repo's existing per-module mutation-gate convention |

**Not touched:** `app/state/workspace.py`, `app/state/workspace_store.py` (Codex-owned, and did not exist in this worktree at execution time  -  see Section 3), `app/state/memory_store.py`, LLM client wrappers/sampling parameters.

## 3. Design Decisions

- **Codex's `app/state/workspace.py` doesn't exist in this worktree.** Per the parallel-execution plan, Codex builds it independently in `codex/phase-01`; it isn't merged into `claude/phase-01`. Rather than hard-importing a module this branch must not own and cannot see, `pipeline.py` defines a structural `WorkspaceSnapshotLike` `Protocol` (`epoch`/`revision`) that Codex's real frozen `CognitiveWorkspaceSnapshot` dataclass will satisfy automatically once branches integrate, with zero code change required on either side.
- **`ActionIntent` is always committed, not only when a `BehaviorDecision` is attached.** Some BT branches (short-circuited deterministic plans) don't build one; `_commit_action_intent` falls back to a synthesized `{"goal", "action_type"}` payload so AC-01 ("100% of turns reference a valid tuple") holds unconditionally.
- **`isinstance(plan.behavior_decision, BehaviorDecision)` rather than `is not None`.** Several pre-existing tests build `ActionPlan` from a bare `MagicMock()`, where `.behavior_decision` auto-vivifies as a truthy mock, not `None`. Using `is not None` broke those tests by trying to `.model_dump()` a `MagicMock`; `isinstance` degrades to the synthesized-payload branch for anything that isn't a real `BehaviorDecision`, additive rather than newly required of every caller.
- **`getattr(self, "_active_action_intent", None)` at every read site**, mirroring the codebase's own existing pattern for `_active_response_turn_id`. Several pre-existing tests build `BrainAgent` via `object.__new__`, bypassing `__init__` entirely  -  a direct attribute read would `AttributeError`, silently swallowed by the enclosing handler's `except Exception`, which is exactly what caused the two real regressions described in Section 6.
- **Cancellation vs. truncation don't double-record.** `_cancel_active_generation` only emits `CANCELLED` when nothing had streamed yet; when something had, it defers entirely to `_truncate_interrupted_reply` (called immediately after it by the only production caller, `_on_audio_stop`), so an interrupted turn gets exactly one terminal `OutcomeRecord`, matching PLAN.md's "terminal" framing.
- **`ActionIntent`/`OutcomeRecord` stay in-process, not NATS `Topics` members**  -  same reasoning `behavior_contracts.BehaviorDecision`'s docstring already gives: promoting a type to the wire is later work, once the shape has proven itself here first.
- **Kind mapping is a small explicit table** (`BACKGROUND_CONSOLIDATION` -> `REFLECT`, everything else -> `SPEAK`), since every other current `action_type` (`RESPOND_CHAT`, `STORE_MEMORY`) still ends in `action.py` streaming spoken content.

## 4. Tests Added

`backend/tests/test_causal_slice.py`  -  28 tests:

- `test_percept_envelope_from_all_modalities` (12 parametrized cases  -  each of the 6 modalities exercised once with optional fields present using values deliberately distinct from the hardcoded fallback, and once absent) plus `test_percept_ids_are_unique_per_call`.
- `test_clamp_confidence_bounds` (5 cases) + `test_clamp_confidence_uses_its_own_default_when_caller_omits_one`.
- `test_build_outcome_record_defaults_character_offset_to_zero`, `test_build_outcome_record_elapsed_ms_measures_real_time_since_commit`.
- `test_pipeline_commits_action_intent`, `test_pipeline_action_intent_defaults_workspace_when_absent`.
- `test_turn_completion_emits_completed_outcome`, `test_turn_interruption_emits_truncated_outcome`, `test_cancelled_generation_emits_cancelled_outcome`, `test_cancel_active_generation_defers_to_truncation_when_text_exists`, `test_outcome_record_with_no_active_intent_is_skipped`.

## 5. Tests Executed and Results

All commands run from `backend/` with `../.venv/bin/python`. **Note on tooling:** `CLAUDE_TASK.md`'s literal baseline command (`pytest tests/test_behavior_tree.py`) references a file that doesn't exist in this repo (the real file is `tests/test_behavior_contracts.py`); ran the corrected path instead. Similarly, `mutmut`'s installed version (3.7.0) no longer accepts the `--paths-to-mutate` CLI flag documented in the task  -  scope is now configured via `pyproject.toml`'s `[tool.mutmut]` table, used instead.

| Command | Result |
|---|---|
| `pytest tests/test_behavior_contracts.py tests/test_pipeline.py tests/test_brain_agent_*.py -q` (baseline) | 28 passed |
| `pytest tests/test_causal_slice.py -q` | 28 passed |
| `pytest -q` (full suite) | **1865 passed, 0 failed, 0 errors** |
| `pre-commit run --files <changed files>` | end-of-file-fixer, trailing-whitespace, merge-conflict, private-key, ruff, ruff-format, codespell  -  all passed |
| `radon cc app/ --min D -s` (changed files) | no output (zero D/E/F complexity findings) |
| `radon mi` (changed files) | `A` on all four |
| `mypy app` | 16 pre-existing errors in 6 files unrelated to this change (verified identical on the unmodified baseline via `git stash`); **zero new errors** |
| `bandit -r` (changed files) | 0 issues, all severities |
| `ruff check` / `ruff format --check` (changed files) | clean |
| `codespell` (changed files) | clean |
| `mutmut run` (scoped to `percept.py`/`action_intent.py` via `pyproject.toml`) | **261/266 mutants killed (98.1%)**  -  remaining 5 are the `elapsed_ms` floor/scale (`max(1.0,...)`, `*1001.0` vs `*1000.0`, sub-millisecond precision on a diagnostic field) and three `observed_at=time.time()`-removal mutants that are genuinely equivalent (`PerceptEnvelope.observed_at`'s own pydantic field default is also `Field(default_factory=time.time)`) |

### Regressions found and fixed during verification

The full-suite run surfaced two real (pre-existing-test-exposed) bugs in this package's own code, both fixed before commit:

1. **`tests/test_phase6_advanced_cognition.py::test_vap_predictive_pre_generation`**  -  builds `ActionPlan` from a bare `MagicMock()`; `plan.behavior_decision` auto-vivifies truthy, so `_commit_action_intent`'s original `is not None` check tried `.model_dump()` on a `MagicMock`, raising a `pydantic.ValidationError`. Fixed via the `isinstance(..., BehaviorDecision)` check in Section 3.
2. **`tests/test_barge_in_truncation.py`** (4 tests)  -  builds `BrainAgent` via `object.__new__`, which skips `__init__`, so `self._active_action_intent` didn't exist as an attribute; reading it directly raised `AttributeError`, silently caught by `_on_audio_stop`'s enclosing `except Exception`, aborting the handler *before* it reached the real assertions the tests were checking (truncation, adrenaline release). Fixed via `getattr(self, "_active_action_intent", None)` at every read site, matching the codebase's own existing convention for `_active_response_turn_id`.

Both are documented in the codebase's own comments at the fix sites, and both classes of test double (mock `ActionPlan`, `object.__new__`-built `BrainAgent`) are exercised by `test_causal_slice.py` too, so a regression here would be caught by this package's own suite going forward, not just the pre-existing files that originally surfaced it.

## 6. Known Limitations

- **Environment tooling quirks** (documented pre-existing, reproduced and confirmed unrelated to this change via `git stash` before investigating further):
  - `CLAUDE.md`'s documented pytest-benchmark output-swallowing issue is real and was hit directly: `pytest` exits non-zero with fully empty stdout/stderr (past the one benchmark warning line) when any path on its command line doesn't exist, rather than printing the usual "file not found" usage message  -  this reproduces identically on the clean `bb5be86` baseline with no changes applied.
  - `mutmut run`'s baseline test-verification step crashes (`ImportError: cannot load module more than once per process`, a numpy re-import fragility under mutmut's copied-`mutants/`-tree execution model) whenever `app/state/memory_store.py`'s pre-existing scope is included in the same run as any other file  -  reproduces identically on the clean, unmodified `pyproject.toml`. Worked around by temporarily scoping `only_mutate`/`pytest_add_cli_args_test_selection` down to just this package's two new files for the mutation run itself, then restoring the full list (baseline entries intact, this package's two files and test selection added) before committing  -  see the clean diff in `pyproject.toml`.
- **`ActionIntent`/`OutcomeRecord` are diagnostic-only in this slice**  -  logged and held on `BrainAgent` instance attributes (`_active_action_intent`, `_last_outcome_record`), and, as of the fix round (Section 9, FIX-CLD-03), also retained in-process across turns (`_outcome_history`, queryable via `get_outcome_history(turn_id)`) rather than only the single most recent record. None of this is yet durably persisted across a process restart or published on the mesh  -  durable persistence is `WorkspaceStore`'s territory (Codex's package); publishing them as NATS `Topics` members is explicitly deferred, matching `behavior_contracts.BehaviorDecision`'s own precedent.
- **`WORKSPACE_AUTHORITATIVE`/dual-write (AC-07)** was not implemented here  -  that flag and `SessionState`'s dual-write hook are `CODEX_TASK.md`'s file (`app/state/session_state.py`). This package's `execute()` accepts `workspace=None` gracefully (falls back to `(0, 0)`), so it will not break either state of that flag once Codex's side lands, but AC-07 itself isn't exercised by anything in this branch alone.
- **16 pre-existing mypy errors, 4 pre-existing `ruff format` violations in `brain_agent.py`, and 16 lines the `ruff-format` pre-commit hook incidentally reformatted (whitespace/line-wrap only, verified semantically identical via diff) elsewhere in that file** predate this change (confirmed via `git stash` on the unmodified baseline) and were left as pre-existing rather than fixed, per the "preserve unrelated behavior" scope constraint  -  except the 4 `ruff format` violations, which the `ruff-format` pre-commit hook (required by AC-09) auto-corrected as an unavoidable side effect of running it against `brain_agent.py` for this package's own changes; confirmed cosmetic-only via diff before accepting.
- **AC-GPU-01/02/03**: unaffected by this package (no LLM/TTS/latency-path code touched) and remain `PENDING_GPU` per the orchestration schedule  -  nothing to report until the GPU server is online.

## 7. Unresolved Dependencies

- Integration with `app/state/workspace.py`/`WorkspaceStore` (Codex's package)  -  this branch's `WorkspaceSnapshotLike` Protocol is designed to accept Codex's real `CognitiveWorkspaceSnapshot` with zero code change on merge, but that hasn't been exercised against the real class yet since it doesn't exist in this worktree. **Update (fix round, Section 9):** `CognitiveService.process_event` now threads a supplied `workspace=` through to `pipeline.execute()` (FIX-CLD-01), so once a real `WorkspaceStore`-backed snapshot is wired into `BrainAgent`/`CognitiveService` (still outside this package's file ownership), the causal trace becomes real without any further change here. Until that wiring lands, `workspace=` is still never actually supplied in production, so turns still commit against the `(0, 0)` fallback  -  what changed is that the *pipe* is no longer the blocker; the *producer* still is.
- ~~`CognitiveService.process_event` (core.py, not owned by either package per `PLAN.md`'s work-package split) does not yet pass `percept=`/`workspace=` through to `pipeline.execute()`~~  -  **resolved by FIX-CLD-01** (Section 9): `process_event` now accepts and forwards both, and `BrainAgent` passes `self.last_percept` through on every chat-input turn.

## 8. Final Commit (initial implementation)

```
bad24de3c93b88cbeb52e6b556eda292d4e4c5ea
feat(cognitive): Phase 01 perception normalization and causal outcome loop
```

## 9. Fix Round (`orchestration/PHASE_01/CLAUDE_FIX_TASK.md`, `FIX_PLAN.md` Part B)

Executed after Codex's review of this package (`CODEX_REVIEW_OF_CLAUDE.md`) surfaced 7 findings, all accepted by the orchestrator's arbitration (`FIX_PLAN.md`) and assigned back to this branch as FIX-CLD-01..07.

### 9.1 Fixes implemented

| ID | Severity (Codex's review) | Fix |
|---|---|---|
| FIX-CLD-01 | BLOCKER | `CognitiveService.process_event` (`app/cognitive/core.py`) gained `percept: PerceptEnvelope \| None` / `workspace: WorkspaceSnapshotLike \| None` parameters, forwarded unchanged to `CognitivePipeline.execute`. `BrainAgent._process_chat_input_flow` now passes `percept=self.last_percept`. Before this, `process_event` had no such parameters at all, so every production turn's Stage 6 commit fell through to the `(0, 0)` fallback tuple regardless of what `self.last_percept` actually held. |
| FIX-CLD-02 | BLOCKER | `transport_agent.py`'s `_on_nats_audio` now enqueues a completion marker (empty PCM, `completed=True`) onto the same FIFO `audio_queue` whenever a stream message carries `done=True`, behind any real audio that same message enqueued. `_audio_playback_worker` recognizes the marker and calls `_maybe_publish_playback_progress(..., completed=True)` without attempting to capture it as audio  -  so the terminal `AudioPlaybackProgress(completed=True, ...)` publishes only once every real frame ahead of it has actually reached `audio_source.capture_frame`, the closest observable "reached the speaker" point in this architecture (same reasoning P4-2's mid-utterance progress events already use). Before this, only a confirmed `audio.stop` interruption ever produced a terminal signal; a turn that simply finished speaking normally produced none, so `BrainAgent` never saw `progress.completed` for the common case. |
| FIX-CLD-03 | BLOCKER | `BrainAgent._emit_outcome_record` now appends every record to `self._outcome_history: list[OutcomeRecord]` (lazily initialized via `getattr` for `object.__new__`-built test doubles, matching this file's existing convention), and a new `get_outcome_history(turn_id)` filters it. Before this, `_last_outcome_record` held only the single most recent record, overwritten by the next turn. |
| FIX-CLD-04 | HIGH | `_on_audio_playback_progress`'s COMPLETED path now uses `min(progress.character_offset, len(delivered))` instead of unconditionally assuming the full response was delivered. Trusts a genuinely smaller reported offset; clamps an offset that reaches or exceeds the delivered length down to the real string length rather than indexing past it. |
| FIX-CLD-05 | HIGH | `_replace_active_generation` now emits a `CANCELLED` `OutcomeRecord` (read under `_turn_state_lock`, after the prior task is confirmed cancelled but before the new task's coroutine has had a chance to run and reset `_active_action_intent`) whenever it actually cancelled a running turn. Before this, a new incoming `chat.input` preempting an in-flight generation left that turn with zero terminal records  -  only the `audio.stop` path (`_cancel_active_generation`) produced one. |
| FIX-CLD-06 | MEDIUM | `percept._clamp_confidence` now checks `math.isfinite(confidence)` and falls back to `default` for `NaN`/`+Inf`/`-Inf`  -  `max(0.0, min(1.0, nan))` returns `nan` unclamped in Python (`nan` compares `False` against everything) and `min(1.0, inf)` returns `1.0`, both of which previously slipped past the bounds check. |
| FIX-CLD-07 | MEDIUM | New `percept._percept_id(modality, data)` helper: derives `f"percept:{modality}:{source_id}"` from `data.get("utterance_id") or data.get("event_id") or data.get("id") or data.get("turn_id")` when present, falling back to the existing random `_new_percept_id` otherwise. Wired into `from_chat_input`, `from_audio_stop`, `from_playback_progress`  -  the three converters whose source contracts (`ChatInput`, `AudioStop`, `AudioPlaybackProgress`) carry a replay-identifying field. `from_vision_description`/`from_facial_reflex`/`from_system_tick` keep the random id (their source contracts carry no such field). Before this, every percept got a fresh random id on every call, so a JetStream redelivery of the same event (CLAUDE.md finding A1: a slow-acking handler triggers redelivery) minted a second, distinct percept for what was really one event. |

### 9.2 Design decisions

- **FIX-CLD-02's marker travels through the real audio queue, not a side channel.** An earlier, simpler design considered publishing `completed=True` directly from `_on_nats_audio` the moment `is_done` is observed, but that would announce completion before the queued PCM ahead of it has actually played through `_audio_playback_worker` -- premature relative to this file's own stated philosophy (`_maybe_publish_playback_progress`'s docstring: "the closest observable 'reached the speaker' point"). Routing the marker through the same `asyncio.Queue` gets FIFO ordering for free.
- **FIX-CLD-05 reads `_active_action_intent` after cancellation but before creating the new task's dependents can run.** `asyncio.create_task(coro)` only schedules `coro`; it does not run synchronously. So the interrupted turn's `_active_action_intent` is still in place when `_replace_active_generation` reads it, even though the new task has already been created and assigned by that point.
- **FIX-CLD-04 uses `min(...)`, not a conditional.** "Use the reported offset, or the delivered length if the report reaches/exceeds it" is exactly `min(progress.character_offset, len(delivered))` given `AudioPlaybackProgress.character_offset`'s own `ge=0` contract -- no branch needed.

### 9.3 Tests added

All in `backend/tests/test_causal_slice.py` unless noted:

- FIX-CLD-01: `test_process_event_forwards_percept_and_workspace_to_pipeline`, `test_process_event_defaults_percept_and_workspace_to_none`, `test_chat_input_flow_passes_last_percept_into_process_event`.
- FIX-CLD-02 (`backend/tests/test_transport_agent_playback_completion.py`, new file, 9 tests): producer-side marker enqueue/ordering (3 tests), consumer-side worker draining and publish ordering (2 tests), `_maybe_publish_playback_progress`'s `completed=True` dedupe-bypass and no-offset fallback (3 tests), plus a companion negative case. Also updated 2 pre-existing tests in `test_playback_progress.py` whose tuple-unpacking assumed the old 6-tuple queue shape.
- FIX-CLD-03: `test_outcome_history_is_queryable_by_turn_id`, `test_outcome_history_keeps_multiple_records_for_the_same_turn_in_order`, `test_outcome_history_initializes_lazily_without_init`.
- FIX-CLD-04: `test_completed_outcome_uses_the_reported_offset_when_smaller_than_full_text`, `test_completed_outcome_clamps_an_offset_that_exceeds_delivered_length`.
- FIX-CLD-05: `test_replace_active_generation_emits_cancelled_outcome_for_preempted_turn`, `test_replace_active_generation_emits_no_outcome_when_nothing_was_running`.
- FIX-CLD-06: `test_clamp_confidence_rejects_non_finite_values` (NaN/+Inf/-Inf, parametrized).
- FIX-CLD-07: `test_percept_id_prefers_utterance_id_over_other_identifiers` (parametrized, all 4 priority levels), `test_percept_id_falls_back_to_random_when_no_identifier_present`, `test_percept_id_is_stable_across_simulated_redelivery`; also updated the existing `test_percept_envelope_from_all_modalities` table (3 cases switched from prefix- to exact-match assertions, 1 new fallback case added for `from_playback_progress`).

Also required updating `tests/test_regressions.py::test_brain_agent_emits_fallback_when_stream_errors_without_content`'s inline `process_event` stub to accept the new `percept=` keyword (FIX-CLD-01 changed the real call site's signature).

### 9.4 Tests executed and results

| Command | Result |
|---|---|
| `pytest tests/test_causal_slice.py tests/test_pipeline.py -q` (task's required focused suite) | 57 passed |
| `pytest tests/test_transport_agent_playback_completion.py tests/test_transport_agent_barge_in_flush.py -q` | 16 passed |
| `pytest -q` (full suite) | **1893 passed, 0 failed, 0 errors** |
| `ruff check .` | clean |
| `ruff format --check` (changed files) | clean, except one pre-existing violation in `test_playback_progress.py:389` on a line this fix round did not touch (left as-is, consistent with `CODEX_RESULT.md`'s own note on the ~43 pre-existing repo-wide formatting violations) |

**Mutation spot-check** (manual, not a full `mutmut` run, given time constraints -- targeted at the highest-risk line of each fix): for every one of the 7 fixes, the guarding logic was manually mutated (isfinite check removed, offset clamp removed, history append removed, cancellation-outcome block removed, percept-id priority chain removed, core.py forwarding removed, completion-marker enqueue removed) and the corresponding new test(s) confirmed to fail; each mutation was then reverted and the test(s) reconfirmed green. All 7 caught their own mutation.

### 9.5 Known limitations (fix round)

- The FIX-CLD-02 mutation spot-check above exercises the producer-side enqueue and the `_maybe_publish_playback_progress` unit directly; it does not include a full `mutmut`-driven mutation of `_audio_playback_worker`'s branch structure itself (e.g. the `if completed: ... continue` early-exit) -- covered functionally by `test_playback_worker_publishes_completed_progress_after_draining_real_frames` and `test_playback_worker_skips_audio_capture_for_a_marker_frame`, but not independently mutation-verified line-by-line.
- FIX-CLD-01 only threads `workspace=` through the pipe; no production caller supplies a non-`None` value yet (that remains gated on `WorkspaceStore` integration, per the updated Section 7 entry above). `percept=` is now genuinely supplied in production for chat-input turns; the other four modality handlers (`_on_vision_description`, `_on_facial_reflex`, `_on_audio_stop`, `_on_audio_playback_progress`) still only stash `self.last_percept` without it reaching `process_event`, since none of those paths call `process_event` themselves.
- GPU-touching criteria remain `PENDING_GPU`, unaffected by this round.

## 10. Final Commit (fix round)

```
5b4f4af59ec4d0daed8dbb1e920e96c70c1d9dab
fix(cognitive): Phase 01 fix round -- thread percept/workspace, close outcome gaps
```

Stopping here per instructions  -  not proceeding further until the orchestrator requests it.
