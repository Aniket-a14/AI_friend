# Phase 06 Reciprocal Peer Review: Claude reviews Codex Package A

Reviewer: Claude (Package B author, `ai-friend-claude`)
Subject: Codex Package A -- Verified Planning and Sandboxed Episodic
Simulation, branch `codex/phase-06`, commit `45b3955`
Files reviewed: `backend/app/cognitive/planning.py`,
`backend/app/cognitive/simulation.py`, `backend/tests/test_planning_simulation.py`
Reviewed against: `orchestration/PHASE_06/CODEX_TASK.md`, `PLAN.md`,
`ACCEPTANCE_CRITERIA.md`, `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (Sections
16, 17, 38)
Method: full read of all three files; independent execution of the shipped
test suite; independent scratch-script probes of code paths the shipped
suite does not exercise; mutation testing (8 mutations) with restore-and-
reverify after each; `ruff check`, `radon cc`, and an independent ASCII
byte scan.

---

## Verdict

**Do not merge as-is.** The schema layer (`PlanArtifact`/`PlanStep`/
`PlanPrecondition`/`PlanEffect`/`PlanVerificationResult`) is solid, and code
hygiene (ASCII, ruff, radon) is fully clean. But I found two P0s in the
combination of `EpisodicSimulator.simulate_plan()` with
`DeterministicPlanExecutor`: one is a demonstrated silent-success bug (a
plan where every step fails reports `succeeded=True` with zero errors, and
this path is directly reachable through `simulate_plan`, not just through
bare-executor misuse), and the other is a demonstrated quarantine gap (an
`action` callback passed into `simulate_plan` can perform real side effects
that nothing in this module observes, tags, or blocks). I also found a
concrete false-positive in `DeterministicPlanVerifier`'s cycle check that
rejects a genuinely valid, fully-executable plan as "circular." All three
are backed by runnable repros below, not just code reading. Test coverage
for the execution/retry/effect-operator surface is materially thinner than
the code it is meant to protect -- confirmed by four mutations that the
current 10-test suite does not catch.

---

## 1. Schema Completeness (review dimension 1)

`PreconditionOp`, `PlanEffectOp`, `PlanPrecondition`, `PlanEffect`,
`PlanStep`, `PlanArtifact`, `PlanVerificationResult` all match the
`PLAN.md` section 3.A shared contract field-for-field, type-for-type. Two
deliberate additions beyond the contract, both reasonable hardening:

- `PlanArtifact.steps` gets `min_length=1` (the contract leaves it
  unconstrained). A zero-step plan is nonsensical, so this is a sound
  addition, not a deviation worth flagging.
- `field_validator`s reject blank `key`/`step_id`/`name`/`action_type`/
  `plan_id`/`goal_id` strings, and a `model_validator` on `PlanArtifact`
  rejects duplicate `step_id`s and a `fallback_step_id` that does not name
  a real step in the plan.

`PlanVerificationResult` matches the contract exactly (`valid`, `errors`,
`cycle_detected`, `unreachable_steps`, `invariant_violations`).

Gap (see P1-3 below): the fallback-reference validator checks "does this
id exist in the plan" but not "is this id the step's own id" -- a step can
legally name itself as its own `fallback_step_id`.

`PlanStepStatus`, `PlanStepExecution`, `PlanExecutionResult` are sensible,
non-contract additions needed to report execution traces; not a concern.

**No direct unit test exercises any of the blank-key/blank-text/duplicate-id
validators individually** -- the only schema test
(`test_plan_artifact_rejects_duplicate_steps_and_unknown_fallbacks`) covers
duplicate ids and unknown fallback references, but nothing exercises
`PlanPrecondition`/`PlanEffect`'s own blank-key validators,
`PlanStep`'s blank-text validator, `timeout_s`'s `gt=0.0` bound, or
`max_retries`'s `ge=0` bound. Given `AC-P6-01` explicitly asks for "schema
validation tests pass 100%," this is a real, if narrow, gap. **P2** (the
validators themselves are correct by inspection; this is a coverage gap,
not a defect).

---

## 2. DeterministicPlanVerifier Soundness (review dimension 2)

### P0-1: `simulate_plan()` can report `succeeded=True` with zero errors for a plan where every step failed

`EpisodicSimulator.simulate_plan()` (`simulation.py:69-77`) calls
`DeterministicPlanExecutor().execute(plan, workspace_state, action)`
directly. It never calls `DeterministicPlanVerifier` first, and nothing in
`DeterministicPlanExecutor.execute()` requires the plan to have been
verified. `DeterministicPlanExecutor._execute_chain`
(`planning.py:450-479`) has an explicit, commented safety net for a
fallback cycle:

```python
while step.step_id not in completed:
    if step.step_id in chain:
        errors.append(f"execution fallback cycle at step {step.step_id}")
        return
    chain.add(step.step_id)
    execution = self._attempt_step(step, state, action)
    trace.append(execution)
    completed.add(step.step_id)
    ...
```

`completed.add(step.step_id)` runs on the **same iteration** a node is
added to `chain`. That means by the time execution would ever revisit a
node already in `chain`, that node is *also already in `completed`* -- so
the outer `while step.step_id not in completed` loop guard exits the loop
silently, before the `if step.step_id in chain` check is ever reached. The
`"execution fallback cycle"` error is dead code: it can never fire, for
any input, because the two membership tests race and `completed` always
wins first.

Reproduction (`DeterministicPlanExecutor` used exactly as the shipped test
`test_executor_tracks_failed_step_and_runs_declared_fallback` uses it --
directly, standalone, the same pattern `simulate_plan` uses internally):

```python
plan = PlanArtifact(
    plan_id="fb-cycle", goal_id="g",
    steps=[
        PlanStep(step_id="a", name="a", action_type="ACT", fallback_step_id="b"),
        PlanStep(step_id="b", name="b", action_type="ACT", fallback_step_id="a"),
    ],
)
result = DeterministicPlanExecutor().execute(plan, {}, action=lambda s, st: False)
```
Result: `result.succeeded == True`, `result.errors == []`, while
`result.step_executions` shows **both** steps as `FAILED`. A plan in which
every single step failed is reported as a successful execution with an
empty error list.

This is not purely a "misuse the bare executor without verifying first"
concern, either: `EpisodicSimulator.simulate_plan()` -- one of this
package's two headline deliverables -- reaches this exact code path with
no verification gate in between, and is directly unit-tested in that
configuration
(`test_simulator_executes_a_plan_on_a_cloned_workspace`, which happens not
to exercise a fallback cycle, so it does not catch this). Note also that
the *verifier's* cycle graph would have caught this specific 2-step
example (its edges include fallback edges, so a pure fallback cycle is a
subset of what it checks) -- but that only holds if a caller actually runs
`verify()` before `execute()`/`simulate_plan()`, which nothing enforces,
and which `simulate_plan()` itself does not do.

**Severity: P0.** A caller (e.g. a future goal-review or action-selection
consumer of `PlanExecutionResult.succeeded`, or a counterfactual evaluation
built on `EpisodicSimulationResult`) can be confidently told a plan
succeeded when every step in it failed, with no error trail to contradict
that claim.

**Recommendation:** fix the race by checking `chain` membership before
mutating `completed`, or by tracking "failed nodes visited in this chain"
separately from "attempted at all"; alternatively, have `simulate_plan()`
(and ideally `execute()`) refuse to run a plan that
`DeterministicPlanVerifier.verify()` marks invalid, so the (fixed) dead
code becomes genuinely unreachable by design rather than by accident.

### P1-3: `DeterministicPlanVerifier` rejects a fully valid, fully executable plan as "circular"

`_dependency_graph` (`planning.py:356-377`) builds cycle-detection edges
from *any* step whose precondition is unsatisfied by the **initial**
state to *any* step anywhere in the plan (regardless of declared order)
whose effects could plausibly establish that precondition
(`_effect_can_establish`, `planning.py:389-399`). This is
order-agnostic: it does not distinguish "a step earlier in the declared
list establishes this" (a real, benign forward dependency, which is how
this plan format is actually executed -- see `_replay` and
`DeterministicPlanExecutor.execute`, both of which iterate `plan.steps` in
declared order) from "a step *later* in the list, or a step that also
happens to touch the same key for an unrelated reason, could establish
this" (not a real dependency at all).

Reproduction:

```python
plan = PlanArtifact(
    plan_id="false-positive-cycle", goal_id="g",
    steps=[
        PlanStep(step_id="P", name="prep", action_type="ACT",
                  effects=[PlanEffect(key="ready", op=PlanEffectOp.SET, value=True)]),
        PlanStep(step_id="A", name="a", action_type="ACT",
                  preconditions=[PlanPrecondition(key="ready", op=PreconditionOp.EQUAL, value=True)],
                  effects=[PlanEffect(key="done_a", op=PlanEffectOp.SET, value=True)]),
        PlanStep(step_id="B", name="b", action_type="ACT",
                  preconditions=[PlanPrecondition(key="done_a", op=PreconditionOp.EQUAL, value=True)],
                  effects=[PlanEffect(key="ready", op=PlanEffectOp.SET, value=True)]),  # redundant re-affirmation
    ],
)
result = DeterministicPlanVerifier().verify(plan)
```
Result: `result.valid == False`, `result.cycle_detected == True`,
`result.unreachable_steps == []`, `errors == ["plan contains a circular
dependency"]`. But actually executing this exact plan in its declared
order succeeds cleanly: `DeterministicPlanExecutor().execute(plan, {})`
gives `succeeded == True`, `workspace_state == {"ready": True, "done_a":
True}`, all three steps `SUCCEEDED`. The "cycle" is an artifact of B
redundantly re-setting a key A also depends on (a completely ordinary
plan-authoring pattern -- idempotently reaffirming a shared flag) -- there
is no genuine circular *need* between A and B given the plan's actual
declared-order semantics.

A second, compounding issue in the same heuristic: `_effect_can_establish`
says a `DELETE` effect can establish a `NOT_EQUAL` precondition. But
`precondition_holds`'s own `NOT_EQUAL` branch is guarded by `actual is not
_MISSING` (`planning.py:177-178`) -- a deleted (and therefore missing) key
can *never* satisfy `NOT_EQUAL` under this module's own evaluation
semantics. So `_effect_can_establish` disagrees with `precondition_holds`
about what a `DELETE` effect actually accomplishes, in a direction that
only adds more spurious graph edges (never fewer), which can only make the
false-positive-cycle problem above worse, never better.

**Severity: P1** (not P0: this fails *safe*, over-rejecting rather than
under-accepting a truly broken plan, so it does not violate `AC-P6-02`'s
literal "0% false acceptance" bar -- but it directly contradicts
`AC-P6-02`'s soundness framing, and a planner that rejects ordinary,
correct plans as "cyclic" will not survive contact with real plan
authoring).

**Recommendation:** the `_replay` reachability pass already correctly
computes order-aware reachability by simulating declared-order execution
with a real running state. Consider dropping the separate,
order-agnostic "causal producer" edges from the cycle graph entirely and
reserving graph-based cycle detection for what is unambiguously a graph
concept -- fallback edges (two or more steps whose declared
`fallback_step_id` chain returns to a step already in that chain) -- while
letting `_replay`'s existing unreachable-step reporting be the sole
signal for "a precondition is never actually established in this plan's
declared order." At minimum, fix the `DELETE`/`NOT_EQUAL`
inconsistency with `precondition_holds`.

### Reachability, invariants, budget: correctly implemented, correctly ordered

- `test_verifier_rejects_unfulfilled_precondition_and_invariant_violation`
  demonstrates a step with a precondition nothing establishes is correctly
  flagged unreachable, and a same-run invariant violation is correctly
  named with the offending step. I independently confirmed the `step=None`
  ("initial state," before any step runs) branch of `_invariant_errors`
  also works (`invariants=[safe==True]` against an initial state where
  `safe=False` correctly produces `"invariant violated initial state:
  safe"`) -- untested by the shipped suite, but correct.
- `terminal_conditions` (untested by the shipped suite) also verified
  correct via direct probe: an unmet terminal condition is reported.
- Budget: `test_verifier_rejects_declared_or_actual_step_budget_overrun`
  only exercises the "`budget_max_steps` field itself exceeds the fixed
  ceiling of 20" branch. The *other* branch in the same method
  (`len(plan.steps) > plan.budget_max_steps` -- e.g. a plan that declares
  `budget_max_steps=5` but supplies 6 steps) is completely untested. I
  confirmed by direct probe that this branch is in fact correctly
  implemented (`errors == ["plan step count exceeds budget_max_steps"]`).
  Coverage gap noted under P1-4 below, since this is a distinct,
  independently-named invariant in `ACCEPTANCE_CRITERIA.md`'s checklist
  ("a plan exceeding `max_steps`... must be rejected").

### P1-5: A step can legally name itself as its own fallback

`PlanArtifact.validate_step_references` (`planning.py:115-129`) checks
that every `fallback_step_id` names a real step in the plan, but does not
reject `fallback_step_id == step_id`. Confirmed by direct probe:
`PlanStep(step_id="s", ..., fallback_step_id="s")` inside a `PlanArtifact`
constructs without error. This is exactly the degenerate, one-node version
of the fallback-cycle bug in P0-1 above (a step falling back to itself),
and it is legal input today. **Recommendation:** reject
`fallback_step_id == step_id` alongside the existing "must reference a
real step" check -- one extra line in an already-present validator.

---

## 3. Deterministic Execution, Bounded Retries, Fallback Transitions (review dimension 3)

The one shipped test
(`test_executor_tracks_failed_step_and_runs_declared_fallback`) correctly
demonstrates a failed primary step redirecting to its declared fallback,
with a correct trace and `fallback_transitions` list. I verified by direct
probe (not just code reading) that the following also behave correctly:

- Retry-then-succeed: a flaky `action` that fails once and succeeds on the
  second call is retried and reports `SUCCEEDED` with `attempt_count == 2`.
- Retry exhaustion with no fallback: an `action` that always fails reports
  `FAILED` after exactly `max_retries + 1` attempts, correct
  `attempt_count`, and a populated `errors` list.
- `INCREMENT`/`APPEND`/`DELETE` effects (3 of the 4 `PlanEffectOp`
  variants) all apply correctly.

**None of these three behaviors is exercised by the shipped test suite.**
I confirmed this is a real gap, not a formality, via mutation testing (see
Section 6): removing the execution-time precondition gate entirely,
introducing an off-by-one bug that silently drops one retry attempt, and
disabling `INCREMENT` (making it a no-op) each produced **zero** test
failures against the current 10-test suite. Given "deterministic plan step
execution, bounded retries, and fallback transitions" is named explicitly
as its own review dimension and its own `CODEX_TASK.md` deliverable line
item, I am treating the combination of (a) untested and (b) demonstrably
mutable-without-detection as a genuine gap rather than a nice-to-have.

**Severity: P1.**

---

## 4. EpisodicSimulator Prospective Rollouts (review dimension 4)

`rollout()` correctly clones the workspace via `copy.deepcopy`, never
touches the caller's original mapping (`test_simulator_rollout_tags_...`
asserts `original` is byte-identical after the call), and tags every
percept/action/outcome. `simulate_plan()` correctly clones via the
executor's own internal deep copy and reports the prospective, not the
live, `phase` value in `test_simulator_executes_a_plan_on_a_cloned_workspace`.

Both entry points correctly avoid *aliasing* the live workspace. The gap is
elsewhere -- see P0-2 below, which is about the `action`/`policy` callback
boundary, not the workspace-cloning boundary (that part is solid).

Untested, but verified correct by direct probe:
- `outcome_resolver` when actually supplied (only the default-resolver
  path is exercised by the shipped test).
- `_call_commit` rejecting an awaitable with a clear `TypeError`.
- A clean, non-simulated record passing `assert_production_safe` and
  reaching a real commit callback unmodified (only the *rejection* path is
  tested; there is no positive-path test proving the gate does not
  false-block a legitimate record).
- Nested `is_simulation` detection (`_is_simulation_record`'s recursive
  check into `metadata`/`payload`/etc.) -- verified working via a record
  with `metadata={"is_simulation": True}` at the top level absent.

These are **P2** coverage gaps; the code itself is correct.

---

## 5. Simulation Quarantine Invariant (review dimension 5)

The tagging mechanism (`_tag`) and the standalone commit guards
(`assert_production_safe`, `commit_to_production_memory`,
`commit_to_production_state`) are correctly implemented and correctly
tested for the one path they cover: a record explicitly constructed with
`is_simulation: True` and handed to `EpisodicSimulator`'s own commit
methods is rejected before any callback runs
(`test_simulated_records_cannot_reach_production_memory_or_state`).
Mutation-confirmed (Section 6): disabling the gate, or flipping the tag
to `False`, is caught by the shipped suite.

### P0-2: `simulate_plan()`'s `action` callback has no simulation signal and no isolation from real side effects

The quarantine invariant as stated in `CODEX_TASK.md` ("Block any attempt
to commit simulated records to production memory stores or persistent
state") and `ACCEPTANCE_CRITERIA.md`'s invariant checklist
("`MemoryStore.save_memory` or state mutations must raise
`SimulationQuarantineViolationError` if invoked with simulated records")
is only enforced for writes that go *through*
`EpisodicSimulator.commit_to_production_memory`/`commit_to_production_state`.
Nothing marks the *execution context itself* as a simulation, and nothing
prevents a caller-supplied `action` callback (the exact same `StepAction`
type real, non-simulated `DeterministicPlanExecutor.execute()` accepts) from
performing real I/O directly, bypassing `EpisodicSimulator` entirely.

Reproduction:

```python
production_ledger = []  # stands in for a real MemoryStore / external system

def action(step, state):
    production_ledger.append({"step": step.step_id, "note": "REAL SIDE EFFECT DURING SIMULATION"})
    return True

plan = PlanArtifact(plan_id="leak", goal_id="g", steps=[
    PlanStep(step_id="s", name="s", action_type="ACT",
             effects=[PlanEffect(key="phase", op=PlanEffectOp.SET, value="prospective")]),
])
result = EpisodicSimulator().simulate_plan(plan, {"phase": "live"}, action=action)
```
Result: `production_ledger == [{"step": "s", "note": "REAL SIDE EFFECT DURING SIMULATION"}]`
-- a real write happened, unblocked, unflagged, and unrelated to whatever
`result.actions[0]["is_simulation"]` says (which is `True`, but only
describes the *trace metadata `simulate_plan` builds about the step*, not
whether the step's own code did anything real).

I recognize this is, in the fully general case, not perfectly solvable in
pure Python -- no sandbox can fully contain arbitrary caller-supplied code
without process/OS-level isolation, and Package B's own
`LearningGovernor.state_applier` has the identical shape of
externally-injected-callback trust boundary. The difference is that
`state_applier` is explicitly, by design, meant to perform a real write
(it is the mechanism by which an *approved, activated* proposal takes
effect) -- whereas `simulate_plan`'s entire reason to exist is that it is
*supposed* to be safe to call with a realistic action implementation
without side effects reaching production. Right now, nothing distinguishes
those two contexts for a caller writing an `action` implementation; the
type signature is identical (`Callable[[PlanStep, dict[str, Any]], bool |
None]`), and `simulate_plan`'s one-line docstring gives no warning.

**Severity: P0.** This is the flagship "sandboxed... strict memory
quarantine" deliverable of this package (`CODEX_TASK.md` section 1.2), and
the one entry point that actually executes an arbitrary caller-supplied
action during a "simulation" provides no isolation, no signal, and no
warning beyond the workspace-dict clone.

**Recommendation:** at minimum, document prominently (module docstring and
`simulate_plan`'s own docstring) that `action` must be pure/side-effect-free
under simulation and must not call any real commit/write API directly. Better:
give `simulate_plan` its own callback type that receives an explicit
`is_simulation=True` marker (or a `SimulationContext` object) so an action
implementation *can* branch on it, and/or thread every `action`-returned
value through `EpisodicSimulator._tag` before it can be observed by
anything outside the sandbox, making "did this go through the quarantine
tag" independently checkable regardless of what the action did internally.

---

## 6. Code Quality (review dimension 6)

Independently verified (not just re-reading `CODEX_RESULT.md`'s claims):

```
$ /Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m ruff check \
    app/cognitive/planning.py app/cognitive/simulation.py tests/test_planning_simulation.py
All checks passed!

$ /Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m radon cc app/ -s -n D
(no output -- zero D/E/F findings)
```
Full `radon cc -s` on both files: worst-ranked functions are
`DeterministicPlanVerifier._dependency_graph` and
`DeterministicPlanExecutor._attempt_step`, both **B(10)** -- comfortably
inside the review's A/B/C bar and the task's D/E/F gate. Everything else is
A or low B.

ASCII: independently re-scanned all three files for any byte >= 128;
found none. Confirms `CODEX_RESULT.md`'s claim rather than just trusting
it.

`test_phase_six_files_are_strictly_seven_bit_ascii` additionally guards
`CODEX_RESULT.md` itself, which I did not independently re-scan (out of
review scope) but is a reasonable belt-and-suspenders test.

---

## 7. Test Suite Run

```
$ /Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m pytest \
    tests/test_planning_simulation.py -q --junit-xml=<scratch>/res.xml
```
Result (via JUnit XML, per this repo's documented pytest-summary-line
unreliability): **10 passed, 0 failed, 0 errors, 0 skipped.** Matches
`CODEX_RESULT.md`'s claim.

---

## 8. Mutation Testing

Eight mutations applied via scripted in-place edits, tested, then reverted
and `diff`-confirmed byte-identical to the pre-mutation file before the
next mutation. Both files were re-verified clean (`diff` = no output) after
the full sequence, and the full 10-test suite plus `ruff check .` were
re-run green afterward.

| # | Mutation | Result |
|---|---|---|
| 1 | `DeterministicPlanVerifier._has_cycle` forced to always return `False` | **Caught** -- 1 failure (`test_verifier_rejects_cyclic_causal_dependencies`) |
| 2 | `_invariant_errors` forced to always return `[]` | **Caught** -- 1 failure (`test_verifier_rejects_unfulfilled_precondition_and_invariant_violation`) |
| 3 | `_budget_errors` forced to always return `[]` | **Caught** -- 1 failure (`test_verifier_rejects_declared_or_actual_step_budget_overrun`) |
| 4 | `EpisodicSimulator._tag` forced to set `is_simulation=False` | **Caught** -- 2 failures (both simulator tagging tests) |
| 5 | `assert_production_safe`'s guard condition forced to `False` (never raises) | **Caught** -- 1 failure (`test_simulated_records_cannot_reach_production_memory_or_state`) |
| 6 | `_attempt_step`'s execution-time precondition gate removed entirely | **NOT caught** -- 0 failures |
| 7 | Retry loop bound changed from `max_retries + 2` to `max_retries + 1` (silently drops one retry attempt) | **NOT caught** -- 0 failures |
| 8 | `_increment` made a no-op (`INCREMENT` effect silently does nothing) | **NOT caught** -- 0 failures |

Mutations 1-5 confirm the verifier's core soundness checks (cycle,
invariant, budget) and the quarantine tag/gate are genuinely enforced by
the shipped suite, not just present in the code. Mutations 6-8 confirm the
P1-4 coverage gap in Section 3 above is real and not merely a documentation
nitpick: three concrete, meaningfully-different correctness regressions in
the execution/retry/effect path go completely undetected today.

---

## 9. Acceptance Criteria Mapping

| Criteria | Status | Note |
|---|---|---|
| AC-P6-01 (schema completeness) | Mostly met | Contract fields match exactly; individual field validators lack direct tests (P2) |
| AC-P6-02 (verifier soundness: 0% false acceptance) | **Not fully met** | No false acceptance of a truly cyclic plan found; but P1-3's false *rejection* of a valid plan undermines the soundness claim this criterion is framed around, and the underlying heuristic (P1-3) is a latent risk for the false-acceptance direction too if `_effect_can_establish` is ever loosened without revisiting `precondition_holds`'s own MISSING-value semantics |
| AC-P6-03 (sandboxed rollouts compute prospective outcome) | Met | `rollout()` and `simulate_plan()` both correctly clone and compute; correctness of the *executor* they call is P0-1's concern, not this criterion's |
| AC-P6-04 (100% simulation tagging; 0% leak into live memory/state) | **Not met** | Tagging itself is 100% correct where exercised; but P0-2 demonstrates a real, unblocked leak path via `simulate_plan`'s `action` callback |
| AC-P6-10 (code hygiene / CI compliance) | Met | ASCII, ruff, radon all independently reverified clean |

(AC-P6-05 through AC-P6-09 are Package B's/my own criteria, out of scope
for this review of Package A.)

---

## 10. Summary of Findings by Severity

**P0 (blocker):**
1. `simulate_plan()` reaches a dead/broken fallback-cycle guard in
   `DeterministicPlanExecutor._execute_chain` that silently reports
   `succeeded=True` / `errors=[]` for a plan where every step failed.
2. `simulate_plan()`'s `action` callback has no simulation signal and no
   isolation from real side effects; a realistic action implementation can
   leak a real write out of the "sandbox" undetected.

**P1 (must fix):**
3. `DeterministicPlanVerifier`'s cycle check produces a false positive on a
   genuinely valid, fully-executable plan (order-agnostic causal-edge
   heuristic, compounded by a `DELETE`/`NOT_EQUAL` inconsistency with
   `precondition_holds`).
4. Test coverage gap for bounded-retry semantics, execution-time
   precondition gating, and 3 of 4 `PlanEffectOp` variants -- confirmed via
   3 undetected mutations, not just absent test names.
5. Schema allows `fallback_step_id == step_id` (self-fallback), the
   degenerate trigger case for finding #1.

**P2 (improvement):**
6. No direct tests for `PlanPrecondition`/`PlanEffect`/`PlanStep`'s blank-
   value field validators or numeric bound fields (`timeout_s`,
   `max_retries`, `budget_max_steps`).
7. No test for the "actual step count exceeds a valid `budget_max_steps`"
   branch (distinct from the tested "`budget_max_steps` itself exceeds 20"
   branch) -- verified correct by direct probe, just untested.
8. No test for `terminal_conditions`, or for `_invariant_errors`'s
   initial-state (`step=None`) branch -- both verified correct by direct
   probe.
9. No test for `rollout()`'s `outcome_resolver` parameter actually being
   supplied, `_call_commit`'s awaitable rejection, nested `is_simulation`
   detection, or the positive case of a clean (non-simulated) record
   passing the quarantine gate untouched -- all verified correct by direct
   probe.
10. Overall suite breadth (10 tests) is thin relative to the module's
    surface area and its "verified"/safety-critical framing; for scale,
    Package B's equivalent Phase 06 suite has 50 tests and this same
    author's own Phase 05 package grew from 60 to 123 tests across one
    review round.
11. `commit_to_production_memory` and `commit_to_production_state` are
    byte-identical implementations; fine if intentionally kept separate
    for future divergence, but worth a one-line docstring note saying so.
12. Minor duplicate invariant reporting: an invariant already violated by
    the initial state and never fixed by any step is reported twice
    (`"invariant violated initial state: ..."` and
    `"invariant violated after step <last>: ..."` for the same underlying
    condition) -- not incorrect, just noisier than necessary for a
    verification-result consumer.

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
