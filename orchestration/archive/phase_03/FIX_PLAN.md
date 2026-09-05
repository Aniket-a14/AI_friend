# Phase 03 Fix Plan: Arbitration and Resolution

Date: 2026-09-04
Phase: 03 (Causal Affect and Global Control)
Status: IN_PROGRESS (Fix Round)

## 1. Executive Summary

Both reciprocal peer reviews have completed with deep architectural and security scrutiny:
- Claude reviewed Codex: 9 findings (2 High, 5 Medium, 2 Low).
- Codex reviewed Claude: 5 findings (2 Blocker, 1 High, 2 Medium).

Gemini (Orchestrator) has arbitrated all findings. This document records the verdict and
action items for Codex (Package A) and Claude (Package B).

---

## 2. Arbitration of Claude Review of Codex (Package A)

### H1 [HIGH] `release_adrenaline` does not refresh global controls
- Verdict: ACCEPT
- Rationale: Adrenaline burst changes `AgentState.arousal`, which is a direct input to `urgency_gain`. When a startle or barge-in event triggers `release_adrenaline`, `urgency_gain` must reflect the burst immediately.
- Action: Call `self._refresh_global_controls_locked()` inside `release_adrenaline`'s `async with self._state_lock:` block.

### H2 [HIGH] Structured appraisal engine (`appraise_event` / `AppraisalRecord`) disconnected from live loop
- Verdict: ACCEPT WITH MODIFICATION
- Rationale: The new pure appraisal reducer was only exercised in unit tests while live state updates used relevance/novelty proxies.
- Action: Wire `appraise_event` into `StateService.apply_affect_delta` or provide an integrated helper `appraise_and_update(event_metadata, active_goals)` that computes an `AppraisalRecord` and feeds genuine appraisal inputs into `_refresh_global_controls_locked`.

### M1 [MEDIUM] NaN/inf inputs silently clamp to 1.0 in `_unit_interval`
- Verdict: ACCEPT
- Rationale: `min(1.0, nan)` returns 1.0 in Python, causing NaN to become maximum intensity instead of a safe default.
- Action: Guard against non-finite values: if `not math.isfinite(value)`, return default 0.0 (or neutral 0.5) before clamping. Add unit tests for NaN and inf inputs.

### M2 [MEDIUM] `exploration_budget` formula omits positive arousal
- Verdict: ACCEPT
- Rationale: Architecture Section 10 explicitly lists "positive arousal" as an exploration driver.
- Action: Update `exploration_budget` in `derive_global_controls` to incorporate both positive valence and positive arousal:
  `exploration_budget = 0.15 + 0.20*positive_arousal + 0.20*positive_valence + 0.25*bounded_prediction_error + 0.20*available_capacity`.

### M3 [MEDIUM] Endocrine backward-compatibility adapters uncalled
- Verdict: ACCEPT WITH MODIFICATION
- Rationale: The functions exist and pass tests, but live integration should verify round-trip integrity.
- Action: Ensure docstrings and unit tests verify bidirectional fidelity and expose them for the action execution sampling layer.

### M4 [MEDIUM] Mutable `affect_delta` dict in `AppraisalRecord`
- Verdict: ACCEPT
- Rationale: Shallow `frozen=True` does not prevent in-place mutation of nested dicts.
- Action: Wrap or validate `affect_delta` to ensure immutability (or document caller non-mutation).

### M5 [MEDIUM] Test assertions in `test_causal_affect.py`
- Verdict: ACCEPT
- Rationale: Clean test hygiene.
- Action: Strengthen tests to assert that `GlobalControls` remains immutable when passed into selection.

---

## 3. Arbitration of Codex Review of Claude (Package B)

### B1 [BLOCKER] `score_and_select` does not guarantee constraint-first selection
- Verdict: ACCEPT
- Rationale: If a caller passes candidates directly to `score_and_select` without pre-filtering, a forbidden candidate can win on high control score alone, violating Architecture Section 34 Invariant 6.
- Action:
  1. Update `CandidateSelector.score_and_select(...)` to accept optional `forbidden_claims: list[str] | None = None`.
  2. If `forbidden_claims` is provided, automatically run `self.filter_constraints(candidates, forbidden_claims)` before scoring.
  3. If not provided or if all candidates are filtered, ensure safe fallback handling.
  4. Add an adversarial test passing forbidden candidates directly to `score_and_select` under maximal urgency and exploration controls.

### B2 [BLOCKER] Regulation output crosses transport before identity safety validation
- Verdict: ACCEPT
- Rationale: `_execute_reappraise` and `_execute_redirect_attention` yielded unvalidated model text directly without `ControlMarkupSanitizer` or identity boundary validation, allowing acute distress turns to leak unsafe text before Stage 9 validation.
- Action:
  1. Sanitize model output using `ControlMarkupSanitizer` and validate text against identity boundaries before yielding any content chunk in `_execute_reappraise` and `_execute_redirect_attention`.
  2. If validation fails or unsafe markup is detected, yield the deterministic fallback line (`_REAPPRAISE_FALLBACK_LINE` / `_REDIRECT_ATTENTION_FALLBACK_LINE`).
  3. Add test verifying that an unsafe regulation generation is suppressed and replaced by the fallback line.

### H3 [HIGH] Regulation fallback does not cover stalled streams
- Verdict: ACCEPT
- Rationale: A hanging LLM stream causes the regulation turn to freeze without producing an utterance.
- Action: Wrap the generation stream iteration in `asyncio.wait_for` with `timeout=Config.LLM_STREAM_MAX_SECONDS`; on timeout, yield the deterministic fallback line. Add test for stalled stream timeout.

### M6 [MEDIUM] Phase 03 activation silently requires Phase 02 flag
- Verdict: ACCEPT
- Rationale: In `decision.py::_plan_social_response`, candidate selection was nested under `Config.PHASE_02_MEMORY_TRUTH`, so enabling only `Config.PHASE_03_AFFECT_CONTROL` resulted in no candidate selection or regulation actions.
- Action: Trigger candidate selection if `Config.PHASE_02_MEMORY_TRUTH or Config.PHASE_03_AFFECT_CONTROL`. If Phase 02 is False, supply an empty `memory_activations` list. Add regression test for `PHASE_03_AFFECT_CONTROL=True, PHASE_02_MEMORY_TRUTH=False`.

### M7 [MEDIUM] Dict-shaped global controls unvalidated in `_control_value`
- Verdict: ACCEPT
- Rationale: Duck-typed dict inputs could pass `urgency_gain=1000` or `inf`, bypassing bounds.
- Action: In `_control_value`, check `math.isfinite(val)` and clamp values to `[0.0, 1.0]`. Add tests for out-of-range and non-finite dict inputs.

---

## 4. Next Steps

1. Dispatch `CODEX_FIX_TASK.md` to `/Users/aniketsaha/Projects/ai-friend-codex`.
2. Dispatch `CLAUDE_FIX_TASK.md` to `/Users/aniketsaha/Projects/ai-friend-claude`.
3. Update `peer_review_prompts` artifact with single-paragraph prompts.

