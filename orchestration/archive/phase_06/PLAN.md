# Phase 06 Implementation Plan: Optional Advanced Learning and Planning

Phase: PHASE_06
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 16, 17, 19, 20, 21, 38, 40)
Baseline Git Commit: 9203f55
Status: READY_FOR_DISPATCH

---

## 1. Executive Objective

Phase 06 addresses Section 38 Phase 6 of the Humanoid Brain Architecture: "admit only advanced mechanisms that beat the simpler kernel after Phases 1-5 provide trustworthy evaluation."

In Phases 1-5, we established the authoritative causal slice (Phase 1), grounded memory and action selection (Phase 2), causal affect and global control (Phase 3), outcome-grounded self, social state, and metacognition (Phase 4), and provider/embodiment portability (Phase 5).

Phase 06 builds isolated, sound, and governed mechanisms for:
1. Verified Planning and Sandboxed Episodic Simulation:
   - Structured plan artifacts with preconditions, invariants, verifiable transitions, and fallback steps.
   - Deterministic sound plan verifier (acyclicity, reachability, invariant preservation, budget bounds).
   - Sandboxed prospective episodic simulation with strict memory quarantine (simulated records never leak into production memory).
2. Trusted Learning Governance and Progress Curiosity:
   - Section 21 LearningProposal schema, risk-tiered approval gate, and 1-step reversible rollback.
   - Hard invariant: Identity core, constitutional boundaries, and safety invariants are strictly non-targetable.
   - Learning-Progress Curiosity engine calculating empirical progress delta over sliding windows.
   - Offline Adapter Gate enforcing zero behavioral regression on held-out evals and prompt digest matching.

---

## 2. Package Decomposition and Ownership

### Package A: Codex (Verified Planning & Sandboxed Episodic Simulation)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-codex
- Branch: codex/phase-06
- Owned Files:
  - backend/app/cognitive/planning.py (NEW)
  - backend/app/cognitive/simulation.py (NEW)
  - backend/tests/test_planning_simulation.py (NEW)

### Package B: Claude (Trusted Learning Governance, Curiosity & Offline Adapter Gate)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-claude
- Branch: claude/phase-06
- Owned Files:
  - backend/app/cognitive/learning_governance.py (NEW)
  - backend/app/llm/adapter_gate.py (NEW)
  - backend/tests/test_learning_governance.py (NEW)

---

## 3. Shared Contracts (Pure 7-bit ASCII)

### A. Planning & Simulation Contracts
```python
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class PreconditionOp(str, Enum):
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    CONTAINS = "CONTAINS"
    NOT_EMPTY = "NOT_EMPTY"

class PlanPrecondition(BaseModel):
    key: str
    op: PreconditionOp
    value: Any

class PlanEffectOp(str, Enum):
    SET = "SET"
    INCREMENT = "INCREMENT"
    APPEND = "APPEND"
    DELETE = "DELETE"

class PlanEffect(BaseModel):
    key: str
    op: PlanEffectOp
    value: Any

class PlanStep(BaseModel):
    step_id: str
    name: str
    action_type: str
    preconditions: list[PlanPrecondition] = Field(default_factory=list)
    effects: list[PlanEffect] = Field(default_factory=list)
    fallback_step_id: str | None = None
    timeout_s: float = 5.0
    max_retries: int = 1

class PlanArtifact(BaseModel):
    plan_id: str
    goal_id: str
    version: int = 1
    steps: list[PlanStep]
    initial_preconditions: list[PlanPrecondition] = Field(default_factory=list)
    terminal_conditions: list[PlanPrecondition] = Field(default_factory=list)
    invariants: list[PlanPrecondition] = Field(default_factory=list)
    budget_max_steps: int = 20
    estimated_cost: float = 0.0

class PlanVerificationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    cycle_detected: bool = False
    unreachable_steps: list[str] = Field(default_factory=list)
    invariant_violations: list[str] = Field(default_factory=list)

class SimulationQuarantineViolationError(RuntimeError):
    """Raised when a simulated record or action attempts to commit to production memory/state."""
    pass
```

### B. Learning Governance & Curiosity Contracts
```python
class LearningRiskClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class LearningProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    ACTIVATED = "ACTIVATED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"

class LearningProposal(BaseModel):
    proposal_id: str
    source_records: list[str] = Field(default_factory=list)
    target_domain: str
    proposed_value: dict[str, Any]
    expected_effect: str
    risk_class: LearningRiskClass
    counterfactual_baseline: float | None = None
    approval_policy: str = "risk_tiered"
    activation_revision: int | None = None
    rollback_value: dict[str, Any] | None = None
    status: LearningProposalStatus = LearningProposalStatus.PROPOSED
    created_at: float = 0.0
    evaluated_at: float | None = None

class AdapterQualificationRequest(BaseModel):
    adapter_id: str
    base_model_tag: str
    held_out_eval_file: str
    prompt_digest: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class AdapterQualificationResult(BaseModel):
    adapter_id: str
    qualified: bool
    pass_rate: float
    regression_detected: bool
    details: dict[str, Any] = Field(default_factory=dict)
```

---

## 4. Peer Review, Arbitration, and Fix Process

1. Codex develops Package A in `ai-friend-codex`.
2. Claude develops Package B in `ai-friend-claude`.
3. Reciprocal Peer Reviews:
   - Codex reviews Claude's PR.
   - Claude reviews Codex's PR.
4. Orchestration Arbitration:
   - Antigravity reviews findings, arbitrates disputes, and generates `FIX_PLAN.md`.
5. Fix rounds applied in isolated branches.
6. Integration into `integration/phase-06`, full test suite execution, local micro-benchmarks, and remote GPU benchmarks.
7. Phase Gate evaluation and merge into `main`.

---

## 5. Hard Invariants & Code Standards

1. Pure 7-bit ASCII ONLY across all code and documentation files.
2. 0 ruff errors and 0 radon D/E/F cyclomatic complexity findings.
3. Strict simulation quarantine: zero simulated data in production memory or state stores.
4. Strict immutable core protection: zero learning modifications to identity core or safety bounds.
