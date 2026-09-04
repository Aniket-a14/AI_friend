# Phase 06 Package B Completion Summary: Claude

Assignment: Package B - Trusted Learning Governance, Curiosity, and Offline
Adapter Gate
Branch: claude/phase-06
Worktree: /Users/aniketsaha/Projects/ai-friend-claude
Baseline: main at 9203f55 (checked out at b3552d5)

---

## 1. Files Delivered

- `backend/app/cognitive/learning_governance.py` (NEW)
- `backend/app/llm/adapter_gate.py` (NEW)
- `backend/tests/test_learning_governance.py` (NEW)

No files outside this ownership list were modified.

---

## 2. Naming Deviation From CLAUDE_TASK.md / PLAN.md (read this first)

`PLAN.md` section 2 lists `backend/app/cognitive/learning.py` as a NEW file
for this package. On this branch/baseline it is not new: it already holds
`ReflectionService` ("AI Friend Solid State Learning Layer"), 415 lines,
imported by `app/cognitive/core.py`, `app/agents/subconscious_agent.py`, and
five existing test files. Separately, `app/cognitive/learning_review.py`
(Phase 04) already defines a `LearningProposal` / `LearningProposalStatus`
pair -- but with a different, incompatible schema (status
PENDING/APPROVED/REJECTED/ROLLED_BACK, no `activation_revision`, a plain
`str` `risk_class`) than Section 21's PLAN.md contract for this phase
(PROPOSED/VALIDATED/APPROVED/ACTIVATED/REJECTED/ROLLED_BACK, a
`LearningRiskClass` enum, `source_records`, `activation_revision`).

Writing this phase's `LearningProposal`/`LearningGovernor`/etc. into
`learning.py` would have meant either overwriting `ReflectionService`
(breaking five call sites and their tests) or creating two same-named,
schema-incompatible `LearningProposal` classes inside one package.

Per user direction (this worktree, this session), the new Section 21
governance surface lives in `backend/app/cognitive/learning_governance.py`
instead -- purely additive, `learning.py` and `learning_review.py` are
untouched. `backend/app/llm/adapter_gate.py` and
`backend/tests/test_learning_governance.py` match `PLAN.md` exactly (neither
path was already occupied).

---

## 3. What Was Built

### `app/cognitive/learning_governance.py`

- `LearningRiskClass` (str Enum): LOW, MEDIUM, HIGH, CRITICAL.
- `LearningProposalStatus` (str Enum): PROPOSED, VALIDATED, APPROVED,
  ACTIVATED, REJECTED, ROLLED_BACK.
- `LearningProposal` (Pydantic model): every field `PLAN.md` section 3.B and
  architecture Section 21 name -- `source_records`, `target_domain`,
  `proposed_value`, `expected_effect`, `risk_class`,
  `counterfactual_baseline`, `approval_policy`, `activation_revision`,
  `rollback_value`, `status`, `created_at`, `evaluated_at` -- plus
  `rejection_reason` (audit-trail detail, not in the shared contract, additive
  only). One deliberate deviation from the contract's literal stub: `PLAN.md`
  writes `created_at: float = 0.0`; here it is
  `Field(default_factory=time.time)` so a proposal's audit trail is populated
  for free rather than requiring every caller to remember to stamp it. Field
  name, type, and presence are unchanged.
- `check_targets_protected_domain(target_domain) -> (bool, str)`: the hard
  invariant. Tokenizes `target_domain` on any of `.:/[]_- ` (so bracket,
  underscore, dash, and case variations cannot dodge the check -- the same
  bypass class `learning_review.py`'s peer-reviewed fix round already found
  once) and flags it if any contiguous token run matches a static
  safety/immutable/constitutional marker, an `IMMUTABLE_CORE` key
  (`persona.profile.IMMUTABLE_CORE`), or any CONSTITUTIONAL-tier
  `PersonaProfile` field name (`PersonaProfile.fields_in(Tier.CONSTITUTIONAL)`
  -- computed once at import time, since that set is a schema constant, not
  runtime state).
- `LearningApprovalGate`: the risk-tiered policy alone, kept separate from
  the governor so it can be tested/swapped independently.
  `evaluate(proposal) -> (approved, reason)`: re-checks the protected-domain
  invariant first (defense in depth -- the hard invariant is not only
  enforced once), then LOW auto-approves, CRITICAL is unconditionally
  blocked regardless of any configured gatekeeper, and MEDIUM/HIGH require
  an explicit `gatekeeper` callback (`Callable[[LearningProposal], bool]`),
  refusing by default if none is configured.
- `LearningGovernor`: owns the full lifecycle --
  `submit` -> `validate` -> `approve` -> `activate` -> `rollback`. `submit`
  hard-rejects (raises, registers nothing) a protected `target_domain`, a
  duplicate `proposal_id`, or a missing `rollback_value` (a change with
  nothing to undo it can never be safely activated, so it is refused at the
  earliest point rather than allowed to reach `activate` and fail there).
  Every transition method checks the proposal's current status and raises
  `ValueError`/`KeyError` on an out-of-order call. `activate` stamps a
  monotonically increasing `activation_revision` and applies
  `proposed_value` via an injected `state_applier(domain, value)` callback.
  `rollback` is the 1-step atomic restore: it applies `rollback_value`
  through the same `state_applier` and flips status to ROLLED_BACK in one
  call -- there is no intermediate, partially-restored state observable
  between those two effects, and a second `rollback()` call on an
  already-rolled-back proposal raises rather than silently no-op'ing.
- `LearningProgressCuriosity`: `record(domain, error)` appends one empirical
  error/loss observation per call, bounded to `2 * window_size` samples per
  domain. `progress_delta(domain)` compares an older window's mean error to
  the most recent window's mean (positive = improving); `None` until two
  full windows exist. `is_mastered(domain)` flags a domain whose recent-
  window mean is already at or below `mastery_threshold`. `rank()` returns
  domains with a real, above-`noise_threshold` positive delta, excluding
  mastered domains, sorted highest-progress first -- so a flat, already-
  solved routine and a domain that is pure noise (oscillating with no net
  trend) both rank below a domain with a genuine, sustained error
  reduction.

### `app/llm/adapter_gate.py`

- `AdapterQualificationRequest` / `AdapterQualificationResult`: exactly the
  fields `PLAN.md` section 3.B specifies.
- `compute_prompt_digest(text) -> str`: sha256[:16] of prompt text, the same
  shape as `evals/schema.py`'s `fingerprint()` (not imported from there --
  `app/` may not depend on `evals/`, per CLAUDE.md -- so this is an
  independent, self-contained implementation of the same idea).
- `compute_constitution_digest(persona: PersonaProfile) -> str`: sha256[:16]
  of a canonical JSON payload built from `persona.immutable`
  (`IMMUTABLE_CORE`) plus every CONSTITUTIONAL-tier field's current value.
  Deliberately excludes ADAPTIVE fields (e.g. `relationship`), so a routine
  reflection-driven adaptive change does not falsely invalidate every
  adapter already qualified against the persona's safety/temperament
  configuration.
- `OfflineAdapterGate`: tracks one active `AdapterRecord`
  (`app.llm.adapter_registry.AdapterRecord`, reused rather than
  reinvented). `qualify(request, baseline_results, candidate_results,
  target_prompt_digest, target_constitution_digest)` is pure -- it never
  mutates gate state. Regression is pass/fail per shared probe id (a probe
  that passed at baseline and fails at candidate), the same definition
  `evals/compare.py` uses and the same rationale it documents ("a score
  delta ... is one check flipping; deciding how much of that is tolerable
  would be a tuning knob nobody has measured yet"); an empty
  baseline/candidate probe-id intersection fails safe as a regression
  rather than a vacuous pass. Qualification additionally requires the
  request's `prompt_digest` to equal the live target's, and
  `request.metadata["constitution_digest"]` to equal the live target's
  constitution digest (kept in `metadata` rather than as a new top-level
  field, so `AdapterQualificationRequest` matches `PLAN.md` exactly), and an
  optional minimum pass rate. `activate()` raises -- and changes nothing --
  on an unqualified result; on success it snapshots the incumbent
  `AdapterRecord` and digests, swaps to the candidate, and sets
  `rollback_pointer` to the incumbent's version. `rollback()` is the 1-step
  atomic restore of that snapshot; a second call raises rather than
  no-op'ing, matching the governor's rollback semantics above.

### `tests/test_learning_governance.py`

50 tests covering:

- `LearningProposal` validation: `risk_class` has no default and rejects an
  unknown value; a proposal defaults to PROPOSED with no
  `activation_revision`/`evaluated_at`; `created_at` is populated
  automatically.
- Full lifecycle: PROPOSED -> VALIDATED -> APPROVED -> ACTIVATED ->
  ROLLED_BACK on a LOW-risk proposal, asserting the `state_applier` receives
  `proposed_value` on activation and `rollback_value` on rollback; every
  out-of-order transition (activate-before-approve, unknown proposal id,
  submit without `rollback_value`, duplicate `proposal_id`) raises and
  leaves the proposal's status unchanged.
- Immutable-core / constitutional hard rejection: 8 parametrized
  `target_domain` variants (dotted, bracketed, underscored, dashed, mixed
  case) covering `IMMUTABLE_CORE` keys, static safety/immutable/
  constitutional markers, and a CONSTITUTIONAL-tier field name, all flagged
  by `check_targets_protected_domain`; an ordinary domain is not flagged;
  `LearningGovernor.submit` refuses (and registers nothing for) both an
  immutable-core target and a constitutional-bound target; a protected
  target is refused by `LearningApprovalGate.evaluate` directly even with an
  always-approving gatekeeper, proving the invariant lives in the domain
  check itself and not only at one call site.
- Risk-tiered gating: LOW auto-approves; CRITICAL is blocked even with a
  gatekeeper that would approve everything; MEDIUM and HIGH are refused
  with no gatekeeper configured and approved/rejected according to whatever
  the gatekeeper returns; `LearningGovernor.approve` marks a gatekeeper-less
  HIGH-risk proposal REJECTED with a reason and a stamped `evaluated_at`.
- Atomic rollback fidelity: rollback restores the exact `rollback_value`
  (not a derived/partial value); a second rollback on an already-rolled-back
  proposal raises; rollback before activation raises;
  `activation_revision` increments monotonically across separate proposals
  on the same governor.
- Learning-progress curiosity: `progress_delta` is `None` before two full
  windows and positive for a genuinely improving domain; a mastered
  (flat, near-zero-error) domain is excluded from `rank()` even though it
  has a computable delta; a domain oscillating with zero net trend between
  windows (the same three values in the older and recent window) is
  excluded; `rank()` on three domains (one improving, one mastered, one
  trend-free) returns only the improving one; `window_size < 2` is
  rejected.
- Offline adapter qualification: zero-regression + matching digests
  qualifies; a probe that passed at baseline and fails at candidate is
  caught and named in `details["regressed_probe_ids"]`; disjoint probe-id
  sets fail safe; a prompt-digest mismatch, a constitution-digest mismatch,
  and a below-minimum pass rate each independently fail qualification (with
  the specific `details` flag asserted for the first two);
  `activate()` refuses (and leaves `gate.active` unchanged for) an
  unqualified result; `activate()` then `rollback()` restores the exact
  incumbent `AdapterRecord`; `rollback()` with no prior `activate()`, and a
  second `rollback()` after one already succeeded, both raise;
  `compute_prompt_digest` is stable and content-sensitive;
  `compute_constitution_digest` changes when a CONSTITUTIONAL field changes
  and is unaffected by an ADAPTIVE field change.

---

## 4. Verification

Run from `backend/` (this worktree has no `.venv` of its own -- it shares
the interpreter at `/Users/aniketsaha/Projects/AI_friend/.venv`, which is on
`PATH` in this environment; the CLAUDE.md-documented `../.venv/bin/python`
form resolves to the same interpreter):

```
python3 -m pytest tests/test_learning_governance.py -q --junit-xml=<scratch>/res.xml
```
Result: **50 passed, 0 failed, 0 errors, 0 skipped** (verified via the XML,
per CLAUDE.md's guidance that the terminal summary line is unreliable in
this environment; the terminal output here did show only a dot-progress
line with no trailing "N passed" line, consistent with that documented
quirk).

```
python3 -m ruff check .
```
Result: **All checks passed** (both files were clean on first pass except
two `C408` findings in the test file's `make_proposal`/`make_request`
helpers -- `dict(...)` calls rewritten as literal `{...}` -- fixed before
this final run).

```
python3 -m radon cc app/ -s -n D
```
Result: **no output** -- zero functions at cyclomatic-complexity rank D or
higher in either new module.

ASCII purity: a `grep` for any byte outside the printable-ASCII-plus-tab
range against all three new files found nothing; each is pure 7-bit ASCII.

Mutation testing (four mutations, each applied via a scripted in-place edit,
tested, then reverted and diffed back to byte-identical with the pre-
mutation file before moving to the next):

1. `check_targets_protected_domain` forced to always return `(False, "")`
   -> **11 of 50** tests failed (the 8 parametrized protected-domain cases,
   both `submit`-time hard-rejection tests, and the direct-gate-bypass
   test).
2. `LearningApprovalGate.evaluate`'s CRITICAL branch flipped to approve
   instead of block -> **1 of 50** failed
   (`test_critical_risk_is_always_blocked_even_with_gatekeeper_approval`).
3. `OfflineAdapterGate.rollback()` edited to clear the snapshot without
   restoring `_active`/digests from it -> **1 of 50** failed
   (`test_activate_then_rollback_restores_incumbent_atomically`).
4. `OfflineAdapterGate.qualify()`'s `regression_detected` forced to always
   be `False` -> **3 of 50** failed (the explicit regression-detection
   test, the no-shared-probes fail-safe test, and -- because it now
   silently claimed a green qualification -- indirectly perturbed the
   qualifies-cleanly assertion count, all three confirmed as the expected
   failures by name in the XML).

All four mutations were reverted; `diff` against the pre-mutation backup
confirmed byte-identical restoration each time, and the full 50-test suite
plus `ruff check .` and `radon cc app/ -s -n D` were re-run clean
afterward (see the final verification block above, run last).

---

## 5. Design Notes and Deviations

- Section 2 above (naming deviation) is the primary deviation; repeated
  here only as a pointer since it changes where a reviewer should look for
  this phase's `LearningProposal`, not what it contains.
- `created_at`'s `default_factory=time.time` instead of the contract's
  literal `= 0.0` (Section 3 above).
- `LearningProposal.rejection_reason` is an addition beyond the `PLAN.md`
  field list -- needed so `LearningGovernor`'s audit trail can record *why*
  a proposal was rejected (protected domain, or a gate's stated reason)
  without a separate side-channel. It is optional (`None` default) and does
  not change any contract field's name or type.
- `LearningGovernor` and `OfflineAdapterGate` both take an injected
  `state_applier`/require an explicit incumbent snapshot at construction
  rather than reaching into `StateService`, `PersonaProfile`, or
  `adapter_registry.save_adapter_record`/`load_adapter_record` directly.
  Section 6 explains why wiring a live caller was out of scope; this keeps
  both classes pure and testable without a running agent process, consistent
  with `ProviderCapabilityNegotiator`'s posture from Phase 05 (Package B's
  prior deliverable in this same worktree).
- `check_targets_protected_domain`'s token-based matching (delimiter-
  normalize, then contiguous-phrase containment) reuses the exact technique
  `app/cognitive/learning_review.py`'s peer-reviewed fix round already
  proved closes bracket/underscore/case bypasses (see that file's own
  docstring), rather than inventing a new, unreviewed matching strategy for
  the same problem.

---

## 6. NOT Done / Out of Scope for This Package

- No wiring of `LearningGovernor`, `LearningApprovalGate`,
  `LearningProgressCuriosity`, or `OfflineAdapterGate` into any live agent
  process (`subconscious_agent.py`, `brain_agent.py`, `background_scheduler.py`).
  The task scope was the governance/curiosity/gating contracts and their
  hard invariants, not mesh integration; both classes accept dependency-
  injected callbacks (`state_applier`, `gatekeeper`) precisely so that
  wiring can happen later without changing this module.
- No migration of `app/cognitive/learning_review.py`'s existing
  `LearningProposal`/`LearningReviewQueue` (Phase 04) onto this phase's
  richer schema -- see Section 2. That is a separate, higher-blast-radius
  piece of work touching `ReflectionService` and multiple existing tests,
  explicitly deferred per user direction in this session.
- No connection between `LearningProgressCuriosity` and any real error/loss
  signal from memory retrieval, calibration (`app/cognitive/calibration.py`),
  or action outcomes -- `record()` takes a caller-supplied `error` float,
  and wiring an actual empirical source is future integration work.
- No live invocation of `backend/evals/`'s `run`/`compare` CLI from
  `OfflineAdapterGate` -- by design (`app/` may not import `evals/`); a real
  qualification run means the caller runs `evals compare` externally and
  hands `qualify()` the resulting per-probe pass/fail map.
- Package A's deliverables (`planning.py`, `simulation.py`,
  `test_planning_simulation.py`) -- owned by the Codex worktree, not
  touched here.
- Reciprocal peer review, orchestration arbitration, and integration into
  `integration/phase-06` are the next steps in the Phase 06 process
  (`PLAN.md` section 4), not part of this package's delivery.

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
