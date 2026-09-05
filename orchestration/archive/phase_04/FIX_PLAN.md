# Phase 04 Fix Plan: Arbitration of Reciprocal Peer Reviews

Orchestrator: Gemini (Antigravity)
Date: 2026-09-04
Context: Phase 04 reciprocal peer review between Codex (`codex/phase-04`) and Claude (`claude/phase-04`).

---

## 1. Executive Arbitration Summary

Both Codex and Claude conducted thorough, code-level reviews with reproduction tests. All critical and high-priority findings are valid and accepted for resolution in the fix round.

Key Arbitrated Fixes:
1. **Package A (Codex):**
   - Fix circular import: eliminate module-level import of `CapabilityLimitationModel` in `agent_state.py` using `if TYPE_CHECKING:` and deferred factory, ensuring `pytest tests/test_state.py` passes in isolation.
   - Fix state sync: ensure `StateService` updates legacy scalar trust mirrors whenever `active_person_id` changes or a person is loaded.
   - State lock safety: enforce `_state_lock` conventions on `_get_active_person_model_locked`.
   - Robustness: skip empty/whitespace strings in `is_known_limitation`, guard numeric inputs with `math.isfinite`, reject invalid rupture/repair kinds, and fail closed in `can_disclose` when `is_private=True` but `fact_owner_id is None`.
2. **Package B (Claude):**
   - Close immutable core bypass: canonicalize target domain path segments to prevent bypass via brackets, casing, or whitespace; revalidate in `approve()` before applying.
   - Restore backward compatibility in `learning_review.py`: support legacy `submit(suggestions, ...)` call signature and adapter properties (`id`, `suggestions`, `contradicts_id`, `approve(id, identity_manager)`), so that `tests/test_learning_review.py` (10 tests) and `ReflectionService` pass cleanly without regression.
   - Reentrant foreground preemption: use reference counting for foreground activity and wrap `pipeline.execute()` in `try ... finally` to guarantee cleanup on generator exit or exception.
   - Metacognitive Candidate Selection: make `ABSTAIN` a true disqualifier for SPEAK candidates so WAIT/boundary candidates win, and give `HEDGE` a concrete metadata/directive impact.
   - Complete `GoalRecord`: add Architecture Section 11 fields (`utility_terms`, `constraints`, `parent`, `evidence_ids`, `satiation_or_expiry`).

---

## 2. Package A Fix Directives (Codex)

### Target: `codex/phase-04` (`/Users/aniketsaha/Projects/ai-friend-codex`)

1. **Circular Import Resolution in `agent_state.py`:**
   - Move `from ..cognitive.calibration import CapabilityLimitationModel` inside `if TYPE_CHECKING:`.
   - Implement `_new_capability_model()` helper:
     ```python
     def _new_capability_model() -> "CapabilityLimitationModel":
         from ..cognitive.calibration import CapabilityLimitationModel
         return CapabilityLimitationModel()
     ```
   - In `AgentState`:
     `capability_model: "CapabilityLimitationModel" = field(default_factory=_new_capability_model)`
   - Verify that `pytest tests/test_state.py` passes when executed in complete isolation.

2. **Bidirectional & Switch Sync for Active Person:**
   - In `StateService`:
     - Add `set_active_person(person_id: str) -> PersonModel`: acquires `_state_lock`, updates `current_state.active_person_id`, fetches or seeds the person model, synchronizes the legacy scalar mirror (`trust_competence`, `trust_benevolence`), and returns the model.
     - In `_get_active_person_model_locked()`: if `active_person_id` was changed directly, refresh scalar mirror to match.

3. **Lock Convention & Naming:**
   - Rename `get_active_person_model()` to `_get_active_person_model_locked()` when called inside existing locked methods.
   - Provide an async public `get_active_person_model() -> PersonModel` that acquires `_state_lock`.

4. **Input Hardening & Edge Cases:**
   - In `calibration.py` (`is_known_limitation`):
     - Filter out empty or whitespace-only limitation strings (`if not lim.strip(): continue`).
   - In `person_model.py`:
     - In `update_trust_from_reliance`: guard with `if not math.isfinite(stake_weight): return`.
     - In `record_rupture_repair`: guard with `if not math.isfinite(magnitude): return`.
     - In `record_rupture_repair`: normalize `kind = kind.lower().strip()`. If `kind not in ("rupture", "repair")`: raise `ValueError(f"Invalid rupture/repair kind: {kind}")`.
     - In `can_disclose`: if `is_private and fact_owner_id is None`: return `False` (fail closed on unowned private facts).

5. **Verification Requirements:**
   - `../.venv/bin/python -m pytest tests/test_state.py` (isolated run MUST pass).
   - `../.venv/bin/python -m pytest tests/test_social_metacognition.py`.
   - `../.venv/bin/python -m ruff check .`.
   - `../.venv/bin/python -m radon cc app --min D -s`.
   - Pure 7-bit ASCII verification on all touched files.

---

## 3. Package B Fix Directives (Claude)

### Target: `claude/phase-04` (`/Users/aniketsaha/Projects/ai-friend-claude`)

1. **Immutable Core Protection Hardening in `learning_review.py`:**
   - Normalize target domain strings by replacing brackets, colons, slashes, and dots with spaces, stripping whitespace, and lowercasing.
   - Prohibit any proposal where normalized tokens contain: `name`, `core_values`, `safety_boundaries`, `immutable`, `constitutional`.
   - Revalidate proposal safety in `approve()` before applying.
   - Add unit tests verifying rejection of bracketed paths (e.g. `persona[name]`), case variants, and attempted post-submit mutations.

2. **Backward Compatibility in `learning_review.py` for Existing Callers & Tests:**
   - Support legacy signature in `LearningReviewQueue.submit`:
     - Allow submitting raw suggestions dict: `submit(suggestions: dict[str, Any] | None = None, source: str = "reflection", speaker: str | None = None, contradicts_id: str | None = None, proposal: LearningProposal | None = None)`.
     - If `suggestions` is passed, wrap it into a `LearningProposal` with `target_domain="persona_adaptive_traits"`, `proposed_value=suggestions`, `expected_effect="reflection_update"`, `contradicts_id=contradicts_id`.
   - Add compatibility properties on `LearningProposal`:
     - `id`: alias to `proposal_id`.
     - `suggestions`: alias to `proposed_value`.
   - Add compatibility methods on `LearningReviewQueue`:
     - `pending()`: returns list of pending proposals.
     - `contradictions()`: returns pending proposals with `is_contradiction=True`.
     - Support `async def approve(proposal_id: str, identity_manager: Any | None = None)`: if `identity_manager` is supplied, apply to `identity_manager` as before.
   - Verify that `pytest tests/test_learning_review.py` passes 10/10 with 0 failures!

3. **Reentrant Foreground Preemption & Guaranteed Generator Cleanup:**
   - In `BackgroundScheduler`:
     - Replace `is_foreground_active: bool` with reentrant reference counter: `_foreground_depth: int = 0`.
     - `preempt()`: increment `_foreground_depth += 1`. Cancel active task.
     - `resume_foreground_idle()`: decrement `_foreground_depth = max(0, _foreground_depth - 1)`.
     - `is_foreground_active`: property returning `self._foreground_depth > 0`.
   - In `CognitivePipeline.execute()`:
     - Enclose the entire pipeline body in a `try ... finally` block ensuring `self._maybe_resume_background()` is guaranteed to execute on all exits, returns, exceptions, or generator teardown (`aclose()`).

4. **Metacognitive Action Modulation & ABSTAIN Enforcement:**
   - In `action_candidate.py` (`CandidateSelector`):
     - When `metacognitive_directive == "ABSTAIN"`: apply a prohibitive penalty (`-1000.0`) to any `SPEAK` candidate, or strictly reject `SPEAK` candidates so that `WAIT` or polite boundary actions are selected.
     - When `metacognitive_directive == "HEDGE"`: append a hedging marker to selected candidate's metadata or stance.

5. **GoalRecord Alignment with Architecture Section 11:**
   - In `goals.py` (`GoalRecord`):
     - Add missing Section 11 fields:
       `utility_terms: dict[str, float] = Field(default_factory=dict)`
       `constraints: list[str] = Field(default_factory=list)`
       `parent: str | None = None`
       `evidence_ids: list[str] = Field(default_factory=list)`
       `satiation_or_expiry: float | None = None`

6. **Verification Requirements:**
   - `../.venv/bin/python -m pytest tests/test_background_governed_learning.py`.
   - `../.venv/bin/python -m pytest tests/test_learning_review.py` (MUST PASS 10/10).
   - `../.venv/bin/python -m ruff check .`.
   - `../.venv/bin/python -m radon cc app --min D -s`.
   - Pure 7-bit ASCII verification on all touched files.

