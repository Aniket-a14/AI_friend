# Phase 03 Reciprocal Peer Review: Claude reviews Codex (Package A)

Reviewer: Claude (Package B), branch claude/phase-03
Reviewed: Codex (Package A), branch codex/phase-03, commit f6cddb1
Reviewed worktree: /Users/aniketsaha/Projects/ai-friend-codex (clean, no edits made)
Reference: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md Sections 9, 10, 21, 38;
orchestration/PHASE_03/PLAN.md

Files inspected: backend/app/cognitive/global_controls.py,
backend/app/cognitive/appraisal.py, backend/app/state/agent_state.py,
backend/tests/test_causal_affect.py, orchestration/PHASE_03/CODEX_RESULT.md.
No Codex file was modified during this review.

## Verification performed

- `cd backend && ../.venv/bin/python -m pytest -q --junit-xml=<scratch>/res.xml`
  on codex/phase-03 f6cddb1: 1996 tests, 0 failures, 0 errors (parsed from
  the XML per this repo's documented "pytest summary is unreliable" note).
- `../.venv/bin/python -m ruff check app/cognitive/global_controls.py
  app/cognitive/appraisal.py app/state/agent_state.py
  tests/test_causal_affect.py`: All checks passed.
- Independent whole-file byte scan (not just trusting
  `test_phase03_owned_files_are_ascii_only`) of all 5 owned files: all pure
  7-bit ASCII, confirmed byte-for-byte.
- Ad hoc scripts run against the actual `derive_global_controls` and
  `StateService` code (not merely reading source) to probe edge-case
  inputs and concurrency; see findings below for what each showed.

## Summary

The core derivation math is sound and genuinely self-bounding (formula
coefficients sum to exactly 1.0 at saturation, so the defensive clamp is a
backstop, not a mask for an overflowing formula), `appraise_event` is a
verified pure function, content isolation from belief/evidence/memory types
is structurally clean (zero coupling found anywhere in either owned
cognitive module), and lock discipline around `_state_lock` is correct and
was concurrency-stress-tested with no lost updates. `update_from_event`
picking up `_state_lock` here is also a genuine fix to a real pre-existing
gap, not just new-code hygiene.

The main gaps are integration gaps, not correctness bugs in the code that
does run: the new "structured appraisal" path (`appraise_event`,
`AppraisalRecord`) and the endocrine adapters are built and unit-tested in
isolation but never called from anywhere in the live turn loop, and one
release path (`release_adrenaline`) does not refresh the derived controls
even though the value it changes (arousal, via the adrenaline term) is a
direct input to their derivation.

## Findings

### HIGH

**H1. `release_adrenaline` does not refresh global controls, so `urgency_gain` goes stale exactly at a startle/interrupt event.**
File: `backend/app/state/agent_state.py`, lines 1576-1590 (async
`release_adrenaline`; compare lines 1543-1560 and 1562-1574, the sibling
`release_cortisol`/`release_dopamine`, which also do not refresh -- see
note below on why those two are fine and this one is not).

Scenario: `AgentState.arousal` (the property `_refresh_global_controls_locked`
reads to derive `urgency_gain`, `exploration_budget`, `learning_gain`) is
defined as `energy + fatigue_restlessness + adrenaline_lift` -- confirmed
by reading the property getter directly. `release_adrenaline` mutates the
adrenaline burst state under `_state_lock` but never calls
`_refresh_global_controls_locked()` afterward, unlike every other
affect-mutating method in this file (`apply_somatic_perception`,
`apply_facial_reflex`, `apply_sensory_perception`,
`update_from_appraisal`, `update_from_event`, `apply_external_state`,
`apply_semantic_appraisal`, `handle_system_tick`, `apply_affect_delta` all
call it). The result: immediately after a startle burst, `arousal` (read
fresh) has already jumped, but `get_global_controls()` /
`get_context_snapshot()["global_controls"]` still report the pre-burst
`urgency_gain` until some unrelated later call happens to refresh it
(possibly up to one `handle_system_tick` interval later).

This is not academic: `backend/app/agents/brain_agent.py:1002` calls
`state.release_adrenaline(...)` on the real barge-in/startle path (see
`backend/tests/test_barge_in_truncation.py`), which is exactly the
"safety/social urgency, interruption, high-confidence threat" scenario
Architecture Section 10's table names as `urgency_gain`'s primary driver,
and exactly the scenario decision.py's `_REFLEX_URGENCY_THRESHOLD` /
`is_facial_reflex_interruption_worthy` machinery exists to detect. Package
B's `CandidateSelector` modulation (urgency_gain > 0.5 favors fast/
low-risk candidates) will not see the effect of the startle on the very
turn that follows it.

`release_cortisol`/`release_dopamine` correctly do NOT need this fix:
neither cortisol nor dopamine feeds `derive_global_controls` at all (it
reads only `valence`, `arousal`, `dominance`, `load`), so a burst on
either of those two channels genuinely cannot change the derived controls.
Adrenaline is different because it is folded into the `arousal` property
itself, which `_refresh_global_controls_locked` does read.

Fix: add `self._refresh_global_controls_locked()` inside
`release_adrenaline`'s `async with self._state_lock:` block, mirroring
every other mutation path.

**H2. The new "structured appraisal" path (`appraise_event` / `AppraisalRecord`) is fully built and unit-tested but never called from anywhere in the live cognitive loop; the actually-live path substitutes loosely-related legacy fields for `urgency`/`prediction_error` instead.**
Files: `backend/app/cognitive/appraisal.py` (whole `appraise_event`
function and `AppraisalRecord` class, lines 29-132, have zero callers
outside `tests/test_causal_affect.py` -- confirmed by
`grep -rln "appraise_event\|AppraisalRecord" backend --include="*.py"`
matching only `appraisal.py` itself and the test file);
`backend/app/state/agent_state.py`, lines ~1177-1211 (`apply_affect_delta`,
the method meant to consume an `AppraisalRecord.affect_delta`, also has no
caller outside the same test file -- confirmed by
`grep -rln "apply_affect_delta\|get_global_controls\b" backend --include="*.py"`
matching only `agent_state.py`).

Architecture Section 9 states appraisal "maps `(event, active goals,
expectation, agency, controllability/coping, relationship, norms)` to an
affect delta, goal update, and stored appraisal record" -- this is
precisely what `appraise_event` computes, correctly and purely (see
positive notes below). PLAN.md's Package A deliverable #2 is "Structured
appraisal engine mapping ... to AppraisalRecord and affect deltas." As
delivered, this engine exists and is correct in isolation, but the actual
running system never constructs an `AppraisalRecord` or calls
`apply_affect_delta`; instead, the live paths that DO call
`_refresh_global_controls_locked` (`update_from_appraisal`,
`update_from_event`) feed it values from the old `AppraisalVector`:
`update_from_appraisal` passes `urgency=R` where `R = appraisal.relevance`
and `prediction_error=N` where `N = appraisal.novelty`
(agent_state.py, lines ~1224-1229 and the call at ~1281); `update_from_event`
passes `prediction_error=abs(event_valence)` (line ~1320). Relevance is not
urgency (a highly relevant but calm, expected topic scores as "urgent"
under this substitution), and novelty is not prediction error (`appraise_event`
itself computes something much closer to a real prediction error from
`expectation`/`unexpectedness`, and does not use "novelty" as a stand-in
for it). So two different, non-interchangeable definitions of urgency and
prediction error exist in this codebase after this change: the one
`derive_global_controls`'s own docstring describes, and the one actually
wired into the live turn.

This means "prove ... that internal appraisal and emotional state
systematically modulate deliberation" (PLAN.md's executive objective) is
demonstrated only in isolated unit tests for the new reducer, not for the
system as it will actually run once this branch merges. Concretely,
`state_snapshot["global_controls"]` (which Package B reads) IS populated
with live, changing values once merged -- so integration will not crash or
silently no-op -- but the values it carries come from the ad hoc proxy
substitution above, not from the structured reducer this phase was
supposed to establish.

Recommendation: either wire `appraise_event`/`apply_affect_delta` into the
live turn (replacing or feeding the `update_from_appraisal`/
`update_from_event` call sites) before this merges to
`integration/phase-03`, or explicitly document in CODEX_RESULT.md that
this is deferred and that the live path uses the relevance/novelty proxy
instead, so the integration reviewer does not assume `AppraisalRecord` is
what is actually driving production behavior.

### MEDIUM

**M1. NaN inputs silently clamp to the maximum bound (1.0), not a safe default -- masking pydantic's own stricter rejection.**
File: `backend/app/cognitive/global_controls.py`, lines 24-31
(`_unit_interval`, `_signed_unit_interval`).

`max(0.0, min(1.0, float(value)))` on a NaN `value`: Python's two-argument
`min(1.0, nan)` returns `1.0` (NaN comparisons are always False, so the
first argument survives), so `_unit_interval(nan) == 1.0` and
`_signed_unit_interval(nan) == 1.0` (verified directly:
`min(1.0, float('nan'))` -> `1.0`, `max(-1.0, 1.0)` -> `1.0`). Verified
empirically against `derive_global_controls` with NaN/inf valence, load,
urgency, and prediction_error: every case returns a fully in-bounds,
non-NaN `GlobalControls` (no crash, no bound violation, so the [0.0, 1.0]
contract itself is never actually broken) -- but a NaN valence is silently
treated identically to `+inf` valence, i.e. "maximally positive mood",
rather than a neutral/default reading or a rejected input. This is the
opposite of fail-safe: a NaN prediction_error (plausible from a division
by zero upstream) becomes `bounded_prediction_error = 1.0`, i.e. "maximum
surprise", pushing `exploration_budget` and `learning_gain` toward their
ceiling on exactly the kind of malformed telemetry that should probably be
treated as "no signal."

Notably, this clamp-before-construct pattern also defeats a real safety
net that already exists one layer down: calling
`GlobalControls(urgency_gain=float('nan'))` directly (bypassing
`derive_global_controls`) correctly raises `pydantic.ValidationError`
(verified) -- pydantic's own `ge=0.0, le=1.0` constraint checking does
treat NaN as failing both bounds. The hand-rolled clamp helpers are
strictly weaker than the validation the model would otherwise provide.

No test in `test_causal_affect.py` covers NaN or infinite inputs; only
finite -1.0/0.0/0.5/1.0 boundary values are exercised.

Suggested fix: reject or default (rather than clamp) on
`not math.isfinite(value)` before the `min`/`max` clamp, matching the
`math.isfinite` guard `AgentState._burst_amount` already uses elsewhere in
this same file for burst releases.

**M2. `exploration_budget` derives from `positive_valence`, not `positive_arousal`, contradicting Architecture Section 10's explicit table -- undocumented.**
File: `backend/app/cognitive/global_controls.py`, lines 75-80.

Architecture Section 10's table states `exploration_budget` is "Derived
from: novelty, unresolved uncertainty, learning progress, **positive
arousal**." The implemented formula is
`0.15 + 0.35*positive_valence + 0.30*bounded_prediction_error + 0.20*available_capacity`
-- arousal does not appear in this formula at all; valence is used in its
place, with no comment explaining the substitution. This is a real
behavioral divergence, not a naming quibble: under the architecture's
stated intent, a calm-but-happy state and an aroused-and-happy state
should differ in how much they widen exploration; under this
implementation they do not (only valence matters), while an aroused-but-
neutral-mood state (which the architecture says should raise exploration)
does not raise it at all here.

**M3. `endocrine_to_global_controls`/`global_controls_to_endocrine` (the "backward-compatible adapters" PLAN.md item 1 requires) are correct and unit-tested in isolation, but have zero call sites outside `test_causal_affect.py`.**
File: `backend/app/cognitive/global_controls.py`, lines 90-116; confirmed
via `grep -rn "endocrine_to_global_controls\|global_controls_to_endocrine"
backend --include="*.py"` matching only the definition file and the test
file. `_refresh_global_controls_locked` (agent_state.py, lines 553-568)
always calls `derive_global_controls` directly from PAD; it never routes
through the endocrine bridge. `action.py::_compute_endocrine_options` (the
one consumer of cortisol/dopamine/fatigue for LLM sampling) is unchanged
and still reads `AgentState.cortisol`/`dopamine`/`fatigue` directly, not
through `global_controls_to_endocrine`. AC-P3-03 ("Zero regression on
legacy endocrine callers") is trivially true today only because nothing
routes production data through these functions yet, not because
round-trip compatibility was exercised end to end against a real caller.

**M4. `AppraisalRecord.affect_delta` is a mutable dict nested inside a `frozen=True` model -- `frozen` does not deep-freeze it.**
File: `backend/app/cognitive/appraisal.py`, lines 29-45.

Verified directly: `record = appraise_event(...); record.affect_delta["pleasure"] = 999.0`
succeeds silently (no `ValidationError`), even though
`record.affect_delta = {...}` (reassigning the field itself) correctly
raises one. This undermines the class's own stated intent ("a pure event
reducer output," and `derive_global_controls`'s parallel docstring: "The
calculations are pure so callers can audit or replay a control decision
from its input snapshot") once any caller holds a shared reference to a
record and a second caller mutates its `affect_delta` in place -- a
classic mutable-default/shared-reference hazard, here surfacing through
pydantic's shallow `frozen`. Currently low practical risk only because
nothing in production holds onto an `AppraisalRecord` at all (see H2);
worth fixing (e.g. `Field(default_factory=dict)` plus a validator that
returns `MappingProxyType`, or documenting the caller obligation not to
mutate it) before this path is wired into anything that caches or replays
records.

**M5. Two tests in `test_causal_affect.py` provide weaker evidence than their names/docstrings claim.**
File: `backend/tests/test_causal_affect.py`, lines 98-152.

- `test_affect_controls_cannot_mutate_belief_truth_or_evidence` (lines
  98-133) constructs a `BeliefRecord`/`ExperienceRecord`, calls
  `state.apply_affect_delta(...)`, and asserts the records are unchanged.
  But `apply_affect_delta`'s signature takes no belief/evidence/memory
  argument at all, and neither it nor anything it calls references
  `MemoryStore`/`BeliefRecord`/`ExperienceRecord` (confirmed by grepping
  both owned cognitive modules). The test demonstrates "two unrelated
  objects remain unrelated" rather than probing an actual coupling path.
  It is a legitimate regression guard against a *future* accidental
  coupling, but it does not currently exercise the isolation invariant
  under any real interaction.
- `test_global_controls_are_immutable_action_selection_inputs` (lines
  136-152) never passes `global_controls` into
  `CandidateSelector.score_and_select(...)` at all -- it calls
  `selector.score_and_select([candidate], active_goals=[])` with no third
  argument. On codex/phase-03, `action_candidate.py` is Package B's file
  and this branch does not carry Package B's `global_controls` parameter
  addition to `score_and_select`, so the test cannot currently do what its
  docstring claims ("Selection may read controls but cannot rewrite a
  supplied control snapshot"). It only verifies that `GlobalControls`
  itself is frozen and that an unrelated `score_and_select` call does not
  touch a `GlobalControls` object sitting in the test's local scope. This
  is an artifact of the parallel package split rather than a mistake, but
  the integration/phase-03 merge should add a real test that threads a
  `GlobalControls` instance through `score_and_select` and asserts
  `model_dump()` is unchanged afterward.

### LOW

**L1. `learning_gain` omits two of its four architecturally-specified inputs.**
File: `backend/app/cognitive/global_controls.py`, lines 84-86.

Architecture Section 10: `learning_gain` derives from "prediction error,
goal outcome, salience, source reliability." The implementation is
`0.10 + 0.60*bounded_prediction_error + 0.30*salience` -- `derive_global_controls`'s
signature (`affect_pad, load, urgency, prediction_error`) has no parameter
for goal outcome or source reliability, so they cannot be represented at
all yet. Architecture Section 38's Phase 3 roadmap explicitly lists
"outcome-linked learning gain" as an "Add" item for this phase. This may
be a reasonable first pass given which signals are currently available
elsewhere in the system, but it is not disclosed as a limitation anywhere
in CODEX_RESULT.md.

**L2. CODEX_RESULT.md's "Not Done" section is incomplete relative to Architecture Section 38's Phase 3 roadmap and to this review's findings.**
File: `orchestration/PHASE_03/CODEX_RESULT.md`.

The "Not Done" section names only "Package B action-selection modulation,
integration merge, remote GPU benchmarks, and remote CI." It does not
mention that Section 38 Phase 3's "registered intervention runner" and
"dose-response telemetry" roadmap items are absent from this delivery, nor
that `appraise_event`/`AppraisalRecord`/the endocrine adapters are built
but unwired (H2, M3). A reviewer relying on this document alone, without
reading the diff, would not learn any of this.

**L3. CODEX_RESULT.md's "Verification" section is stale.**
File: `orchestration/PHASE_03/CODEX_RESULT.md`, line 12.

States "Pending final local verification after implementation." This
review independently re-ran the full suite (1996 tests, 0 failures/errors)
and `ruff check` (clean) against the exact commit under review (f6cddb1);
both pass. The document was apparently not updated after verification
actually completed, which could cause an integration reviewer to
under-trust a delivery that is, in fact, green.

### NIT

**N1. Repeated local imports of `global_controls` instead of one top-level import.**
File: `backend/app/state/agent_state.py`, lines 500, 557, 577 (inside
`__init__`, `_refresh_global_controls_locked`, `get_global_controls`
respectively).

`global_controls.py` has exactly two imports, both from `pydantic`
(`from __future__ import annotations` and
`from pydantic import BaseModel, ConfigDict, Field`) -- it imports nothing
from `app.state` or anywhere else in this codebase, so a top-level
`from ..cognitive.global_controls import GlobalControls, derive_global_controls`
at the top of `agent_state.py` would not create a circular import, unlike
the genuinely-deferred `TYPE_CHECKING`-only import of `UserMentalModel`
sitting next to it. The repeated local imports cost a `sys.modules` dict
lookup on every affect-mutating call (negligible) but are unnecessary
caution; a single top-level import would be simpler and equally safe.

## Positive notes (things done well)

- Lock discipline is correct everywhere checked: every one of the 11
  `_refresh_global_controls_locked()` call sites (hydrate_state,
  apply_external_state, apply_semantic_appraisal, apply_affect_delta,
  update_from_appraisal, update_from_event, apply_sensory_perception,
  apply_somatic_perception, apply_facial_reflex, handle_system_tick) is
  inside its method's `async with self._state_lock:` block; verified by
  reading each in full, not just the diff context. A concurrency stress
  test (100 concurrent `apply_affect_delta` calls interleaved with 100
  concurrent legacy `update_from_event` calls against one `StateService`)
  showed zero lost updates (`interaction_count` landed at exactly 100, the
  expected count if and only if the lock correctly serializes the
  `+= 1`).
- `update_from_event` used to run entirely outside `_state_lock` (a real
  pre-existing gap in this file, per the audit note already present in
  `handle_system_tick`'s own docstring citing the same class of bug for
  the tick path) and is now correctly wrapped in `async with
  self._state_lock:` as part of this change -- a genuine fix, not merely
  new-code hygiene riding along with it.
- `GlobalControls`/`AppraisalRecord` field names, types, and bounds match
  PLAN.md's shared contract exactly, field for field, including the
  `frozen=True` immutability declared there.
- Content isolation (AC-P3-07 / INV-P3-02) is structurally clean: neither
  `global_controls.py` nor `appraisal.py` references any belief, evidence,
  or memory-store type anywhere (grep-verified across both files), so the
  invariant holds by absence of coupling, not merely by a test asserting
  it.
- `appraise_event` is a genuinely pure function: verified directly that it
  does not mutate its `event_metadata`/`active_goals` arguments and
  performs no I/O or logging (unlike the adjacent `AppraisalEngine.appraise`,
  which does log).
- The core `derive_global_controls` formulas are self-bounding by
  construction for all finite inputs (each control's coefficients sum to
  exactly 1.0 at full saturation with a 0.0 base for three of the four),
  so the final `_unit_interval` clamp is a backstop rather than a mask for
  an overflowing formula -- good engineering discipline even though the
  NaN edge case (M1) still gets through it.
- ASCII compliance was done thoroughly: the whole files were rewritten to
  pure 7-bit ASCII (curly em-dashes, section signs), not just the added
  lines, and `test_phase03_owned_files_are_ascii_only` whole-file-scans
  them; independently re-verified byte-for-byte in this review, all 5
  files pass.
- Full local regression suite (1996 tests) and `ruff check` both pass
  cleanly at the reviewed commit.

## Severity summary

| Severity | Count | IDs |
|---|---|---|
| BLOCKER | 0 | -- |
| HIGH | 2 | H1, H2 |
| MEDIUM | 5 | M1, M2, M3, M4, M5 |
| LOW | 3 | L1, L2, L3 |
| NIT | 1 | N1 |
