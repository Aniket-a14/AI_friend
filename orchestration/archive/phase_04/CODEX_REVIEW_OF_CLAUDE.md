# Codex Reciprocal Review: Claude Phase 04 Package B

Review target: `main..claude/phase-04` in
`/Users/aniketsaha/Projects/ai-friend-claude`.

Verdict: REQUEST CHANGES.

The branch establishes useful foundations: stable descending-priority/FIFO
ordering, exact `(idempotency_key, watermark)` deduplication, a real
`asyncio.wait_for` time limit, correct ACTIVE-to-EXPIRED deadline handling,
and direct CandidateSelector privacy rejection. It does not yet meet the Phase
04 safety, durability, budget-enforcement, or end-to-end integration bar in
architecture Sections 11, 19, 20, and 21. Most importantly, it deliberately
leaves a live caller and regression suite broken, and the immutable-persona
guard is bypassable.

## Findings

### P0 - Immutable persona protection is bypassable

`learning_review.py:65-82` checks only a few dot/colon/slash-delimited
segments, and only in `submit()` (`95-100`). A submitted Pydantic model remains
mutable; changing a safe proposal's `target_domain` to an immutable target
before `approve()` is accepted because `approve()` at `108-115` does not
revalidate. The parser also accepts `persona[name]`, `persona.core_values[0]`,
and `identity.safety_boundaries[0]`, all plausible target-path forms.

This violates the hard requirement that immutable core persona attributes and
safety boundaries can never be proposed or altered. Passing only a small list
of dotted-string tests is insufficient.

Recommendation: allowlist canonical mutable target schemas rather than
blocklisting string spellings. Store an immutable snapshot on submit, reject
duplicate IDs, and revalidate the stored snapshot at every transition and just
before an owner applies it. Test mutation after submit, bracket/JSON-pointer
paths, case/whitespace variants, and duplicate IDs.

### P1 - The declared breaking schema change breaks a live flow and 10 tests

`learning.py:273-277` still calls removed
`submit(suggestions, contradicts_id=...)`. `test_learning_review.py` still
uses removed fields and methods (`id`, `suggestions`, `pending`,
`contradictions`, and async `approve(id, identity_manager)`). This is not a
harmless out-of-package incompatibility: with `LEARNING_REVIEW_REQUIRED=True`,
the production reflection path catches the incompatibility in its broad handler
and drops a high-confidence proposal instead of queuing it.

Independent run from `backend/`:

```text
../.venv/bin/python -m pytest tests/test_background_governed_learning.py tests/test_learning_review.py -q --junit-xml=/private/tmp/phase04-claude-review.xml
JUnit: 20 tests, 10 failures, 0 errors
```

All 10 failures are in `tests/test_learning_review.py` and directly caused by
the removed API. The 10 new Package B tests pass.

Recommendation: migrate ReflectionService and its tests in the same change, or
ship a narrow compatibility adapter while migration completes. The caller must
map a reflection result into a structured proposal with canonical mutable
target, proposed and rollback values, source-record provenance, risk, and
expected effect. Do not merge a known failing suite as a follow-up.

### P1 - Learning review is not durable or auditable, and rollback restores nothing

`LearningReviewQueue` is an in-memory dictionary (`learning_review.py:85-106`),
despite calling itself durable. A restart loses all proposals and decisions.
Mutable models are retained without transition events, actor, timestamp, policy
decision, activation revision, source-record IDs, or post-activation outcome.
Reusing a proposal ID overwrites the prior entry.

`rollback()` at `127-136` changes a status and returns an arbitrary value; no
owner applies it, verifies exact restoration, or records restoration.
`approve()` only changes status. This cannot meet AC-P4-09 exact restoration
or Section 21 versioned activation, monitoring, rollback, and complete audit
trail. `risk_class` is an unrestricted string and does not enforce policy.

Recommendation: persist proposals and append-only transition events through an
owning state/configuration service. Approval must invoke a versioned,
owner-authorized apply and record its revision. Rollback must use the same owner
with the stored prior value and verify read-back. Use constrained risk/policy
enums and test restart/reload, ID collision, failed apply/restore, and exact
read-back restoration.

### P1 - The scheduler does not enforce token or allowed-write budgets

`budget_tokens` and `allowed_writes` are declared at
`background_scheduler.py:38-48`, but `run_next()` at `116-148` only applies a
timeout. The executor returns unconstrained `Any`, so token use cannot be
measured, limited, or audited; it can also write any state domain. This fails
AC-P4-06 and the Section 19 budget/write contract.

The time-budget path itself is sound: it uses `asyncio.wait_for`, records a
timeout, and the focused timeout test passes. Priority order and
same-watermark dedupe also work. Those partial successes do not substitute for
token and write enforcement.

Recommendation: define a typed executor result with token usage, output type,
watermark progression, and requested writes. Pass a cooperative token
limiter/checkpoint to executors, reject over-budget results, and have the owner
validate requested writes against `allowed_writes`. Validate finite positive
budgets. Preserve input and completed watermarks separately rather than
overwriting `job.watermark` with wall-clock completion time.

### P1 - Foreground preemption is not safe under overlap or generator teardown

`BackgroundScheduler` uses one Boolean (`background_scheduler.py:65-104`). Two
foreground turns call `preempt()` and the first to finish calls
`resume_foreground_idle()`, clearing the Boolean while the second turn is still
active. Background work may then dequeue during active foreground work.

`CognitivePipeline.execute()` preempts at the correct earliest point
(`pipeline.py:726-731`), but manual resume calls occur only at selected returns
and after the final `yield` (`747`, `766`, and `892`). There is no outer
`try/finally`. An exception, cancellation, or a consumer closing the async
generator after receiving the terminal chunk can leave the scheduler permanently
foreground-active. The claimed every-exit-path guarantee is false. The test
sleeps 10 ms before preempting; it does not measure the required less-than-5-ms
latency, concurrent turns, generator close, or exception cleanup.

Recommendation: use reference-counted or lease/token foreground ownership and
release only the matching acquisition. Wrap the full async-generator body in
`try/finally`. Add concurrency, exception, consumer-close, and monotonic-clock
latency tests.

### P1 - Metacognitive and privacy controls are not live, and ABSTAIN is unsafe

Direct selector plumbing exists in `action_candidate.py:337-465` and
`decision.py:375-446, 1005-1091`, but not as end-to-end enforcement. In the
reviewed configuration, `PHASE_02_MEMORY_TRUTH` and
`PHASE_03_AFFECT_CONTROL` are both false. CandidateSelector is invoked only
when either legacy flag is true (`decision.py:832`), so supplied metacognitive
directives and privacy filters are ignored by the default decision path. The
pipeline supplies neither a calibrated directive nor a real PersonModel-based
privacy predicate.

Further, ABSTAIN is merely a fixed -5 score adjustment
(`action_candidate.py:85-122`). `ActionCandidate.score` is unbounded: a SPEAK
candidate at 10 still beats WAIT at 0 under ABSTAIN; this was reproduced
directly. HEDGE has no behavioral effect despite the comment claiming it is
prompt-level; no plan or action payload carries it. Unknown/lowercase directives
silently act as PROCEED.

Recommendation: source a typed MetacognitiveDirective from calibration and a
real cross-person disclosure predicate from PersonModel/workspace context, then
pass both on every selection path. Privacy must fail closed. Implement ABSTAIN
as a hard filter or guaranteed safe fallback, carry HEDGE to language
realization, and validate the directive enum. Test live default configuration,
high scores, HEDGE output, and two-person isolation through the pipeline.

### P2 - Due-goal expiry is correct, but GoalRecord is short of Section 11

`review_due_goals()` correctly leaves non-ACTIVE/no-deadline/future goals alone
and marks ACTIVE goals EXPIRED at `current_watermark >= deadline`
(`goals.py:35-56`). That satisfies the narrow expiry contract.

However, `GoalRecord` at `18-32` omits Section 11's `utility_terms`,
`constraints`, `parent`, `evidence_ids`, and `satiation_or_expiry`, and uses
unrestricted strings for status/type. It cannot represent the target's
arbitration, provenance, or constrained-state model.

Recommendation: add the Section 11 fields and typed status/class enums, or
explicitly retain a compatible existing goal model. Add equality-boundary,
invalid-status, and non-finite watermark/deadline tests.

## Verification and hygiene

- New focused test file: 10 passed.
- Existing learning-review test file: 10 failed due to removed API.
- Targeted Ruff check of all changed Python files: passed.
- `radon cc app --min D -s`: no rank D/E/F output.
- `git diff --check main..claude/phase-04`: passed.
- A byte-level 7-bit ASCII scan found no non-ASCII bytes in changed Python
  files or `CLAUDE_RESULT.md`.

This review file is pure 7-bit ASCII.

## Required resolution order

1. Close immutable-target bypasses and revalidate every lifecycle step.
2. Migrate live callers/tests and implement persistent, owner-authorized
   apply/rollback with audit events.
3. Enforce token/write budgets and make preemption lease-safe with cleanup.
4. Wire calibrated directives and real privacy context through default paths;
   make ABSTAIN and HEDGE behavioral.
5. Align GoalRecord and add missing edge/integration coverage.

