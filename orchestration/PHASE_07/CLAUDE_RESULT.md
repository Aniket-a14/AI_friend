# Phase 07 Claude Result: Epistemic Quarantine, Memory Truth Bridge & Governance

Branch: claude/phase-07
Package: B (Cognitive / Memory Truth / Governance)
Worktree: /Users/aniketsaha/Projects/ai-friend-claude

---

## 1. Summary of changes

### B1: Epistemic Dream Memory Quarantine (`subconscious_agent.py`)

`_run_dream_sequence` no longer calls `memory_store.add_memory(..., source="subconscious_dream")`. A generated dream insight is logged only:

```python
logger.info(
    "[Subconscious] Dream insight generated (ephemeral quarantine): '%s'",
    dream_text,
)
```

`tests/test_phase6_advanced_cognition.py::test_sleep_dreaming_neo4j` now asserts `add_memory` is never called, and specifically never with `source="subconscious_dream"`, while still asserting the Neo4j `apoc.coll.randomItems` query still runs (the quarantine only removes persistence, not the dream generation itself).

Mutation check: reverted the quarantine locally (re-added the `add_memory` call) and confirmed the test fails; restored and confirmed it passes again.

### B2: Memory Truth Bridge (`memory_activation.py` & `memory_store.py`)

`memories_to_activations` no longer hardcodes `contradiction_state="NONE"` and `outage_flag=False`. Two new helpers:

- `_extract_contradiction_state(memory)`: an explicit `contradiction_state` key on the legacy dict wins; failing that, a linked `belief_record`/`belief` (dict or object) contributes its `contradiction_type` (CONFLICT/UPDATE/CORRECTION/ELABORATION, from `temporal_store.py`'s `ContradictionDecision`) or its `status` (ACTIVE/SUPERSEDED/INVALIDATED/DISPUTED, from `memory_records.py`'s `BeliefRecord`). `ACTIVE` maps to `NONE`. Anything unrecognized falls back to `NONE`.
- `_extract_outage_flag(memory)`: `outage_flag` or an `error`/`retrieval_error` key on the dict marks a degraded retrieval.

`ContradictionState` (the Pydantic Literal on `MemoryActivation`) was widened to include `CONFLICT`, `UPDATE`, `CORRECTION`, `ELABORATION` alongside the existing `NONE`/`DISPUTED`/`SUPERSEDED`/`INVALIDATED`. `decision.py`'s only consumer of this field (`activation.contradiction_state != "NONE"`) is a not-equal check, so the widened Literal is backward compatible.

New tests in `tests/test_action_selection.py` (`TestMemoriesToActivationsContradictionAndOutage`, 8 cases) cover: explicit state propagation, unrecognized-state fallback, linked-BeliefRecord status propagation (including the ACTIVE-to-NONE mapping), linked-ContradictionDecision-shaped `contradiction_type` propagation, explicit `outage_flag`, `error`-key-as-outage, and a regression guard that an ordinary legacy dict still resolves to `NONE`/`False`.

`backend/app/state/memory_store.py`: **no code change was needed.** `search_memories` already records `self.last_search_error` / `self.last_search_error_at` on both the embedding-failure path and the generic exception path (see the existing `P3-6` comment at that call site), and already returns `[]` alongside setting the error rather than raising -- this is exactly "surfaces degraded status rather than silently returning `[]` on outages." Verified against the existing `tests/test_l1_cache.py` coverage of `last_search_error`.

### B3: Active Configuration Defaults & Test Compatibility (`config.py`)

Set:
- `PHASE_02_MEMORY_TRUTH: bool = True`
- `PHASE_03_AFFECT_CONTROL: bool = True`
- `WORKSPACE_AUTHORITATIVE: bool = True` (newly declared as a real field; previously only existed as a `getattr(Config, "WORKSPACE_AUTHORITATIVE", False)` default inside `state/session_state.py::workspace_authoritative_enabled()`)
- `LEARNING_REVIEW_REQUIRED: bool = True`

Test compatibility fixes made to reach 100% pass on the specified verification files, plus fallout found by running the full suite:

- `tests/test_phase5_tom.py`: `mock_decide` now accepts `**kwargs` so it tolerates `global_controls` (and any future keyword extras) the pipeline passes now that `PHASE_03_AFFECT_CONTROL` defaults on.
- `tests/test_context_assembly.py::test_instruction_shaped_memory_stays_inside_the_markers`: updated to assert the injected text is quarantined to `[UNTRUSTED_CONTENT_FILTERED]` by the now-active `AntiInjectionGate` (a strictly stronger property than "the raw text stays inside the markers," which is what it asserted before Phase 02 defaulted on).
- `tests/test_action_selection.py::TestBackwardCompatibility`: all three tests now monkeypatch **both** `PHASE_02_MEMORY_TRUTH` and `PHASE_03_AFFECT_CONTROL` to `False` (candidate selection in `decision.py::_plan_social_response` is reached when *either* flag is on, so a genuine "both off" backward-compatibility test needs both pinned).
- `tests/test_reflection.py::test_identity_evolution_trigger` and `tests/test_learning_review.py::test_default_config_still_auto_applies_directly` (renamed `test_legacy_config_still_auto_applies_directly`): both exercise the legacy direct-`evolve_persona` path and now explicitly monkeypatch `LEARNING_REVIEW_REQUIRED` to `False` instead of relying on the old default.
- `tests/test_scenarios.py::test_scenario_hostile_interaction_drift`: pins `LEARNING_REVIEW_REQUIRED` to `False` for its duration (manual save/restore, matching this test's existing `LLM_INTENT_CLASSIFICATION_ENABLED` pattern) -- this scenario is specifically about the legacy auto-apply drift landing in `identity.history`, which the new default routes through governed review instead.

### B4: Governed Learning Wiring (`learning.py`)

`ReflectionService.__init__` now also constructs `self.governor = LearningGovernor()` (from `cognitive/learning_governance.py`, the Phase 06 governance module -- kept separate from `cognitive/learning_review.py`'s `LearningReviewQueue`/`LearningProposal` per that module's own documented reasoning: different, incompatible schemas, and both are permanently-supported call shapes).

`_consolidate_persona`, when `LEARNING_REVIEW_REQUIRED` is `True`, now calls a new `_governed_persona_proposal(suggestions, contradicts_id)` **before** `self.review_queue.submit(...)`:

- Builds a real `learning_governance.LearningProposal` with `target_domain="identity.reflection_persona_suggestion"`, `proposed_value` copied from `suggestions`, `risk_class=LOW`, and `rollback_value={"relationship_before": ...}`.
- Calls `governor.submit()` -> `validate()` -> `approve()`. `submit()` raising `ValueError` (the proposal names a protected -- immutable/constitutional -- field, anywhere, including nested inside `proposed_value`) means the suggestion is dropped entirely and never reaches the review queue or `evolve_persona`.
- Otherwise the proposal is recorded (APPROVED, LOW risk auto-approves) and the suggestion proceeds to `review_queue.submit(...)` exactly as before -- the human review queue remains the actual content-approval gate; the governor is a hard content-safety filter ahead of it, not a duplicate reviewer.

**Real bug found and fixed while wiring this up:** `evolve_persona`'s own suggestion key `new_traits` (an ADAPTIVE-tier list of trait *additions*, see `PersonaProfile.learn_traits`) tokenizes to `["new", "traits"]` under `learning_governance.py`'s delimiter-splitting tokenizer, and `"traits"` alone is a protected single-word marker there because `PersonaProfile.traits` (an unrelated CONSTITUTIONAL, fixed-at-creation field) happens to be named exactly that. Every ordinary reflection suggestion carrying `new_traits` was therefore rejected outright by the very first version of this wiring -- a false positive on the one shape this call site actually produces, caught by `test_review_required_routes_to_queue_instead_of_auto_applying` failing during self-verification. A first fix attempt (JSON-serializing the whole suggestion into one opaque string value) was also wrong: it hid every key from the scanner, including a genuinely dangerous smuggled one, silently defeating the invariant -- caught by a second self-written test (`test_review_required_rejects_a_suggestion_smuggling_a_protected_field`). The final fix renames only the one known-colliding key (`new_traits` -> `new_trait_additions`, singular "trait") while every other key -- including a hypothetical smuggled `mood_decay_rate` -- passes through as a real, scannable dict key.

New tests in `tests/test_learning_review.py`:
- `test_review_required_records_a_governed_proposal_alongside_the_legacy_queue`: an ordinary suggestion registers as a real APPROVED `LearningGovernor` proposal.
- `test_review_required_rejects_a_suggestion_smuggling_a_protected_field`: a suggestion carrying `mood_decay_rate` is rejected outright -- never reaches `review_queue` or `governor.list_proposals()`.

### B5: Genuine Cross-Provider Portability Test (`tests/test_provider_portability_validation.py`, new)

Addresses the audit finding that `BM-GPU-P5-01` was a same-provider tautology. Two parts:

1. **Real client classes, network boundary mocked** (`OllamaClient` via `httpx.AsyncClient.post`, `AnthropicClient` via `self._client.messages.create`): both satisfy the `LLMClient` Protocol; `generate()` returns identical text for identical logical upstream content despite completely different wire formats; the `system` prompt reaches both transports unmodified (Ollama's `/api/chat` `messages` list vs. Anthropic's `system` kwarg); both degrade to a non-empty string (never an exception) on a transport failure.
2. **`ActionService` response processing**, parametrized over two fake `LLMClient`-shaped streaming patterns: many small, sub-word "Ollama-shaped" chunks (splitting the `<thought>` tag's own characters apart, matching CLAUDE.md's documented common case) vs. few, large "Anthropic-shaped" deltas. Both shapes produce identical `<thought>`-stripped output and identical "as an AI" identity-boundary self-correction behavior. A final test confirms `_build_shared_history` (prompt assembly) is unaffected by which client is attached to `ActionService`.

9 tests, all passing.

---

## 2. Verification & Fix Round Resolution

```
cd backend
../.venv/bin/python -m pytest -q --junit-xml=/tmp/claude_res2.xml
../.venv/bin/python -m ruff check .
../.venv/bin/python -m radon cc app/ -s -n D
```

Results (run from `/Users/aniketsaha/Projects/ai-friend-claude/backend` against `/Users/aniketsaha/Projects/AI_friend/.venv`):

- Full backend suite: **2,371 tests passed, 0 failures, 0 errors, 0 skipped** (58.887s).
- `ruff check .`: **All checks passed.**
- `radon cc app/ -s -n D`: **no output** -- zero functions at complexity grade D or worse.
- Pure 7-bit ASCII: verified across all modified files.

### Fix Round Items Resolved (orchestration/PHASE_07/FIX_PLAN.md):

1. **Resolved `test_scenarios.py::test_scenario_hostile_interaction_drift` (P7-FIX-04):**
   - Root cause identified: `tests/test_mesh.py`'s `test_config_environment_override` called `importlib.reload(config)`, destroying the singleton object identity of `Config` across previously imported modules (`learning.Config` remained pointing to the pre-reload class object, leaving its `LEARNING_REVIEW_REQUIRED` untouched by test monkeypatching).
   - Fix: Updated `test_mesh.py` to instantiate `AppSettings()` directly without destroying global module identity, and made `test_scenarios.py` defensively patch `learning.Config` and `Config` using `monkeypatch`.
2. **Unified Learning Governor & Eliminated Key Renaming Hack (P7-FIX-01/P7-FIX-05):**
   - `ReflectionService.__init__` accepts `governor: LearningGovernor | None = None`.
   - Payload preservation: `_governed_persona_proposal` passes `dict(suggestions)` without renaming `new_traits`.
   - `_ADAPTIVE_ALLOWED_FIELD_NAMES` in `learning_governance.py` exempts `new_traits` while keeping constitutional `traits` strictly protected.
3. **Surfaced Retrieval Outages on Degraded/Empty Results (P7-FIX-06):**
   - In `memories_to_activations`: handles empty content for outage memories and appends `_retrieval_outage_activation` when `last_search_error` is supplied and no outage is yet flagged.

---

## 3. NOT done / explicitly out of scope

- `backend/app/state/memory_store.py`: no changes needed as `last_search_error` was already recorded.
- `backend/tests/test_runtime_composition.py` is owned by Package A (Codex).
- Governor wiring in `learning.py` acts as a pre-flight content-safety gate ahead of the review queue rather than executing the full `activate()`/`rollback()` lifecycle.

---

## 4. Files changed

- `backend/app/agents/subconscious_agent.py`
- `backend/app/cognitive/memory_activation.py`
- `backend/app/cognitive/learning.py`
- `backend/app/cognitive/learning_governance.py`
- `backend/app/config.py`
- `backend/tests/test_action_selection.py`
- `backend/tests/test_context_assembly.py`
- `backend/tests/test_learning_governance.py`
- `backend/tests/test_learning_review.py`
- `backend/tests/test_mesh.py`
- `backend/tests/test_phase5_tom.py`
- `backend/tests/test_phase6_advanced_cognition.py`
- `backend/tests/test_provider_portability_validation.py` (new)
- `backend/tests/test_reflection.py`
- `backend/tests/test_scenarios.py`
- `orchestration/PHASE_07/CLAUDE_RESULT.md`

