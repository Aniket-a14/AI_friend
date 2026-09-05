# Codex Reciprocal Review of Claude Phase 06 Package B

Review target: `claude/phase-06` at `9eb260a` (`9eb260a feat(learning-governance)`).

Reviewed files:

- `backend/app/cognitive/learning_governance.py`
- `backend/app/llm/adapter_gate.py`
- `backend/tests/test_learning_governance.py`

Reference documents: `orchestration/PHASE_06/CLAUDE_TASK.md`, `PLAN.md`,
`ACCEPTANCE_CRITERIA.md`, and `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` sections
21, 38, and 40. The reference documents are in the orchestration worktree,
not in Claude's isolated worktree.

## Verdict: REQUEST CHANGES

The implementation has a clear state-machine structure, correctly models the
six requested proposal states, and its ordinary-path tests are well organized.
However, two P0 safety/qualification bypasses mean it does not meet AC-P6-06
or AC-P6-09. The hard gate can be bypassed through values, unhandled path
syntax, or post-approval mutation; adapter qualification can omit baseline
probes and activation can bypass the qualified digests. Do not merge Package B
until the P0 findings are fixed and regression-tested.

## Findings

### P0-1: The immutable/safety hard invariant is bypassable

`check_targets_protected_domain()` at
`backend/app/cognitive/learning_governance.py:143-158` examines only the
free-text `target_domain`. It never inspects `proposed_value` or
`rollback_value`, although the AC-P6-06 invariant explicitly requires
rejection when either the target domain or proposed value intersects a
protected field. A proposal with target `procedure.greeting` and proposed
value `{"mood_decay_rate": 0.0}` completes the lifecycle and activates.

The tokenizer at lines 104-111 recognizes only `. `, `:`, `/`, `[`, `]`, `_`,
`-`, and whitespace. It does not recognize braces, parentheses, commas,
backslashes, or joined/camel-cased protected names. For example,
`persona{mood_decay_rate}` returns unprotected.

There is also no hard-gate re-check in `LearningGovernor.activate()` at lines
268-280 or `rollback()` at lines 282-293. `LearningProposal` is mutable, so
a proposal can be submitted, validated, and approved with an ordinary target,
then have `target_domain` set to `persona.mood_decay_rate` before activation.
The governor invokes the state applier on the protected target.

This violates the absolute Section 21/38 and AC-P6-06 requirement: identity
core, constitutional boundaries, and safety invariants are never targetable.
It is not sufficient for the common spelling variants to be blocked.

Fix: use an allowlisted, structured target path rather than free text where
possible; recursively validate proposed and rollback mapping keys; canonicalize
all delimiters and case forms (including joined forms) before comparison; and
re-run the complete protected-domain/value validation immediately before every
state write. Prevent mutation after submission, or store and validate an
immutable deep copy. Add adversarial tests for value-key, braced, parenthesized,
comma, backslash, joined/camel-case, mutation-after-approval, and
mutation-before-rollback variants.

### P0-2: Offline adapter qualification and activation do not preserve the
zero-regression/digest gate

`OfflineAdapterGate.qualify()` at
`backend/app/llm/adapter_gate.py:132-166` compares only the intersection of
probe IDs. If the baseline is `{p1: True, p2: True}` and the candidate is
`{p1: True}`, `shared` is `p1`, no regression is recorded, and the candidate
qualifies. A missing held-out result must fail closed: zero regressions cannot
be established unless the candidate and baseline cover the same required probe
set. The current no-shared-probes check at lines 138-141 is insufficient.

`activate()` at lines 176-212 trusts a caller-supplied
`AdapterQualificationResult` and accepts arbitrary activation digests. A
caller can construct `AdapterQualificationResult(adapter_id="candidate",
qualified=True, ...)` directly, then activate it with `wrong-prompt` and
`wrong-constitution`. Neither the result provenance nor the values supplied to
`activate()` are tied to the matching digests passed to `qualify()`.

This defeats AC-P6-09 and the Section 40 provenance gate. Qualification must
not be a convention followed by cooperative callers; it is an enforcement
boundary.

Fix: require exact required-probe-set equality (and report missing and extra
IDs); persist an unforgeable or internally registered qualification record
containing the request identity, candidate/base-model identity, result digest,
and target prompt/constitution digests; then make activation consume that
record and re-check all of it. Do not accept arbitrary digest strings or a
standalone caller-created result as evidence of qualification. Add tests for a
missing formerly-passing probe, extra/mismatched probe sets, forged result,
and mismatched digests at activation.

### P1-1: LearningProposal is incomplete against architecture Section 21

`LearningProposal` at
`backend/app/cognitive/learning_governance.py:60-83` correctly includes source
records, target/value, expected effect, risk class, counterfactual baseline,
approval policy, activation revision, rollback value, and lifecycle fields.
It omits the Section 21-required training/evaluation provenance when relevant
and post-activation measurement. Consequently the governor cannot record the
held-out/retention evaluation that justified an approval, nor determine whether
to roll back on measured regression.

Fix: add typed provenance and post-activation measurement fields (with
explicit defaults for non-training proposals), require the relevant evidence
before approval, and add lifecycle tests showing that the audit record survives
activation and rollback.

### P1-2: The claimed atomic rollback cannot be guaranteed by the current
state-applier interface

`LearningGovernor.rollback()` calls the external `state_applier` before it
sets status to `ROLLED_BACK` (lines 289-292), with no transaction, lock, or
compensating operation. A state applier that writes the rollback value and then
raises leaves external state restored but proposal status `ACTIVATED`; the
reverse partial-write case is equally possible. The same split exists for
activation. A one-call callback is not atomic by itself.

Fix: define a transactional state-store interface (for example, a CAS/commit
operation that includes proposal status and target value), or document and
enforce an atomic state-applier contract with a durable transaction boundary.
Add a failure-injection test proving no externally visible state/lifecycle
split remains after an applier error.

### P1-3: Curiosity treats chance noise and non-finite values as learning
progress

`LearningProgressCuriosity.rank()` at lines 379-391 filters only on one
two-window mean delta. It does not estimate variance, trend consistency, or
confidence, so a high-variance sequence can receive a large positive chance
delta and outrank genuine progress. For example, with a window of three,
`[1, 0, 1, 0.2, 0, 0.2]` ranks above the supplied steadily improving example.
The current noise test uses a specially repeated zero-delta oscillation and
does not exercise this case.

`record()` also accepts `NaN` and infinity. `NaN <= noise_threshold` is false,
so a domain with non-finite observations is emitted with a `NaN` score and can
affect ordering. This is not an empirical learning signal.

Fix: reject non-finite observations and require a robust positive trend over
multiple windows (or a variance/confidence criterion) before ranking. Add
seeded random/high-variance and NaN/infinity tests that enforce Progress >
Noise and Progress > Mastery.

### P2

No P2-only findings. The remaining concerns are either merge-blocking safety
and qualification defects or P1 architecture/integrity gaps.

## What is correct

- The enum contains exactly PROPOSED, VALIDATED, APPROVED, ACTIVATED,
  REJECTED, and ROLLED_BACK. Ordinary lifecycle ordering is enforced and
  activation revisions increase monotonically.
- LOW auto-approval, MEDIUM/HIGH gatekeeper requirements, and permanent
  CRITICAL rejection are implemented correctly on their tested paths.
- The normal rollback path restores the supplied `rollback_value` in one
  applier call and cannot be invoked twice.
- The adapter gate detects a pass-to-fail result among shared probes and
  checks prompt and constitution digests during `qualify()`.
- The implementation is additive and avoids colliding with the existing
  `learning.py` and Phase 04 `learning_review.py` contracts.

## Verification evidence

Executed from `/Users/aniketsaha/Projects/ai-friend-claude/backend` using the
requested interpreter:

- `DEBUG=false /Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m pytest /Users/aniketsaha/Projects/ai-friend-claude/backend/tests/test_learning_governance.py`
  - JUnit XML: 50 tests, 0 failures, 0 errors, 0 skipped.
- `/Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m ruff check .`
  - Passed with zero violations.
- `/Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m radon cc app/cognitive/learning_governance.py app/llm/adapter_gate.py -s -n D`
  - No D/E/F results. Full output shows only A/B in
    `learning_governance.py` and A/C in `adapter_gate.py` (highest is C=11
    for `OfflineAdapterGate.qualify`).
- ASCII scan of all three target files found no non-ASCII bytes.
- Manual mutation checks, reverted immediately after each run:
  - disabling protected-phrase detection: killed, 11 tests failed;
  - allowing CRITICAL approval: killed, 1 test failed;
  - suppressing regression detection: killed, 3 tests failed.

The mutations demonstrate useful coverage of the currently tested branches,
but they do not cover the P0 bypasses above. Adversarial black-box probes
confirmed all of the P0 and P1-2/P1-3 behaviors described in this review.

Remote CI and home-GPU results were not run or inferred by this review.

