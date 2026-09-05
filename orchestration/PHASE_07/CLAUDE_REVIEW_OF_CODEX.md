# Phase 07 Reciprocal Peer Review: Claude reviews Codex Package A

Reviewer: Claude (Package B author, `ai-friend-claude`)
Subject: Codex Package A -- Runtime Composition Root, Action Realization &
State Integrity, branch `codex/phase-07`, commit `3a3a268`
Files reviewed: `backend/app/cognitive/core.py`, `pipeline.py`, `decision.py`,
`action.py`, `backend/app/agents/brain_agent.py`,
`backend/app/state/session_state.py` (unchanged; verified), and the new
`backend/tests/test_runtime_composition.py`
Reviewed against: `orchestration/PHASE_07/CODEX_TASK.md`,
`ACCEPTANCE_CRITERIA.md`, `PLAN.md`, `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`
Method: full read of every changed file (via `git diff main..codex/phase-07`
and `git show codex/phase-07:<path>`); independent execution of the shipped
test suites (focused bar and full suite) in the `ai-friend-codex` worktree
against the shared `AI_friend/.venv`; independent `ruff`/`radon`/ASCII scans;
three targeted mutations with restore-and-reverify after each, including one
whole-service-removal mutation across the entire runtime (not just the
touched files) to test the central finding below.

---

## Verdict

**Conditional pass -- real, well-tested fixes for the three concrete bugs
the audit named, plus one significant, unflagged gap in the composition
claim.** The workspace pass-through (AC-P7-02) and WAIT silence realization
(AC-P7-05) are genuinely fixed, causally wired into production code paths
(not just constructor plumbing), and covered by tests that fail when I
mutate the fix away. Quality gates (ruff, radon, ASCII, the stated test
counts) all check out independently.

The problem is **AC-P7-01**. Of the eight services the task asked to
compose, only two -- `SQLiteWorkspaceStore` and `BackgroundScheduler` --
are actually exercised by any code path a real turn runs. The other six
(`TemporalMemoryStore`, `DeterministicPlanVerifier`,
`DeterministicPlanExecutor`, `EpisodicSimulator`, `LearningGovernor`,
`OfflineAdapterGate`, `ProviderCapabilityNegotiator` -- seven, counting
`ExternalActionDispatcher` as an eighth that is *referenced* but never
*consulted*) are constructed once in `CognitiveService.__init__`, stored as
attributes, forwarded to `CognitivePipeline`, and then never read, called,
or otherwise exercised anywhere else in the entire codebase. I verified this
by deleting all six from `core.py`'s constructor and pipeline forwarding
outright and running the full 2,337-test suite: exactly one test failed
(the new composition test itself, which only checks `isinstance`/`is`).
Nothing else in the system -- not one existing test, not one other code
path -- noticed six "composed" services vanish. This is precisely the
defect the Final System Audit chartered this phase to fix ("Phase 01-06
components were built and unit-tested in isolation... never composed into
the production runtime" / Invariant 1: "No phase service shall remain an
uncalled standalone library"), now reproduced one layer deeper: the
services are no longer *uncomposed* libraries, but six of them are still
*uncalled* ones, wearing a constructor-injection costume.

None of this means the work should be reverted -- the two genuinely wired
services are the two hardest and most safety-relevant to get right
(workspace causality, background preemption), and the three targeted bugs
(workspace pass-through, WAIT mapping, WAIT silence) are fixed correctly. It
means `CODEX_RESULT.md` and the `.agents/CONTEXT.md` entry should not be
read as "the architecture now actually runs in production" for six of the
eight services named, and the acceptance criteria / test suite should be
tightened before this is treated as done.

---

## 1. Composition Root (`core.py`, `pipeline.py`) -- Task A1 / AC-P7-01

### 1.1 What is genuinely wired

- `self.workspace_store = SQLiteWorkspaceStore(...)` is constructed in
  `core.py` with a real on-disk path derived from `Config.IDENTITY_BASE_PATH`
  (or `Config.WORKSPACE_DB_PATH` if set), forwarded into `CognitivePipeline`,
  and used for real: `pipeline._persist_turn_session` refreshes the
  workspace snapshot via `workspace_store.get_snapshot(...)` on every turn,
  and `session_state.py`'s pre-existing (untouched by this phase)
  `_persist_workspace_session_state` genuinely calls
  `workspace_store.commit_transition(...)`, which increments `revision` by
  one per commit (`workspace_store.py:319-320`,
  `current.revision + 1`). I confirmed this dual-write path was previously
  unreachable in production because nothing ever passed a real
  `workspace_store` into `persist_session_state` -- Codex's fix is what
  makes that pre-existing Phase 02 machinery finally run. This is a real,
  causal fix, not cosmetic.
- `self.scheduler = BackgroundScheduler()` is forwarded and was already
  read by `pipeline._maybe_preempt_background` before this phase; Codex's
  contribution is only that `core.py` now actually constructs and passes a
  real instance instead of leaving `pipeline.scheduler` `None` (confirmed
  via `test_pipeline_composition_has_scheduler_and_session_store`, which I
  reran independently -- passes).

### 1.2 P0: six of eight "composed" services have zero call sites anywhere

`TemporalMemoryStore`, `DeterministicPlanVerifier`,
`DeterministicPlanExecutor`, `EpisodicSimulator`, `LearningGovernor` (the
one instantiated in `core.py` -- see 1.3), and `OfflineAdapterGate` /
`ProviderCapabilityNegotiator` are:

```
core.py:96   self.temporal_memory_store = TemporalMemoryStore(...)
core.py:100  self.plan_verifier = DeterministicPlanVerifier()
core.py:101  self.plan_executor = DeterministicPlanExecutor()
core.py:102  self.episodic_simulator = EpisodicSimulator()
core.py:103  self.learning_governor = LearningGovernor()
core.py:105  self.offline_adapter_gate = OfflineAdapterGate(...)
core.py:115  self.provider_capability_negotiator = ProviderCapabilityNegotiator()
```

...and then forwarded into `CognitivePipeline.__init__` (`core.py:173-179`),
which stores them as `self.<name> = <name>` (`pipeline.py:120-126`). I
grepped every `.py` file in `backend/app/` on the `codex/phase-07` tree for
each attribute name outside its own definition site: **zero matches**. No
turn ever calls `plan_verifier.verify(...)`, no turn ever calls
`plan_executor.execute(...)`, no turn ever calls
`episodic_simulator.simulate_plan(...)`, no code path ever consults
`offline_adapter_gate` or `provider_capability_negotiator`, and nothing
ever reads or writes `temporal_memory_store`.

**Reproduction (not just static reading):** I removed the instantiation of
all six from `core.py`'s `__init__` and the corresponding six keyword
arguments from the `CognitivePipeline(...)` call, leaving
`workspace_store`, `scheduler`, and `external_action_dispatcher` untouched,
then ran the full backend suite (`pytest -q`) in the `ai-friend-codex`
worktree:

```
tests 2337  failures 1  errors 0
tests.test_runtime_composition test_cognitive_service_composes_phase_services
```

Exactly one test out of 2,337 failed, and it is the shallow composition
test itself (`isinstance(...)` / `is` identity checks -- see Section 5).
The change was reverted (`git checkout -- app/cognitive/core.py`) after
verification and the tree is clean.

This means AC-P7-01's literal wording ("instantiated and wired") is
technically satisfied by attribute assignment, and the acceptance test
Codex wrote for it also only checks that wiring, so the criterion "passes"
by the letter of its own verification target. It does **not** satisfy
Invariant 1 ("No phase service shall remain an uncalled standalone
library") in any behavioral sense -- these six services are exactly as
uncalled today as they were before this phase; they are simply uncalled
*with a live reference held on `CognitiveService`* now, which is strictly
worse from a "why does this exist" standpoint than a standalone library,
because it now *looks* integrated to anyone reading `core.py` or
`CODEX_RESULT.md` without checking call sites.

I want to be precise about scope: **this is not a claim that Codex should
have implemented Sections 16/17/21/38's full plan-verification, episodic-
simulation, or offline-adapter-gating behavior inside this phase** -- that
would be a much larger scope than "compose the completed Phase 01-06
services," and per Phase 06's own review history
(`orchestration/PHASE_06/CLAUDE_REVIEW_OF_CODEX.md`) those modules had
their own P0s at the unit level that this phase's task list does not ask
Package A to fix. The finding is narrower and, I think, more actionable:
the composition root should either (a) call each service somewhere real in
the turn lifecycle (even a minimal, clearly-labeled integration point --
e.g. `plan_verifier.verify()` gating `plan_executor.execute()` for any
`ActionPlan` that carries a `PlanArtifact`, or `episodic_simulator` behind
an explicit Phase-06-parity flag), or (b) the task/ledger should say
plainly "constructed and available on `CognitiveService`, not yet consumed
by any turn" rather than the current framing ("owns and forwards... Phase
01-06... services" in `.agents/CONTEXT.md`) which reads as functional
integration to anyone who does not check call sites the way I did here.

### 1.3 P1: two independent `LearningGovernor` instances now exist in one process, unreconciled

`core.py:103` constructs `self.learning_governor = LearningGovernor()` and
forwards it to `pipeline.learning_governor` -- entirely unused, per 1.2.
Separately, Package B's `ReflectionService.__init__`
(`backend/app/cognitive/learning.py`, my own work this phase) constructs
its own `self.governor = LearningGovernor()`, which **is** genuinely used
(a real content-safety gate ahead of the persona-suggestion review queue).
`LearningGovernor` is stateful and append-only (`self._proposals: dict[str,
LearningProposal]` is its "durable, append-only audit trail," per its own
docstring) -- with two independent instances in one running
`CognitiveService`/`ReflectionService` pair, "the" audit trail an operator
would inspect depends on which instance they ask, and Section 21's "complete
audit trail" requirement is split across two objects that do not know about
each other. Neither package is wrong in isolation (Package B's task
explicitly asked for `LearningGovernor` wired into `ReflectionService`;
Package A's task asked for `LearningGovernor` composed into
`CognitiveService`), but this is a real integration gap neither side's
result document flags, and it will need reconciling before merge -- most
likely by having `CognitiveService` pass its `learning_governor` instance
into `ReflectionService`'s constructor instead of `ReflectionService`
building its own, once `core.py`'s instance is actually load-bearing for
something.

### 1.4 P2: `ExternalActionDispatcher` is threaded through three constructors and never consulted

`core.py` constructs `self.external_action_dispatcher =
ExternalActionDispatcher()` and passes it into **both** `ActionService`
(`core.py:148`) and `CognitivePipeline` (`core.py:180`).
`ActionService.__init__` stores it as `self.external_action_dispatcher`
(`action.py:518`). The `EXTERNAL_ACT` branch in `ActionService.execute`
(`action.py:1848-1853`), however, unconditionally fails closed without
ever reading `self.external_action_dispatcher`:

```python
elif plan.action_type == "EXTERNAL_ACT":
    logger.warning("[Action] External action blocked: %s", plan.goal)
    yield {"type": "error", "data": "External action blocked."}
    yield {"type": "done", "data": ""}
```

This is a reasonable, intentionally conservative implementation of Task
A3's "fail-closed safe execution for EXTERNAL_ACT" instruction, and I do
not think the fail-closed *behavior* is wrong -- an unauthorized dispatcher
should not run actions. But composing and passing a dispatcher object into
two constructors that then never reference it is dead plumbing: either the
dispatcher should gate the decision (e.g. "fail closed unless
`self.external_action_dispatcher.is_authorized(plan)`"), or it should not
be constructed and threaded through yet. As written, a future reader will
reasonably assume `self.external_action_dispatcher` on `ActionService`
does something.

### 1.5 Confirmed correct: `session_state.py` needed no change (Task A4)

I independently verified `git diff main..codex/phase-07 --
backend/app/state/session_state.py` is empty, and that
`_workspace_authoritative_enabled()` (`session_state.py:126-128`) already
reads `bool(getattr(Config, "WORKSPACE_AUTHORITATIVE", False))` -- exactly
the graceful-default behavior Task A4 asked for, and exactly what Package
B's `config.py` change (declaring `WORKSPACE_AUTHORITATIVE: bool = True`)
now activates on merge without requiring any code change here. Codex's
claim in `CODEX_RESULT.md` ("session_state.py already contained the
required... lookup; no change was needed") is accurate.

---

## 2. Causal Workspace Pass-Through (`brain_agent.py`) -- Task A2 / AC-P7-02

**Correct and genuinely tested.** `_process_chat_input_flow` now fetches
`workspace_snapshot = await self.cognitive_core.workspace_store.get_snapshot(user_id)`
for every non-subconscious turn (`brain_agent.py:838-841`) and forwards it
into `process_event` via a signature-introspecting `process_kwargs` dict
that degrades gracefully for an older double lacking a `workspace`
parameter (`brain_agent.py:860-877`) -- a defensive pattern consistent with
this codebase's existing `_decision_accepts_memory_activations` /
`_decision_accepts_global_controls` style in `pipeline.py`, so it is not an
invented idiom.

`core.py:process_event` (`process_event(self, raw_event, percept=None,
workspace=None, ...)`) forwards `workspace` straight into
`self.pipeline.execute(..., workspace=workspace)` (verified: `core.py:517`).
`pipeline.execute` threads it through `_persist_turn_session`, which
re-reads the current snapshot from the store when
`Config.WORKSPACE_AUTHORITATIVE` is on, and the (possibly refreshed)
`workspace` local is what actually reaches `_commit_action_intent` at Stage
6 (`pipeline.py:906`), which stamps `workspace_epoch=workspace.epoch`,
`workspace_revision=workspace.revision` onto the `ActionIntent` -- falling
back to `0, 0` only `if workspace is not None else 0`, i.e. only when no
workspace was supplied at all.

I checked whether a fresh session's first snapshot could itself read
`(epoch=0, revision=0)`, which would make the fix pass the letter of "not
`(0,0)`" trivially rather than for a substantive reason:
`SQLiteWorkspaceStore.get_snapshot`'s epoch-bootstrap path
(`workspace_store.py:226-241`) assigns `epoch = 1` when no epoch row exists
yet, not `0` -- so even a session's very first turn commits against `(1,
0)`, not `(0, 0)`, and every subsequent turn's `commit_transition` call
(from the session-state dual-write, confirmed real per Section 1.1)
advances `revision` further. This is a substantive fix, not a boundary
trick.

**Mutation test:** I removed the `workspace_snapshot` fetch in
`brain_agent.py` (replacing it with an unconditional `workspace_snapshot =
None`) and reran `tests/test_runtime_composition.py`: it failed
(`test_brain_agent_passes_workspace_to_process_event`, which asserts
`(passed_workspace.epoch, passed_workspace.revision) != (0, 0)`). Reverted
after verification.

`test_brain_agent_passes_workspace_to_process_event`
(`test_runtime_composition.py:72-149`) is a good test: it builds a real
`SQLiteWorkspaceStore` against a `tmp_path` database (not a mock), drives
the actual `BrainAgent._process_chat_input_flow` method (constructed via
`__new__` with hand-populated attributes, a legitimate pattern for this
class given its heavy `__init__`), captures the real `workspace` keyword
`process_event` receives, and then separately feeds that same object
through a real `CognitivePipeline._commit_action_intent` call to confirm
the committed `ActionIntent`'s `(workspace_epoch, workspace_revision)` is
non-zero end to end. This is exactly the kind of test that would have
caught the original bug (`workspace` silently defaulting to `None` all the
way to `ActionIntent`), not merely a shape check.

One scope note, not a defect: subconscious/proactive turns
(`is_subconscious=True`) do not fetch or pass a workspace at all
(`brain_agent.py:838-841`), and separately `generate_proactive_response`
(`core.py:551`) builds and executes an `ActionPlan` directly via
`self.action.execute(...)` rather than through `pipeline.execute`, so it
never reaches `_commit_action_intent` and never produces an `ActionIntent`
with a `(0, 0)` fallback to worry about. AC-P7-02's "0 turns commit against
the (0, 0) fallback" is satisfied for every turn that actually produces an
`ActionIntent`; I confirmed proactive turns are structurally exempt from
that mechanism rather than silently falling back to `(0, 0)` unnoticed.

---

## 3. Action Realization for WAIT (`decision.py`, `action.py`) -- Task A3 / AC-P7-05

**Correct.** `decision.py:857-858` adds `elif selected_kind == "WAIT":
action_type = "WAIT"` in `_plan_social_response`, positioned correctly
between the pre-existing `ASK`->`CLARIFY` mapping and the
`REAPPRAISE`/`REDIRECT_ATTENTION` mapping -- no branch shadowing, verified
by reading the full `if`/`elif` chain (`decision.py:844-863`).

I confirmed `WAIT` is a real, reachable `ActionCandidate.kind` produced by
`_build_candidates` (`decision.py:919`, `967`) under genuine scoring
conditions -- not a candidate kind invented only for this test -- and that
`CandidateSelector.filter_constraints`'s fallback explicitly special-cases
`kind == "WAIT"` as the safe floor when every other candidate is
constraint-rejected (`decision.py:1063`,
`action_candidate.py:30`,`125`). So `test_wait_candidate_maps_to_silent_action`
forcing `_select_action_candidate` to return a `WAIT` selection is a
faithful stand-in for a real scoring outcome, not a fabricated code path.

`action.py:1848-1849` adds `elif plan.action_type == "WAIT": async for out
in self._execute_wait(plan): yield out`, correctly ordered in the dispatch
chain before the `EXTERNAL_ACT` and catch-all branches, and
`_execute_wait` (`action.py:1856-1859`) is exactly the two-line async
generator the task asked for:

```python
async def _execute_wait(self, plan: ActionPlan) -> AsyncGenerator[dict[str, Any], None]:
    del plan
    yield {"type": "done", "data": ""}
```

**Mutation test:** I removed the `elif selected_kind == "WAIT":` branch
from `decision.py` and reran `tests/test_runtime_composition.py`: it failed
(`test_wait_candidate_maps_to_silent_action`). Reverted after verification.

`test_wait_candidate_maps_to_silent_action`
(`test_runtime_composition.py:152-189`) asserts `chunks == [{"type":
"done", "data": ""}]` -- an exact-equality check on the full chunk list,
not merely "no content chunk present," which is the strongest form of this
assertion and matches AC-P7-05's "100% silence compliance" framing well.

`test_external_action_is_fail_closed`
(`test_runtime_composition.py:192-201`) similarly asserts the exact
two-chunk fail-closed sequence for `EXTERNAL_ACT`. Combined with the
catch-all `else` branch (pre-existing, unchanged) yielding `{"type":
"error", ...}` / `{"type": "done", ...}` for any unrecognized
`action_type`, Task A3's "never unhandled exception" requirement is met for
both named cases.

---

## 4. Session State Authority (`session_state.py`)

Covered in Section 1.5 above: no change was made, none was needed, and I
independently confirmed why. No further findings here.

---

## 5. Test Coverage (`test_runtime_composition.py`) -- Task A5

The file has four tests, matching the four items Task A5 lists:

1. `test_cognitive_service_composes_phase_services` -- **shallow by
   construction.** It iterates a name->type map and asserts
   `isinstance(getattr(cognitive_service, attribute), expected_type)` plus
   `getattr(cognitive_service.pipeline, attribute) is
   getattr(cognitive_service, attribute)` for all ten services. This proves
   "the right class was instantiated and the same object reached the
   pipeline" -- a real and worthwhile check, and I do not think it should
   be removed -- but it structurally cannot catch "this service is
   instantiated and then never called," which is exactly the P0 in Section
   1.2. A test asking "does composing `X` change any observable behavior
   of a turn" for the six inert services does not exist anywhere in this
   suite, because there is no such behavior yet to test.
2. `test_pipeline_composition_has_scheduler_and_session_store` -- solid,
   narrow, and passes independently.
3. `test_brain_agent_passes_workspace_to_process_event` -- strong, as
   detailed in Section 2; drives real objects rather than mocking the
   thing under test.
4. `test_wait_candidate_maps_to_silent_action` and
   `test_external_action_is_fail_closed` -- strong, as detailed in Section
   3.

I would not block merge on test coverage alone -- the four tests that
exist are well-constructed for what they check -- but the suite's title
("Regression coverage for the Phase 07 production composition root") and
`CODEX_RESULT.md`'s framing invite a reader to believe composition itself
is now safety-net-covered, when only two of the eight named services
actually have any behavior a regression could break.

---

## 6. Quality Gates (AC-P7-09) -- independently reproduced

Run from `/Users/aniketsaha/Projects/ai-friend-codex/backend` against the
shared `/Users/aniketsaha/Projects/AI_friend/.venv`:

- **Focused bar** (`test_runtime_composition.py`, `test_causal_slice.py`,
  `test_action_selection.py`): `119 passed, 0 failed, 0 errors` -- matches
  `CODEX_RESULT.md`'s claimed number exactly.
- **Full backend suite** (`pytest -q`, no path filter): `2337 passed, 0
  failed, 0 errors, 0 skipped` -- matches `CODEX_RESULT.md`'s claimed
  number exactly (their reported "8 NATS setup `PermissionError`" issue is
  described as sandbox-specific and did not reproduce in this session's
  environment).
- `ruff check .`: **All checks passed** (reproduced independently).
- `radon cc app/ -s -n D`: **no output** -- zero D/E/F-complexity functions
  (reproduced independently).
- **7-bit ASCII**: I ran an independent byte-level scan of every line added
  in the diff (`git diff main..codex/phase-07 -- <each changed file>`,
  filtered to `+`-prefixed lines, encoded as strict ASCII) across
  `brain_agent.py`, `action.py`, `core.py`, `decision.py`, `pipeline.py`,
  `test_runtime_composition.py`, `CODEX_RESULT.md`, and the
  `.agents/CONTEXT.md` entry: **zero non-ASCII bytes found**. This confirms
  Codex's own claim rather than merely trusting it.

`pre_test_causal_slice.py::test_pipeline_action_intent_defaults_workspace_when_absent`
(pre-existing, untouched) still asserts the `(0, 0)` fallback is preserved
for a caller that genuinely supplies no workspace -- confirming the
workspace fix is additive and does not remove the safe default for callers
that predate it.

---

## 7. Documentation / Ledger Accuracy

`orchestration/PHASE_07/CODEX_RESULT.md` and the `.agents/CONTEXT.md` entry
both describe the composition as "`CognitiveService` now owns and forwards
the Phase 01-06 workspace, temporal memory, scheduler, planning, simulation,
learning, adapter, provider, and external-action services" without
distinguishing the two that do real work from the six (arguably seven,
counting the dispatcher) that do not yet. This is not inaccurate as
literally written -- the services genuinely are owned and forwarded -- but
it is the kind of framing this repository's own conventions explicitly
guard against (`CLAUDE.md`'s "NOT done" discipline, and this project's own
ledger culture of stating what was measured/verified versus what was only
scaffolded). I recommend both documents gain an explicit line to the effect
of: "of the ten composed attributes, `workspace_store` and `scheduler` are
consumed by a real turn path; `temporal_memory_store`, `plan_verifier`,
`plan_executor`, `episodic_simulator`, `learning_governor`,
`offline_adapter_gate`, `provider_capability_negotiator`, and
`external_action_dispatcher` are constructed and referenced but not yet
called by any code path -- composing their actual behavior into a turn is
follow-up work."

---

## 8. Cross-Package Integration Note (not a defect in either package alone)

Package B's `memories_to_activations` (`memory_activation.py`) is ready to
propagate a real `contradiction_state`/`outage_flag` from a linked belief
record on a surfaced-memory dict (Task B2, this phase). Package A's
`TemporalMemoryStore` is now instantiated in `core.py` (Section 1.2) but,
being one of the six unused services, never actually produces belief
records that reach `memories_to_activations` in production. AC-P7-06 (the
memory truth bridge) and this composition therefore do not yet meet at
integration: the bridge exists on the consuming side, and the producing
side exists as an object with no callers. This will need closing in the
integration branch, not necessarily by either individual package alone.

---

## 9. Summary of Findings by Severity

**P0 (blocker for the composition claim specifically, not for the three named bugs):**
1. Six of eight (arguably seven of nine, counting the dispatcher) composed
   Phase 01-06 services -- `TemporalMemoryStore`,
   `DeterministicPlanVerifier`, `DeterministicPlanExecutor`,
   `EpisodicSimulator`, `LearningGovernor` (the `core.py` instance),
   `OfflineAdapterGate`, `ProviderCapabilityNegotiator` -- are instantiated
   and forwarded but have zero call sites anywhere in the codebase.
   Demonstrated by removing all six from the runtime entirely and
   confirming exactly one test (the shallow composition test) notices,
   out of 2,337. This is the specific defect AC-P7-01 and Invariant 1 were
   written to close, still present one layer beneath the constructor
   wiring.

**P1 (must reconcile before merge):**
2. Two independent, unreconciled `LearningGovernor` instances now exist in
   one process (Package A's inert `core.py` instance; Package B's actually-
   used `ReflectionService.governor`), splitting Section 21's "complete
   audit trail" requirement across two objects.
3. `ExternalActionDispatcher` is constructed and threaded into both
   `ActionService` and `CognitivePipeline` constructors but never read;
   the `EXTERNAL_ACT` fail-closed branch does not consult it at all.

**P2 (documentation / coverage, not correctness):**
4. `CODEX_RESULT.md` / `.agents/CONTEXT.md` frame the composition in terms
   that read as full functional integration for all named services; should
   explicitly disclose which are consumed versus merely constructed.
5. `test_cognitive_service_composes_phase_services` cannot and does not
   catch "instantiated but never called" by its own design (isinstance/is
   checks only) -- worth keeping, but should not be read as behavioral
   regression coverage for the six inert services.
6. AC-P7-06 (memory truth bridge) has a producer/consumer gap across
   packages: `TemporalMemoryStore` exists but nothing yet feeds a real
   belief record into `memories_to_activations`.

**Confirmed correct, no changes requested:**
7. Causal workspace pass-through (`brain_agent.py`, `core.py`,
   `pipeline.py`) -- genuinely wired, causally verified (epoch bootstraps
   to 1, revision advances via the pre-existing dual-write path now
   finally reachable), and covered by a test that fails under mutation.
8. WAIT action realization (`decision.py`, `action.py`) -- correctly
   mapped from a real, reachable candidate kind, cleanly dispatched, and
   covered by an exact-equality test that fails under mutation.
9. `EXTERNAL_ACT` and unknown-action-type fail-closed handling -- correct
   behavior (modulo the unused-dispatcher note in P1-3 above).
10. `session_state.py` -- correctly required no change; independently
    verified the pre-existing graceful `Config.WORKSPACE_AUTHORITATIVE`
    lookup.
11. Quality gates -- ruff, radon, ASCII, and both stated test counts (119
    focused / 2,337 full) all independently reproduced exactly as claimed.

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
