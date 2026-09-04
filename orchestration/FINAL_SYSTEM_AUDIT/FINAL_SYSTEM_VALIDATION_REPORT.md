# Final System Validation Report

Phase: FINAL_SYSTEM_AUDIT
Date: 2026-09-04
Orchestrator: Gemini (Antigravity Orchestration Lead)
Independent Auditors:
- Codex: Engineering / Runtime / Integration Audit
- Claude: Cognitive / Behavioral / Research Audit
Audited Revision: `f0333fc063d4fb4b336b5fa517a55964ff7e26cc` (main)
Architecture Reference: `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (2026-09-03)

---

## 1. Executive Verdict

### Final System Gate: FAIL (BLOCKED ON RUNTIME INTEGRATION)

The audited repository contains an extensive, high-quality, and thoroughly unit-tested body of software comprising 2,332 Python tests and 179 Rust tests. Across all six implementation phases, components for verified planning, episodic simulation, trusted learning governance, bi-temporal memory truth, global control modulation, and provider portability have been designed, coded, and verified in isolation.

However, both independent final audits (Codex and Claude), operating without visibility into each other's assessments, converged on the same central architectural truth:

**The accepted six-phase architecture is component-complete, but it is not runtime-integrated in the production agent.**

Specifically:
1. The production composition root (`CognitiveService.__init__` and `BrainAgent`) continues to instantiate and run the legacy cognitive pipeline without composing the newly created services (`TemporalMemoryStore`, `BackgroundScheduler`, `DeterministicPlanVerifier`, `EpisodicSimulator`, `LearningGovernor`, `OfflineAdapterGate`, `StructuredVisionPercept`, `SpeechIntent` compilers, and `ExternalActionDispatcher`).
2. Core architectural feature flags (`PHASE_02_MEMORY_TRUTH` and `PHASE_03_AFFECT_CONTROL`) default to `False` in `backend/app/config.py`, and `WORKSPACE_AUTHORITATIVE` is not declared on `AppSettings`. When these flags are enabled, legacy test mocks break, proving the production agent was never composed or regression-tested with the new architecture active.
3. In the live background loop, `SubconsciousAgent._run_dream_sequence` persists ungrounded, LLM-generated dream fiction directly into autobiographical memory (`source="subconscious_dream"`), directly violating Architecture Invariant 12 and Sections 19/37.
4. Action selection does not faithfully execute `WAIT`: when `CandidateSelector` chooses `WAIT`, `decision.py` does not map it to an executable action type, causing `ActionService` to fall through to `RESPOND_CHAT` and speak anyway.
5. Provider independence was not empirically demonstrated at the system level: the benchmark cited for provider swap (`BM-GPU-P5-01`) compared two models on the same local Ollama runtime and asserted continuity across local variables that were never mutated.

In accordance with `GEMINI_FINAL_AUDIT_ORCHESTRATOR.md` ("Do not lower standards to obtain PASS. Critical architectural, behavioral, integration, or evaluation problems remain"), the release gate verdict is **FAIL**.

The repository is not rejected as defective code; it is rejected as an uncomposed system. The modules built are sound and should serve as the foundation for a focused **Production Runtime Consolidation** stage.

---

## 2. Final Repository State

- **Git Commit:** `f0333fc063d4fb4b336b5fa517a55964ff7e26cc` (`main`, synchronized with `origin/main`).
- **Python Test Suite:** 2,332 tests passed, 0 failures, 0 errors, 0 skipped (in 59.83s on Apple Silicon Mac).
- **Rust Workspace:** 179 tests passed (21 cognitive-rust, 10 contracts, 70 stt-agent, 78 voice-agent).
- **Static Analysis & Linting:**
  - `ruff check .`: 0 errors across the repository.
  - `radon cc app/ -s -n D`: 0 functions at cyclomatic complexity rank D, E, or F.
  - `mypy app`: 17 type errors across 7 files (persona policy, intent classifier, vision, planning).
  - Formatter: 80 files have formatting drift under `ruff format --check`.
- **Hardware Validated:**
  - Local: Apple Silicon Mac (M5 8-core GPU, Python 3.13.15).
  - Remote: Dedicated Home GPU Server -- NVIDIA GeForce RTX 2060 Super 8GB VRAM (Ubuntu 24.04, Python 3.12.3, Ollama `llama3.2:3b` and `qwen2.5:3b`).

---

## 3. Architecture Conformance

| Architectural Domain | Current Production Behavior | Specification Status | Audit Verdict |
|---|---|---|---|
| **Perception Integration** | `PerceptEnvelope` normalization exists; `last_percept` captured but overwritten by chat input | Partial | CAUSAL (NARROW) |
| **Attention & Salience** | Deterministic pre-classification and startle reflex exist; no unified salience arbiter | Partial | CAUSAL (NARROW) |
| **Working Mental State** | `AgentState` locked; `WorkspaceStore` CAS tested in isolation, but uncalled in live turns | Partial | SCAFFOLD |
| **Memory Truth** | Mature ACT-R decay RAG is live; bi-temporal `TemporalMemoryStore` has zero production callers | Partial | CAUSAL (RAG) / SCAFFOLD (Truth) |
| **Appraisal** | Keyword/ALMA appraisal is live; spec-compliant `AppraisalRecord` path has zero live callers | Partial | CAUSAL (Legacy) |
| **Emotion & Mood** | Tonic/phasic dopamine and cortisol actively shape LLM temperature/top_p/num_predict | Conforming | CAUSAL |
| **Global Control** | `derive_global_controls` derived; consumption gated by `PHASE_03_AFFECT_CONTROL=False` | Gated | SCAFFOLD (Off by default) |
| **Goals** | Legacy per-turn utility scoring live; durable `GoalRecord` has no live caller | Partial | NARROW |
| **World Model** | No entity/state transition prediction structures exist; only next-turn affect valence loop | Non-conforming | ABSENT (as specified) |
| **Self Model** | Narrative/numeric persona with code-enforced immutability live; operational calibration absent | Partial | CAUSAL (Identity) / ABSENT (Operational) |
| **Social Cognition** | 3-way trust dynamics live (6.00x rupture ratio); rich PersonModel fields unread by decisions | Partial | NARROW |
| **Reasoning & Planning** | Intent classification live; `DeterministicPlanVerifier` / `EpisodicSimulator` have zero live callers | Partial | SCAFFOLD |
| **Fast Cognition** | Deterministic responses and startle barge-in with sub-ms audio stop and transcript truncation | Conforming | CAUSAL |
| **Slow Cognition** | Async System-2 appraisal runs; no multi-step deliberative reasoning lane | Partial | CAUSAL (Standard LLM) |
| **Background Cognition** | `BackgroundScheduler` unused; live loop runs unbudgeted and writes dream fiction to memory | Non-conforming | FAIL / UNGOVERNED |
| **Action Selection** | Candidate selector gated by default-off flags; WAIT falls through to chat; 9 of 12 kinds unreachable | Non-conforming | FAIL |
| **Learning & Adaptation** | `LearningGovernor` and `OfflineAdapterGate` uncalled; live reflection mutates traits without review | Non-conforming | FAIL / UNGOVERNED |
| **Voice Boundary** | `SpeechIntent` and compilers built; production emits legacy `ChatOutput` to Rust GPT-SoVITS | Disconnected | SCAFFOLD |
| **Vision Boundary** | `StructuredVisionPercept` built; production emits semantic VLM captions and reflex deltas | Disconnected | SCAFFOLD |
| **Provider Portability** | `LLMClient` abstracts providers; embeddings hard-coded to Ollama; cross-provider unproven | Partial | PARTIAL |

---

## 4. Codex Engineering Audit Summary

The Codex audit focused on runtime composition, execution paths, state integrity, and failure recovery:
1. **Composition Root Failure (F-01, BLOCKER):** `CognitiveService.__init__` constructs only the pre-phase services. It does not instantiate `SQLiteWorkspaceStore`, `TemporalMemoryStore`, `BackgroundScheduler`, `DeterministicPlanVerifier`, `EpisodicSimulator`, `LearningGovernor`, `OfflineAdapterGate`, `ProviderCapabilityNegotiator`, `VoiceCompiler`, or `ExternalActionDispatcher`.
2. **Missing Causal Slice in Production (F-02, HIGH):** `BrainAgent` passes `raw_event` and `percept`, but passes no `workspace` into `process_event`. Consequently, every `ActionIntent` committed in production falls back to epoch/revision `(0, 0)`.
3. **Action Execution Disconnect (F-03, HIGH):** Most declared actions in `ActionCandidateKind` have no generator in `decision.py` or executor in `action.py`. If `WAIT` is selected, it falls through to `_execute_respond_chat`.
4. **Memory Outage Masking (F-04, HIGH):** `MemoryStore.search_memories` catches all exceptions and returns `[]`. Callers do not check `last_search_error`, causing database or embedding outages to look identical to "no memories found."
5. **State Ownership Across Processes (F-02, HIGH):** `BrainAgent` and `SubconsciousAgent` each maintain a separate `StateService`. Equal-revision writes from different writers are resolved arbitrarily without a unified workspace owner.
6. **Benchmark Disconnect (F-08, HIGH):** All six GPU benchmark scripts construct isolated classes and query Ollama directly; none executes through the integrated `BrainAgent` or `CognitiveService`.

---

## 5. Claude Cognitive Audit Summary

The Claude audit focused on cognitive mechanisms, causal wiring, behavioral validity, and scientific defensibility:
1. **Dual Layer Architecture (Executive Verdict):** The codebase consists of a genuine, pre-existing causal substrate (endocrine sampling modulation, ACT-R memory decay, startle reflex barge-in, persona immutability tiers) surrounded by freshly built scaffolding that is either flagged off or uncalled.
2. **Epistemic Memory Contamination (F2, BLOCKER):** `SubconsciousAgent._run_dream_sequence` synthesizes surreal dream text and calls `memory_store.add_memory(..., source="subconscious_dream")`. This violates Invariant 12 and Section 19/37, directly inserting hallucinations into autobiographical memory.
3. **Provider Independence Benchmark Tautology (F3, BLOCKER):** Benchmark `BM-GPU-P5-01` tested two Ollama models on the same host and asserted that local variables `person.trust_competence` and `authoritative_affect["valence"]` did not drift. Because those local variables were never modified in the loop, the benchmark was a tautology that could not fail.
4. **Metacognition Starvation (F6, HIGH):** The metacognitive gate logic (`ABSTAIN`, contradiction-triggered `ASK`) is fully implemented, but `blackboard["metacognitive_directive"]` is permanently set to the default `"PROCEED"`, and `DomainCalibration` is never invoked in live turns.
5. **Pace and Process Assessment (F18, HIGH):** All six phases were completed in an 11.5-hour window on 2026-09-04, adding 22,283 lines across 76 files. The phase-gate process verified component unit tests and isolated performance, but completely missed the absence of live production wiring.

---

## 6. Reconciled Findings

| Finding ID | Source | Description | Severity | Release Gate Impact |
|---|---|---|---|---|
| **F-01** | Codex F-01, Claude F1 | The 6-phase architecture is uncomposed in production (`CognitiveService`, `BrainAgent`). | **BLOCKER** | Blocks PASS |
| **F-02** | Claude F2, Codex F-05 | `SubconsciousAgent._run_dream_sequence` persists dream text directly into `MemoryStore`. | **BLOCKER** | Blocks PASS |
| **F-03** | Claude F3, Codex F-08 | Provider independence benchmark was a same-provider tautology; cross-provider unproven. | **BLOCKER** | Blocks PASS |
| **F-04** | Claude F10, Codex F-03 | Selected `WAIT` candidate is not mapped to an executable action, causing agent to speak. | **HIGH** | Blocks PASS |
| **F-05** | Claude F4, Codex F-05 | `BackgroundScheduler` has zero production callers; live background loop is ungoverned. | **HIGH** | Major Limitation |
| **F-06** | Claude F5, Codex F-01 | Phase 06 planning, simulation, and learning governance have zero live callers. | **HIGH** | Major Limitation |
| **F-07** | Claude F7, Codex F-06 | `LEARNING_REVIEW_REQUIRED=False` allows unverified reflection LLM to mutate persona. | **HIGH** | Safety Risk |
| **F-08** | Claude F6, Codex F-09 | Metacognitive directive permanently "PROCEED"; calibration engine never invoked live. | **HIGH** | Overclaimed Capability |
| **F-09** | Claude F8, F9, Codex F-09 | Operational self-model and environment world-model do not exist as specified. | **HIGH** | Overclaimed Capability |
| **F-10** | Codex F-02, Claude F11 | `PersonModel` rich fields unread; collapsed to single scalar trust average. | **MEDIUM** | Behavioral Limitation |
| **F-11** | Codex F-11 | 17 mypy errors; 80 unformatted files; C-grade complexity at state hydration. | **MEDIUM** | Technical Debt |
| **F-12** | Codex F-12 | Phase 06 learning governance microbenchmark is sensitive to concurrent CPU load. | **LOW** | Performance Note |

---

## 7. Fixes Applied & Fix Plan

Per `GEMINI_FINAL_AUDIT_ORCHESTRATOR.md` line 212 ("Do not begin new architecture phases or add new features during this audit"), massive architectural rewiring was not initiated during the audit. 

Instead, the audit established `orchestration/FINAL_SYSTEM_AUDIT/FINAL_FIX_PLAN.md` with targeted remediations:
1. **Dream Memory Quarantine (F-02):** Eliminate direct `memory_store.add_memory` in `_run_dream_sequence`.
2. **WAIT Realization (F-04):** Map `WAIT` to `action_type="WAIT"` in `decision.py` and handle it as a silent completion in `action.py`.
3. **Safe Defaults (F-07):** Declare `WORKSPACE_AUTHORITATIVE` on `AppSettings` and set `LEARNING_REVIEW_REQUIRED: bool = True`.
4. **Architectural Truthfulness:** Explicitly downgrade overclaimed capabilities in master documentation.

---

## 8. End-to-End Cognitive Flow Validation

| Operational Scenario | Traced Runtime Path | Live Cognitive Status |
|---|---|---|
| **Normal Interaction** | `chat.input` -> `BrainAgent` -> `CognitiveService.process_event` -> legacy pipeline -> streamed `chat.output` | Functional legacy flow; no workspace CAS, candidate selection, or speech intent |
| **Memory Retrieval** | `SurfacingAgent` -> `MemoryStore.search_memories` -> `surfaced_memories` dicts -> prompt assembly | Functional ACT-R decay RAG; bi-temporal truth and contradiction logic bypassed |
| **Affective Change** | Appraisal -> `StateService` locked update -> tonic/phasic endocrine -> sampling parameters | Genuinely causal; temperature and top_p actively shift with stress/reward |
| **High-Salience Event** | `reflex_name == "startle"` -> `is_facial_reflex_interruption_worthy` -> instant `AudioStop` | Genuinely causal; deterministic non-LLM reaction |
| **Interruption / Barge-in** | `audio.stop` -> generation task cancellation -> transcript truncated to heard byte offset | Genuinely causal; cross-language Python/Rust synchronization |
| **Fast Reaction** | Deterministic keyword response before LLM classification | Genuinely causal; sub-millisecond bypass |
| **Slow Deliberation** | Model intent classification and async System-2 appraisal | Standard LLM turn; verified planning and episodic simulation uncalled |
| **Background Work** | `SubconsciousAgent._continuous_monologue_loop` (5s polling tick) | Active but ungoverned; persists dream text without budget or review |
| **Action Selection** | `decision.py` evaluates candidate selection only if flags on; otherwise falls through to chat | Default-off; WAIT speaks; 9 of 12 action kinds unreachable |
| **Speech Intent** | Brain publishes `ChatOutput`; Rust voice agent constructs GPT-SoVITS `/tts` request | `SpeechIntent`, voice compilers, and loss telemetry bypassed |
| **Restart Recovery** | `StateService`, biography, and weights hydrate from Postgres/SQLite | Workspace epoch, session state, and Phase 06 learning state not restored |

---

## 9. Architecture Invariants Evaluation

| # | Architecture Invariant (Section 41) | Status | Empirical Grounding |
|---:|---|---|---|
| 1 | Identity-bearing state is not only prompt/provider state | **PASS** | Persona profile, biography, and affective state persist to database. |
| 2 | One owner per mutable domain; revision + restart epoch | **FAIL** | Multiple `StateService` writers; workspace/epoch absent from live turns. |
| 3 | Provenance for beliefs, predictions, inferences, updates | **PARTIAL** | Schemas carry provenance; live memory bridge strips metadata. |
| 4 | Distinct observation, report, inference, imagination, belief | **FAIL** | Unused in `TemporalMemoryStore`; dreams and facts share legacy store. |
| 5 | Modulation changes parameters/budgets, never truth/safety | **PASS** | Endocrine and control channels only modulate sampling and scoring. |
| 6 | Hard constraints filter before utility | **PARTIAL** | Implemented in `CandidateSelector`, but candidate selection is default-off. |
| 7 | Action selection is separable and commits intent first | **FAIL** | Live intent uses `(0, 0)` fallback; language generation is the action. |
| 8 | Retrieved memory is untrusted, never executable instruction | **PARTIAL** | Delimiter wrapping is active; active regex filtering is default-off. |
| 9 | Contradictions preserve evidence/history | **PARTIAL** | Implemented in `TemporalMemoryStore`; production retrieval lacks it. |
| 10 | Storage/reflection is not called learning without improvement | **FAIL** | Unverified reflection LLM directly mutates persona traits. |
| 11 | Model self-confidence requires empirical calibration | **FAIL** | Reflection accepts self-reported confidence >= 0.8; calibration uncalled. |
| 12 | Generated background content cannot self-promote to truth | **FAIL** | Dream sequence directly writes fiction to `MemoryStore`. |
| 13 | Fast actions update same causal workspace as slow actions | **FAIL** | Fast reflex barge-in updates conversation store, but no workspace exists. |
| 14 | Background work is bounded, preemptible, idempotent | **FAIL** | `BackgroundScheduler` uncalled; live monologue loop is unbudgeted. |
| 15 | Voice owns sound; vision observables; brain meaning | **PARTIAL** | Voice synthesizes audio, but receives legacy text rather than intent. |
| 16 | Provider capability loss is explicit | **PARTIAL** | Loss schemas exist; production memory outage silently collapses to `[]`. |
| 17 | Provider swap requires behavioral/safety conformance | **PARTIAL** | Factory abstracts LLMs; full cross-provider conformance untested. |
| 18 | Infrastructure does not define cognitive semantics | **PARTIAL** | Legacy and temporal memory stores have conflicting live semantics. |
| 19 | Benchmark provenance includes full environment fixture | **FAIL** | Phase GPU scripts used synthetic state and direct component harnesses. |
| 20 | No claim of consciousness, ToM, or human-level cognition | **PASS** | No consciousness or general Theory of Mind claims are made. |

**Invariant Summary:** 3 PASS, 8 PARTIAL, 9 FAIL.

---

## 10. Memory and Persistent State

The memory subsystem exhibits an architectural bifurcation:
- **Engine A (Production-Wired):** `MemoryStore` provides ACT-R base-level activation decay, spreading activation over Neo4j, lexical cue matching, and Qdrant vector retrieval. This is a functional, production-hardened RAG system that measurably influences generation.
- **Engine B (Scaffolded):** `TemporalMemoryStore` provides typed bitemporal intervals (`valid_from`, `valid_until`), immutable event histories, and 4-way contradiction resolution (`UPDATE`, `CORRECTION`, `CONFLICT`, `ELABORATION`). This engine is fully unit-tested but has zero callers in the live agent loop. The legacy adapter (`memories_to_activations`) hardcodes `contradiction_state="NONE"` and `outage_flag=False`, blinding the agent to contradictions.

---

## 11. Emotion and Appraisal

- **Tonic/Phasic Endocrine Causal Chain:** Valence and arousal deterministically compute `cortisol_tonic` and `dopamine_tonic`. Phasic bursts (`release_dopamine`, `release_cortisol`) are tracked relative to tonic floors and decayed by time. These values map to LLM sampling options (`temperature`, `top_p`, `num_predict`), creating real behavioral variance under stress or reward.
- **Somatic Vision Appraisal:** `SomaticAppraiser` processes facial observables and triggers dopamine bursts and valence shifts under positive interaction.
- **Limitation:** While sampling parameters shift, generated text vocabulary is unconstrained by PAD coordinates: an agent in high cortisol can still generate words asserting calm optimism.

---

## 12. Global Control / Neuromodulation

- Four global control channels are derived by `derive_global_controls`: `urgency_gain`, `exploration_budget`, `effort_budget`, and `learning_gain`.
- In unit tests (`test_global_control_selection.py`), urgency gain demonstrably modulates candidate scores and flips the selected action from high-cost SPEAK to low-risk WAIT.
- In production, `Config.PHASE_03_AFFECT_CONTROL` defaults to `False`. Furthermore, `learning_gain` has zero read sites across the entire codebase, making it a dead variable.

---

## 13. Fast and Slow Cognition

- **Fast Path (Genuinely Supported):**
  - Deterministic pre-classification keyword response in `decision.py` bypasses all LLM calls.
  - Facial startle reflex in `brain_agent.py` detects startle expressions, immediately publishes `AudioStop`, cancels in-flight LLM streaming, truncates transcript records to exact audio playback offsets, and logs a terminal `OutcomeRecord`. Rust voice agent halts playback immediately upon receiving `AudioStop`.
- **Slow Path:**
  - Standard intent classification and async System-2 appraisal.
  - Phase 06 verified planning (`DeterministicPlanVerifier`) and episodic simulation (`EpisodicSimulator`) are not wired into the deliberative turn.

---

## 14. World, Self, and Social Models

- **World Model:** Evaluated as **ABSENT as specified**. The repository contains no data structures for entity affordances, environmental state transitions, or action-conditioned forward predictions. The only predictive mechanism is next-turn affective valence expectation in `reappraisal.py`.
- **Self Model:** The narrative and numeric persona profile is genuine and robustly protected by code-enforced immutability (`IMMUTABLE_CORE`). However, the operational self-model (empirical tracking of system capabilities and domain limitations) does not exist.
- **Social Model:** Competence and benevolence trust scalars update asymmetrically (ruptures drop trust 6.00x faster than repairs build it). Downstream, however, competence and benevolence are averaged into a single scalar, and rich fields (`current_knowledge`, `disclosures`, `obligations`) are unread by decision logic.

---

## 15. Learning and Metacognition

- **Governed Learning:** `LearningGovernor` and `OfflineAdapterGate` provide Section 21 proposal lifecycles, risk tiers, and 1-step atomic rollbacks. However, they have no production callers. The active reflection service mutates adaptive persona traits directly whenever LLM confidence exceeds 0.8.
- **Metacognition:** The `CandidateSelector` includes code to disqualify candidates on `ABSTAIN` directives and raise `ASK` candidates on contradictions. However, in production, the metacognitive directive is permanently `"PROCEED"`, and `DomainCalibration` is never invoked live.

---

## 16. Action Selection

- `CandidateSelector` implements constraint-first filtering and multi-attribute utility scoring over `ActionCandidate` instances.
- In production, `PHASE_02_MEMORY_TRUTH` and `PHASE_03_AFFECT_CONTROL` are `False` by default, skipping candidate selection entirely.
- When enabled, only 3 canonical candidates (SPEAK, WAIT, ASK) and 2 regulation candidates (REAPPRAISE, REDIRECT_ATTENTION) can be generated. 7 of 12 canonical kinds (`OBSERVE`, `RETRIEVE`, `VERIFY`, `REFLECT`, `UPDATE_GOAL`, `UPDATE_STATE`, `EXTERNAL_ACT`) have no generators.
- When `WAIT` is selected, `decision.py` fails to set an executable action type, causing `action.py` to speak chat text.

---

## 17. Voice and Vision Boundaries

- **Voice Boundary:** `SpeechIntent`, `ElevenLabsVoiceCompiler`, `GPTSoVITSVoiceCompiler`, and `IntentLossRecord` pass standalone unit tests. In production, `BrainAgent` publishes legacy `ChatOutput` and `SpeechExpressionWire`, and the Rust voice agent directly constructs GPT-SoVITS `/tts` payloads.
- **Vision Boundary:** `StructuredVisionPercept`, `VLMCaptionVisionAdapter`, and `SpatialTrackingVisionAdapter` pass unit tests. In production, `vision/agent.py` emits semantic VLM captions and reflex deltas.

---

## 18. Provider Independence

- `LLMClient` protocol supports both `OllamaClient` and `AnthropicClient`.
- Embeddings are hard-coded to Ollama endpoints (`/api/embed` and `/api/embeddings`) in `MemoryStore`.
- Benchmark `BM-GPU-P5-01` tested two Ollama models (`llama3.2:3b` and `qwen2.5:3b`) on the same host and verified identical local variables that were never mutated. True cross-provider behavioral invariance remains untested.

---

## 19. Regression and Integration Results

- Total tests on `main`: **2,332 passed, 0 failures, 0 errors, 0 skipped**.
- Full test pass rate: 100%.
- Blind Spot Analysis: The test suite passed 100% because each new module was tested in isolation, and phase integration tests monkeypatched flags to `True` within test cases without testing the unpatched production composition.

---

## 20. GPU and Runtime Benchmarks

- Hardware: Dedicated Home GPU Server -- NVIDIA GeForce RTX 2060 Super 8GB VRAM.
- Software: Ubuntu 24.04, Python 3.12.3, Ollama (`llama3.2:3b`, `qwen2.5:3b`).
- Results:
  - Phase 01: Mean TTFT 32.10 ms (+3.12 ms overhead), 0.4 ms barge-in.
  - Phase 02: Mean TTFT 28.96 ms, 100% soak test stability.
  - Phase 03: Mean TTFT 30.95 ms, 0.0% unparseable output.
  - Phase 04: Mean TTFT 33.81 ms, 6.00x rupture-to-repair ratio.
  - Phase 05: TTFT delta between models 2.88 ms, 0.085 ms voice compiler latency.
  - Phase 06: Mean TTFT 27.06 ms (p95 36.20 ms), 0.08 ms adapter qualification.
- Provenance Note: All GPU benchmarks executed isolated test harnesses with synthetic workspace states, rather than the production `BrainAgent` composition.

---

## 21. Ablation Results

1. **Endocrine Sampling Modulation:** Disabling endocrine injection (`ActionService._compute_endocrine_options`) reverts LLM sampling to static defaults (`temperature=0.7`, `top_p=0.9`), eliminating stress-induced focus and reward-induced divergence.
2. **Global Control Candidate Selection:** In isolated harnesses, ablating `urgency_gain` prevents the candidate selector from prioritizing low-risk actions under stress. In production, this mechanism is ablated by default via `PHASE_03_AFFECT_CONTROL=False`.
3. **Reflex Startle Barge-In:** Disabling `is_facial_reflex_interruption_worthy` prevents immediate `AudioStop` publication, causing the system to complete full multi-second LLM generation before processing visual shock.

---

## 22. Remaining Weaknesses

1. **Uncomposed Production Root:** New services operate as standalone libraries rather than an integrated cognitive loop.
2. **Default-Off Behavior Flags:** Phase 2 and 3 capabilities are disabled in production configuration.
3. **Dream Memory Contamination:** Ungrounded dream fiction is written to autobiographical memory.
4. **Non-Functional WAIT Action:** Agent speaks when it chooses to wait.
5. **Disconnected Governance:** Phase 06 plan verification and learning governance have no live call sites.
6. **Starved Metacognition:** Calibration and contradiction signals never reach decision logic.
7. **Tautological Provider Benchmark:** Cross-provider portability is asserted without genuine multi-provider validation.
8. **Collapsed Social Modeling:** Rich person model data is collapsed to an undifferentiated trust scalar.
9. **Absent World Model:** No environmental state or affordance prediction exists.
10. **Dual Memory Disconnect:** Bi-temporal truth tracking is bypassed in favor of legacy RAG.
11. **Static Typing Debt:** 17 mypy type errors in core modules.
12. **Load-Sensitive Governance:** Governance microbenchmark exhibits latency degradation under concurrent CPU load.

---

## 23. Research Claims Currently Supported

The following 4 claims are empirically supported by genuine, live causal code:
1. **Endocrine Sampling Modulation:** Tonic and phasic dopamine/cortisol deterministically modulate LLM sampling parameters and memory retrieval.
2. **ACT-R Memory Decay & Mood Congruence:** Multi-store memory retrieval actively weights items by activation decay and emotional congruence.
3. **Real-Time Startle Barge-In:** Deterministic facial startle interruption operates cross-language (Python/Rust) with sub-millisecond audio halt and exact-offset transcript truncation.
4. **Three-Tier Persona Immutability:** Core safety invariants and identity values are code-enforced against modification.

---

## 24. Research Claims Not Yet Supported

The following 8 claims are not supported by the live production system:
1. **Operational Self-Model:** Tracking of system capabilities and limitations.
2. **Predictive World Model:** Environmental state transitions and affordance tracking.
3. **Calibrated Metacognition:** Empirical Brier-score uncertainty guiding decision gates.
4. **Governed Learning in Production:** Section 21 proposal lifecycles and atomic rollbacks.
5. **Bounded Background Cognition:** Monologue and dream loops operating under preemption and idempotency budgets.
6. **Language-Independent Action Selection:** General candidate selection operating in production across all 12 action kinds.
7. **Cross-Provider Behavioral Invariance:** Empirical proof that persona and behavior survive model/provider swaps.
8. **Unified Six-Phase Architecture:** Coherent execution of all six phases in a single production runtime loop.

---

## 25. Final Release Gate

### Gate: FAIL (BLOCKED ON RUNTIME INTEGRATION)

**Conclusion:**
The six implementation phases succeeded in constructing the necessary components, algorithms, and schemas for an advanced humanoid brain architecture, supported by 2,332 green unit tests. However, because those components were never composed into the production agent, and because critical safety and execution invariants (dream contamination, non-functional WAIT, unverified provider swaps) remain unfulfilled on `main`, the architecture cannot be certified as complete or released as an integrated system.

**Next Recommended Stage: PRODUCTION RUNTIME CONSOLIDATION**
1. Unify `CognitiveService` and `BrainAgent` to compose the full suite of Phase 01-06 components into a single production runtime.
2. Eliminate dream memory writing in `SubconsciousAgent`.
3. Implement executable semantics for `WAIT` and resolve the action selection dispatcher.
4. Refactor legacy test mocks to allow `PHASE_02_MEMORY_TRUTH` and `PHASE_03_AFFECT_CONTROL` to default to `True`.
5. Execute an end-to-end integration benchmark through the unified production agent with genuine cross-provider validation.
