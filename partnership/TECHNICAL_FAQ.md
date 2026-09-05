# Technical Frequently Asked Questions (FAQ)

## Document Status
- **Classification:** Partner Due Diligence Technical FAQ
- **Audience:** External Technical Leads, Architects, Systems Engineers
- **Character Encoding:** Strict 7-bit ASCII
- **Authoritative System Commit:** Merged on `main` (`156f3b7`)

---

### Q1: Why is this not just an LLM wrapper?
**Answer:**
A wrapper is a stateless proxy that passes inputs to an LLM API and forwards text back. Our architecture possesses:
1. **Autonomous Process Lifecycle:** Background daemons (`subconscious_agent`, `system_agent`) execute continuously without incoming user requests, performing circadian decay, graph consolidation, and episodic memory pruning.
2. **Single-Owner Authoritative State Kernel:** Affect, trust, fatigue, and memory cannot be mutated by the LLM. All mutations require mutex-locked Compare-And-Swap (CAS) state validation (`StateService._state_lock`).
3. **Bi-Temporal Memory Engine:** Maintains separate assertion timestamps and validity intervals (`[valid_from, valid_to]`), mathematically preventing superseded facts from colliding in retrieval.
4. **Hardware-Level Sampler Modulation:** Internal neurochemical states modulate temperature, top-p, and token budgets directly at the inference engine level.
5. **Fail-Closed Action Gate:** Physical tool executions and robotic movements are mediated by `ExternalActionDispatcher`, checking risk classes (`LOW` to `CRITICAL`) and preconditions before authorization.

---

### Q2: Why not let the LLM manage memory itself (e.g. via long-context or prompt summarization)?
**Answer:**
Three reasons rooted in fundamental transformer architecture:
1. **Context Bloat & Latency:** Ingesting 100k tokens of conversation history on every turn increases prompt evaluation time by hundreds of milliseconds, making real-time voice conversational cadence impossible on edge hardware.
2. **Semantic Collisions in Vector RAG:** If a user says "I live in Seattle" in turn 5 and "I moved to Tokyo" in turn 200, semantic embedding search retrieves both turns because they are semantically identical ("user residence"). The LLM has no mathematical basis to distinguish current truth from superseded truth without temporal interval indexing.
3. **Catastrophic Forgetting & Prompt Injection:** If the model manages its own memory via autonomous tool calls without validation, malicious or noisy user inputs easily corrupt the agent database permanently.

---

### Q3: What happens when the underlying foundation model changes?
**Answer:**
The agent identity, character temperament, relational history, and behavioral rules remain 100% intact.
- In benchmark `BM-GPU-P7-02`, we evaluated the architecture across two distinct foundation model families (`qwen2.5:3b` and `llama3.2:3b`).
- The system passed **40 out of 40 adversarial boundary probes** with **zero safety violations** and zero persona degradation across both models.
- Because persona tiers (Immutable Core, Constitutional Temperament) live in the architecture (`app/persona/profile.py`), the model provides linguistic realization while the brain enforces behavior.

---

### Q4: What exactly is your intellectual property?
**Answer:**
We distinguish implemented architecture know-how from formal IP candidates. We have identified four primary mechanisms for professional prior-art and IP review (`evidence/IP_REVIEW_CANDIDATES.md`):
1. **Closed-Loop Endocrine Modulation of Autoregressive Sampling:** Mapping continuous tonic/phasic mathematical affect variables directly to generative sampling hyperparameters ($T, \text{top\_p}, \text{num\_predict}$).
2. **Bi-Temporal Contradiction Resolution with Epistemic Quarantine:** Memory retrieval store combining real-world validity intervals with strict isolation of background dream sequences from hot memory tables.
3. **Governed Multi-Tier Persona Engine with Microsecond Atomic Rollback:** Transactional governance of autonomous reflection with sub-50 microsecond atomic recovery.
4. **Decoupled Speech Intent Compiler with Expressive Loss Accounting:** Vendor-neutral communicative speech compiler generating structured fidelity audit records.

---

### Q5: Which mechanisms are actually validated versus experimental?
**Answer:**
We strictly classify all capabilities (`evidence/TECHNICAL_EVIDENCE_PACKAGE.md`):
- **PROVEN (Backed by Automated Benchmarks):**
  - Composed turn TTFT of 119.35 ms on 8GB GPU (`BM-GPU-P7-01`).
  - Sub-millisecond acoustic barge-in interruption of 0.099 ms (`BM-GPU-02`).
  - Cross-provider boundary invariance across Qwen and Llama (`BM-GPU-P7-02`).
  - Governed proposal review and atomic rollback in 14.28 microseconds (`BM-LOC-P7-04`).
  - Zero spoken leakage during WAIT action silence (`BM-LOC-P7-02`).
  - Epistemic dream quarantine compliance at 100.0% (`BM-LOC-P7-03`).
- **DEMONSTRATED:**
  - Continuous MediaPipe facial reflex expression nudges.
  - Multi-session relational trust accumulation.
- **NOT YET PROVEN / EXPERIMENTAL:**
  - Real-time multimodal spatial embodiment with live humanoid joint controllers.
  - Sub-50 ms end-to-end TTFT on consumer 8GB GPUs without dedicated NPU hardware.

---

### Q6: What is the latency overhead introduced by the cognitive brain?
**Answer:**
In our end-to-end GPU benchmark (`BM-GPU-P7-01`), the total turn latency breaks down as:
- **Pre-Generation Cognitive Deliberation:** **34.57 ms** (Perception, affect snapshot, bi-temporal memory search, appraisal, and action plan formation).
- **Prompt Evaluation / Prefill (Ollama):** **84.78 ms** (150 dynamic context tokens).
- **Time-to-First-Token (TTFT):** **119.35 ms**.
- **Autoregressive Generation:** ~538 ms for 15-20 tokens at 25.07 tok/s.
The brain architecture itself adds only ~35 ms of deliberation overhead, well within real-time voice latency budgets (< 150 ms).

---

### Q7: How does identity persist across sessions and reboots?
**Answer:**
Identity is structured into three formal tiers (`app/persona/profile.py`):
1. **Immutable Core:** Safety rules, ethical invariants, and core identity markers. Stored in code/config; cannot be modified by user or LLM.
2. **Constitutional Temperament:** Mathematical baselines for valence, arousal, mood decay rates, and trust sensitivity. Loaded from configuration and bounded by strict schema invariants.
3. **Adaptive Traits:** Evolving conversational traits learned from interaction (capped at 5). Persisted in PostgreSQL/SQLite and governed by `LearningGovernor`.

---

### Q8: How does emotion affect cognition in practice?
**Answer:**
Emotion is represented mathematically as a continuous Pleasure-Arousal-Dominance (PAD) vector, Marsh relational trust, and neurochemical proxies (cortisol, dopamine, fatigue).
Emotion affects cognition across four distinct pathways:
1. **Mood-Congruent Memory Recall:** Memory search boosts memories whose historical valence matches the agent current valence.
2. **Appraisal Biasing:** Negative valence sensitizes the appraisal engine to potential goal obstacles.
3. **Physical Sampling Modulation:** Cortisol narrows generation temperature; dopamine broadens nucleus sampling.
4. **Expressive Speech Intent:** PAD coordinates are attached to `SpeechIntent.affect`, dictating prosody, pitch, and speaking rate to external voice engines.

---

### Q9: What does "neuromodulation" actually mean here? Are you claiming biological simulation?
**Answer:**
**No. We reject all claims of biological equivalence.**
In this architecture, "neuromodulation" is an engineering term referring to the closed-loop mathematical scaling of algorithmic sampling parameters:
- `cortisol` is a derived scalar function of negative valence, arousal, and fatigue.
- `dopamine` is a derived scalar function of positive valence and goal achievement.
Both scalars feature tonic (baseline) and phasic (decaying exponential burst) terms. These mathematical values are mapped deterministically to floating-point arguments passed to the LLM API (`temperature = base_temp * (1.0 - 0.4 * cortisol)`).

---

### Q10: How is online learning controlled and prevented from drifting?
**Answer:**
Via the `LearningGovernor` (`app/cognitive/learning_governance.py`):
1. Background reflection formulates a structured `LearningProposal`.
2. The proposal is evaluated against the `IMMUTABLE_CORE`. Any proposal that touches safety invariants, baseline boundaries, or ethical constraints is rejected immediately.
3. If approved, the proposal is activated, and an atomic rollback snapshot is registered.
4. The system executes automated evaluation probes. If behavioral regression or jailbreak risk is detected, `governor.rollback()` reverts the state to baseline in **14.28 microseconds** with 100.0% fidelity.

---

### Q11: Can the system run entirely locally / air-gapped?
**Answer:**
**Yes.**
The entire system has been benchmarked and validated running on a standalone Linux host with an 8GB NVIDIA GPU:
- Inter-agent bus: Local NATS JetStream container.
- Storage: Local SQLite / embedded Postgres and local Qdrant vector index.
- Foundation model: Local Ollama runtime (`qwen2.5:3b`).
- Audio: SenseVoice STT and local GPT-SoVITS TTS.
No external internet connectivity or proprietary cloud APIs are required.

---

### Q12: What hardware is required to run the architecture?
**Answer:**
- **Minimum Requirement (Local Inference):** Consumer NVIDIA GPU with >= 8GB VRAM (e.g. RTX 2060 Super, RTX 3060, or Apple Silicon Mac M1/M2/M3 with 16GB unified RAM).
- **Robotics Embodiment:** NVIDIA Jetson Orin Nano (8GB) or Orin NX (16GB).
- **Server / Cloud Deployment:** Standard cloud GPU instance (e.g. T4, A10G, or L4).

---

### Q13: How does a commercial voice provider (e.g. ElevenLabs, Sarvam) integrate?
**Answer:**
Via `VoiceCompilerProtocol` (`app/voice/compiler.py`):
1. The brain produces a `SpeechIntent` object containing semantic text, PAD affect coordinates, urgency, epistemic hedging, and timeline markers (pauses, emphasis).
2. The partner-specific compiler converts this intent into the provider native API request (e.g. ElevenLabs WebSocket or Sarvam REST endpoint).
3. The compiler records any unrenderable dimensions into an `IntentLossRecord`, providing full auditability without leaking vendor markup into the brain.

---

### Q14: How does computer vision integrate into the brain?
**Answer:**
Via `StructuredVisionPercept` (`app/cognitive/vision_percept.py`):
- The brain does not ingest raw video frames in the cognitive deliberative loop.
- External vision pipelines (e.g. MediaPipe, YOLO, or a vision-language model) process camera frames and emit structured perceptual events: detected entities, facial expressions, gaze vectors, and spatial distances.
- The adapter `to_percept_envelope` validates spatial invariants and injects them into working memory.

---

### Q15: What is the failure model? What happens if a subsystem crashes?
**Answer:**
- **Foundation Model Timeout/Crash:** If the LLM service fails or exceeds timeout, `ActionService` falls back to a deterministic fallback statement or safe WAIT action.
- **External Actuator Disconnect:** `ExternalActionDispatcher` fails closed; unregistered or disconnected robot joints return safe simulated completion or explicit cancellation errors.
- **State Mutex Contention:** State mutations are non-blocking or bounded by microsecond mutex timeouts; CAS version mismatches trigger a clean state re-fetch.

---

### Q16: What data does the system store, and how is user privacy handled?
**Answer:**
- Memory is stored locally in relational tables (SQLite/PostgreSQL) and vector indexes (Qdrant).
- Memories are structured into hierarchical wings, rooms, and drawers (`personal`, `relational`, `factual`).
- The architecture supports deterministic memory purging and GDPR/right-to-be-forgotten compliance via explicit entity deletion functions in `MemoryStore`.

---

### Q17: What resources and time would a Proof-of-Concept (PoC) require?
**Answer:**
- **Duration:** 2 to 3 weeks.
- **Partner Resources:** 1 designated technical contact; standard API documentation / sandbox credentials (for voice providers) or ROS2 topic specifications (for robotics OEMs).
- **Deliverables:** A fully working integration demonstrator proving multi-turn memory continuity, emotion-modulated speech delivery, and sub-millisecond barge-in interruption.
