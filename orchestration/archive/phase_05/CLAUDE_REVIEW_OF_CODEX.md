# Reciprocal Peer Review: Codex Phase 05 Package A

Reviewer: Claude (Package B owner, this phase)
Subject branch: `codex/phase-05` at commit `3a4d0b5`
Subject worktree: `/Users/aniketsaha/Projects/ai-friend-codex`
Reviewed against: `orchestration/PHASE_05/CODEX_TASK.md`, `PLAN.md`,
`ACCEPTANCE_CRITERIA.md`, and `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`
(SS23, SS27, SS28, SS29, SS38)

Files in scope:
- `backend/app/cognitive/speech_intent.py`
- `backend/app/voice/__init__.py`
- `backend/app/voice/compiler.py`
- `backend/app/cognitive/external_action.py`
- `backend/tests/test_voice_external_action.py`

---

## Verdict

**Do not merge as-is.** One finding (P0-1) is a real crash on realistic
production data that directly contradicts a stated Objective ("backward-
compatible bidirectional conversion") and an Acceptance Criterion (AC-P5-06).
The rest of the implementation is well-structured, matches the specified
schemas field-for-field, and its authorization-gating invariant -- the
single most safety-critical piece of this package -- is genuinely solid and
well-tested. Fixing P0-1 and the P1 items below should be quick; nothing here
requires a redesign.

---

## How this review was conducted

- Read every target file in full against `CODEX_TASK.md`'s per-file field
  lists and `PLAN.md`'s shared-contract code blocks.
- Ran the target test suite, the full backend suite, `ruff check .`, and
  `radon cc app/ -s -n D` from `/Users/aniketsaha/Projects/ai-friend-codex/backend`
  against the shared venv (`/Users/aniketsaha/Projects/AI_friend/.venv` --
  this worktree, like mine, has no `.venv` of its own; both are git
  worktrees of the same repository and share the interpreter).
- For every claim below that could be checked empirically rather than by
  inspection, I ran the actual code (including the real `cognitive_rust`
  Rust extension, not a mock) rather than reasoning from the source alone.
- Performed targeted mutation testing on the invariants this review was
  specifically asked to evaluate: the authorization gate, the
  exception/simulation dispatch branches, and the telemetry completeness
  claim. Every mutation was reverted and the working tree diffed back to
  clean before moving on.

### Automated verification results

```
pytest tests/test_voice_external_action.py -q --junit-xml=...
```
**13 passed, 0 failed, 0 errors** (verified via JUnit XML, per this repo's
own documented guidance that the terminal summary line is unreliable).

```
pytest -q (full backend suite, codex/phase-05 checked out)
```
**2,102 passed, 0 failed, 0 errors.** (Package B's files are absent from
this branch, which is why the count differs from the 2,149 on
`claude/phase-05`; expected, not a regression.)

```
ruff check .
```
**All checks passed.**

```
radon cc app/ -s -n D
```
**No output** -- zero functions at rank D or higher. A full, ungated
listing of the five new/changed modules shows every unit at rank A or B
(the worst is `ElevenLabsVoiceCompiler.compile` at B(7) and its class at
B(8)); nothing at C or worse.

```
ASCII check
```
All five files decode cleanly under strict `ascii` -- confirmed independently
of the suite's own `test_phase_package_files_are_strict_7_bit_ascii`.

`git diff --stat 09f5d42 HEAD -- backend` confirms the branch touches
exactly the five owned files and nothing else -- no scope creep into shared
or Package-B-owned modules.

---

## P0 (blocker)

### P0-1: `legacy_expression_to_speech_intent` crashes on real `AgentVoiceModulation` payloads, not just contrived ones

**Location:** `app/voice/compiler.py:211-236` (`legacy_expression_to_speech_intent`),
interacting with `SpeechDelivery.relative_energy`'s `ge=0.5` bound
(`app/cognitive/speech_intent.py:48`).

**What's wrong:** The function builds `SpeechDelivery.relative_energy` from
`first_frame.get("volume", 1.0)`, where `first_frame = frames[0]` -- the
*first* trajectory frame. But the real trajectory generator
(`cognitive_rust::generate_apra_trajectory`, `crates/cognitive-rust/src/lib.rs`
around line 651) deliberately fades volume in from zero over the first 150ms
for natural-sounding breathing:

```rust
let vol_envelope = if t_ms < 150 { t_ms as f64 / 150.0 } else { ... };
let step_volume = ((0.40 + 0.60 * dominance + ...) * vol_envelope).clamp(0.10, 1.00);
```

At `t_ms = 0`, `vol_envelope` is exactly `0.0`, so `step_volume` collapses to
its floor, `0.10`, on essentially every real trajectory regardless of mood.
`SpeechDelivery.relative_energy` requires `ge=0.5`. `0.10 < 0.5`, so
constructing the intent raises `pydantic.ValidationError` and the migration
function never returns.

**Verified against the actual production code path**, not a synthetic
example:

```
$ python -c "
import cognitive_rust
from app.contracts import AgentVoiceModulation, ProsodyFrame
from app.voice.compiler import legacy_expression_to_speech_intent

traj = cognitive_rust.generate_apra_trajectory(0.1, 0.5, 0.5, 0.0, 0.2, 0.1, 0.0)
print('first frame (t, rate, pitch, volume):', traj[0])
frames = [ProsodyFrame(time_offset_ms=t, rate=r, pitch=p, volume=v) for t,r,p,v in traj]
data = AgentVoiceModulation(trajectory=frames).model_dump()
data['turn_id'] = 't1'; data['semantic_text'] = 'hello there'
legacy_expression_to_speech_intent(data)
"
first frame (t, rate, pitch, volume): (0, 0.96, 1.06, 0.1)
RAISED ValidationError 1 validation error for SpeechDelivery
relative_energy
  Input should be greater than or equal to 0.5 [type=greater_than_equal, input_value=0.1, input_type=float]
```

This is not an edge case that requires an unusual affect state to trigger --
it fires for *any* PAD input, because the fade-in envelope is unconditional
and frame 0 always lands in it.

**Why the existing test didn't catch it:**
`test_legacy_modulation_migrates_bidirectionally_without_losing_prosody`
(`test_voice_external_action.py:140-161`) hand-writes a single legacy frame
with `"volume": 1.1` -- comfortably inside `SpeechDelivery`'s range. The test
fixture was never grounded in what the real wire producer
(`surfacing_agent.py` -> `cognitive_rust.generate_apra_trajectory` ->
`AgentVoiceModulation`) actually emits, so the one code path this function
exists to handle -- a genuine mesh payload -- was never exercised.

**Impact:** Objective #4 ("Implement backward-compatible bidirectional
conversion with legacy expression wire") and AC-P5-06 ("Legacy expression
wire converts bi-directionally... Backward compatibility verified") are not
actually satisfied for real data. Any caller that feeds a live
`AgentVoiceModulation` message into this migration path (the stated purpose
of having it) will crash.

**Suggested fix:** Don't trust a single frame's instantaneous, envelope-
biased value as the intent-level "delivery" summary. Either (a) sample a
frame from the steady-state middle of the trajectory instead of index 0, (b)
take a duration-weighted average of `rate`/`pitch`/`volume` across all
frames, or (c) clamp the derived values into `SpeechDelivery`'s valid range
before construction (least preferred -- it silently distorts the signal
rather than fixing the sampling). Whichever is chosen, add a test built from
an actual `cognitive_rust.generate_apra_trajectory(...)` call (as above),
not a hand-picked frame, so this class of bug cannot reappear unnoticed.

---

## P1 (must fix)

### P1-1: IntentLossRecord telemetry is silently incomplete for two whole SpeechIntent dimensions, on both compilers, always

**Location:** `app/voice/compiler.py` -- neither `ElevenLabsVoiceCompiler.compile`
(lines 114-146) nor `GPTSoVITSVoiceCompiler.compile` (lines 162-183)
reference `intent.epistemics` or `intent.relationship` anywhere:

```
$ grep -n "epistemics\|relationship\|\.stance\|\.register\|\.hedge\|\.confidence\|\.uncertainty\|\.familiarity" app/voice/compiler.py
(no output)
```

Section 23 explicitly lists "evidence/uncertainty ... relationship register"
as brain-owned dimensions that "the voice adapter declares supported
dimensions [for], compiles lossily ... and reports dropped/substituted
intent" -- i.e., these are in scope for compiler telemetry, not just
`affect`/`delivery`/`timeline`. AC-P5-05's target metric is explicit: "100%
loss/substitution captured." For `epistemics` and `relationship`, the actual
capture rate is 0%, for every intent, on both compilers.

A second, narrower instance of the same root cause: `GPTSoVITSVoiceCompiler`
declares `capabilities.supports_affect_modulation=False` (line 158), which
is an explicit claim that it cannot honor `intent.affect`'s PAD values -- yet
`compile()` never reports any of `affect.valence`/`arousal`/`dominance`/
`intensity` as dropped. Verified directly:

```
$ python -c "
from app.cognitive.speech_intent import build_speech_intent, SpeechAffect
from app.voice.compiler import GPTSoVITSVoiceCompiler
intent = build_speech_intent(turn_id='t1', semantic_text='...',
    affect=SpeechAffect(valence=0.95, arousal=0.95, dominance=-0.8, intensity=1.0))
payload, loss = GPTSoVITSVoiceCompiler().compile(intent)
print(payload.synthesis_parameters, loss.dropped_dimensions, loss.fidelity_score)
"
{'rate': 1.0, 'pitch': 1.0, 'energy': 1.0, 'urgency': 0.0} [] 1.0
```

An intent carrying near-maximal, oppositely-signed valence and arousal
compiles to a **perfect fidelity_score of 1.0** with **zero dropped
dimensions** on a compiler that has already declared, in its own
`VoiceCapability`, that it cannot modulate affect at all.

**Root cause:** `VoiceCapability` is purely decorative. Neither `compile()`
method ever reads `self.capabilities` to decide what to drop -- all the
drop/keep logic is hand-written per field, independently of the declared
capability flags. The two can (and here, do) drift apart silently. If
someone edits a capability flag later without touching the matching
`compile()` branch (or vice versa), nothing enforces that they stay
consistent.

**Why the tests didn't catch it:** `_full_intent()` (the shared test
fixture, line 34) never sets non-default `epistemics` or `relationship`
values, so no assertion could have noticed their disappearance even if one
had been written.

**Suggested fix:** Either (a) drive `dropped_dimensions` computation from
`self.capabilities` programmatically (a field is dropped iff its
corresponding capability flag is `False` and the intent's value differs from
default), which also closes the drift risk, or (b) explicitly enumerate
`epistemics`/`relationship` handling in both compilers -- even if the
correct behavior is "always drop, no provider we've integrated can render
these," that must show up in `dropped_dimensions`, not silently vanish.

### P1-2: Two dispatch() branches are entirely untested, one of them safety-relevant

**Location:** `app/cognitive/external_action.py:73-105` (`dispatch`).

Mutation-tested both branches by editing the working file, running the
suite, then reverting:

1. Flipping the unregistered-tool "simulate" branch's status from
   `"COMPLETED"` to `"FAILED"` (line 90): **13/13 tests still pass.**
2. Removing the `try/except` around `executor(intent)` entirely (lines
   93-101), so an executor's exception would propagate uncaught instead of
   being caught and turned into a `FAILED` result: **13/13 tests still
   pass.**

Neither mutation was observed by any assertion in the suite. (2) is the more
important gap: a real actuator/tool adapter is exactly the code most likely
to raise (network failures, hardware faults, timeouts) at exactly the moment
this protocol exists to handle safely. If this guard were ever weakened or
removed by a future refactor, nothing here would notice, and an executor
exception would propagate uncaught into whatever calls `dispatch()`
(presumably `BrainAgent`/`CognitivePipeline`) instead of resolving to a
terminal `FAILED` outcome as designed.

**Suggested fix:** Add a test that registers an executor which raises, and
assert `dispatch()` returns `status: "FAILED"` with the exception message in
`error` (not an uncaught exception); add a second test for the no-executor
path asserting `simulated: True` and `status: "COMPLETED"` are actually
produced, not just assumed.

### P1-3: A simulated (never-executed) action is indistinguishable from a real one in the terminal OutcomeRecord

**Location:** `app/cognitive/external_action.py:84-92` (simulate branch) and
`:127-144` (`create_action_outcome`).

When `tool_or_actuator` has no registered executor, `dispatch()` returns
`{"executed": False, "simulated": True, "status": "COMPLETED", ...}`. But
`create_action_outcome` only reads `status`, `message`, and `error` off that
dict -- `simulated` is read nowhere and appears nowhere in the resulting
`OutcomeRecord`. The terminal record for an action that was never actually
performed is, by every field an `OutcomeRecord` exposes, identical in shape
to one for an action a real adapter genuinely completed: `status="COMPLETED"`,
`error=None`, `actual_delivered_text=None` either way (no `message` key is
even set on the simulate branch).

`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` SS26 lists "outcome-linked learning"
as core brain IP -- exactly the mechanism this feeds. As written, an agent
in a deployment where an actuator adapter simply hasn't been registered yet
would learn "this action reliably succeeds," because every simulated
dispatch is recorded as an indistinguishable success.

Note: `OutcomeRecord` itself (`app/cognitive/action_intent.py`) is a
pre-existing, unowned-by-either-package contract, so adding a dedicated
field to it may be out of this package's scope. A lower-cost fix that stays
within Package A's owned files: have the simulate branch set a `message`
(e.g. `"simulated: no adapter registered for <tool>"`), which
`create_action_outcome` already forwards into `actual_delivered_text` --
giving downstream consumers at least an inspectable signal without touching
the shared schema.

### P1-4: `timeout_s` is validated but never enforced

**Location:** `app/cognitive/external_action.py:45` (field declared,
`gt=0.0`) vs. `:73-105` (`dispatch`, no timeout logic anywhere).

`ExternalActionIntent.timeout_s` is part of the spec and is given a sensible
field constraint, but `dispatch()` calls `executor(intent)` synchronously
with no deadline of any kind. A hung or slow executor blocks the calling
turn indefinitely rather than failing at the caller's declared
`timeout_s`. For a protocol whose stated purpose is governing calls to
external tools/actuators -- exactly the kind of dependency expected to hang
occasionally -- an unenforced timeout field is worse than no field at all,
because it invites a caller to trust a guarantee that doesn't exist.

**Suggested fix:** Wrap the executor call with a wall-clock deadline (e.g.
`concurrent.futures` with a timeout, or document clearly that
`ExternalActionDispatcher` is expected to be driven from an async context
that applies `asyncio.wait_for(..., timeout=intent.timeout_s)` around
`dispatch()` itself, if synchronous dispatch is the deliberate design). Either
is fine; leaving `timeout_s` silently decorative is not.

---

## P2 (improvement)

### P2-1: No test proves the authorization gate is correctly *scoped*, only that it fires when it should

Mutating `authorization_required` to the constant `True` (i.e., every
action, including `LOW`/`REVERSIBLE` ones, would wrongly require a token)
passes the full local suite (13/13) unnoticed. The three existing
parametrized cases all test the "should block" side of the gate; nothing
tests the "should *not* block" side (a `LOW`-risk, `REVERSIBLE` action with
no token dispatching successfully). Given how safety-critical this gate is,
a positive/negative pair is cheap insurance against an over-broad regression
that would otherwise look like "extra caution" rather than a bug.

### P2-2: `SpeechRelationship.register` triggers a `UserWarning` on every import

```
UserWarning: Field name "register" in "SpeechRelationship" shadows an
attribute in parent "BaseModel"
```

This comes from Pydantic's model metaclass colliding with
`abc.ABCMeta.register`, and the field name itself is prescribed by the
architecture (`PLAN.md`'s shared contract), so this isn't something Codex
chose freely. Still, it fires on every import of `speech_intent.py` and
every test run that touches it, and is worth either suppressing explicitly
(with a comment explaining why) or at minimum acknowledging in the module
docstring so a future reader doesn't mistake it for a real defect.

### P2-3: `_gpt_sovits_tags` can silently no-op on overlapping/duplicate emphasis spans

`app/voice/compiler.py:186-200`. `speech.replace(marker.text_span, emphasized, 1)`
is called once per `EMPHASIS` marker. If two markers share an identical or
overlapping `text_span` (plausible: the same word emphasized differently, or
one span a substring of another), the second `.replace()` call can find
nothing left to replace (the text is already wrapped in the first marker's
`<emphasis>` tag) and silently no-ops. Because this isn't caller-visible and
isn't recorded in `IntentLossRecord`, an emphasis instruction can vanish
without any telemetry trail. Not exercised by the current tests (only a
single `EMPHASIS` marker is ever used in the shared fixture).

### P2-4: `ExternalActionDispatcher.create_action_outcome` is a redundant wrapper

`app/cognitive/external_action.py:107-114` is an instance method whose
entire body is `return create_action_outcome(intent, result, elapsed_ms)` --
a call to the module-level function of the identical name defined just
below it. Harmless (Python resolves the bare name to the module-level
function, not infinite recursion), but confusing to read at a glance, and
duplicates a public entry point for no behavioral reason. Consider keeping
only one of the two (the free function is sufficient; the class already
delegates dispatch-related work to itself elsewhere via free-function
helpers like `_has_authorization`).

### P2-5: `preconditions`/`expected_effects` are schema-only, never inspected

`PLAN.md`'s package description calls for "pre-flight checks" (plural) in
`ExternalActionDispatcher`; the only pre-flight check actually implemented
is the authorization-token gate plus a blank-`tool_or_actuator` check.
`ExternalActionIntent.preconditions` and `.expected_effects` are captured in
the schema but never read anywhere. This may be intentional (precondition
verification requires a semantics this protocol deliberately doesn't own),
but if so it's worth a one-line comment saying that explicitly, since the
current silence reads as an oversight rather than a decision.

---

## What's solid (worth stating explicitly in a review, not just what's wrong)

- **Schema completeness (AC-P5-03):** every field in Section 23's
  `SpeechIntent` block -- `SpeechAffect`, `SpeechEpistemics`,
  `SpeechRelationship`, `SpeechDelivery`, `TimelineMarkerKind`,
  `SpeechTimelineMarker`, `SpeechTurnPolicy`, and `SpeechIntent` itself --
  matches `PLAN.md`'s shared contract exactly, field name for field name,
  default for default. `build_speech_intent` correctly stamps a fresh
  `intent_id` while taking `turn_id` as a caller-supplied correlation key,
  consistent with the existing `build_action_intent` convention in
  `action_intent.py`.
- **VoiceCompilerProtocol conformance (AC-P5-04):** both compilers are
  structurally `isinstance`-compatible with the `runtime_checkable` protocol,
  and both produce sensible provider-shaped payloads (ElevenLabs: styles,
  affect dict, pause list; GPT-SoVITS: SSML-style prosody tags with inline
  emphasis and break markup) that plausibly map to what each real vendor's
  API would need, without ever contacting a vendor -- keeping the adapter
  boundary honest.
- **Authorization gating (AC-P5-10) is genuinely well-built.** The
  disjunction (`HIGH`/`CRITICAL` risk OR `IRREVERSIBLE`) is correct per
  spec, and three independent mutations against it (weakening the risk set,
  removing the reversibility clause, and broadening it to apply
  universally) were all caught by the existing tests except the last
  (P2-1). `dispatch()` unconditionally calls `validate_action` first, so
  there is no code path that reaches an executor while bypassing the gate.
  `_has_authorization` correctly treats a whitespace-only token as absent.
- **Code hygiene (AC-P5-12):** ruff clean, radon reports nothing above rank
  B across all five files (most are A), and all five files are verified
  pure 7-bit ASCII independently of the suite's own check.
- **Scope discipline:** `git diff --stat` against the `09f5d42` baseline
  shows only the five owned files touched -- no incidental edits to shared
  or Package-B-owned modules.
- **Honest self-reporting:** `CODEX_RESULT.md`'s "Not done" section
  accurately scopes what wasn't attempted (no live TTS/actuator/NATS
  wiring) and its own mutation-testing note (inverting the authorization
  gate) matches what I independently reproduced.

---

## Summary

| ID | Severity | One-line summary |
|---|---|---|
| P0-1 | Blocker | `legacy_expression_to_speech_intent` crashes on real `AgentVoiceModulation` data (frame-0 volume always below `SpeechDelivery`'s floor) |
| P1-1 | Must fix | `epistemics`/`relationship` never handled or reported by either compiler; GPT-SoVITS reports zero affect loss despite declaring `supports_affect_modulation=False` |
| P1-2 | Must fix | `dispatch()`'s exception-handling and no-executor-simulate branches are untested; mutating either passes the full suite |
| P1-3 | Must fix | Simulated (unregistered-tool) actions are recorded as indistinguishable from genuinely completed ones in the terminal `OutcomeRecord` |
| P1-4 | Must fix | `timeout_s` is validated but never enforced by `dispatch()` |
| P2-1 | Improvement | No test proves the authorization gate does *not* over-block low-risk actions |
| P2-2 | Improvement | `SpeechRelationship.register` shadows an ABCMeta attribute, warning on every import |
| P2-3 | Improvement | Overlapping/duplicate `EMPHASIS` spans can silently no-op in GPT-SoVITS tag rendering |
| P2-4 | Improvement | `create_action_outcome` instance method is a redundant wrapper around the module function |
| P2-5 | Improvement | `preconditions`/`expected_effects` are schema-only, never inspected |

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
