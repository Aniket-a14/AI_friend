# Phase 03 Package B Result

Branch: claude/phase-03
Worktree: /Users/aniketsaha/Projects/ai-friend-claude

Two rounds are recorded below: the initial implementation (commit
ae24e8f), and a fix round (this update) addressing accepted findings
B1, B2, H3, M6, M7 from Codex's reciprocal review, arbitrated in
`orchestration/PHASE_03/FIX_PLAN.md`. The "Deliverables" and "Design
notes" sections describe the code as it now stands, after both rounds;
where the fix round changed something the initial round did, that is
called out explicitly rather than left as a stale description.

## Fix Round: Codex Review Findings B1, B2, H3, M6, M7

Per `orchestration/PHASE_03/CLAUDE_FIX_TASK.md`, arbitrated in
`FIX_PLAN.md` section 3 (Codex's review of Package B,
`orchestration/PHASE_03/CODEX_REVIEW_OF_CLAUDE.md`).

1. **B1 [BLOCKER] score_and_select did not guarantee constraint-first
   selection.** `CandidateSelector.score_and_select` (`action_candidate.py`)
   gained an optional `forbidden_claims: list[str] | None = None`
   parameter. When supplied, the method now runs `self.filter_constraints`
   on `candidates` itself, before any scoring or modulation, and raises
   `ValueError` (matching the existing empty-candidate-list contract) if
   every candidate is filtered out. Omitting `forbidden_claims` (the
   default) reproduces the exact pre-fix contract. Codex's reproduction --
   passing a forbidden candidate directly to `score_and_select` under
   `urgency_gain=1.0, exploration_budget=1.0` and getting it back as the
   winner -- no longer succeeds: `test_forbidden_claims_rejects_forbidden_
   candidate_under_maximal_controls` in the fix-round test file reproduces
   the exact scenario and asserts the safe candidate wins.
   `decision.py::_select_action_candidate` now also passes
   `forbidden_claims` into its own `score_and_select` call, for
   defense-in-depth on top of its existing pre-filter (a no-op in the
   normal path, since `survivors` is already filtered by then; it also
   converts a previously-silent pathological fallback -- no WAIT candidate
   available at all -- into a raised `ValueError` instead of a possible
   forbidden winner).

2. **B2 [BLOCKER] regulation output could cross the transport before
   identity safety validation.** `_execute_reappraise` and
   `_execute_redirect_attention` (`action.py`) previously accumulated raw
   model text and yielded it directly. Both now route through a new shared
   helper, `ActionService._stream_regulation_line`, which strips
   `<thought>`/`<think>` chain-of-thought, runs the result through
   `ControlMarkupSanitizer`, and validates it with
   `_validate_partial_response` (the same forbidden-AI-persona-phrase and
   hostile-to-user-language checks ordinary chat gets) before it is ever
   returned for yielding. If sanitization strips anything (disallowed
   control markup was present) or validation fails, the deterministic
   fallback line is returned instead and the model's output is discarded
   entirely -- never partially yielded.

3. **H3 [HIGH] regulation fallback did not cover a stalled stream.**
   `_stream_regulation_line` iterates the stream manually (not via
   `async for`), tracking one rolling deadline and wrapping each
   `stream_iter.__anext__()` in `asyncio.wait_for(..., timeout=remaining)`
   -- the same pattern `_stream_primary_response` already uses for
   ordinary chat. A stream that never yields a first token, or one that
   yields some tokens and then stops, both hit the deadline and fall back
   to the deterministic line rather than hanging the turn.
   `_execute_reappraise`/`_execute_redirect_attention` compute
   `stream_budget = max(15, int(Config.LLM_STREAM_MAX_SECONDS))`, matching
   `_execute_respond_chat`'s own computation exactly.

4. **M6 [MEDIUM] Phase 03 activation silently required the Phase 02
   flag.** `decision.py::_plan_social_response`'s gate changed from
   `if Config.PHASE_02_MEMORY_TRUTH:` to
   `if Config.PHASE_02_MEMORY_TRUTH or Config.PHASE_03_AFFECT_CONTROL:`.
   `memory_activations` already defaulted to `[]` when unset (the
   blackboard normalizes it), so no other change was needed for that half
   of the fix. `PHASE_03_AFFECT_CONTROL=True` alone now runs the full
   candidate-selection machinery -- including distress-triggered
   regulation candidates -- exactly as the flag's own config comment
   always claimed it would. Both flags `False` is unaffected (the `or`
   still evaluates `False`), so pre-fix legacy behavior for that
   combination is unchanged.

5. **M7 [MEDIUM] dict-shaped global controls were not bounded at the
   consumer boundary.** `_control_value` (`action_candidate.py`) now
   checks `math.isfinite(value)` after the float conversion: a NaN, +inf,
   or -inf value is treated as absent and returns `default`, exactly like
   a missing or non-numeric value always did. A finite value is clamped to
   `[0.0, 1.0]` via the existing `_clamp01` helper before being returned,
   so an out-of-range duck-typed dict input (`{"urgency_gain": 1000.0}`)
   can no longer apply unbounded score modulation, and a non-finite one
   (`{"urgency_gain": float("nan")}`) can no longer be silently treated as
   an extreme value -- it falls back to the same neutral default the
   modulation formula already uses for a missing key.

**Test additions** (`backend/tests/test_global_control_selection.py`, 28
-> 49 tests): `TestScoreAndSelectConstraintFirst` (B1, 4 tests),
`TestControlValueValidation` (M7, 6 tests), `TestPhase03Independent
OfPhase02` (M6, 4 tests), `TestRegulationOutputSafety` (B2 + H3, 7 tests,
including one wiring test confirming `_execute_reappraise` threads the
configured stream budget through). The stalled-stream tests call
`_stream_regulation_line` directly with a small `stream_budget` (e.g.
0.05s) rather than monkeypatching `Config.LLM_STREAM_MAX_SECONDS` and
going through `execute()`, since `_execute_reappraise`/
`_execute_redirect_attention` floor the computed budget at 15 seconds
(`max(15, ...)`, matching `_execute_respond_chat`) -- calling the helper
directly keeps the test fast (well under a second) while still exercising
the exact same timeout code path.

## Deliverables

- `backend/app/cognitive/action_candidate.py`: extended `ActionCandidateKind`
  with `REAPPRAISE`, `REDIRECT_ATTENTION`, `SUPPRESS_EXPRESSION`.
  `CandidateSelector.score_and_select` gained an optional `global_controls`
  parameter (dict- or attribute-shaped, duck-typed so this module never
  imports Package A's `global_controls.py`) that additively modulates
  scoring: `urgency_gain > 0.5` rewards low risk/cost, `exploration_budget >
  0.5` rewards uncertainty (a novelty/breadth proxy), `effort_budget < 0.3`
  penalizes cost. Modulation is applied only after the caller's own
  `filter_constraints` pass -- constraint-first ordering is unchanged and
  documented explicitly in the method's docstring.
- `backend/app/cognitive/action_intent.py`: extended `ActionKind` with the
  same three kinds (a schema ceiling; `SUPPRESS_EXPRESSION` has no
  generator/executor wired up yet, same reasoning as the existing
  `UPDATE_STATE`/`EXTERNAL_ACT`/`CONTINUE` entries).
- `backend/app/cognitive/decision.py`: `_is_acute_distress` (valence < -0.5
  AND arousal > 0.4, both required); `_build_regulation_candidates`
  generates `REAPPRAISE`/`REDIRECT_ATTENTION`/a distress-specific `WAIT`,
  each carrying a real `constraint_claims` entry. `_build_candidates` calls
  it when `Config.PHASE_03_AFFECT_CONTROL` is True and distress is
  detected; `_select_action_candidate`/`decide` thread `state_snapshot` and
  `global_controls` through, gating `global_controls` forwarding on the
  same flag. `_plan_social_response` maps a selected `REAPPRAISE`/
  `REDIRECT_ATTENTION` candidate to a matching `action_type`, same pattern
  as the existing ASK -> CLARIFY mapping.
- `backend/app/cognitive/pipeline.py`: `_decision_accepts_global_controls`
  (mirrors `_decision_accepts_memory_activations`); `execute()` reads
  `state_snapshot.get("global_controls")` and threads it into
  `decision.decide` only when `Config.PHASE_03_AFFECT_CONTROL` is True and
  the injected decision object accepts the keyword. `_ACTION_KIND_BY_TYPE`
  gained defensive `REAPPRAISE`/`REDIRECT_ATTENTION` fallback entries.
- `backend/app/cognitive/action.py`: `_execute_reappraise` and
  `_execute_redirect_attention` -- short, non-streaming-validated
  generations (same shape as `_execute_clarify`) with dedicated system-
  prompt guidelines and deterministic fallback lines
  (`_REAPPRAISE_FALLBACK_LINE`, `_REDIRECT_ATTENTION_FALLBACK_LINE`) used
  whenever there is no LLM, generation raises, or returns nothing usable.
  Wired into `execute()`'s dispatch on `plan.action_type`.
- `backend/app/config.py`: added `Config.PHASE_03_AFFECT_CONTROL: bool =
  False`. This file is not in Package B's file-ownership list in
  `orchestration/PHASE_03/CLAUDE_TASK.md`/`PLAN.md`, but the task's own
  instructions require gating behind exactly this flag, and no package owns
  `config.py` under the current split. The change is a single additive
  field following the existing `PHASE_02_MEMORY_TRUTH` pattern; flag this
  for the integration pass in case Package A also touched this file.
- `backend/tests/test_global_control_selection.py` (NEW): 28 tests across
  six areas -- global-control scoring modulation, distress-induced
  regulation candidate generation (unit and end-to-end through
  `DecisionService.decide`), REAPPRAISE/REDIRECT_ATTENTION execution and
  deterministic fallbacks, the constraint-first invariant under maximal
  global controls, the "global controls cannot bypass identity boundaries"
  invariant end-to-end, PHASE_03_AFFECT_CONTROL-off backward compatibility
  (both in `DecisionService` and in `CognitivePipeline`'s kwarg-threading),
  and a diff-scoped pure-ASCII check.

## Design notes

- `global_controls.py` (Package A) does not exist yet in this worktree at
  the time of this work, so `Any | None` plus duck-typed attribute/dict
  access is used throughout instead of importing `GlobalControls`. This
  matches the parallel-work-package precedent already established in
  `pipeline.py`'s `WorkspaceSnapshotLike` Protocol for Codex's
  `CognitiveWorkspaceSnapshot`.
- Superseded by the fix round above (M6): the initial round nested
  regulation-candidate generation under `Config.PHASE_03_AFFECT_CONTROL`
  inside `_build_candidates`, but left `_plan_social_response`'s outer gate
  as `if Config.PHASE_02_MEMORY_TRUTH:` only, which made
  `PHASE_03_AFFECT_CONTROL=True` alone operationally inert -- exactly the
  finding Codex's review caught. The gate is now
  `if Config.PHASE_02_MEMORY_TRUTH or Config.PHASE_03_AFFECT_CONTROL:`, so
  either flag alone reaches candidate selection. Regulation candidates
  still additionally require `Config.PHASE_03_AFFECT_CONTROL` True inside
  `_build_candidates` (unchanged, and correct: that is the flag that
  specifically gates regulation, as opposed to candidate selection in
  general).
- The ASCII test scans two new/no-op files whole
  (`action_candidate.py`, the new test file) and diff-scopes the rest
  against the pre-Phase-03 merge base with `main`, because
  `decision.py`/`pipeline.py`/`action.py`/`action_intent.py`/`config.py`
  already carried pre-existing non-ASCII bytes (curly em-dashes, section
  signs) in lines this package did not touch; a whole-file scan would fail
  on content outside this package's contribution.

## Verification

Initial round (commit ae24e8f):

```
cd backend
../.venv/bin/python -m pytest tests/test_global_control_selection.py -v
  -> 28 passed

../.venv/bin/python -m pytest -q --junit-xml=<scratch>/res.xml
  -> parsed from XML per CLAUDE.md's "pytest summary is unreliable" note:
     tests=2018 failures=0 errors=0 skipped=0

../.venv/bin/python -m ruff check app/cognitive/action_candidate.py \
  app/cognitive/action_intent.py app/cognitive/decision.py \
  app/cognitive/pipeline.py app/cognitive/action.py \
  tests/test_global_control_selection.py app/config.py
  -> All checks passed!
```

Fix round (this update):

```
cd backend
../.venv/bin/python -m pytest tests/test_global_control_selection.py -v
  -> 49 passed (21 new: B1 x4, M7 x6, M6 x4, B2+H3 x7)

../.venv/bin/python -m pytest -q --junit-xml=<scratch>/res.xml
  -> parsed from XML: tests=2039 failures=0 errors=0 skipped=0

../.venv/bin/python -m ruff check app/cognitive/action_candidate.py \
  app/cognitive/action_intent.py app/cognitive/decision.py \
  app/cognitive/pipeline.py app/cognitive/action.py \
  tests/test_global_control_selection.py
  -> All checks passed!

Independent whole-file/diff-scoped ASCII scan (see TestPureAscii): pass.
```

## Not Done

- `SUPPRESS_EXPRESSION` has no candidate generator or executor -- type-level
  only, per the task's explicit scope (item C names only REAPPRAISE and
  REDIRECT_ATTENTION for execution).
- Package A's `global_controls.py`/`appraisal.py`/`agent_state.py`
  integration (real `GlobalControls` values flowing from `StateService`
  into `state_snapshot["global_controls"]`) is Package A's scope; this
  package only reads that key defensively and is a no-op until Package A
  populates it.
- Remote GPU acceptance criteria (AC-GPU-P3-01, AC-GPU-P3-02) are out of
  scope for this worktree.
- Integration merge into `integration/phase-03` is a separate step.
- All five findings assigned to Package B in `FIX_PLAN.md` section 3
  (B1, B2, H3, M6, M7) are addressed as of the fix round above; nothing
  from `CLAUDE_FIX_TASK.md` remains outstanding. `_execute_clarify`
  (Phase 02, not in this fix task's scope) still lacks the same
  sanitization/validation/timeout treatment B2/H3 gave the two regulation
  executors -- out of scope here, but worth the same fix in a future
  round since it shares the accumulate-then-yield shape that motivated
  B2/H3 in the first place.
