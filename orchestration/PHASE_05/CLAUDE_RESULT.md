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

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
