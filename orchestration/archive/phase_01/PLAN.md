# Phase 01: Authoritative Causal Slice — Master Plan

**Phase Identifier:** `PHASE_01`  
**Target Architecture Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (§38 & §39)  
**Baseline Git Commit:** `bb5be86ba7c14ab7f8afa056707597a37d3bdd86`  
**Execution Date:** Scheduled for execution tomorrow  
**Status:** Prepared & Gate-Ready (Implementation strictly frozen today)

---

## 1. Exact Phase Objective

Introduce an authoritative `CognitiveWorkspace` as the single resumable source of truth for active foreground cognition, fed by an internal normalized `PerceptEnvelope`, committing an explicit `ActionIntent` before execution, and recording a terminal `OutcomeRecord` upon speech completion or interruption truncation.

This creates a complete, closed **Percept → Workspace → ActionIntent → Outcome** causal trace with durable restart epochs and compare-and-swap (CAS) concurrency guards.

---

## 2. Architectural Rationale: Why Phase 1 is First

As established in `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` §38 and §39:
1. **Prerequisite for All Causal Claims:** Today, cognitive turns assemble ephemeral context from fragmented dictionaries (`BrainAgent` attributes, `SessionState`, `StateService`, raw NATS payloads). The agent cannot prove whether a downstream response was caused by internal cognitive state, a retrieved memory, or an arbitrary foundation-model hallucination.
2. **Missing Causal Link:** Interrupted turns truncate history in `ConversationHistoryStore`, but no structured record connects the original `BehaviorDecision` with the actual number of characters/audio delivered to the user.
3. **Multi-Writer & Restart Vulnerability:** `StateService` has in-memory locking and local revision counters, but revisions reset to zero on process restart, causing spurious stale-write conflicts or silent overwrites across processes.
4. **Foundation for Subsequent Phases:** Memory truth (Phase 2), causal affect & neuromodulation (Phase 3), self/social models (Phase 4), and provider portability (Phase 5) all require attributing outcomes to specific state revisions and intent decisions. Without Phase 1, subsequent evaluations cannot distinguish cognition from prompt alterations.

---

## 3. Current Relevant Architecture

* **Session State:** `backend/app/state/session_state.py` defines `SessionState` backed by `WorkingMemoryStore` (Redis + SQLite fallback). However, `load_session_state` has no production caller on turn initialization or recovery; turns start afresh without resuming active state.
* **Agent State & CAS:** `backend/app/state/agent_state.py` tracks PAD affect and local revision counters (`revision`, `writer_id`), but these are non-persistent across restarts and do not encompass workspace focus, active goals, or pending action intents.
* **Perception:** `backend/app/cognitive/perception.py` parses `CognitiveEvent` with heuristic intent classification, while `brain_agent.py` subscribes separately to `chat.input`, `vision.description`, `vision.facial_reflex`, `audio.playback.progress`, and `audio.stop`. There is no unified envelope with calibrated confidence, modality provenance, and sensor staleness.
* **Action Decision:** `backend/app/cognitive/behavior_contracts.py` defines `BehaviorDecision` and `CommunicativeIntent`. However, these are immediately converted into prompt injection text in `action.py` rather than being committed as a durable `ActionIntent`.
* **Interruption & Outcomes:** `brain_agent.py` truncates stored text in `_truncate_interrupted_reply` based on `last_audio_progress`, but does not emit or persist an `OutcomeRecord` linking the planned intent to the truncated result.

---

## 4. Intended End State

1. **Authoritative `CognitiveWorkspace`:**
   * Contains: `session_id`, `epoch` (persisted monotonic restart generation counter), `revision` (monotonic per-write counter), `focus`, `active_goals`, `pending_action`, `affect_snapshot`, `last_percept_id`, `updated_at`.
   * Managed by a single-owner repository `WorkspaceStore` supporting CAS commits (`commit_transition(expected_epoch, expected_revision, command)`) and deterministic conflict rejection.
2. **Normalized `PerceptEnvelope`:**
   * All incoming sensor and mesh events (`chat.input`, `audio.perception`, `vision.description`, `vision.facial_reflex`, `system.tick`, `audio.playback.progress`) convert into a unified `PerceptEnvelope` carrying `percept_id`, `modality`, `source`, `observed_at`, `confidence`, and structured observables before entering cognition.
3. **Explicit `ActionIntent` & `OutcomeRecord`:**
   * Stage 6 commits an `ActionIntent` (`intent_id`, `turn_id`, `workspace_revision`, `kind`, `behavior_decision`, `committed_at`).
   * When playback completes or is interrupted, `BrainAgent` emits and stores an `OutcomeRecord` (`outcome_id`, `intent_id`, `status: COMPLETED | TRUNCATED | CANCELLED`, `actual_delivered_text`, `character_offset`, `elapsed_ms`, `error`).
4. **Dual-Write Compatibility:**
   * A feature flag `Config.WORKSPACE_AUTHORITATIVE` (default `False` during initial verification, enabled during validation) allows non-breaking parallel dual-writing alongside existing `SessionState` so no existing test breaks.

---

## 5. Work Package Decomposition

To prevent merge conflicts and duplicated effort, responsibilities are split along strict architectural boundaries:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             PHASE 01 SLICE                               │
├─────────────────────────────────────┬────────────────────────────────────┤
│         PACKAGE A: CODEX            │         PACKAGE B: CLAUDE          │
│    (Plumbing, State & CAS Store)    │   (Percept, Pipeline & Causal Loop)│
├─────────────────────────────────────┼────────────────────────────────────┤
│ • backend/app/state/workspace.py    │ • backend/app/cognitive/percept.py │
│   (CognitiveWorkspace models)       │   (PerceptEnvelope normalization)  │
│ • backend/app/state/                │ • backend/app/cognitive/           │
│   workspace_store.py                │   action_intent.py                 │
│   (WorkspaceStore, CAS, Epoch,      │   (ActionIntent & OutcomeRecord)   │
│    SQLite/Redis persistence)        │ • backend/app/cognitive/           │
│ • backend/app/state/                │   pipeline.py                      │
│   session_state.py                  │   (Workspace transition seam)      │
│   (Dual-write adapter hook)         │ • backend/app/agents/              │
│ • backend/tests/                    │   brain_agent.py                   │
│   test_workspace_store.py           │   (Percept conversion & outcome)   │
│   (CAS, conflict, epoch recovery)   │ • backend/tests/                   │
│                                     │   test_causal_slice.py             │
│                                     │   (End-to-end trace verification)  │
└─────────────────────────────────────┴────────────────────────────────────┘
```

---

## 6. Shared Interface Contracts

Codex and Claude must adhere strictly to these frozen contracts. Neither agent may alter field names or types without orchestrator approval:

```python
# Shared Domain Contract: CognitiveWorkspaceSnapshot
@dataclass(frozen=True)
class CognitiveWorkspaceSnapshot:
    session_id: str
    epoch: int
    revision: int
    focus: str | None
    active_goals: list[str]
    pending_action: dict[str, Any] | None
    affect_snapshot: dict[str, float]
    last_percept_id: str | None
    updated_at: float

# Shared Domain Contract: WorkspaceCommand
@dataclass
class WorkspaceCommand:
    session_id: str
    expected_epoch: int
    expected_revision: int
    percept_id: str | None = None
    focus_update: str | None = None
    add_goals: list[str] = field(default_factory=list)
    remove_goals: list[str] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    affect_update: dict[str, float] | None = None
    command_source: str = "pipeline"
```

```python
# Shared Domain Contract: PerceptEnvelope
class PerceptEnvelope(BaseModel):
    percept_id: str
    modality: Literal["text", "audio", "vision", "reflex", "system", "playback"]
    source: str
    observed_at: float
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    text_content: str | None = None
    provenance: str = "nats"

# Shared Domain Contract: ActionIntent
class ActionIntent(BaseModel):
    intent_id: str
    turn_id: str
    workspace_epoch: int
    workspace_revision: int
    kind: Literal["SPEAK", "ASK", "WAIT", "OBSERVE", "REFLECT", "INTERRUPT"]
    behavior_decision: dict[str, Any]
    committed_at: float = Field(default_factory=time.time)

# Shared Domain Contract: OutcomeRecord
class OutcomeRecord(BaseModel):
    outcome_id: str
    intent_id: str
    turn_id: str
    status: Literal["COMPLETED", "TRUNCATED", "CANCELLED", "FAILED"]
    actual_delivered_text: str | None = None
    character_offset: int = 0
    elapsed_ms: float = 0.0
    recorded_at: float = Field(default_factory=time.time)
    error: str | None = None
```

---

## 7. Architecture Invariants to Enforce

1. **State Ownership & Epoch Invariant:** Every workspace write requires `(expected_epoch, expected_revision)`. Stale writes MUST raise `StaleWorkspaceError` and be rejected.
2. **Causal Trace Completeness:** Every `ActionIntent` MUST reference the exact `workspace_revision` and `workspace_epoch` from which it was derived.
3. **No Unbounded Growth:** `CognitiveWorkspace` stores active foreground context only. Deep memories stay in `MemoryStore`; graph relationships stay in `GraphDB`.
4. **Outcome Attribution:** Interrupted turns MUST produce an `OutcomeRecord` with `status="TRUNCATED"` and exact `character_offset`, matching what was actually heard by the user.
5. **Zero Breaking Changes:** Existing tests (`1834` passing) and CLI tools must pass untouched when `Config.WORKSPACE_AUTHORITATIVE = False`.

---

## 8. Verification Strategy

### A. Local Validation (Mac — Executable Tomorrow)
* **Unit Concurrency Tests:** Verify CAS rejection under 50 concurrent simulated writers; test epoch increments across simulated crashes.
* **Perception Normalization Tests:** Verify that text, audio, vision description, and facial reflex events map losslessly to `PerceptEnvelope`.
* **Causal Trace Tests:** Execute full turns through `BrainAgent` and verify that `CognitiveWorkspaceSnapshot` updates, `ActionIntent` is recorded, and `OutcomeRecord` is durably logged.
* **Regression Suite:** `../.venv/bin/python -m pytest` must pass all 1,834 existing tests.
* **Pre-commit Hooks:** All configured pre-commit hooks (`pre-commit run --all-files`) must pass clean.
* **Cyclomatic Complexity (Radon):** Zero D/E/F tier functions (`radon cc app/ --min D -s`) and maintainability index check (`radon mi app/`).
* **Static Type Checking (Mypy):** Zero type regressions (`mypy app`).
* **Mutation Testing (Mutmut):** Zero surviving mutants on critical concurrency and causal tracing paths (`mutmut run`).
* **Security Scanning (Bandit):** Zero security vulnerabilities (`bandit -r app/ -c pyproject.toml`).
* **Linting & Formatting (Ruff):** Code formatting and linting clean (`ruff check .` and `ruff format --check .`).
* **Spell Checking (Codespell):** Clean dictionary check (`codespell`).

### B. Remote GPU Benchmarks (RTX 2060 Super — PENDING_GPU)
* When the GPU server is online tomorrow:
  * End-to-end cognitive turn latency with live Ollama inference.
  * Live acoustic interruption latency and truncation verification.
  * 20-turn live conversational state-stability soak test.

---

## 9. Integration Strategy

1. Codex and Claude work independently in `../ai-friend-codex` and `../ai-friend-claude`.
2. Each agent writes a result summary (`CODEX_RESULT.md`, `CLAUDE_RESULT.md`).
3. Cross-peer review:
   * Claude reviews `codex/phase-01` -> `CLAUDE_REVIEW_OF_CODEX.md`
   * Codex reviews `claude/phase-01` -> `CODEX_REVIEW_OF_CLAUDE.md`
4. Gemini arbitrates findings in `FIX_PLAN.md` (`ACCEPT`, `MODIFY`, `REJECT`, `NEEDS_TEST`).
5. Original owners apply accepted fixes.
6. Merge into `integration/phase-01` in `../ai-friend-integration`.
7. Local validation suite runs on integration worktree.
8. GPU benchmarks run tomorrow on RTX 2060 Super.
9. Final Phase Gate evaluation in `PHASE_GATE.md`.

