# Phase 05 Package B Completion Summary: Claude

Assignment: Package B - Foundation Model Roles and Structured Vision Boundary
Branch: claude/phase-05
Worktree: /Users/aniketsaha/Projects/ai-friend-claude
Baseline: main at 09f5d42

---

## 1. Files Delivered

- `backend/app/llm/model_roles.py` (NEW)
- `backend/app/cognitive/vision_percept.py` (NEW)
- `backend/app/vision/adapters.py` (NEW)
- `backend/tests/test_model_roles_vision.py` (NEW)

No files outside this ownership list were modified.

---

## 2. What Was Built

### `app/llm/model_roles.py`

- `ModelRole` (str Enum): INTERPRETATION, CANDIDATE_GENERATION, PLANNING,
  EVALUATION, COMPRESSION, REALIZATION.
- `ProviderScenario` (str Enum): SCENARIO_A_FRONTIER, SCENARIO_B_LOCAL_COMPACT,
  SCENARIO_C_ALTERNATIVE_PROVIDER. Purely descriptive; `classify_scenario`
  derives it from whether a `model_tag` is registered in
  `app.llm.model_manifest` (Scenario B) or, if not, whether its name matches
  a known frontier-provider naming convention (Scenario A) or not (Scenario
  C). The label never grants capability on its own -- an unregistered tag
  always abstains regardless of which prefix it matches.
- `FallbackStrategy` (str Enum): NATIVE, TEMPLATE_PROCEDURE, ROLE_DEGRADATION,
  ABSTAIN -- a closed set so a negotiation result can never carry an
  ad hoc, unaudited fallback string.
- `RoleExecutionRequest` / `RoleExecutionResult`: exactly the fields
  specified in `CLAUDE_TASK.md` / `PLAN.md` section 3.A.
- `RoleRequirement` + `ROLE_REQUIREMENTS`: per-role minimum
  `ModelCapability` (context window floor, whether structured output or
  streaming is required), set deliberately per role rather than uniformly
  -- PLANNING/EVALUATION need structured output because they commit to
  claims a validator checks; COMPRESSION has the highest context floor
  because it must see what it condenses; CANDIDATE_GENERATION/REALIZATION
  need streaming because the action pipeline consumes them incrementally.
- `ProviderCapabilityNegotiator` with `evaluate_capability(role, capability)`
  and `negotiate_role(role, model_tag)`, both pure functions with no model
  calls and no imports of the agent-state service or identity manager.
  Missing structured output falls back to TEMPLATE_PROCEDURE; insufficient
  context window or missing streaming falls back to ROLE_DEGRADATION; an
  unregistered (capability-unknown) model tag always ABSTAINs -- failing
  closed rather than trusting a name pattern.

### `app/cognitive/vision_percept.py`

- `IdentityEstimate`, `DetectedObject`, `SpatialRelation`,
  `StructuredVisionPercept`: exactly the fields specified.
- `FacialObservable`: `action_units` and `muscle_movement` carry Pydantic
  field validators that reject any string containing emotional language
  (a fixed lexicon of common emotion words, word-boundary matched,
  case-insensitive) at construction time.
- `validate_vision_invariants(percept)`: a defense-in-depth re-check of
  every facial observable in a percept. This matters because Pydantic does
  not re-run field validators when a list field is mutated in place
  (`observable.action_units.append("happy")` after construction bypasses
  the constructor-time check entirely) -- this function is the
  authoritative re-check any caller can run before trusting a percept.

### `app/vision/adapters.py`

- `VisionAdapterProtocol`: a `runtime_checkable` `Protocol` with
  `process(raw_data: Any) -> StructuredVisionPercept`.
- `VLMCaptionVisionAdapter`: adapts a plain string or a dict shaped like
  `VisualAppraisalService`'s output into a low-confidence (default 0.35)
  percept with a single scene delta and `provenance="vlm_caption"`.
- `SpatialTrackingVisionAdapter`: adapts a structured detector/tracker
  payload into a full percept (track IDs, objects, identity estimates,
  facial observables, spatial relations), `provenance="spatial_tracking"`.
  Every nested structure is built through its own Pydantic model, so a
  facial observable carrying an emotional label is rejected before it can
  ever reach the returned percept.
- `to_percept_envelope(structured)`: normalizes a `StructuredVisionPercept`
  into `app.cognitive.percept.PerceptEnvelope` for `CognitivePipeline`
  ingestion. Re-runs `validate_vision_invariants` immediately before
  conversion -- the last checkpoint before a percept enters cognition.

### `tests/test_model_roles_vision.py`

60 tests covering:

- `ModelRole` taxonomy completeness and `RoleExecutionRequest` /
  `RoleExecutionResult` field defaults and required-field validation.
- `ProviderCapabilityNegotiator` against the real seeded manifest (Scenario
  B: native fit and context-window-driven ROLE_DEGRADATION on real models
  `llama3.2:3b` / `qwen2.5:3b`), against unregistered tags (Scenario A/C:
  both ABSTAIN, proving name patterns alone never grant capability), and
  against synthetic `ModelCapability` objects (structured-output gap ->
  TEMPLATE_PROCEDURE, streaming gap -> ROLE_DEGRADATION, fully-capable ->
  NATIVE for every role).
- Invariant tests: an exhaustive role x capability-variant matrix asserting
  the returned strategy is always one of the four closed `FallbackStrategy`
  values and that the boolean result is true if and only if the strategy is
  NATIVE; a structural source-scan asserting `model_roles.py` never
  references the agent-state or identity classes by name; and an assertion
  that `ProviderCapabilityNegotiator`'s public surface is exactly its two
  advisory read-only methods.
- `StructuredVisionPercept` defaults, confidence bounds (0.0-1.0) on
  `IdentityEstimate`/`DetectedObject`/`StructuredVisionPercept`, and nested
  model composition.
- Anti-emotion-fact enforcement: `FacialObservable` rejects emotion words
  in `action_units` and embedded in `muscle_movement` at construction; a
  companion test constructs a clean observable, mutates its list in place
  to smuggle in "happy", and confirms `validate_vision_invariants` (and
  `to_percept_envelope`, separately) still catches it.
- Both adapters' `VisionAdapterProtocol` conformance, their happy-path
  output shape, and `SpatialTrackingVisionAdapter` rejecting an emotional
  label inside a raw facial-observable payload.
- `to_percept_envelope` normalization: modality/source/provenance/
  confidence propagation, scene-delta/action-event text joining, empty-
  input handling, and percept-id uniqueness across calls.
- Pure 7-bit ASCII compliance: a byte-level scan plus a companion
  smart-punctuation regex check across all four Package B files (including
  this test file itself).

---

## 3. Verification

Run from `backend/` against the shared root `.venv`
(`/Users/aniketsaha/Projects/AI_friend/.venv` -- this worktree has no
`.venv` of its own; it is a git worktree of the same repository and shares
the interpreter):

```
../../AI_friend/.venv/bin/python -m pytest tests/test_model_roles_vision.py -q
```
Result: **60 passed, 0 failed, 0 errors** (verified via `--junit-xml`, per
CLAUDE.md's guidance that the terminal summary line is unreliable in this
environment).

```
../../AI_friend/.venv/bin/python -m ruff check .
```
Result: **All checks passed.**

```
../../AI_friend/.venv/bin/python -m radon cc app/ -s -n D
```
Result: **no output** -- zero functions at cyclomatic-complexity rank D or
higher.

Full backend regression suite (all 2,149 tests, not just this file):
```
../../AI_friend/.venv/bin/python -m pytest -q --junit-xml=...
```
Result: **2,149 passed, 0 failures, 0 errors, 0 skipped.**

Mutation testing (deliberately broke, then restored, two invariants to
confirm the tests fail for the right reason):
- Disabled the emotion-word check in `FacialObservable.action_units`'s
  validator -> 5 of the anti-emotion-fact tests failed as expected.
- Flipped the ABSTAIN branch in `evaluate_capability` (`capability is None`)
  to return NATIVE -> 2 of the Scenario A/C and closed-fallback-set tests
  failed as expected.
Both mutations were reverted and the full targeted suite re-verified green
afterward.

ASCII purity: verified both by the test suite's own byte-level scan (part
of the 60 passing tests) and manually via `ruff check` (which would flag
encoding issues) plus a direct `.decode("ascii")` pass on all four files.

---

## 4. Design Notes and Deviations

- `ProviderScenario` is not threaded through `negotiate_role`'s required
  signature (`negotiate_role(role, model_tag) -> tuple[bool, str, dict]`,
  fixed by the spec), but it is computed internally via `classify_scenario`
  and included in the returned details dict under `"scenario"`, so the
  taxonomy is exercised as part of every negotiation rather than being an
  unused type.
- No changes were made to `app/llm/model_manifest.py` (shared, unowned by
  either Phase 05 package) to add frontier/alternative-provider capability
  entries. Scenario A and C behavior is tested against unregistered model
  tags (which correctly ABSTAIN) and, separately, against synthetic
  `ModelCapability` objects passed directly to `evaluate_capability` for
  cases that need a concrete (non-None) capability profile to exercise
  TEMPLATE_PROCEDURE / ROLE_DEGRADATION / NATIVE branches.
- `to_percept_envelope` sets both `PerceptEnvelope.source` and
  `PerceptEnvelope.provenance` to the structured percept's own
  `provenance` value (`"vlm_caption"` / `"spatial_tracking"`), rather than
  leaving `provenance` at its `"nats"` default the way the existing
  `app/cognitive/percept.py` converters do for mesh-sourced events. This
  adapter boundary constructs envelopes directly rather than from a NATS
  wire payload, so the more specific value is more informative for a
  downstream consumer trying to distinguish a caption-derived percept from
  a spatial-tracking one.

---

## 5. NOT Done / Out of Scope for This Package

- Package A's deliverables (`speech_intent.py`, `voice/compiler.py`,
  `external_action.py`) -- owned by the Codex worktree, not touched here.
- No live camera, MediaPipe, or VLM wiring -- both adapters operate on
  already-produced data (a caption string/dict, or a structured
  tracker/detector payload); connecting a real spatial tracker to
  `SpatialTrackingVisionAdapter` is future integration work, not part of
  this package's scope per `CLAUDE_TASK.md`.
- No wiring of these adapters or `to_percept_envelope`'s output into
  `agents/brain_agent.py` or `CognitivePipeline`'s live event handling --
  the task scope was the boundary contract and its adapters, not mesh
  integration.
- Integration with Package A's output and cross-package regression
  verification is explicitly the orchestrator's job in
  `/Users/aniketsaha/Projects/ai-friend-integration`, not this worktree's.

---

## 6. Fix Round (peer-review response)

Following reciprocal review, `orchestration/PHASE_05/FIX_PLAN.md` arbitrated
two P1 findings from `CODEX_REVIEW_OF_CLAUDE.md` and one P2 finding, all
against this package. This section records what changed in response;
sections 1-5 above describe the original implementation and are otherwise
unchanged.

### P1: anti-emotion-fact invariant was bypassable via `scene_deltas` and non-lexicon words

The review demonstrated two concrete gaps: `scene_deltas` (free-form text,
the natural home for a VLM caption) was never checked by
`validate_vision_invariants` at all, so `StructuredVisionPercept(
scene_deltas=["the user is angry"])` built and normalized without
complaint; and the emotion lexicon missed several common words the review
named explicitly ("furious", "ecstatic", "depressed") plus the adverb form
of an already-covered word ("angrily").

- `app/cognitive/vision_percept.py`: `contains_emotional_language` (renamed
  from the module-private `_contains_emotional_language` -- it is now a
  genuine cross-module utility, needed by `app/vision/adapters.py` too, so
  it no longer hides behind a leading underscore) gained roughly 50 new
  lexicon entries: the review's own three named words plus their inflected
  forms (furious/furiously/fury, ecstatic/ecstasy/ecstatically,
  depressed/depression/depressing/depressive), several adjacent
  high-intensity emotion words (terrified, devastated, heartbroken,
  distraught, petrified, overjoyed, jubilant), and the adverb form of every
  base word likely to appear predicatively ("angrily", "sadly", "happily",
  and others) -- English inflection is irregular enough that a
  suffix-stripping heuristic would either miss these or false-positive on
  unrelated words, so each form is listed explicitly. Deliberately
  *removed* "content"/"contentment": once the lexicon runs over
  `scene_deltas`-shaped free narrative text rather than only a constrained
  `muscle_movement` label, "content" collides constantly with its ordinary
  sense ("the content of the frame"), and rejecting a benign caption for
  using a common English word in its mundane sense is a worse failure than
  missing the rare case where it was meant emotionally.
- `validate_vision_invariants` now also inspects `percept.scene_deltas` and
  raises `ValueError` on the same terms as `facial_observables`.
- `app/vision/adapters.py`: `VLMCaptionVisionAdapter` now sanitizes caption
  text through a new `_sanitize_caption` helper before it can become a
  scene delta. An emotion-bearing caption is dropped whole (scene_deltas
  stays empty for that frame) rather than edited down to its non-emotional
  clause -- word-level surgery on a sentence the adapter didn't generate
  risks leaving a grammatically broken or misleadingly-reworded fragment
  that still reads as authoritative observation. `validate_vision_invariants`
  still runs at the end of `process()` as a second, independent backstop,
  so a gap in the sanitizer's lexicon is not the only line of defense.
- 21 new tests: the review's exact three probe phrases plus the adverb
  form, parametrized across `contains_emotional_language`,
  `FacialObservable.muscle_movement`, `validate_vision_invariants` on a
  direct `scene_deltas` construction, `to_percept_envelope` end-to-end, and
  every `VLMCaptionVisionAdapter` caption path (string input, dict
  payload); a benign-caption-is-preserved test and a
  `content`-is-no-longer-flagged regression test guard against the fix
  being too aggressive in the other direction.

### P1: `RoleExecutionResult` had no enforceable validation gate

The review's exact probe: `RoleExecutionResult(raw_output="unsafe claim")`
reported `validated=True` by construction default, with zero checks ever
run -- and nothing in the module prevented a `TEMPLATE_PROCEDURE` or
`ROLE_DEGRADATION` fallback result from being treated the same way.

- `app/llm/model_roles.py`: `RoleExecutionResult.validated` now defaults to
  `False` (fail-closed, consistent with the rest of this module's posture).
  Added `fallback_strategy: FallbackStrategy = FallbackStrategy.NATIVE` and
  `validation_errors: list[str] = Field(default_factory=list)`.
- New `validate_execution_result(request, result, custom_validator=None) ->
  RoleExecutionResult`: checks `request.allowed_claims` against whatever
  claims `result.parsed_output` actually makes (a bare list, or a dict with
  a `"claims"` list -- the two natural shapes; if `allowed_claims` is
  configured but `parsed_output` offers nothing checkable, that is a
  failure, not a silent pass), validates `result.parsed_output` against
  `request.schema_definition` when present, and runs an optional
  `custom_validator` (an exception from a broken validator is recorded as a
  failure rather than propagated, so a bad validator cannot crash the gate
  it exists to strengthen). Returns a new `RoleExecutionResult` with
  `validated=True` only if every configured check passed; this module
  remains pure throughout, consistent with `ProviderCapabilityNegotiator`
  -- the input `result` is never mutated.
- Schema checks use the real `jsonschema` library rather than a hand-rolled
  subset of the spec (added as a new backend dependency --
  `requirements-base.txt`, `jsonschema>=4.25.0,<5.0.0`, installed into the
  shared `.venv`; no existing dependency covered this and a partial
  reimplementation would only ever validate what someone remembered to
  handle).
- New `RoleResultRejected(Exception)` and `ensure_committable(result) ->
  RoleExecutionResult`: the hard gate. Raises unless `result.validated` is
  `True`; a result's `fallback_strategy` grants no exemption --
  `TEMPLATE_PROCEDURE` and `ROLE_DEGRADATION` are checked exactly like
  `NATIVE`, since a degraded role is still asserting claims into cognition.
  This is the enforcement point a future caller committing a role result to
  a candidate or action is expected to call; there is no path to
  commitment within this module that skips it.
- 19 new tests: the review's exact probe rejected by `ensure_committable`;
  `allowed_claims` acceptance/rejection (list and dict-with-"claims"
  shapes) and the fail-closed case where claims are configured but
  unparseable; `schema_definition` acceptance/rejection via real
  `jsonschema` errors; `custom_validator` rejection and
  exception-is-recorded-not-raised; a purity check (`validate_execution_result`
  returns a new object, leaves the input untouched); and, directly
  answering the fix's core requirement, both `TEMPLATE_PROCEDURE` and
  `ROLE_DEGRADATION` results parametrized through the identical
  reject-until-validated-then-commit sequence as a `NATIVE` result,
  including a fallback result that still gets rejected for an
  out-of-scope claim.

### P2: adapter input coercion for malformed upstream payloads

- `app/vision/adapters.py`: `SpatialTrackingVisionAdapter.process()` now
  routes every list-shaped field through `_coerce_raw_list` (returns `[]`
  for a missing key, an explicit `None`, or any non-list value -- closing
  the specific bug the review demonstrated, where a string `track_ids`
  value silently iterated into one bogus track per character) and, for the
  four nested-Pydantic-model fields, `_coerce_model_list` (additionally
  drops any list entry that isn't a mapping, so a stray string or number
  inside an otherwise-valid list can't crash the `model(**entry)`
  unpacking). `staleness_ms` on both adapters now goes through
  `_safe_staleness_ms`, collapsing a missing, non-numeric, negative, or
  non-finite (NaN/infinite) value to `0.0` instead of raising or silently
  carrying a nonsensical value forward -- applied to `VLMCaptionVisionAdapter`
  too, since the original finding described the gap as present in "either
  adapter."
- 11 new tests: `None` raw_data at the top level; each list field
  individually set to `None`; the exact string-splits-into-characters case
  named by the review; malformed nested entries mixed with well-formed
  ones (confirms the well-formed entries survive); a parametrized sweep of
  clearly-malformed whole payloads (wrong types, non-dict raw_data)
  asserting `process()` never raises; and `staleness_ms` parametrized over
  NaN, +/-infinity, negative, non-numeric-string, and `None`, plus one
  confirming a valid positive value is preserved unchanged.

### Verification (fix round)

```
../../AI_friend/.venv/bin/python -m pytest tests/test_model_roles_vision.py -q
```
Result: **123 passed, 0 failed, 0 errors** (60 original + 63 new; verified
via `--junit-xml`).

```
../../AI_friend/.venv/bin/python -m ruff check .
```
Result: **All checks passed** (three findings surfaced and fixed during
this round: an implicit-string-concatenation-in-a-list-literal warning in
`_check_allowed_claims`'s error message, a stale `noqa` comment, and
`_coerce_model_list`'s `TypeVar`-based generic converted to PEP 695 `def
_coerce_model_list[ModelT: BaseModel](...)` syntax per ruff's own
preference for this codebase's inferred target Python version).

```
../../AI_friend/.venv/bin/python -m radon cc app/ -s -n D
```
Result: **no output** -- zero functions at rank D or higher across all
three changed modules (worst is `VLMCaptionVisionAdapter` and its
`process` method at B(8)/B(7); everything else is A or low B).

Full backend regression suite: **2,212 passed, 0 failures, 0 errors, 0
skipped** (up from 2,149 before this round, reflecting the 63 new tests).

Mutation testing (four mutations, each reverted and the working tree
diffed back to clean before moving on):
- Disabled the new `scene_deltas` check in `validate_vision_invariants` ->
  5 of the scene-delta/caption tests failed as expected.
- Disabled `VLMCaptionVisionAdapter`'s caption sanitizer (the
  `validate_vision_invariants` backstop still runs inside `process()`) -> 6
  of the caption tests failed, now via an uncaught `ValueError` from
  `process()` itself rather than a shape mismatch, confirming the
  sanitizer and the backstop are doing distinct, both-tested work.
- Reverted `RoleExecutionResult.validated`'s default back to `True` -> 5 of
  the gate tests failed as expected.
- Made `ensure_committable` unconditionally pass (dead code the `if`
  guarded) -> 4 of the gate/fallback tests failed as expected.

ASCII purity: verified via direct `.decode("ascii")` on all three changed
source files, the test file, and `requirements-base.txt`.

Dependency change: `jsonschema>=4.25.0,<5.0.0` added to
`backend/requirements-base.txt` (chained into `requirements-ai.txt` ->
`requirements.txt`) and installed into the shared
`/Users/aniketsaha/Projects/AI_friend/.venv`. This is the only file this
fix round touched outside the four owned files, and it was necessary: no
existing dependency provides JSON Schema validation, and
`validate_execution_result`'s schema check needs the real spec rather than
a hand-rolled subset.

**NOT done (fix round):** `ensure_committable` is defined and tested but
not yet called from any commitment/candidate path -- that integration
point does not exist in this phase's scope for model-role results, so the
gate is enforced structurally (it is the only way to obtain a committable
result) but not yet wired into a live caller. Package A's corresponding
fix-round items (legacy migration crash, compiler telemetry completeness,
`dispatch()` branch coverage, simulated-outcome visibility, `timeout_s`
enforcement) are Codex's responsibility in `ai-friend-codex`, not addressed
here.

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
