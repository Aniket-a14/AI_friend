# Phase 02: Memory Truth and General Action Selection -- Master Plan

**Phase Identifier:** PHASE_02
**Target Architecture Reference:** FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 8, 11, 22, 39)
**Baseline Git Commit:** 5fd816f75e84a1c1605cecff08477df8356d21a9 (Phase 01 merged to main)
**Status:** Prepared and Ready for Worker Dispatch

---

## 1. Exact Phase Objective

Make temporal memory change action selection rather than only text wording. Introduce structured memory records (ExperienceRecord, BeliefRecord, ProcedureRecord), explicit bi-temporal validity intervals (valid_from, valid_until, recorded_at), four contradiction classes (ELABORATION, UPDATE, CORRECTION, CONFLICT), structured MemoryActivation tokens with typed outage reporting, and constraint-first ActionCandidate selection before language realization.

---

## 2. Architectural Rationale: Why Phase 2 Follows Phase 1

1. Phase 01 created the closed causal loop: Percept -> CognitiveWorkspace -> ActionIntent -> OutcomeRecord.
2. In Phase 01, cognitive actions were still mostly hardcoded to chat responses, with memories injected only as raw text snippets.
3. In Phase 02, memory becomes authoritative:
   - Historical truth and current truth are distinguished via bi-temporal intervals.
   - Contradictions are explicitly classified and handled rather than silently overwritten.
   - Memories produce typed MemoryActivation tokens that feed directly into action candidate generation and selection.
   - Hard constraints (identity, boundaries, safety) filter candidates before language realization occurs.

---

## 3. Work Package Decomposition

```text
+--------------------------------------------------------------------------+
|                             PHASE 02 SLICE                               |
+-------------------------------------+------------------------------------+
|         PACKAGE A: CODEX            |         PACKAGE B: CLAUDE          |
|  (Memory Records, Temporal Truth,   |   (Retrieval Activation, Action    |
|       Contradiction Engine)         |   Candidates, Selection & Gate)    |
+-------------------------------------+------------------------------------+
| * backend/app/state/                | * backend/app/cognitive/           |
|   memory_records.py                 |   action_candidate.py              |
|   (ExperienceRecord, BeliefRecord,  |   (ActionCandidate, Candidate-     |
|    ProcedureRecord, Contradiction)  |    Selector, constraint filtering) |
| * backend/app/state/                | * backend/app/cognitive/           |
|   temporal_store.py                 |   memory_activation.py             |
|   (TemporalMemoryStore, SQLite/mem, |   (MemoryActivation, typed outage, |
|    bitemporal queries, transitions) |    AntiInjectionGate defense)      |
| * backend/tests/                    | * backend/app/cognitive/           |
|   test_memory_truth.py              |   pipeline.py & decision.py        |
|   (Interval, contradiction, CAS,    |   (Candidate selection wire,       |
|    historical vs current truth)     |    memory-driven action branch)    |
|                                     | * backend/tests/                   |
|                                     |   test_action_selection.py         |
|                                     |   (Constraint-first, ablation,     |
|                                     |    injection defense, outage test) |
+-------------------------------------+------------------------------------+
```

---

## 4. Shared Interface Contracts

Codex and Claude must adhere strictly to these contracts:

### A. Memory Records & Activation (Package A defines, Package B consumes)

```python
from dataclasses import dataclass, field
from typing import Any, Literal
from pydantic import BaseModel, Field
import time

# 1. Episodic Record
class ExperienceRecord(BaseModel):
    record_id: str
    session_id: str
    participants: list[str]
    interval_start: float
    interval_end: float
    source_evidence_ids: list[str] = Field(default_factory=list)
    appraisal_snapshot: dict[str, float] = Field(default_factory=dict)
    action_id: str | None = None
    outcome_id: str | None = None
    summary: str
    recorded_at: float = Field(default_factory=time.time)

# 2. Semantic Belief Record with Bi-temporal Intervals
class BeliefRecord(BaseModel):
    record_id: str
    subject: str
    predicate: str
    object: str
    valid_from: float
    valid_until: float | None = None  # None means currently valid
    recorded_at: float = Field(default_factory=time.time)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: Literal["ACTIVE", "SUPERSEDED", "INVALIDATED", "DISPUTED"] = "ACTIVE"
    superseded_by: str | None = None
    contradicts_id: str | None = None
    provenance: str = "conversation"

# 3. Procedural Record
class ProcedureRecord(BaseModel):
    procedure_id: str
    name: str
    preconditions: list[str] = Field(default_factory=list)
    expected_effects: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    rollback_pointer: str | None = None

# 4. Contradiction Classification
ContradictionType = Literal["ELABORATION", "UPDATE", "CORRECTION", "CONFLICT"]

class ContradictionDecision(BaseModel):
    contradiction_type: ContradictionType
    existing_record_id: str
    new_record_id: str
    action_taken: str
    reason: str

# 5. Memory Activation Token
class MemoryActivation(BaseModel):
    record_id: str
    record_type: Literal["experience", "belief", "procedure"]
    structured_value: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    validity: bool = True
    provenance: str = "memory"
    contradiction_state: Literal["NONE", "DISPUTED", "SUPERSEDED", "INVALIDATED"] = "NONE"
    outage_flag: bool = False
```

### B. Action Candidates & Selection (Package B defines, Stage 6 consumes)

```python
# Action Candidate Model
class ActionCandidate(BaseModel):
    candidate_id: str
    kind: Literal[
        "SPEAK", "ASK", "WAIT", "OBSERVE", "RETRIEVE", "VERIFY", "REFLECT", "UPDATE_GOAL"
    ]
    source: str  # "reflex", "goal", "policy", "memory_activation", "model"
    target_goal_ids: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    predicted_outcomes: list[str] = Field(default_factory=list)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    cost: float = Field(default=0.0)
    constraint_claims: list[str] = Field(default_factory=list)
    score: float = 0.0
```

---

## 5. Non-Breaking Backward Compatibility Rule

All existing tests (1,909 tests) MUST pass without regression. A configuration toggle `Config.PHASE_02_MEMORY_TRUTH` (default False during development) ensures that legacy behavior is completely preserved unless explicitly opted in.

---

## 6. Verification & Quality Gates

* Local Mac Suite: All 1,909 existing tests + new Phase 02 tests must pass.
* Static Quality: Mypy 0 errors on new files; Radon CC 0 functions with rating D or worse; Bandit 0 security findings; Codespell clean; Pre-commit hooks clean.
* GPU Validation: Memory retrieval and candidate evaluation latency benchmarks on RTX 2060 Super.

