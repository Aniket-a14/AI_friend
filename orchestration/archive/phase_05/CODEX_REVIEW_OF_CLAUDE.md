# Codex Reciprocal Review: Phase 05 Package B

Reviewed branch: `claude/phase-05` at `6f6da65` against baseline `09f5d42`.

Reviewed implementation files:

- `backend/app/llm/model_roles.py`
- `backend/app/cognitive/vision_percept.py`
- `backend/app/vision/adapters.py`
- `backend/tests/test_model_roles_vision.py`

Specification baseline: `orchestration/PHASE_05/CLAUDE_TASK.md`,
`orchestration/PHASE_05/PLAN.md`,
`orchestration/PHASE_05/ACCEPTANCE_CRITERIA.md`, and
`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` Sections 24, 25, and 38. The governing
documents are present in the shared `AI_friend` checkout, not this worktree;
their Phase 05 contract content was reviewed there.

## Recommendation: REQUEST CHANGES

The package implements the requested public shapes and has a clean, focused
diff. The nominal conformance suite passes. However, two Phase 05 safety
boundaries are presently descriptive rather than enforced: an emotion claim
can cross the vision boundary, and a model-role fallback is not coupled to an
authoritative validation gate. These prevent acceptance of AC-P5-01,
AC-P5-02, and AC-P5-09 as written.

## Findings

### P1 - Vision can still emit facial-emotion facts

`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` Section 24 requires that vision never
reports facial emotion as fact, while the task and AC-P5-09 call this a strict
brain invariant. The implementation only scans `FacialObservable` fields with
a deliberately non-exhaustive emotion-word denylist
(`vision_percept.py:33-38`, `100-101`). The comment explicitly notes that
`"angrily"` is not detected. More importantly,
`VLMCaptionVisionAdapter.process()` places arbitrary VLM text directly in
`scene_deltas` (`adapters.py:76-100`), and
`validate_vision_invariants()` never examines scene deltas
(`vision_percept.py:174-198`). Thus an adapter returns and normalizes a
percept with `scene_deltas=["the user is angry"]`; it reaches cognitive input
as `PerceptEnvelope.text_content` (`adapters.py:160-171`).

Direct review probes also accepted the emotion assertions `"the user appears
furious"`, `"the user looks ecstatic"`, and `"the user is depressed"` in
both `FacialObservable.muscle_movement` and VLM caption output. The tests only
cover four lexical forms in action units and one `angry` phrase in muscle
movement (`test_model_roles_vision.py:410-442`); they do not test caption
content or adversarial paraphrases.

Fix the boundary by using a positive, machine-observable representation for
facial movement (for example action-unit identifiers and documented
blendshape/movement descriptors), or by otherwise validating every
vision-to-cognition textual field against the no-emotion-fact policy. VLM
captions must be constrained, rejected, or retained as clearly untrusted raw
provider output rather than promoted as a brain-facing scene delta. Add tests
that prove `to_percept_envelope()` rejects both direct and VLM-caption emotion
claims, including non-lexicon paraphrases.

### P1 - Role fallback is not bound to a validator or policy gate

The Phase 05 plan requires the execution contract to include a validator and
fallback (PLAN Section 1, item 1; AC-P5-01), and Section 25 requires provider
swaps to preserve constraints. `RoleExecutionRequest` carries
`allowed_claims`, but it is an unconstrained list and has no required
validator/constraint-gate reference or validation result
(`model_roles.py:82-94`). `RoleExecutionResult` has only a caller-controlled
`validated: bool = True` default and a boolean `fallback_applied`, with no
fallback strategy, validation provenance, rejected claims, or hard-gate
outcome (`model_roles.py:96-107`). `ProviderCapabilityNegotiator` correctly
does not mutate state, but it returns only advisory strings
(`model_roles.py:190-256`); nothing makes a TEMPLATE_PROCEDURE or
ROLE_DEGRADATION run pass the same identity/safety validation before its
result can be used.

The current test for this acceptance condition is a source-string scan for a
few class names plus an assertion on method names
(`test_model_roles_vision.py:309-333`). That proves absence of direct coupling,
not that a fallback result cannot bypass a policy gate. A direct probe also
shows an arbitrary `RoleExecutionResult(raw_output="unsafe claim")` reports
`validated=True` by default.

Keep negotiation pure, but make the handoff enforceable. At minimum, encode
the selected `FallbackStrategy` and a required, fail-closed validation/gate
record in the role result, and provide the integration point that refuses an
unvalidated result before candidate/action commitment. Test a native result
and every fallback result against an injected identity/safety gate, proving
that neither can commit or be consumed when the gate rejects it. Do not solve
this by allowing a provider or fallback to own identity/state.

### P2 - Adapter input failures and coercions are not specified or tested

`SpatialTrackingVisionAdapter.process()` assumes every collection is an
iterable list (`adapters.py:117-143`). For example, a string `track_ids`
value becomes one track per character, while `None` raises `TypeError`; an
invalid `staleness_ms` in either adapter can raise a raw `ValueError`. This is
not a bypass of the core invariants, but it makes the provider boundary less
predictable and makes malformed upstream events capable of crashing a caller.

Define a boundary policy (strict Pydantic validation with useful errors, or
fail-closed normalization to empty/default fields) and add cases for `None`,
strings in list fields, malformed nested entries, and non-finite/negative
staleness. Preserve raw payloads only after they meet that policy.

## Areas that meet the requested contract

- `ModelRole` has exactly the six specified values, and both execution models
  have the fields and defaults prescribed by the task.
- Scenario classification is fail-closed for unregistered tags: both a
  frontier-looking Scenario A tag and a Scenario C tag negotiate to ABSTAIN.
  Registered manifest entries use capability data rather than a name prefix.
- The structured vision schema includes all specified fields; nested
  confidence fields and top-level confidence are bounded to `[0, 1]`.
- Both adapters structurally satisfy the runtime-checkable protocol and return
  `StructuredVisionPercept`; spatial data is constructed through nested
  Pydantic models.
- `to_percept_envelope()` preserves the structured payload, sets vision
  modality/source/provenance, carries confidence, and invokes the invariant
  check immediately before conversion.
- The change is isolated to the four owned code/test files plus Claude's
  completion report, with no diff whitespace errors.

## Verification evidence

The exact requested relative interpreter path is unavailable in this worktree
because `/Users/aniketsaha/Projects/ai-friend-claude/.venv` does not exist. I
ran the requested test target from this worktree with the shared repository
virtual environment instead:

```text
/Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m pytest \
  /Users/aniketsaha/Projects/ai-friend-claude/backend/tests/test_model_roles_vision.py \
  -q --junit-xml=/private/tmp/phase05-claude-review.xml
```

JUnit evidence: 60 tests, 0 failures, 0 errors, 0 skipped (0.459 s).

```text
/Users/aniketsaha/Projects/AI_friend/.venv/bin/python -m ruff check \
  app/llm/model_roles.py app/cognitive/vision_percept.py \
  app/vision/adapters.py tests/test_model_roles_vision.py
```

Ruff: all checks passed. A byte scan of the same four files found zero bytes
above `0x7f`. `radon cc app/llm/model_roles.py
app/cognitive/vision_percept.py app/vision/adapters.py -s -n D` produced no
D/E/F entries; the complete report shows ranks A through C only (the highest
is `SpatialTrackingVisionAdapter`, C/11).

Targeted mutation checks demonstrate that the existing tests genuinely cover
two implemented narrow invariants:

- Replacing `_contains_emotional_language()` with `return False` caused 8 of
  60 tests to fail; the original code was restored.
- Mutating the `capability is None` negotiation branch from `ABSTAIN` to
  `NATIVE` caused 2 of 60 tests to fail; the original code was restored.

Those mutants validate the current lexical facial check and unknown-provider
fail-closed behavior. They do not cover the two P1 boundary gaps described
above, which are why this review requests changes.

