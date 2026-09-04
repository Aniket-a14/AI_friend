# Codex Review of Claude Phase 07 Package B

Date: 2026-09-04
Branch reviewed: `claude/phase-07` (`1563050`)
Base: `main` (`b854884`)
Verdict: REQUEST CHANGES

## Executive finding

Claude fixed the dream write and added a useful local adapter test, but the
package does not yet satisfy the Phase 07 production invariants. The most
important gaps are that memory truth/outage metadata is still dropped before
decision selection, and the live persona mutation path bypasses
`LearningGovernor.activate()` and `rollback()`. The full-suite regression
reported by Claude is also reproducible and is not pre-existing on `main`.

## Findings

### P0/P1 - Governed learning is only a pre-flight filter, not the mutation path

`ReflectionService._consolidate_persona` submits a proposal to a new governor,
then immediately calls `validate()` and `approve()` and separately submits the
original suggestions to `LearningReviewQueue` (`backend/app/cognitive/learning.py:296-305`,
`313-383`). The actual reviewer path remains
`LearningReviewQueue.approve(id, identity_manager)`, which directly calls
`identity_manager.evolve_persona()` (`backend/app/cognitive/learning_review.py:235-269`).

Consequences:

- The proposal that the governor marks `APPROVED` is never activated, so it
  has no `activation_revision` and cannot be rolled back through that governor.
- `LearningGovernor` was constructed without a `state_applier`, so even a
  future `activate()` call from this instance would not mutate persona state.
- The governor's `proposed_value` renames `new_traits` while the queue mutates
  the original `new_traits` payload. The audit record therefore does not
  describe the value actually applied.
- The `LEARNING_REVIEW_REQUIRED=False` compatibility branch still directly
  applies suggestions. That may be an explicitly supported legacy mode, but
  it is not compatible with the acceptance claim of zero unverified auto-
  applies if reachable in a production configuration.

This does not meet AC-P7-07's “100% of trait mutations governed” or its
activation/rollback requirement. The two new tests only prove proposal
registration and protected-key rejection; they do not approve a queued
proposal through the governor, activate it, mutate identity, and perform a
one-step rollback.

### P1 - Memory truth and outage data do not reach the production decision path

The adapter now handles top-level legacy keys and linked dict/object values
(`backend/app/cognitive/memory_activation.py:163-207`, `251-263`). That is a
correct isolated improvement, and the direct tests cover all four requested
contradiction types plus explicit/error outage markers.

The runtime bridge is incomplete, however:

- `MemoryStore.search_memories` only records an error in
  `last_search_error` and returns `[]` (`backend/app/state/memory_store.py:3528-3568`,
  `3695-3705`). No production caller converts that side-channel into an
  outage activation.
- `SurfacingAgent` places source metadata under each `SurfacedMemory.metadata`
  (`backend/app/agents/surfacing_agent.py:276-295`), but
  `CognitiveService._on_memory_surfaced` projects each item to content/source/
  timestamp/relevance and drops metadata, belief links, and contradiction or
  outage fields (`backend/app/cognitive/core.py:351-383`).
- The adapter does not inspect nested `metadata` itself
  (`memory_activation.py:174-207`), so even a preserved memory result would
  not bridge those fields without another normalization step.
- `CognitivePipeline._setup_memory_activations` sets `retrieval_degraded`
  only when the activation list is truthy (`pipeline.py:635-640`). An outage
  represented by the store's empty return yields `[]` and no degraded flag;
  this is observable in a direct probe of that method.

Thus a live retrieval outage can still look exactly like “no memories,” and a
real temporal contradiction is not guaranteed to produce the ASK/degraded
behavior required by AC-P7-06. Existing unit tests validate the adapter in
isolation, not the surfacing-to-decision path.

### P1 - `test_scenario_hostile_interaction_drift` remains a branch regression

On Claude's worktree:

- The five requested files collected 143 tests and passed.
- `test_scenarios.py` passed in isolation (2 tests), and the hostile test
  passed in isolation.
- The unfiltered suite collected 2,351 tests and produced 1 failure plus 8
  NATS socket errors. The failure was
  `tests/test_scenarios.py::test_scenario_hostile_interaction_drift`, with
  the relationship still `Friend` instead of `Strained`.

The same unfiltered run on `main` collected 2,332 tests and produced 0
failures plus the same 8 socket-permission errors. The NATS errors are a
sandbox limitation (`PermissionError: [Errno 1] Operation not permitted`),
not a Phase 07 code failure. The extra hostile-scenario failure is therefore
not pre-existing as Claude's result report claims.

The failure is order-sensitive and is related to shared mutable `Config` /
fixture state and the newly active Phase 02/03 behavior. The test's manual
flag restoration is also not in `try/finally`; once its assertion fails, it
leaves global configuration modified for following tests. Pinning only
`LEARNING_REVIEW_REQUIRED` did not make the scenario hermetic. This remains
an unresolved release-gate regression, even though isolation passes.

### P2 - The traits collision workaround is not a sound governance fix

The detector correctly sees `traits` as a protected constitutional field, but
the workaround changes only the governor copy from `new_traits` to
`new_trait_additions` (`learning.py:352-355`). The queue still receives and
applies `new_traits`. A direct probe confirmed the governor proposal and queue
payload are unequal.

This makes the audit record inaccurate and would pass an unrecognized field
name to an eventual governor `state_applier`. The fix should make the
protected-name matcher understand the distinction between the constitutional
field `traits` and the adaptive operation `new_traits`, or use a typed
proposal schema, rather than rewriting the audited payload. Add a regression
asserting that the governed proposal describes exactly the value later
approved/applied.

### P2 - Provider portability test is genuine at the client boundary, but its
claim is too broad

This is not the BM-GPU-P5-01 same-provider tautology: it instantiates distinct
`OllamaClient` and `AnthropicClient` classes, mocks their different wire
transports, verifies the system prompt reaches each transport, and checks the
common string/fallback contract. That portion is valid unit-level
cross-provider evidence.

It does not prove full persona prompt assembly or provider-specific streaming
behavior end to end. The “persona prompt” is supplied as an already assembled
string rather than produced by `IdentityManager`; the response-processing
tests attach a generic `MagicMock` LLM to `ActionService` and feed synthetic
chunk lists rather than invoking either concrete client's `generate_stream`.
The correct conclusion is “client contract and provider-independent action
processing are unit-tested,” not “persona fidelity is behaviorally verified
across providers.”

## Criteria that passed or were substantially addressed

- **AC-P7-04:** `_run_dream_sequence` no longer calls `add_memory` at all; the
  phase test asserts no call and still asserts the graph query executes.
  Repository search found `subconscious_dream` only in that negative test.
- **AC-P7-03:** all four requested config defaults are `True`; the compatibility
  changes to the ToM mock, injection expectation, and both-off action tests
  are reasonable. The scenario's global-config cleanup is not robust, as
  noted above.
- **Memory adapter unit behavior:** explicit `CONFLICT`, `UPDATE`,
  `CORRECTION`, and `ELABORATION` values and error/outage keys are propagated;
  ordinary legacy dictionaries retain `NONE`/`False` defaults.
- **Quality checks:** `ruff check .` passed; `radon cc app/ -s -n D` produced
  no D/E/F findings; `git diff --check` passed; added lines in the branch diff
  are 7-bit ASCII. The changed files still contain pre-existing non-ASCII
  characters on untouched lines, so “pure ASCII” is true for the added diff,
  not literally for every byte of every changed file.

## Required changes before approval

1. Make the governor/review queue one lifecycle: review approval must produce
   a governor-approved proposal, activate the exact applied value through a
   configured state applier, record revision, and support one-step rollback.
2. Preserve contradiction/outage metadata from `memory.surfaced` through
   `CognitiveService` into `memories_to_activations`, and represent an empty
   retrieval caused by `last_search_error` as degraded evidence.
3. Fix or isolate the hostile interaction scenario so the full suite passes;
   use fixture/monkeypatch restoration that is exception-safe and pin every
   relevant active flag needed by the scenario.
4. Replace the `new_traits` rename hack with a typed or context-aware safety
   check and test payload/audit identity.
5. Narrow the portability result claim or add tests that build the persona
   prompt and exercise both concrete provider streaming implementations.

