# Phase 03 Reciprocal Review: Claude Package B

Review target: `ae24e8f` on `claude/phase-03`.

References reviewed:

- `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` Sections 9, 10, 21, and 38.
- `orchestration/PHASE_03/PLAN.md` and `CLAUDE_TASK.md`.
- The requested cognitive modules, focused test file, and `CLAUDE_RESULT.md`.

Verdict: REQUEST CHANGES.

The concrete `DecisionService` path filters candidates before it scores them,
and the off flag is a no-op in both decision scoring and pipeline kwarg
threading. However, the public selector does not enforce the required hard
constraint ordering, and the two new execution paths bypass the existing
safe, bounded chat realization path. These violate the Phase 03 hard-null
invariants for constraints and identity boundaries.

## Findings

### BLOCKER: score_and_select does not guarantee constraint-first selection

File: `backend/app/cognitive/action_candidate.py:277-319`

Scenario: A caller supplies both a safe candidate and a candidate whose
`constraint_claims` conflict with an identity or safety boundary, then calls
`score_and_select` with maximal urgency/exploration. The method has no
`forbidden_claims` input and never calls `filter_constraints`; it ranks the
unfiltered list. The review reproduction selected the forbidden candidate:

```text
CandidateSelector().score_and_select([safe, forbidden], [],
    {urgency_gain: 1.0, exploration_budget: 1.0, effort_budget: 0.0})
-> forbidden
```

This breaks Architecture Section 34 invariant 6 and the explicit Phase 03
requirement that `CandidateSelector.score_and_select` guarantee filtering
before modulation. `DecisionService._select_action_candidate` happens to
filter first at `decision.py:1003-1035`, but that convention cannot secure a
public selector API or future caller.

The purported invariant test is tautological: it manually filters at
`backend/tests/test_global_control_selection.py:534-540` before calling the
method, so it cannot fail if the selector itself lacks the guarantee.

Required fix: make the selector own the order, for example by accepting the
forbidden claim set and filtering internally before any score calculation,
while retaining rejected constraint violations in the returned trace. Add a
direct regression test that passes the forbidden candidate to
`score_and_select` itself under maximal controls.

### BLOCKER: regulation output can cross the transport before identity safety validation

Files: `backend/app/cognitive/action.py:1606-1627`,
`backend/app/cognitive/action.py:1654-1675`, and
`backend/app/cognitive/pipeline.py:794-810,853-868`

Scenario: A regulation candidate is selected and the model returns an
identity-boundary violation, an unsafe claim, or disallowed control markup.
The new executors concatenate raw model chunks and yield the complete text at
`action.py:1626` or `1674`. Stage 8 forwards each content chunk at
`pipeline.py:853-868`. Identity validation only runs afterwards in Stage 9 at
`pipeline.py:802-810`, after the unsafe content was already yielded.

Unlike ordinary chat, these paths do not use `ControlMarkupSanitizer`, the
bounded streaming loop, or `_emit_validated` / `_validate_partial_response`.
The prompt instruction to maintain identity is not an enforcement boundary.
An acute-distress turn can therefore deliver the very claim the Phase 03
constraint filter was meant to prevent; a later retry cannot retract spoken
output. This violates Architecture Sections 9 and 10 and Section 34
invariants 5 and 6.

Required fix: route REAPPRAISE and REDIRECT_ATTENTION through a realization
path that sanitizes and validates before yielding any content, with a safe
fallback when validation fails. Add pipeline-level tests with a regulation
plan and a mock model response that violates an immutable boundary or contains
an unterminated thought/control marker; assert that no unsafe content is
yielded.

### HIGH: regulation fallback does not cover a stalled stream

Files: `backend/app/cognitive/action.py:1606-1627` and
`backend/app/cognitive/action.py:1654-1675`

Scenario: The LLM connection succeeds but does not yield a token or finish.
Both new methods await `generate_stream` without a per-chunk or total timeout.
Their fallback only handles no LLM, an exception, or an empty completed
stream. The user receives neither a grounding line nor a terminal event while
the stream stalls.

The standard chat implementation uses `LLM_STREAM_MAX_SECONDS` and
`asyncio.wait_for` (`action.py:1071-1124` and `1415-1438`); the new paths
bypass that protection despite being used for acute distress.

Required fix: apply the same bounded stream budget to both regulation
executors and yield the deterministic fallback on timeout. Add tests for an
async generator that never yields and one that yields only after the budget.

### MEDIUM: Phase 03 activation silently requires the unrelated Phase 02 flag

Files: `backend/app/cognitive/decision.py:810-836` and
`backend/app/config.py:234-243`

Scenario: An operator sets `PHASE_03_AFFECT_CONTROL=True`, as documented by
the Phase 03 config comment, while `PHASE_02_MEMORY_TRUTH` remains its default
False. The pipeline forwards global controls, but `_plan_social_response`
never calls `_select_action_candidate`; no modulation occurs, no regulation
candidate is generated, and no regulation executor is selected. The Phase 03
flag is therefore operationally inert by itself.

Phase 03 depends on Phase 2 candidates, but that dependency must be explicit
and safe at activation time, not a hidden second flag. `CLAUDE_RESULT.md`
acknowledges the coupling, while its delivery and config text present the
Phase 03 flag as the gate.

Required fix: either make Phase 03 invoke candidate selection independently
of the memory feature (with an empty activation list when Phase 02 is off), or
enforce/document the prerequisite at configuration validation and cover the
`PHASE_03=True, PHASE_02=False` end-to-end behavior.

### MEDIUM: dict-shaped global controls are not bounded at the consumer boundary

File: `backend/app/cognitive/action_candidate.py:82-133`

Scenario: The documented duck-typed dict input contains `urgency_gain=1000`
or `exploration_budget=float('inf')`. `_control_value` converts the value but
does not clamp or reject it, so a caller outside Package A's Pydantic model can
apply an unbounded score modulation. This conflicts with the Phase 03 shared
contract and Architecture Section 10, which require controls bounded to
`[0.0, 1.0]`.

Required fix: reject non-finite values and clamp accepted duck-typed values to
`[0.0, 1.0]`, then add out-of-range dict and attribute-object tests.

## Confirmed behavior

- The concrete DecisionService path does filter before scoring at
  `decision.py:1003-1035`; this is correct locally but insufficient as the
  selector API guarantee.
- Acute distress uses the specified conjunction: `mood < -0.5` and
  `energy > 0.4` at `decision.py:179-191`. Regulation candidates are added
  only when the Phase 03 flag is true at `decision.py:970-975`.
- With `PHASE_03_AFFECT_CONTROL=False`, DecisionService does not add
  regulation candidates or forward controls to scoring, and the pipeline
  does not pass the `global_controls` kwarg (`decision.py:970-975`,
  `decision.py:1030-1035`, `pipeline.py:749-755`). This preserves the
  requested off-path behavior.
- Added lines in the committed Phase 03 code diff are 7-bit ASCII. Some
  requested pre-existing files contain non-ASCII characters outside this
  commit; `CLAUDE_RESULT.md` accurately describes that limitation.

## Verification performed

```text
DEBUG=false ../.venv/bin/python -m pytest tests/test_global_control_selection.py -q --junit-xml=/tmp/claude_phase03_review.xml
28 tests, 0 failures, 0 errors, 0 skipped

../.venv/bin/python -m ruff check app/cognitive/action_candidate.py \
  app/cognitive/action_intent.py app/cognitive/decision.py \
  app/cognitive/pipeline.py app/cognitive/action.py \
  tests/test_global_control_selection.py
All checks passed

git diff --check ae24e8f^ ae24e8f
Passed

Added-line ASCII scan for the committed Phase 03 code diff
Passed
```

The passing focused tests do not invalidate the findings above because they
pre-filter the selector input, exercise fallback only after completion or an
exception, and do not drive an unsafe regulation output through the pipeline.
