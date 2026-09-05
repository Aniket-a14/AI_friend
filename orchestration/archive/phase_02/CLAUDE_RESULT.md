# Phase 02 Package B Result

## Commit

- Commit: `97e87acc1d5248d8fa22954259d43bc8e6937815`
- Message: `feat(cognitive): implement Phase 02 action candidate selection and memory activation`
- Branch: `claude/phase-02`

## Delivered

- `backend/app/cognitive/action_candidate.py` (new): `ActionCandidate` model
  (all fields per the shared contract) and `CandidateSelector` with
  `filter_constraints` (constraint-first, case-insensitive substring overlap
  against forbidden claims) and `score_and_select` (score plus goal-alignment
  ranking, returns winner and reasoned rejected alternatives, raises
  `ValueError` on an empty candidate list rather than inventing a winner).
- `backend/app/cognitive/memory_activation.py` (new): `MemoryActivation`
  model (matching `orchestration/PHASE_02/PLAN.md` section 4.A exactly) and
  `AntiInjectionGate` with `is_injection_attempt` / `sanitize_memory_text`,
  detecting instruction-override phrasing, role-hijack phrasing, and fake
  system/control markup (`<system>`, `[system]`, `<|...|>`, `###system`).
- `backend/app/cognitive/decision.py`: `DecisionService` now generates a
  SPEAK-baseline + WAIT-fallback candidate set per social-response turn (WAIT
  carries no `constraint_claims`, so `filter_constraints` can never empty the
  set), adds a competing ASK candidate when an active `MemoryActivation` is
  high-relevance and disputed/superseded/invalidated, runs
  `CandidateSelector.filter_constraints` against `identity_manager
  .immutable_core["boundaries"]`, and selects via `score_and_select`. All of
  this is gated behind `Config.PHASE_02_MEMORY_TRUTH`; `decide()` gained an
  optional `memory_activations` parameter (default `None`, purely additive).
- `backend/app/cognitive/pipeline.py`: `CognitivePipeline.execute` gained an
  optional `memory_activations` parameter, threaded into `decision.decide`.
  When the flag is on and any activation reports `outage_flag=True`, the
  turn's `event.metadata["retrieval_degraded"]` is set. Stage 6's committed
  `ActionIntent.kind` is now derived from the selected `ActionCandidate` when
  one exists, falling back to the original action_type heuristic otherwise.
- `backend/app/cognitive/behavior_contracts.py`: `BehaviorDecision` gained
  `selected_candidate`, `rejected_alternatives`, and `retrieval_degraded`
  fields (all defaulted, so `.model_dump()` for a legacy caller only gains
  new keys, never changes an existing value).
- `backend/app/cognitive/action_intent.py`: `ActionKind` widened to also
  accept `RETRIEVE`, `VERIFY`, `UPDATE_GOAL` (a strict superset of the Phase 1
  literal) so a selected candidate's kind can always be committed without a
  lossy remap.
- `backend/app/config.py`: added `PHASE_02_MEMORY_TRUTH: bool = False`.
- `backend/tests/test_action_selection.py` (new): 28 tests covering
  constraint-first filtering, goal-alignment scoring, memory-driven action
  shifts (high/low relevance, disputed vs. undisputed), `AntiInjectionGate`
  detection and sanitization, typed outage reporting (unit and full-pipeline
  end-to-end), and backward compatibility with the flag off (including a
  caller that omits `memory_activations` entirely).
- `backend/tests/test_phase5_tom.py`: one pre-existing hand-rolled `decide`
  stub updated to accept the new optional `memory_activations` keyword
  (`async def mock_decide(event, snapshot, memory_activations=None)`) -- the
  only existing test broken by the additive signature change.

## Verification

- Focused suite: `../.venv/bin/python -m pytest tests/test_action_selection.py -v`
  -- 28 passed, 0 failed.
- Full backend suite: `../.venv/bin/python -m pytest -q --junit-xml=...` --
  **1937 tests, 0 failures, 0 errors, 0 skipped** (parsed from the JUnit XML,
  per this repo's documented pytest-terminal-summary unreliability).
- Ruff: `../.venv/bin/python -m ruff check app/cognitive/action_candidate.py
  app/cognitive/memory_activation.py app/cognitive/decision.py
  app/cognitive/pipeline.py tests/test_action_selection.py` -- all checks
  passed.
- Mypy: `../.venv/bin/python -m mypy app/cognitive/action_candidate.py
  app/cognitive/memory_activation.py` -- `Success: no issues found in 2
  source files`. Additionally ran mypy over the two modified files
  (`decision.py`, `pipeline.py`, `behavior_contracts.py`, `action_intent.py`)
  for my own diligence: one pre-existing error in `decision.py` line 281
  (`_DETERMINISTIC_PLAN_INTENTS.get(deterministic_plan.payload.get(...))`),
  in code this change does not touch and outside this task's mypy scope --
  left as-is.
- ASCII check: `git diff` restricted to added (`+`) lines across every
  modified/created cognitive file, scanned byte-by-byte for values > 127 --
  clean. (The unmodified portions of `decision.py`, `pipeline.py`, and
  `config.py` retain pre-existing non-ASCII characters, e.g. em-dashes and
  section signs, from before this change; none were introduced or touched
  here.)
- Mutation check (manual, per this repo's verification bar, actually run
  and reverted -- not merely asserted): temporarily changed
  `_claims_overlap`'s `or` to `and` in `action_candidate.py`;
  `test_candidate_violating_forbidden_claim_is_rejected_before_scoring`
  failed as expected (`test_unrelated_claim_does_not_trigger_rejection`
  still passed under this mutation, since its claim/forbidden-claim pair is
  a true negative under both `or` and `and` -- it does not itself
  distinguish the two operators); reverted. Also temporarily changed the
  ASK-trigger condition in `decision.py::_build_candidates` from
  `!= "NONE"` to `== "NONE"`; both
  `test_high_relevance_disputed_memory_shifts_selection_to_ask` and
  `test_undisputed_high_relevance_memory_does_not_shift_selection` failed
  as expected; reverted.

## NOT DONE

- Package A's `backend/app/state/memory_records.py` /
  `backend/app/state/temporal_store.py` are not imported anywhere in this
  work. `MemoryActivation` is defined independently in
  `memory_activation.py` per the shared contract in
  `orchestration/PHASE_02/PLAN.md` section 4.A, so this package has no
  runtime dependency on Package A's branch. Wiring a real retrieval path
  that constructs `MemoryActivation` tokens from `TemporalMemoryStore`
  query results (rather than a caller passing them in directly, as every
  test here does) is unstarted -- there is currently no production caller
  of `CognitivePipeline.execute(..., memory_activations=...)`.
- `AntiInjectionGate` is not yet wired into any code path that actually
  builds prompt text from `MemoryActivation.structured_value` -- the gate
  exists and is tested standalone, but nothing in `action.py` or
  `decision.py` calls `sanitize_memory_text` on activation content before
  it could reach a prompt. Today's `_build_candidates` never surfaces
  `structured_value` text into anything user-visible, so there is no live
  injection surface yet, but this is the integration Section 39 ultimately
  calls for and it remains open.
- `CandidateSelector`-produced candidates never carry `constraint_claims`
  from the identity boundaries in the current `_build_candidates` builder
  (SPEAK/WAIT/ASK are all unconstrained today) -- `filter_constraints` is
  fully implemented and unit-tested in isolation, but the DecisionService
  integration does not yet derive real per-candidate constraint claims from
  turn content (e.g. detecting that a planned response would claim a
  physical body). `test_action_selection.py`'s constraint-filtering tests
  exercise `CandidateSelector` directly with hand-built candidates for this
  reason.
- `ActionCandidate.kind` values `OBSERVE`, `RETRIEVE`, `VERIFY`, and
  `UPDATE_GOAL` are defined and can be committed as an `ActionIntent.kind`,
  but nothing in `_build_candidates` currently generates a candidate of any
  of those kinds, and `action.py` (Stage 8) has no execution branch for
  them -- only SPEAK/ASK/WAIT are ever produced today, and Stage 8 execution
  is unchanged from Phase 1 (still dispatches on `plan.action_type`, not on
  the selected candidate's kind), by design and by file-ownership scope
  (`action.py` was not in this task's file list).
- No Radon CC / Bandit / Codespell / pre-commit run was performed (PLAN.md
  section 6 lists these as phase-level quality gates); only the Ruff/Mypy
  commands in `CLAUDE_TASK.md` section 3 were run.
- No GPU benchmark, merge, push, or remote CI run was performed.

---

# Fix Round: Response to Codex Peer Review (B1-B8)

## Commit

- Commit: `21520ae89baa7ffe92a351975dcfc18162431cbe`
- Message: `fix(cognitive): address peer review findings for action candidate selection and memory activation`
- Branch: `claude/phase-02`
- Source: `orchestration/PHASE_02/CLAUDE_FIX_TASK.md`, arbitrated findings in
  `orchestration/PHASE_02/FIX_PLAN.md` section 3 (Codex review of Claude,
  findings B1-B8, all verdict ACCEPT).

## Delivered, by finding

- **B1 (blocker) -- production turns could not supply MemoryActivation
  tokens.** Added `memories_to_activations(surfaced_memories)` in
  `memory_activation.py`: converts the legacy `{"content", "source",
  "timestamp", "relevance"}` dict shape `CognitiveService.surfaced_memories`
  has always used into typed tokens. Always `record_type="experience"` and
  `contradiction_state="NONE"` -- a legacy dict carries no
  contradiction/belief information, so the adapter must never invent a
  dispute; `outage_flag` is always `False` (a real outage is a raised
  exception from retrieval, never a shape this function sees).
  `CognitivePipeline.execute` now calls this adapter itself when
  `memory_activations is None and Config.PHASE_02_MEMORY_TRUTH` (an explicit
  caller-supplied list is never overridden). `CognitiveService.process_event`
  gained an optional `memory_activations` parameter, forwarded unchanged to
  `pipeline.execute`. Net effect: a real production turn through
  `process_event()` now reaches Stage 6 candidate selection with real memory
  evidence whenever the flag is on, not only a hand-built test argument.
- **B2 (blocker) -- ASK was committed in the trace but never executed.**
  `decision.py::_plan_social_response` now sets `action_type="CLARIFY"` and
  `payload["clarification_subject"]` whenever the winning candidate's kind
  is `ASK` (subject recovered from the candidate's `predicted_outcomes`,
  itself built from `MemoryActivation.structured_value` when available,
  falling back to `"that"`). `action.py` gained
  `ActionService._execute_clarify` (dispatched from `execute()` on
  `action_type == "CLARIFY"`): asks the LLM for one short, targeted
  clarifying question via a dedicated `_CLARIFY_GUIDELINE` system prompt
  section instructing it not to answer yet; falls back to a fixed,
  deterministic clarification line when there is no LLM configured,
  generation raises, or generation returns nothing usable after
  chain-of-thought stripping. Deliberately smaller than
  `_execute_respond_chat` (no streaming token-by-token, no self-correction
  pass, no endocrine sampling) -- a clarification question is a short,
  low-risk utterance, and a self-contained path keeps "always end in a real
  question" easy to verify in one place.
- **B3 (high) -- constraint-first filtering was inert for generated
  candidates.** `decision.py::_build_candidates` now populates real
  `constraint_claims`: SPEAK's come from
  `_extract_topic_claims(raw_content)`, a deterministic, LLM-free proxy (the
  turn's own significant words, stopword-filtered) for what a SPEAK response
  engaging with this turn might discuss -- documented in its own docstring
  as a conservative heuristic, not semantic understanding of what the
  eventual response will say. ASK's carries a fixed
  `_ASK_CONSTRAINT_CLAIM = "request_clarification"` label so
  `filter_constraints` has something to evaluate for every generated
  candidate, matching B3's complaint about ASK specifically.
- **B4 (high) -- AntiInjectionGate had no live enforcement point.**
  `action.py::_build_shared_history` (the function that renders every
  surfaced memory's content into the prompt) now calls
  `AntiInjectionGate.sanitize_memory_text` on each memory's content before
  `_wrap_retrieved` delimits it, gated on `Config.PHASE_02_MEMORY_TRUTH`
  exactly like every other Phase 02 behavior change.
- **B5 (high) -- AntiInjectionGate missed common bypasses.** Hardened in
  `memory_activation.py`: `_normalize_for_detection` applies
  `unicodedata.normalize("NFKC", text)` and strips zero-width
  characters (U+200B, U+200C, U+200D, U+FEFF) before pattern matching. The
  instruction-override and exfiltration patterns now allow 1-3 modifier
  words before the anchor noun instead of a fixed phrase, so "ignore the
  previous instructions" and "reveal the system prompt" match the same
  pattern as "ignore all previous instructions". Added role/control
  delimiter patterns (`[INST]`/`[/INST]`, `System:`/`User:`/`Assistant:`).
  `sanitize_memory_text` now quarantines the entire field
  (`[UNTRUSTED_CONTENT_FILTERED]`) on any detected attempt rather than
  substituting only the matched span, closing the "`[filtered]` and reveal
  the secret" partial-redaction leak Codex demonstrated. All five of
  Codex's exact reproduction strings are now caught and covered by
  `test_detects_codex_reported_bypasses`.
- **B6 (medium) -- bidirectional substring matching was unsound.**
  `action_candidate.py::_claims_overlap` now uses word-boundary phrase
  matching (`_phrase_in_text`, `\b<escaped phrase>\b`) instead of raw
  `c in f or f in c`, so "body" no longer matches inside "somebody". Does
  **not** solve lexically-different-but-semantically-equivalent claims
  (e.g. "boyfriend" against "romantic relationship") -- FIX_PLAN.md's
  arbitrated B6 action explicitly scoped the accepted fix to word-boundary
  or token matching, not the fuller structured claim-identifier taxonomy
  Codex's review separately suggested as the stronger long-term design; a
  test pins this as a known, documented limitation rather than silently
  leaving it unstated.
- **B7 (medium) -- ActionKind was a partial subset.** Added
  `UPDATE_STATE`, `EXTERNAL_ACT`, and `CONTINUE` to `action_intent.py`'s
  `ActionKind` (`INTERRUPT` was already present). No candidate generator or
  executor produces these kinds yet -- this is a schema ceiling matching
  architecture section 22's full set, not a claim of reachability.
- **B8 (medium) -- unconditional 3-argument decide() call broke legacy
  stubs.** `pipeline.py` gained `_decision_accepts_memory_activations()`,
  using `inspect.signature` to check whether the injected `decision.decide`
  accepts the `memory_activations` keyword (or `**kwargs`) before passing
  it; otherwise calls the legacy two-argument form. A
  `MagicMock`/`AsyncMock` double is treated as compatible (matches this
  codebase's existing test-double convention). Two pre-existing hand-written
  `pipeline.execute` stubs in `test_causal_slice.py` needed the same
  additive `memory_activations=None` parameter this round's own
  `process_event` change now threads through -- fixed alongside the new
  `TestLegacyDecisionCompatibility` regression tests for `decision.decide`
  specifically.

## Test additions

`backend/tests/test_action_selection.py` grew from 28 to 66 tests. New
classes, one per finding: `TestConstraintClaimsPopulation` (B3),
`TestAskClarificationRealization` (B2, including an end-to-end pipeline test
asserting on emitted *content*, not only `ActionIntent.kind`, per Codex's
explicit ask), `TestPromptInjectionWiring` (B4, including a test of the
actual assembled prompt string passed to the mocked LLM, not the gate in
isolation), `TestClaimsOverlapWordBoundary` (B6), `TestActionKindCompleteness`
(B7), `TestLegacyDecisionCompatibility` (B8),
`TestMemoriesToActivationsAdapter` and `TestProductionMemoryWiring` (B1,
including a `CognitiveService.process_event()`-level integration test with
explicit conflicting `memory_activations`, per `CLAUDE_FIX_TASK.md` item 1's
explicit requirement). B5's adversarial cases were added to the existing
`TestAntiInjectionGate` class, including all five of Codex's exact
reproduction strings, an NFKC fullwidth-character test, and a zero-width
mid-word splice test. Two existing sanitize tests
(`test_sanitize_removes_injection_phrase_but_keeps_surrounding_text`,
`test_sanitize_strips_fake_system_tags`) were rewritten for the new
whole-field-quarantine contract; their old partial-redaction assertions no
longer describe the intended behavior.

## Verification

- Focused suite: `../.venv/bin/python -m pytest tests/test_action_selection.py -v`
  -- **66 passed, 0 failed** (up from 28 before this round).
- Full backend suite: `../.venv/bin/python -m pytest -q --junit-xml=/tmp/phase02_claude_fix_test.xml`
  -- **1975 tests, 0 failures, 0 errors, 0 skipped**, parsed from the JUnit
  XML per this repo's documented pytest-terminal-summary unreliability.
- Ruff: `../.venv/bin/python -m ruff check app/cognitive/ tests/test_action_selection.py`
  -- all checks passed (one import-sort auto-fix applied and re-verified).
- Mypy (own diligence, beyond the fix task's pytest/ruff-only verification
  list): `../.venv/bin/python -m mypy app/cognitive/action_candidate.py
  app/cognitive/memory_activation.py` -- `Success: no issues found in 2
  source files`. One new mypy finding surfaced by this round's own
  `memories_to_activations` (an `Any | None` argument to `float()`) was
  fixed by switching to an explicit `isinstance(relevance, (int, float))
  and not isinstance(relevance, bool)` guard -- the same pattern
  `action.py::_memory_relevance` already uses elsewhere in this codebase --
  rather than suppressed.
- ASCII check: `git diff` restricted to added (`+`) lines across every file
  touched this round, scanned byte-by-byte for values > 127 -- clean. Two
  self-caught mistakes during this round are worth recording here plainly:
  I twice typed literal zero-width/fullwidth Unicode characters directly
  into source and test files while implementing the B5 adversarial test
  cases (the exact class of bypass the fix itself defends against), which
  would have violated the ASCII-only requirement had they shipped. Both
  were caught by the same byte-level scan used throughout this project and
  corrected by rewriting the literals as `\uXXXX` escape sequences via a
  Python script rather than typed characters, verified to decode to the
  intended code points before re-running the affected tests.
- Mutation checks (manually applied and reverted, not merely asserted),
  one per finding with the clearest single point of failure:
  - B6: changed `_phrase_in_text`'s pattern from `\b<escaped>\b` back to a
    bare `re.escape(phrase)` (plain substring) -- 
    `test_body_does_not_match_inside_somebody` failed as expected; reverted.
  - B5: changed `sanitize_memory_text` to return the input unchanged --
    both `test_sanitize_quarantines_the_entire_field_not_only_the_trigger_phrase`
    and, importantly, `test_assembled_prompt_sanitizes_injected_memory_content`
    (the prompt-assembly-level test, not just the isolated gate) failed as
    expected; reverted.
  - B8: changed `_decision_accepts_memory_activations` to always return
    `True` -- `test_pipeline_calls_legacy_two_argument_decide_when_flag_on`
    failed with the exact `TypeError` this fix exists to prevent; reverted.

## NOT DONE

- Carried forward from the first round, now resolved: MemoryActivation
  production wiring (B1) and AntiInjectionGate live enforcement (B4) are no
  longer NOT DONE.
- `AntiInjectionGate` remains a denylist detector over rendered text, not
  the allowlisted structured-field isolation Codex's B5 review recommended
  as the stronger long-term design -- explicitly noted in the class's own
  docstring. Only `_build_shared_history`'s surfaced-memory rendering path
  is wired; `MemoryActivation.structured_value` fields reaching a prompt
  through some other future path (e.g. a real `TemporalMemoryStore`
  retrieval integration) would need their own call site.
- `_claims_overlap` still cannot catch a lexically different but
  semantically equivalent claim (B6's "boyfriend" vs. "romantic
  relationship" example) -- word-boundary/token matching was the arbitrated
  scope, not a structured claim-identifier taxonomy. Documented as a known
  limitation with its own test rather than silently unaddressed.
- `_extract_topic_claims` (B3) is a deterministic word-filter heuristic, not
  natural-language understanding of what a generated SPEAK response will
  actually claim -- it can both over-reject (a benign message that happens
  to share a content word with a boundary) and under-reject (a response
  that asserts something never mentioned in the user's own turn). Documented
  as such in its docstring.
- No Radon CC / Bandit / Codespell / pre-commit run was performed this round
  either -- `CLAUDE_FIX_TASK.md`'s verification section lists pytest and
  ruff only.
- No GPU benchmark, merge, push, or remote CI run was performed.
- Package A's `backend/app/state/memory_records.py` /
  `backend/app/state/temporal_store.py` are still not imported anywhere in
  this work; `memories_to_activations` adapts legacy dicts, not real
  `TemporalMemoryStore` query results. A production retrieval path that
  constructs `MemoryActivation` tokens from actual belief/experience
  records (rather than the legacy surfaced-memory dict shape) remains
  unbuilt on both sides of the file-ownership split.
