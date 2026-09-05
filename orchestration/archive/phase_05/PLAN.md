# Phase 05 Implementation Plan: Provider and Embodiment Portability

Phase: PHASE_05
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 23, 24, 25, 27, 28, 29, 38, 40)
Baseline Git Commit: 09f5d42 (Phase 04 merged to main, radon and tests clean)
Status: READY_FOR_DISPATCH

---

## 1. Executive Objective

Phase 05 proves that the stable brain kernel survives specialist-provider and embodiment changes.
The brain owns authoritative state, identity invariants, memory meaning, appraisal, goals, attention,
action commitment, outcome tracking, and governed adaptation. Foundation models, voice engines, vision
systems, and external actuators are replaceable specialist adapters, not cognition.

Key architectural deliverables:
1. Foundation Model Boundary and Provider Negotiation:
   - Explicit ModelRole taxonomy: INTERPRETATION, CANDIDATE_GENERATION, PLANNING, EVALUATION, COMPRESSION, REALIZATION.
   - Role execution contract: role, schema, evidence IDs, allowed claims, token/time budgets, validator, fallback.
   - Provider capability negotiation matching requirements against model capabilities and executing graceful fallbacks (Scenarios A/B/C) without bypassing authoritative state or safety policy.
2. Voice Boundary and Compilers:
   - Versioned SpeechIntent schema capturing semantic text, dialogue act, affect, epistemics, relationship stance, delivery (rate, pitch, energy, style), timeline markers (pause, emphasis, vocalization), and turn policy.
   - At least two voice compilers:
     * ElevenLabsVoiceCompiler (cloud advanced compiler with rich style/delivery support)
     * GPTSoVITSVoiceCompiler (local reference compiler with SSML/pitch/rate support and fallback)
   - IntentLossTelemetry tracking dropped and substituted dimensions per compilation.
   - Backward-compatible migration adapter for legacy expression wire.
3. Structured Vision Boundary:
   - StructuredVisionPercept schema: track IDs, identity estimates, detected objects, actions/events, gaze/head pose, facial observables (action units, never emotion facts), scene deltas, spatial relations, confidence, and staleness.
   - Two vision adapters:
     * VLMCaptionVisionAdapter (adapts unstructured captions/descriptions to low-confidence structured observations)
     * SpatialTrackingVisionAdapter (produces structured track IDs, objects, action units, spatial relations)
   - Strict invariant: vision observations never directly overwrite affect, trust, goals, or relationship state.
4. High-Level External Action Protocol:
   - ExternalActionIntent: action_id, tool_or_actuator, parameters, preconditions, expected_effects, reversibility, risk_level, authorization_token, timeout_s.
   - ExternalActionDispatcher: pre-flight checks, authorization and safety filtering, execution dispatch, and terminal OutcomeRecord integration.

---

## 2. Package Decomposition and Ownership

### Package A: Codex (Voice Boundary and External Action Protocol)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-codex
- Branch: codex/phase-05
- Owned Files:
  - backend/app/cognitive/speech_intent.py (NEW)
  - backend/app/voice/__init__.py (NEW)
  - backend/app/voice/compiler.py (NEW)
  - backend/app/cognitive/external_action.py (NEW)
  - backend/tests/test_voice_external_action.py (NEW)

### Package B: Claude (Foundation Model Roles and Structured Vision Boundary)
- Target Directory: /Users/aniketsaha/Projects/ai-friend-claude
- Branch: claude/phase-05
- Owned Files:
  - backend/app/llm/model_roles.py (NEW)
  - backend/app/cognitive/vision_percept.py (NEW)
  - backend/app/vision/adapters.py (NEW)
  - backend/tests/test_model_roles_vision.py (NEW)

---

## 3. Shared Contracts (Pure 7-bit ASCII)

### A. Model Roles and Capability Negotiation
```python
class ModelRole(str, Enum):
    INTERPRETATION = "INTERPRETATION"
    CANDIDATE_GENERATION = "CANDIDATE_GENERATION"
    PLANNING = "PLANNING"
    EVALUATION = "EVALUATION"
    COMPRESSION = "COMPRESSION"
    REALIZATION = "REALIZATION"

class RoleExecutionRequest(BaseModel):
    role: ModelRole
    prompt: str
    system_prompt: str | None = None
    schema_definition: dict[str, Any] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    budget_tokens: int = 512
    budget_time_s: float = 10.0
    model_tag: str | None = None

class RoleExecutionResult(BaseModel):
    role: ModelRole
    raw_output: str
    parsed_output: Any = None
    validated: bool = True
    fallback_applied: bool = False
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str | None = None
```

### B. Voice Boundary and SpeechIntent
```python
class SpeechAffect(BaseModel):
    valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0)
    dominance: float = Field(default=0.0, ge=-1.0, le=1.0)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    optional_label_hint: str | None = None

class SpeechEpistemics(BaseModel):
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    hedge_required: bool = False

class SpeechRelationship(BaseModel):
    stance: str = "WARM"
    familiarity: float = Field(default=0.5, ge=0.0, le=1.0)
    register: str = "CASUAL"

class SpeechDelivery(BaseModel):
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    relative_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    relative_pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    relative_energy: float = Field(default=1.0, ge=0.5, le=2.0)
    style: str | None = None

class TimelineMarkerKind(str, Enum):
    PAUSE = "PAUSE"
    EMPHASIS = "EMPHASIS"
    VOCALIZATION = "VOCALIZATION"

class SpeechTimelineMarker(BaseModel):
    kind: TimelineMarkerKind
    text_span: str
    strength_or_duration: float = 0.5
    reason: str = ""

class SpeechTurnPolicy(BaseModel):
    start_deadline: float = 0.0
    yield_after: bool = True
    expect_response: bool = True
    interruptible: bool = True
    barge_in_behavior: str = "IMMEDIATE_STOP"

class SpeechIntent(BaseModel):
    schema_version: str = "1.0.0"
    intent_id: str
    turn_id: str
    addressee: str = "user"
    semantic_text: str
    dialogue_act: str = "STATEMENT"
    objective: str = "INFORM"
    claim_evidence_ids: list[str] = Field(default_factory=list)
    affect: SpeechAffect = Field(default_factory=SpeechAffect)
    epistemics: SpeechEpistemics = Field(default_factory=SpeechEpistemics)
    relationship: SpeechRelationship = Field(default_factory=SpeechRelationship)
    delivery: SpeechDelivery = Field(default_factory=SpeechDelivery)
    timeline: list[SpeechTimelineMarker] = Field(default_factory=list)
    turn_policy: SpeechTurnPolicy = Field(default_factory=SpeechTurnPolicy)
    locale: str = "en-US"
    pronunciation_hints: list[str] = Field(default_factory=list)
    safety_constraints: list[str] = Field(default_factory=list)

class IntentLossRecord(BaseModel):
    compiler_id: str
    intent_id: str
    dropped_dimensions: list[str] = Field(default_factory=list)
    substituted_dimensions: dict[str, Any] = Field(default_factory=dict)
    fidelity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
```

### C. Structured Vision Boundary
```python
class IdentityEstimate(BaseModel):
    person_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bounding_box: list[float] | None = None

class DetectedObject(BaseModel):
    label: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bounding_box: list[float] | None = None
    spatial_relation: str | None = None

class FacialObservable(BaseModel):
    action_units: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    muscle_movement: str = ""
    # Invariant: emotional facts are strictly prohibited in vision observations.

class SpatialRelation(BaseModel):
    subject: str
    relation: str
    object: str

class StructuredVisionPercept(BaseModel):
    track_ids: list[str] = Field(default_factory=list)
    identity_estimates: list[IdentityEstimate] = Field(default_factory=list)
    objects: list[DetectedObject] = Field(default_factory=list)
    actions_events: list[str] = Field(default_factory=list)
    gaze_pose: dict[str, float] | None = None
    facial_observables: list[FacialObservable] = Field(default_factory=list)
    scene_deltas: list[str] = Field(default_factory=list)
    spatial_relations: list[SpatialRelation] = Field(default_factory=list)
    staleness_ms: float = 0.0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str = "structured_vision"
```

### D. High-Level External Action Protocol
```python
class ActionReversibility(str, Enum):
    REVERSIBLE = "REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"

class ActionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ExternalActionIntent(BaseModel):
    action_id: str
    turn_id: str
    tool_or_actuator: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    expected_effects: list[str] = Field(default_factory=list)
    reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    risk_level: ActionRiskLevel = ActionRiskLevel.LOW
    authorization_token: str | None = None
    timeout_s: float = 10.0
```

---

## 4. Worktree Discipline

- Codex works ONLY in /Users/aniketsaha/Projects/ai-friend-codex.
- Claude works ONLY in /Users/aniketsaha/Projects/ai-friend-claude.
- Integration and regression verification occurs in /Users/aniketsaha/Projects/ai-friend-integration.
- All written code, tests, and documentation must be pure 7-bit ASCII.
- Zero ruff errors and zero radon D/E/F cyclomatic complexity.
