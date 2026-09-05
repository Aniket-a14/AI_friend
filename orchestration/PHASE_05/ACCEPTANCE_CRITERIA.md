# Phase 05 Acceptance Criteria

Phase: PHASE_05
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 23, 24, 25, 27, 28, 29, 38, 40)
Baseline Git Commit: 09f5d42

---

## Acceptance Criteria Checklist

| ID | Category | Requirement | Target Metric | Verification Method |
|---|---|---|---|---|
| **AC-P5-01** | Model Roles | Explicit ModelRole execution contracts with schema, budget, evidence IDs, validator, and fallback | 100% adherence across all 6 roles | test_model_roles_vision.py |
| **AC-P5-02** | Negotiation | Provider capability negotiation matches requirements and applies graceful fallbacks without state/policy bypass | Correct fallback across Scenarios A/B/C | test_model_roles_vision.py |
| **AC-P5-03** | Voice Boundary | SpeechIntent schema models all Section 23 dimensions (affect, epistemics, relationship, delivery, timeline, turn policy) | Schema validation passes | test_voice_external_action.py |
| **AC-P5-04** | Voice Compilers | At least two voice compilers (ElevenLabs, GPT-SoVITS) compile SpeechIntent to valid provider payloads | Conformance suite passes both | test_voice_external_action.py |
| **AC-P5-05** | Telemetry | IntentLossTelemetry tracks dropped and substituted dimensions with explicit fidelity scores | 100% loss/substitution captured | test_voice_external_action.py |
| **AC-P5-06** | Migration | Legacy expression wire (AgentVoiceModulation) converts bi-directionally with SpeechIntent | Backward compatibility verified | test_voice_external_action.py |
| **AC-P5-07** | Vision Percept | StructuredVisionPercept models tracks, identities, objects, actions, gaze pose, facial action units, spatial relations | Schema validation passes | test_model_roles_vision.py |
| **AC-P5-08** | Vision Adapters | Two vision adapters (VLMCaptionVisionAdapter, SpatialTrackingVisionAdapter) emit normalized PerceptEnvelope | Conformance suite passes both | test_model_roles_vision.py |
| **AC-P5-09** | Brain Invariant | Vision percepts never directly overwrite affect, trust, or goals; facial observables are never emotion facts | Strictly zero direct mutation | test_model_roles_vision.py |
| **AC-P5-10** | External Action | ExternalActionIntent enforces risk levels, reversibility, and authorization token gating | Unauthorized actions blocked 100% | test_voice_external_action.py |
| **AC-P5-11** | Action Outcome | External action execution generates terminal OutcomeRecord with accurate duration and status | Correct status and latency | test_voice_external_action.py |
| **AC-P5-12** | Code Quality | Code hygiene standards: pure 7-bit ASCII, zero ruff violations, zero radon D/E/F cyclomatic complexity | 0 errors, 0 rank D/E/F | ruff check ., radon cc app/ -s -n D |
