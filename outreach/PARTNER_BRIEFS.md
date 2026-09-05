# Partnership Outreach: Deep Technical Partner Briefs

## Document Status
- **Classification:** Internal Strategic Partner Intelligence & Technical Alignment
- **Audience:** Core Engineering & Partnership Lead
- **Character Encoding:** Strict 7-bit ASCII
- **Authoritative System Commit:** Merged on `main` (`156f3b7`)
- **Primary Sources:** Official API documentation, published papers, public technical blogs

---

## 1. Partner Brief 1: Sarvam AI

### 1.1 Public Technical Context & Baseline
- **Mission & Focus:** Frontier foundational AI developed specifically for Indian linguistic and cultural diversity, spanning 22 scheduled Indian languages.
- **Core Models & Technologies (Source: docs.sarvam.ai, 2024-2025):**
  - **Bulbul v3 / v2 (Text-to-Speech):** High-naturalness expressive speech synthesis across Indian languages with controllable pitch and speaking pace.
  - **Saarika v2.5 (Speech-to-Text):** State-of-the-art ASR tailored for Indian accents, regional dialects, and code-mixed conversational Hindi-English (Hinglish).
  - **Sarvam-2B / Sarvam-1:** Custom-trained 2-billion parameter Indic language models with efficient inference profiles for edge and cloud deployment.
  - **Conversational Voice API:** Enterprise voice agent endpoints supporting vernacular telephone and customer interaction workflows.

### 1.2 Architectural Fit & Complementary Strengths
- **What Sarvam Has:** Market-leading Indic acoustic representations, phonetic tokenization for vernacular scripts (Devanagari, Tamil, Telugu, etc.), and low-latency speech pipelines.
- **What Our Brain Adds:** 
  - **Autonomous Mental State & Memory Continuity:** Memory that persists across months with bi-temporal validity tracking, preventing user history from colliding.
  - **Model Independence:** Sarvam-2B can serve as the core deliberative engine while our brain architecture guarantees that persona boundaries, ethical safety rules, and emotional state remain invariant.
  - **Acoustic Barge-In:** Sub-millisecond interruption handling, allowing natural conversational cadence in vernacular dialogues without cloud round-trip delay.
- **What We Are NOT Asking Them to Replace:** We do not touch their acoustic synthesis models, vernacular tokenizers, or speech recognition engines. We sit above their stack as the cognitive deliberation brain.

### 1.3 Anticipated Partner Objections & Technical Answers
- **Objection 1:** *"We already have conversational voice agents via our API."*
  - *Response:* "Your conversational API provides excellent turn-by-turn speech translation and LLM response. However, standard LLM wrappers cannot maintain bi-temporal memory truth across weeks or execute continuous affective sampling modulation. Our architecture provides the cognitive state machine that turns your speech models into an enduring lifelong companion."
- **Objection 2:** *"Does your architecture support Indian languages and code-mixed Hinglish?"*
  - *Response:* "Yes. The cognitive kernel separates communicative pragmatics (`SpeechIntent`) from linguistic surface text. By setting `locale = "hi-IN"` and routing generation through Sarvam-2B, our brain maintains identical memory, affect, and boundary invariants while outputting native Hinglish."

### 1.4 Proposed Proof-of-Concept (Option 1 - 2 to 3 Weeks)
- **Title:** Vernacular Persistent Companion with Bulbul v3 Integration.
- **Interface Seam:** Subclass `VoiceCompilerProtocol` as `SarvamVoiceCompiler` (`app/voice/compiler.py`), mapping `SpeechIntent` (affect, delivery, pause markers) to Sarvam `POST /text-to-speech` endpoints.
- **Success Gate:** End-to-end turn latency overhead added by compiler < 10.0 ms; multi-turn memory recall across simulated reboots; audible pace/pitch modulation reflecting internal affect state.

### 1.5 Strongest Empirical Evidence to Present
- **Cross-Provider Invariance (`BM-GPU-P7-02`):** 100.0% boundary and tone conformance across distinct model families (40/40 checks passed).
- **Bi-Temporal Memory Consistency (`BM-LOC-03`, `BM-LOC-04`):** Zero contradiction collisions across persistent storage restarts.

---

## 2. Partner Brief 2: ElevenLabs

### 2.1 Public Technical Context & Baseline
- **Mission & Focus:** Industry leader in voice synthesis, voice cloning, audio AI research, and conversational voice infrastructure.
- **Core Models & Technologies (Source: elevenlabs.io/docs, 2025-2026):**
  - **Turbo v2 / v2.5 (Streaming TTS):** Sub-200 ms streaming speech synthesis with high vocal quality across 32 languages.
  - **Scribe (Speech-to-Text):** Low-latency transcription engine.
  - **Conversational AI Platform:** End-to-end voice agent orchestrator combining ASR, configurable LLMs, and TTS with client-side tool calling and turn-taking models.

### 2.2 Architectural Fit & Complementary Strengths
- **What ElevenLabs Has:** The world standard for voice aesthetics, streaming audio compression, voice design, and global TTS infrastructure.
- **What Our Brain Adds:**
  - **Lifelong Autobiographical Memory:** Eliminates context-window amnesia and RAG semantic collisions.
  - **Expressive Cognitive Steering via `SpeechIntent`:** ElevenLabs exposes stability, similarity, and style sliders. Our brain computes continuous PAD affect coordinates and pause timeline markers, providing continuous emotional steering rather than flat static settings.
  - **Sub-Millisecond Barge-In Context Truncation:** Interruption halts audio playback and truncates spoken context in **0.099 ms** (`BM-GPU-02`), preventing the agent from remembering words it was interrupted before speaking.
- **What We Are NOT Asking Them to Replace:** We do not replace ElevenLabs voice models, voice cloning, or audio streaming infrastructure.

### 2.3 Anticipated Partner Objections & Technical Answers
- **Objection 1:** *"We already provide conversational agents with custom LLM endpoints and tools."*
  - *Response:* "Your platform provides outstanding audio orchestration, but conversational agents that rely solely on system prompts suffer from prompt bloat, memory collisions, and boundary drift over time. Our brain acts as an authoritative, single-owner cognitive state machine that feeds your TTS engine rich, emotionally grounded communicative intent."
- **Objection 2:** *"Does your state machine increase conversational latency?"*
  - *Response:* "In benchmark BM-GPU-P7-01 on consumer hardware, our entire pre-generation deliberation pipeline (perception, affect snapshot, bi-temporal memory search, and action planning) executed in **34.57 ms**. That overhead is negligible compared to the 200+ ms of network streaming."

### 2.4 Proposed Proof-of-Concept (2 Weeks)
- **Title:** Dynamic Cognitive Steering for ElevenLabs Conversational Voice.
- **Interface Seam:** `ElevenLabsVoiceCompiler` translating `SpeechIntent` into WebSocket streaming payloads with dynamic voice parameter adjustments (stability, style, pause markers).
- **Success Gate:** Sub-5 ms barge-in cutoff over local transport; audible prosody modulation across 10 distinct emotional states; zero memory drift over 100 turns.

### 2.5 Strongest Empirical Evidence to Present
- **Acoustic Barge-In Dispatch (`BM-GPU-02`):** Mean 0.099 ms, max 0.447 ms.
- **Composed Turn TTFT (`BM-GPU-P7-01`):** Mean 119.35 ms on consumer 8GB GPU.

---

## 3. Partner Brief 3: Unitree Robotics

### 3.1 Public Technical Context & Baseline
- **Mission & Focus:** World-leading quadruped and bipedal humanoid robotics manufacturer.
- **Core Hardware & Technologies (Source: unitree.com, 2024-2025):**
  - **Unitree G1 Humanoid ($16,000):** 1.32m tall, 35kg bipedal humanoid robot, 23 to 43 joint degrees of freedom, 2m/s walking speed, 3D LiDAR + RealSense camera.
  - **Unitree H1 Humanoid:** Full-size general-purpose humanoid biped.
  - **Compute Stack:** Onboard high-performance compute (supporting NVIDIA Jetson / x86 GPU acceleration), ROS2 interface, Unitree High-Level / Low-Level SDKs.

### 3.2 Architectural Fit & Complementary Strengths
- **What Unitree Has:** Unrivaled bipedal locomotion, dynamic stability, athletic hardware, and cost-effective commercial manufacturing.
- **What Our Brain Adds:**
  - **An Onboard Cognitive Mind:** The G1 currently relies on external cloud LLM demos. Our brain runs entirely offline on an onboard 8GB GPU footprint (RTX / Jetson Orin), providing real-time autonomy without network lag.
  - **Conversational Silence & Turn-Taking:** Eliminates clumsy chatter via validated `WAIT` action silence fidelity (100.0% compliance).
  - **Social Presence & Persistent Memory:** The robot remembers returning users, recalls prior household tasks, and updates relationship trust over time.
  - **Fail-Closed Action Safety:** G1 joint commands are arbitrated via `ExternalActionDispatcher` checking safety preconditions before execution.
- **What We Are NOT Asking Them to Replace:** We do not touch low-level motor controllers, joint kinematics, or balancing algorithms. We output high-level intent.

### 3.3 Anticipated Partner Objections & Technical Answers
- **Objection 1:** *"We focus on hardware dynamics, locomotion, and motor control, not conversational chat."*
  - *Response:* "Exactly. Your hardware and motor dynamics are best-in-class. But as you sell the G1 to developers and research labs, the #1 requested capability is social interaction and task persistence. Our brain provides an off-the-shelf cognitive layer that plugs directly into your ROS2 topics in less than two weeks."
- **Objection 2:** *"Will this require heavy cloud infrastructure?"*
  - *Response:* "No. The entire architecture was evaluated and verified on a single 8GB consumer GPU (`qwen2.5:3b` at 119 ms TTFT), fitting within the power and thermal limits of an onboard Jetson Orin module."

### 3.4 Proposed Proof-of-Concept (4 Weeks)
- **Title:** G1 Humanoid Embodied Social Interaction in Simulation.
- **Interface Seam:** ROS2 bridge connecting simulated camera and audio topics to `StructuredVisionPercept` and dispatching high-level navigation/manipulation goals to `ExternalActionDispatcher`.
- **Success Gate:** Onboard cognitive deliberation < 50 ms; multi-turn memory recall across reboots in simulation; 100% fail-closed action gating on safety violations.

### 3.5 Strongest Empirical Evidence to Present
- **WAIT Action Silence Fidelity (`BM-LOC-P7-02`):** 100.0% silence compliance across 1,000 runs.
- **Local Memory Soak Stability (`BM-LOC-SOAK`):** Zero memory leaks over continuous runtime (0.02% - 0.12% RSS variance).

---

## 4. Partner Brief 4: 1X Technologies

### 4.1 Public Technical Context & Baseline
- **Mission & Focus:** Designing androids capable of human-like assistance in home and work environments, prioritizing human safety and domestic social presence.
- **Core Hardware & Technologies (Source: 1x.tech, 2024-2025):**
  - **NEO Humanoid Android:** Bipedal domestic humanoid with soft tendon-driven actuators, quiet operation, and non-intrusive form factor.
  - **EVE Humanoid Android:** Wheeled domestic/industrial assistant deployed for security and logistics.
  - **AI Paradigm:** Strong emphasis on physical safety, teleoperation-to-autonomy imitation learning, and safe domestic human-robot interaction.

### 4.2 Architectural Fit & Complementary Strengths
- **What 1X Has:** Revolutionary soft tendon robotics hardware designed specifically for safe proximity with humans, combined with robust manipulation learning.
- **What Our Brain Adds:**
  - **Governed Learning with Microsecond Rollback (`BM-LOC-P7-04`):** If an autonomous android adapts its behavior in a household and begins exhibiting regressive or intrusive traits, our transactional governor reverts state in **14.28 microseconds** with 100% fidelity.
  - **Domestic Non-Intrusiveness:** A domestic robot must not talk unnecessarily. Our architecture features explicit communicative silence (`WAIT` action) and mood decay equations ensuring calm presence.
  - **Bi-Temporal Household Memory:** Recalls where objects belong, user schedules, and personal preferences without factual collision.
- **What We Are NOT Asking Them to Replace:** We do not replace their imitation learning motor policies, teleoperation data collection, or soft actuator controllers.

### 4.3 Anticipated Partner Objections & Technical Answers
- **Objection 1:** *"We are building end-to-end neural network policies for manipulation."*
  - *Response:* "End-to-end neural policies are ideal for low-level manipulation (e.g. grasping a cup). But domestic life requires high-level deliberative continuity: Who owns this cup? Where does it go? Is the user stressed right now? Our brain manages relational memory, affect, and goal selection, handing clean target directives to your manipulation policies."
- **Objection 2:** *"How do you guarantee domestic safety?"*
  - *Response:* "Our architecture enforces a three-tiered persona schema where Tier 1 Immutable Core invariants cannot be overwritten by LLM prompts or autonomous learning, backed by microsecond rollback upon probe detection."

### 4.4 Proposed Proof-of-Concept (4 Weeks)
- **Title:** Safe Domestic Deliberation & Memory Continuity for Humanoid Androids.
- **Interface Seam:** External action dispatch bridge mapping high-level domestic goals to 1X behavioral action servers, validating precondition and reversibility tags.
- **Success Gate:** 100.0% boundary conformance under adversarial home interaction probes; 14.28 us rollback fidelity; complete state persistence across reboots.

### 4.5 Strongest Empirical Evidence to Present
- **Governed Rollback Latency (`BM-LOC-P7-04`):** Mean 14.28 microseconds, 100.0% rollback fidelity.
- **Epistemic Quarantine Compliance (`BM-LOC-P7-03`):** 100.0% quarantine of speculative background reflections.
