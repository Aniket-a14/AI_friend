# Phase 03 Implementation Plan: Causal Affect and Global Control

Phase: PHASE_03
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 9, 10, 21, 38, 39)
Baseline Git Commit: 0827474 (Phase 02 merged to main)
Status: READY_FOR_DISPATCH

---

## 1. Executive Objective

Phase 03 establishes the causal affect and global control subsystem, proving that
internal appraisal and emotional state systematically modulate deliberation and
action selection without compromising factual truth, safety constraints, or identity boundaries.

Key architectural deliverables:
1. Four derived engineering controls (`urgency_gain`, `exploration_budget`, `effort_budget`, `learning_gain`), retiring biological names while providing backward-compatible adapters.
2. Structured appraisal engine mapping `(event, active_goals, expectation, agency, controllability)` to `AppraisalRecord` and affect deltas.
3. CandidateSelector modulation where global controls adjust scoring, deliberation budgets, and risk weighting.
4. Emotion regulation as selectable actions (`REAPPRAISE`, `REDIRECT_ATTENTION`, `WAIT`, `OBSERVE`) under acute distress rather than silent affect overwriting.
5. Invariant enforcement: global controls and affect state must never alter beliefs, identity, or bypass safety refusals.

---

## 2. Package Decomposition & Ownership

### Package A: Codex (Valuation, Appraisal & Global Control State Engine)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-codex
- Branch: codex/phase-03
- Owned Files:
  - `backend/app/cognitive/global_controls.py` (NEW)
  - `backend/app/cognitive/appraisal.py` (NEW)
  - `backend/app/state/agent_state.py` (StateService integration)
  - `backend/tests/test_causal_affect.py` (NEW)

### Package B: Claude (Action Candidate Modulation & Emotion Regulation Actions)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-claude
- Branch: claude/phase-03
- Owned Files:
  - `backend/app/cognitive/action_candidate.py`
  - `backend/app/cognitive/action_intent.py`
  - `backend/app/cognitive/decision.py`
  - `backend/app/cognitive/pipeline.py`
  - `backend/app/cognitive/action.py`
  - `backend/tests/test_global_control_selection.py` (NEW)

---

## 3. Shared Contracts (Pure 7-bit ASCII)

### A. GlobalControls Model
```python
class GlobalControls(BaseModel):
    """Four non-redundant engineering control signals (Architecture Section 10)."""
    urgency_gain: float = Field(default=0.1, ge=0.0, le=1.0)
    exploration_budget: float = Field(default=0.5, ge=0.0, le=1.0)
    effort_budget: float = Field(default=0.5, ge=0.0, le=1.0)
    learning_gain: float = Field(default=0.5, ge=0.0, le=1.0)
```

### B. AppraisalRecord Model
```python
class AppraisalRecord(BaseModel):
    """Structured valuation of one perceived event against goals and expectation."""
    event_id: str
    goal_congruence: float = Field(default=0.0, ge=-1.0, le=1.0)
    expectation: float = Field(default=0.0, ge=-1.0, le=1.0)  # -1 unexpected, +1 expected
    agency: float = Field(default=0.0, ge=-1.0, le=1.0)       # -1 other, +1 self
    controllability: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    affect_delta: dict[str, float] = Field(default_factory=dict)
```

### C. ActionKind Regulation Extensions
`ActionKind` and `ActionCandidateKind` extended with:
- `REAPPRAISE`
- `REDIRECT_ATTENTION`
- `SUPPRESS_EXPRESSION`

---

## 4. Worktree Discipline

- Codex works ONLY in `/Users/aniketsaha/Projects/ai-friend-codex`.
- Claude works ONLY in `/Users/aniketsaha/Projects/ai-friend-claude`.
- No direct branch-to-branch merging; integration occurs in `integration/phase-03`.
- All written code, tests, and documentation must be pure 7-bit ASCII.

