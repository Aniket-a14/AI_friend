# Phase 04 Package B Result: Claude

Branch: `claude/phase-04`
Worktree: `/Users/aniketsaha/Projects/ai-friend-claude`
Baseline: `main` at `ea64b4b`

---

## 1. Summary

Implemented the background scheduler, due-goal review, governed learning
proposal review/rollback, and metacognitive/privacy-aware candidate
selection called for in `orchestration/PHASE_04/CLAUDE_TASK.md`.

## 2. Files Created

- `backend/app/cognitive/background_scheduler.py` -- `BackgroundJobKind`,
  `BackgroundJob`, `BackgroundScheduler` (priority queue, idempotency by
  `(idempotency_key, watermark)`, `budget_time_s` enforcement via
  `asyncio.wait_for`, immediate `preempt()`/`resume_foreground_idle()`).
- `backend/app/cognitive/goals.py` -- `GoalRecord`, `review_due_goals`
  (expires ACTIVE goals whose deadline has passed the supplied watermark).
- `backend/tests/test_background_governed_learning.py` -- the 9 tests
  named in the task spec, all passing (10 test functions total; a rejection
  rollback edge case was split out as its own test rather than folded into
  the approval/rollback test).

## 3. Files Modified

- `backend/app/cognitive/learning_review.py` -- **breaking rewrite** per
  the Phase 04 shared contract (`orchestration/PHASE_04/PLAN.md` Section
  3D): `LearningProposal` now has `proposal_id`/`target_domain`/
  `proposed_value`/`expected_effect`/`risk_class`/`rollback_value`/
  `status`/`rejection_reason` instead of the old `id`/`suggestions`/
  `speaker`/`contradicts_id` shape. `LearningReviewQueue` now exposes
  `submit`/`get`/`list_proposals`/`approve`/`reject`/`rollback`.
  `validate_proposal_safety` rejects (raises `ValueError`) any proposal
  whose `target_domain` names an immutable-core segment (`name`,
  `core_values`, `safety_boundaries`, `immutable`), matched as a whole
  dotted/colon/slash path segment so `nickname_style` cannot collide with
  `name`.
- `backend/app/cognitive/action_candidate.py` -- `CandidateSelector.
  score_and_select` gained `metacognitive_directive: str = "PROCEED"` and
  `privacy_filter: Callable[[ActionCandidate], bool] | None = None`.
  `privacy_filter` runs after constraint filtering and before scoring,
  rejecting non-passing candidates with reason
  `"privacy_disclosure_violation"`; `_metacognitive_modulation` penalizes
  SPEAK / boosts WAIT under `ABSTAIN`, boosts ASK under
  `ASK_CLARIFICATION`, boosts VERIFY under `VERIFY`. This file is not on
  either package's owned-file list in `PLAN.md`, but `score_and_select` is
  the only place the task's File 4 spec can attach to -- it is a shared,
  neither-package-owned module, and Codex's package does not touch it.
- `backend/app/cognitive/decision.py` -- `DecisionService.decide` and
  `_select_action_candidate` gained the same two optional parameters,
  threaded through the blackboard exactly like `global_controls`, and
  forwarded unconditionally to `score_and_select` (their own defaults make
  them no-ops for every existing caller). Also fixed pre-existing non-ASCII
  characters (em dash, section sign, Greek letters, subscripts) left over
  from Phase 1-era docstrings, since this file is now phase-owned and must
  be pure ASCII.
- `backend/app/cognitive/pipeline.py` -- `CognitivePipeline.__init__` gained
  an optional `scheduler: BackgroundScheduler | None` parameter with
  `_maybe_preempt_background()`/`_maybe_resume_background()` helpers.
  `execute()` calls `_maybe_preempt_background()` first, before any other
  stage, and `_maybe_resume_background()` on every exit path (both early
  returns and the normal end of the generator). Also fixed 3 pre-existing
  non-ASCII characters in docstrings/comments.

## 4. Verification

```
cd backend
../.venv/bin/python -m pytest tests/test_background_governed_learning.py -q
  -> 10 passed

../.venv/bin/python -m ruff check .
  -> All checks passed!

../.venv/bin/python -m radon cc app --min D -s
  -> (no output: zero rank D/E/F functions)
```

Regression spot-check (not required by the task, run out of caution since
`action_candidate.py`/`decision.py`/`pipeline.py` are shared files):

```
../.venv/bin/python -m pytest tests/test_decision.py tests/test_pipeline.py -q
  -> 20 passed, 0 failed
```

All owned/modified `.py` files plus this result file contain only bytes
< 128 (enforced by `test_phase04_claude_files_are_ascii_only`).

## 5. Known Breakage at Initial Implementation -- RESOLVED in the Fix Round

`backend/app/cognitive/learning.py` (`ReflectionService`) and
`backend/tests/test_learning_review.py` both called the **old**
`LearningProposal`/`LearningReviewQueue` API (`submit(suggestions,
contradicts_id=...)`, `.id`, `.suggestions`, `.contradicts_id`,
`approve(id, identity_manager)`, `pending()`, `contradictions()`), which
the initial Phase 04 implementation replaced outright per the shared
contract in `PLAN.md` Section 3D, breaking both. This was flagged in this
document and in `CLAUDE_REVIEW_OF_CODEX.md`'s reciprocal-review
counterpart, arbitrated in `FIX_PLAN.md` Section 3 item 2, and fully
resolved in the fix round -- see Section 7 below.
`../.venv/bin/python -m pytest tests/test_learning_review.py -q` now
passes 10/10 with zero changes to `learning.py` or the test file itself.

## 6. Design Notes / Interpretation Calls

- **Idempotency scope**: `BackgroundScheduler.enqueue` rejects a duplicate
  only for the exact same `(idempotency_key, watermark)` pair -- the same
  key at a *new* watermark is accepted, since the task's wording
  ("Rejects if duplicate for same watermark") implies the watermark is
  part of the identity, not the whole key.
- **`run_next` outcomes**: beyond the spec's `(False, None)` /
  `(False, "budget_exceeded")` / `(True, result)`, a fourth outcome,
  `(False, "preempted")`, was added for a job cancelled mid-flight by a
  concurrent `preempt()` -- distinct from a budget timeout so a caller (or
  a test) can tell the two failure modes apart. All timeouts and
  preemptions are also appended to `BackgroundScheduler.errors` for an
  audit trail.
- **ABSTAIN's "ungrounded assertions" qualifier**: `ActionCandidate` has no
  grounding/confidence field to test against, so `_metacognitive_
  modulation` penalizes every SPEAK candidate under `ABSTAIN` rather than
  a subset -- the calibration engine that would supply a groundedness
  signal is Codex's Package A (`calibration.py`), not yet available in
  this worktree.
- **`privacy_filter` is a generic callable**, not typed against Package
  A's `PersonModel` (also not available in this worktree) -- this keeps
  `action_candidate.py`/`decision.py` free of a hard dependency on a
  parallel package, matching the existing `global_controls: Any` pattern
  Phase 03 already established for the same reason.
- **`pipeline.py` preemption placement**: `_maybe_preempt_background()` is
  called before Stage 1 extraction (earliest possible point) rather than
  only around Stage 8 (LLM generation), so any background work is aborted
  the instant a new turn begins, not only once generation is about to
  start.

---

## 7. Fix Round (Response to Reciprocal Peer Review)

Executed `orchestration/PHASE_04/CLAUDE_FIX_TASK.md` per the arbitrated
directives in `orchestration/PHASE_04/FIX_PLAN.md` Section 3. Five
objectives, all addressed:

### 7.1 Immutable-core protection hardening (`learning_review.py`)

The initial `validate_proposal_safety` split `target_domain` on `.`, `:`,
`/` only and required an exact segment match against
`{name, core_values, safety_boundaries, immutable}`. This missed two real
bypasses: brackets (`persona[name]` is one segment, `"persona[name]"`,
which never equals `"name"`) and multi-word markers not reproduced with a
literal underscore (`persona.core values` or `PERSONA.CORE_VALUES` could
in principle be typed in a form that never collapses to the single token
`"core_values"`).

Fixed by widening the delimiter set to also split on `[`, `]`, and `_`,
lowercasing, and checking whether each marker's own words (`"core_values"`
becomes the two-word phrase `("core", "values")`) appear as a **contiguous
token run** anywhere in the normalized domain, rather than requiring one
whole segment to equal the marker verbatim. Added `"constitutional"` to
the marker set per the fix task. Verified no false positive was
introduced: `"conversation.nickname_style"` (tokens `conversation`,
`nickname`, `style`) still passes, since `"nickname"` is its own token,
distinct from `"name"`.

`LearningReviewQueue.approve()` now calls `validate_proposal_safety(proposal)`
again before applying anything, and raises (leaving the proposal PENDING,
not APPROVED) if a `target_domain` mutated after `submit()` now names the
immutable core -- pydantic models here are not frozen, so submission-time
validation alone does not protect against a later in-place mutation.

New tests: `test_learning_proposal_immutable_core_bracket_and_case_bypass_rejected`
(6 bypass domains covering every delimiter/case combination named in the
fix task) and `test_learning_proposal_approve_revalidates_after_mutation`
(submits a safe proposal, mutates it to a forbidden domain, asserts
`approve()` raises and the proposal stays PENDING).

### 7.2 Backward compatibility (`learning_review.py`)

Rather than layering a translation shim in front of the Phase 04 schema,
`LearningProposal` and `LearningReviewQueue` now serve both call shapes as
first-class citizens:

- `target_domain`, `proposed_value`, and `expected_effect` gained defaults
  (`"persona_adaptive_traits"`, `None`, `"reflection_update"`) so
  `LearningProposal(suggestions={...})` -- the legacy direct-construction
  shape `tests/test_learning_review.py` uses -- validates without needing
  the new fields. This is a deliberate, documented deviation from
  `PLAN.md` Section 3D's original "required, no default" declaration,
  directed by the arbitrated fix task itself.
- Added real `speaker: str | None` and `contradicts_id: str | None`
  fields (not just compatibility properties, since `contradicts_id` needs
  to be *settable* at construction) plus read-only `id`, `suggestions`,
  and `is_contradiction` properties aliasing `proposal_id`,
  `proposed_value`, and `contradicts_id is not None`.
- A `model_validator(mode="before")` remaps a `suggestions=` constructor
  kwarg onto `proposed_value` before field validation runs, since
  `suggestions` itself is a read-only property, not a field, and pydantic
  would otherwise reject it as an unknown keyword.
- `LearningReviewQueue.submit()` gained the exact legacy signature
  (`suggestions=None, source="reflection", speaker=None,
  contradicts_id=None, proposal=None`) -- `learning.py`'s real call site,
  `self.review_queue.submit(suggestions, contradicts_id=contradicts_id)`,
  now hits this path unchanged. The new governed-proposal call shape is
  `submit(proposal=LearningProposal(...))`; **this required updating this
  package's own `test_background_governed_learning.py`** call sites from
  positional `queue.submit(proposal)` to keyword `queue.submit(proposal=proposal)`,
  since the first positional slot is now `suggestions`, not `proposal`.
- Added `pending()` (proposals with `status == PENDING`) and
  `contradictions()` (`pending()` filtered to `is_contradiction`) --
  unlike the original Phase 5C queue, which physically removed a resolved
  proposal from its one list, this queue never deletes anything (the audit
  trail Architecture Section 21 asks for), so these are computed views
  rather than the backing store itself; a rejected/approved proposal
  simply stops appearing in `pending()` while remaining addressable via
  `get()`.
- `approve()` is now **async** and takes an optional `identity_manager`:
  `await queue.approve(proposal_id)` for the governed workflow (pure
  status transition, revalidated per 7.1), or
  `await queue.approve(proposal_id, identity_manager)` for the legacy
  workflow (stamps `identity_manager.history["evolved_learnings"]` before
  awaiting `identity_manager.evolve_persona(proposal.suggestions)`,
  preserving the exact prior stamp-before-apply ordering
  `test_approve_persists_evolved_learnings_before_evolve_persona_saves`
  pins). This also required awaiting `approve()` in this package's own
  test file, which previously called it synchronously.

Verified: `../.venv/bin/python -m pytest tests/test_learning_review.py -q`
passes 10/10 with **zero modifications** to that file or to `learning.py`.
Also ran `tests/test_reflection.py`, `tests/test_subconscious.py`, and
`tests/test_subconscious_consolidation.py` (26 tests, `ReflectionService`'s
broader regression coverage) as an extra check since they exercise the
same call site indirectly: all pass unchanged.

### 7.3 Reentrant foreground preemption and guaranteed cleanup

`BackgroundScheduler.is_foreground_active` is now a read-only property
(`self._foreground_depth > 0`) backed by an integer reference count.
`preempt()` increments and cancels the in-flight task (unchanged
behavior); `resume_foreground_idle()` decrements, floored at zero. A
nested or overlapping preemption (two `preempt()` calls before a matching
pair of `resume_foreground_idle()` calls) no longer flips the scheduler
back to idle after only the first resume. New test:
`test_background_scheduler_preemption_is_reentrant`.

`CognitivePipeline.execute()`'s entire body (from `stage_times = {}`
through the final `yield`) is now wrapped in a single `try/finally`, with
`self._maybe_resume_background()` moved into the `finally`. The three
explicit call sites added at the initial implementation's early-return
points were removed as redundant -- `finally` now covers every exit
uniformly: both early returns, the normal end of the generator, any
exception raised by any stage, and the caller closing the generator early
(`aclose()`, which resumes the suspended frame with `GeneratorExit`,
unwinding through the same `finally`). New test:
`test_pipeline_execute_resumes_background_on_exception`, which forces
`perception.perceive` to raise mid-turn and asserts the scheduler is back
to `is_foreground_active is False` afterward -- this would have failed
against the initial implementation's call-site-based approach, since none
of its three explicit calls sit on the exception path through Stage 3.

### 7.4 ABSTAIN as a true disqualifier; HEDGE marker

`CandidateSelector.score_and_select` now hard-filters every surviving
SPEAK candidate out of contention under `ABSTAIN`, before scoring, with
rejection reason `"abstain_disqualified"` -- the same constraint-first
pattern already used for `forbidden_claims` and `privacy_filter`. This
closes the actual gap in the initial implementation's approach: a
finite score penalty, however large relative to typical scores, is not a
true disqualifier, since it can in principle be outweighed by an equally
large `score`. `_ABSTAIN_SPEAK_PENALTY` was raised to `1000.0` and kept as
a second, redundant line of defense (belt and suspenders), but the hard
filter is now the actual enforcement mechanism. If every surviving
candidate is SPEAK, `score_and_select` raises `ValueError` rather than
inventing a winner, matching the file's existing invariant for the other
constraint-first filters. New test:
`test_candidate_selector_abstain_is_a_true_disqualifier`, which gives the
SPEAK candidate a score of `1_000_000.0` against a WAIT candidate scored
`0.0` and confirms WAIT still wins -- this would fail against any
finite-penalty-only implementation.

`ActionCandidate` gained a `metadata: dict[str, Any]` field for
scoring-time stance annotations. Under `HEDGE`, `score_and_select` returns
a copy of the winning candidate with `metadata={"hedge": True}` attached,
so a downstream realizer (e.g. `action.py`'s prompt assembly) can add a
hedging qualifier without re-deriving the directive itself; `PROCEED` and
every other directive leave `metadata` untouched. New test:
`test_candidate_selector_hedge_attaches_marker`.

### 7.5 GoalRecord Section 11 alignment (`goals.py`)

Added `utility_terms: dict[str, float]`, `constraints: list[str]`,
`parent: str | None`, `evidence_ids: list[str]`, and
`satiation_or_expiry: float | None`, all defaulting to
empty/`None` so every existing `GoalRecord(...)` construction (including
`review_due_goals`'s own test fixtures) keeps working unchanged. New test:
`test_goal_record_section_11_fields_default_and_settable`, covering both
the all-defaults case and a populated sub-goal (`parent` set, both
`utility_terms` keys, `constraints`, `evidence_ids`, and
`satiation_or_expiry` all populated).

### 7.6 Verification

```
cd backend
../.venv/bin/python -m pytest tests/test_background_governed_learning.py -q
  -> 18 passed (9 original test names now cover 18 test functions after
     the fix round's additions; see the file for the full list)

../.venv/bin/python -m pytest tests/test_learning_review.py -q
  -> 10 passed, 0 failed  (the critical fix-task requirement)

../.venv/bin/python -m ruff check .
  -> All checks passed!

../.venv/bin/python -m radon cc app --min D -s
  -> (no output: zero rank D/E/F functions)

../.venv/bin/python -m pytest tests/test_decision.py tests/test_pipeline.py \
    tests/test_learning_review.py tests/test_background_governed_learning.py -q
  -> 48 passed, 0 failed

../.venv/bin/python -m pytest tests/test_reflection.py tests/test_subconscious.py \
    tests/test_subconscious_consolidation.py -q
  -> 26 passed, 0 failed

../.venv/bin/python -m pytest -q   (full backend suite)
  -> 2067 passed, 0 failed, 0 errors
```

All touched files (the six `.py` files listed in Section 3/7 plus this
result file) remain pure 7-bit ASCII, enforced by
`test_phase04_claude_files_are_ascii_only`.
