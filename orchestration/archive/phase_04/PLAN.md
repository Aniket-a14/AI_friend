# Phase 04 Implementation Plan: Outcome-Grounded Self, Social State, Metacognition, and Background Work

Phase: PHASE_04
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 11, 13, 15, 19, 20, 21, 38, 40)
Baseline Git Commit: ea64b4b (Phase 03 merged to main, radon and tests green)
Status: READY_FOR_DISPATCH

---

## 1. Executive Objective

Phase 04 turns interaction history into calibrated self and social continuity, reliable metacognition,
and safe background adaptation. It eliminates ungrounded static relationship scalars and uncontrolled
background reflection, replacing them with event-grounded social models, empirical domain calibration,
budget-governed background work, and durable review/rollback proposals.

Key architectural deliverables:
1. PersonModel and Social State:
   - Event-grounded competence trust and benevolence trust separated (retiring static global trust scalar).
   - Per-person knowledge and disclosure tracking with a hard cross-person disclosure isolation invariant.
   - Rupture and repair tracking with asymmetric recovery dynamics.
2. Metacognition and Domain Calibration:
   - CapabilityLimitationModel and DomainCalibration tracking Brier scores and ECE across operational domains.
   - Metacognitive gating producing actionable directives (PROCEED, HEDGE, ASK_CLARIFICATION, VERIFY, ABSTAIN).
   - Grounded confidence replacing uncalibrated verbal LLM self-reports.
3. Background Cognition Scheduler:
   - Watermarks, execution budgets (time, tokens), priority queues, and idempotency keys.
   - Immediate preemption when foreground user interaction arrives.
   - Owner-authorized writes: background tasks emit structured results; only designated services may commit them.
4. Grounded Background Jobs:
   - Due-goal review checking GoalRecord deadlines, priorities, and progress against time watermarks.
   - Contradiction queue processing and categorization (ELABORATION, UPDATE, CORRECTION, CONFLICT).
5. Governed Learning Proposals with Durable Review & Rollback:
   - Evolution of reflection into structured LearningProposal generation.
   - Proposal review queue supporting APPROVE, REJECT, and ROLLBACK with complete audit trail.
   - Strict invariant: immutable persona core and safety boundaries can never be proposed or modified.

---

## 2. Package Decomposition and Ownership

### Package A: Codex (Outcome-Grounded Self, Social State and Calibration Engine)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-codex
- Branch: codex/phase-04
- Owned Files:
  - `backend/app/state/person_model.py` (NEW)
  - `backend/app/cognitive/calibration.py` (NEW)
  - `backend/app/state/agent_state.py` (Integration with PersonModel and Calibration)
  - `backend/tests/test_social_metacognition.py` (NEW)

### Package B: Claude (Background Scheduler, Due-Goal Review, Contradiction Queue and Governed Learning)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-claude
- Branch: claude/phase-04
- Owned Files:
  - `backend/app/cognitive/background_scheduler.py` (NEW)
  - `backend/app/cognitive/goals.py` (NEW: GoalRecord and DueGoalReview)
  - `backend/app/cognitive/learning_review.py` (Durable review and rollback)
  - `backend/app/cognitive/decision.py` (Metacognitive directive and social privacy filtering)
  - `backend/app/cognitive/pipeline.py` (Foreground preemption and calibration integration)
  - `backend/tests/test_background_governed_learning.py` (NEW)

---

## 3. Shared Contracts (Pure 7-bit ASCII)

### A. PersonModel and Social State
```python
class PersonModel(BaseModel):
    """Event-grounded social state for one interacted person (Architecture Section 15)."""
    person_id: str
    name: str | None = None
    identity_keys: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    current_knowledge: dict[str, Any] = Field(default_factory=dict)
    disclosures: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    observed_goals: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    rupture_repair_history: list[dict[str, Any]] = Field(default_factory=list)
    trust_competence: float = Field(default=0.5, ge=0.0, le=1.0)
    trust_benevolence: float = Field(default=0.5, ge=0.0, le=1.0)
```

### B. Metacognitive Directives & Calibration
```python
class MetacognitiveDirective(str, Enum):
    PROCEED = "PROCEED"
    HEDGE = "HEDGE"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    VERIFY = "VERIFY"
    ABSTAIN = "ABSTAIN"

class DomainCalibration(BaseModel):
    """Empirical calibration metrics by domain (Architecture Section 20)."""
    domain: str
    sample_count: int = 0
    brier_score: float = 0.0
    expected_calibration_error: float = 0.0
    known_limitations: list[str] = Field(default_factory=list)
```

### C. Background Jobs and Watermarks
```python
class BackgroundJobKind(str, Enum):
    DUE_GOAL_REVIEW = "DUE_GOAL_REVIEW"
    CONTRADICTION_QUEUE = "CONTRADICTION_QUEUE"
    RELATIONSHIP_STATISTICS = "RELATIONSHIP_STATISTICS"
    EPISODIC_CLUSTERING = "EPISODIC_CLUSTERING"
    CALIBRATION_UPDATE = "CALIBRATION_UPDATE"

class BackgroundJob(BaseModel):
    """Budgeted, watermarked background maintenance task (Architecture Section 19)."""
    job_id: str
    kind: BackgroundJobKind
    watermark: float = 0.0
    budget_tokens: int = 500
    budget_time_s: float = 5.0
    priority: int = 50
    idempotency_key: str
    allowed_writes: list[str] = Field(default_factory=list)
```

### D. Governed Learning Proposals with Rollback
```python
class LearningProposalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"

class LearningProposal(BaseModel):
    """Governed proposal for persistent adaptation (Architecture Section 21)."""
    proposal_id: str
    created_at: str
    source: str
    target_domain: str
    proposed_value: Any
    expected_effect: str
    risk_class: str = "LOW"
    counterfactual_baseline: str | None = None
    approval_policy: str = "REVIEW_REQUIRED"
    rollback_value: Any = None
    status: LearningProposalStatus = LearningProposalStatus.PENDING
```

---

## 4. Worktree Discipline

- Codex works ONLY in `/Users/aniketsaha/Projects/ai-friend-codex`.
- Claude works ONLY in `/Users/aniketsaha/Projects/ai-friend-claude`.
- Integration and regression verification occurs in `/Users/aniketsaha/Projects/ai-friend-integration`.
- All written code, tests, and documentation must be pure 7-bit ASCII.

