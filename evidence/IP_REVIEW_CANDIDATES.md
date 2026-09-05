# Humanoid Brain Architecture: Intellectual Property & Prior-Art Review Candidates

## Document Status
- **Classification:** Technical IP Candidate Review & Prior-Art Investigation Scope
- **Audience:** Patent Attorneys, IP Review Committees, Technical Due Diligence Teams
- **Character Encoding:** Strict 7-bit ASCII
- **Authoritative System Commit:** Merged on `main` (`156f3b7`)

---

## 1. Executive Notice & Legal Disclaimer

This document does **not** constitute a formal legal opinion on patentability, freedom-to-operate, or statutory novelty under patent law (e.g. 35 U.S.C. 101/102/103 or EPC Article 52). Rather, this review identifies novel architectural mechanisms implemented, benchmarked, and validated in the AI Friend repository that represent non-trivial departures from standard agentic patterns, and recommends them as candidates for professional prior-art and intellectual property evaluation.

Every candidate identified here is categorized conservatively as:
`Candidate for professional IP/prior-art review`

---

## 2. IP Candidate 1: Closed-Loop Endocrine Modulation of Generative Sampling Hyperparameters

### 2.1 Technical Mechanism
A closed-loop subsystem that continuously maps internal continuous affect variables (specifically tonic and phasic mathematical representations of simulated cortisol, dopamine, and physical fatigue) directly to the physical inference sampling parameters (temperature, top_p nucleus sampling, and num_predict token limits) of an autoregressive foundation model.

Rather than injecting natural language instructions into the prompt ("You are stressed, act anxious"), the brain mathematically adapts the entropy and search space of next-token generation:
- Elevated cortisol (stress/threat) tightens temperature towards deterministic generation (T -> 0.2 - 0.4), suppressing exploratory branches and narrowing focus.
- Elevated dopamine (reward/curiosity) expands nucleus sampling (top_p -> 0.90 - 0.98), enabling associative, exploratory reasoning.
- Elevated fatigue shortens the maximum token budget (num_predict), enforcing cognitive brevity.

### 2.2 Implementation Location
- `app/cognitive/action.py` (function `_compute_endocrine_options`)
- `app/state/agent_state.py` (StateService affect locking and tonic/phasic burst derivation)
- `app/cognitive/core.py` (cognitive deliberation loop)

### 2.3 Empirical Evidence & Benchmarks
- Validated in BM-GPU-02: sub-millisecond execution latency (< 0.2 ms).
- Validated in BM-LOC-P7-01: zero memory leak during continuous dynamic sampling recalculation across 1,000 iterations.
- Produces measurably distinct text entropy without altering the base prompt text or requiring fine-tuned adapter switching.

### 2.4 Nearest Known Prior Art
- **Prompt-Based Roleplay:** Instructing LLMs via system prompts to simulate moods (e.g. "You feel happy"). (Prior art does not modify physical sampler hyperparameters).
- **Static Sampling Profiles:** Configuring fixed temperature per task type (e.g. T=0.2 for coding, T=0.7 for creative writing). (Prior art is open-loop, human-configured, and non-dynamic).
- **Cooling Schedules in Annealing:** Decay schedules in optimization or RL exploration (epsilon-greedy). (Prior art is task-step driven, not governed by dual-rate affective differential equations).

### 2.5 Points of Distinction
1. Continuous, bi-directional coupling between an independent cognitive state kernel and autoregressive decoding parameters.
2. Dual-rate tonic (valence/arousal baseline) and phasic (decaying event burst) decomposition mapped directly into generation sampling options.

### 2.6 Categorization & Confidence
- **Classification:** Potentially research/IP-worthy architectural mechanism.
- **Confidence:** Moderate-High.
- **Search Vectors:**
  - "Closed-loop affect neuromodulation of autoregressive LLM decoding parameters"
  - "Dynamic temperature and top-p adjustment based on internal affective state"
  - "Endocrine simulation for entropy control in generative conversational systems"

---

## 3. IP Candidate 2: Bi-Temporal Contradiction Resolution with Epistemic Quarantine

### 3.1 Technical Mechanism
A hybrid episodic, semantic, and relational memory retrieval architecture operating over two distinct temporal dimensions:
1. **Assertion Time (System Time):** The timestamp when the system observed or recorded a fact.
2. **Validity Time (World Time):** The real-world temporal interval [valid_from, valid_to] during which the fact is objectively true.

When a newly perceived event collides with an existing entity attribute, the system executes an automated bi-temporal interval update rather than overwriting or creating duplicate entries.

Crucially, this is paired with an **Epistemic Quarantine Layer** (`app/agents/subconscious_agent.py`):
During idle cycles, background reflection processes run "dream sequences" and associative hypothesis generation to discover non-obvious relationship links. An epistemic firewall strictly tags and isolates dream-derived insights, preventing unvalidated speculative associations from being written to long-term factual memory or contaminating hot retrieval paths.

### 3.2 Implementation Location
- `app/cognitive/temporal_store.py` (bi-temporal schema and interval mutation)
- `app/state/memory_store.py` (dual Postgres/SQLite retrieval with valid_to gating)
- `app/agents/subconscious_agent.py` (`_run_dream_sequence` and quarantine filters)

### 3.3 Empirical Evidence & Benchmarks
- Validated in BM-LOC-03 / BM-LOC-04: zero factual collisions across contradiction updates.
- Validated in BM-LOC-P7-03: 100.0% quarantine compliance (0 dream-derived memories leaked across 500 dream sequence cycles).
- Demonstrated in Demo Scenario 2: cold reboot preserves current truth and historical knowledge without hallucination.

### 3.4 Nearest Known Prior Art
- **Snodgrass Bi-Temporal Databases (SQL:2011 standard):** Traditional relational database management systems with transaction time and valid time. (Prior art applied to enterprise databases, not agentic conversational memory).
- **RAG Vector Similarity Search:** Top-K semantic retrieval using cosine distance. (Prior art suffers from semantic collision when outdated facts share high embedding similarity with new facts).
- **Generative Agent Reflection (Park et al., 2023):** Periodic summarization of agent memories into higher-level insights. (Prior art lacks bi-temporal interval pruning and lacks epistemic quarantine for speculative associations).

### 3.5 Points of Distinction
1. First known integration of formal bi-temporal interval filtering inside the fast-retrieval hot path of a conversational humanoid cognitive architecture.
2. Architectural isolation of background synthetic associative generation (dreaming) from retrieval-augmented generation memory tables via cryptographic or tag-based provenance firewalls.

### 3.6 Categorization & Confidence
- **Classification:** Potentially research/IP-worthy architectural mechanism.
- **Confidence:** High.
- **Search Vectors:**
  - "Bi-temporal interval filtering for conversational RAG memory stores"
  - "Epistemic quarantine for autonomous agent synthetic reflection and dreaming"
  - "Temporal contradiction resolution in entity-relationship memory graphs for AI agents"

---

## 4. IP Candidate 3: Governed Persona Engine with Invariant Protection and Microsecond Atomic Rollback

### 4.1 Technical Mechanism
A schema-enforced, three-tiered persona management engine that decouples agent personality into:
1. **Tier 1 - Immutable Core:** Foundational safety invariants and ethical boundaries that are structurally prohibited from being modified by prompts, user input, or autonomous reflection.
2. **Tier 2 - Constitutional Temperament:** Fixed psychological parameters (e.g. baseline valence bounds, mood decay rates) set at creation and strictly bounded.
3. **Tier 3 - Adaptive Persona:** User-seeded and agent-evolved traits that adapt over long-term interaction.

The system features an active `LearningGovernor` (`app/cognitive/learning_governance.py`). When background reflection proposes an update to Tier 3 adaptive traits:
- The proposal is validated against Tier 1 invariants.
- A risk tier (LOW, MEDIUM, HIGH) is assigned.
- If approved, the proposal is activated, and a transactional rollback snapshot is registered.
- If an automated probe or user feedback flags behavioral degradation, the system triggers an atomic rollback in microseconds, restoring the pre-learning persona baseline with 100% fidelity.

### 4.2 Implementation Location
- `app/persona/profile.py` (`PersonaProfile` schema tiers)
- `app/cognitive/learning_governance.py` (`LearningGovernor`, `LearningProposal`)
- `app/cognitive/identity.py` (`IdentityManager`)

### 4.3 Empirical Evidence & Benchmarks
- Validated in BM-LOC-08: sub-50 microsecond proposal evaluation and state staging.
- Validated in BM-LOC-P7-04: mean 14.28 us evaluation and atomic rollback latency across 1,000 iterations with 100.0% rollback fidelity.
- Demonstrated in Demo Scenario 4: instant reversion of regressive adaptive traits under adversarial probe evaluation.

### 4.4 Nearest Known Prior Art
- **Constitutional AI (Anthropic):** Iterative prompt-based self-critique against a constitution. (Prior art operates as runtime prompt text or fine-tuning datasets, not schema-enforced runtime memory tiers with atomic rollback).
- **Software Feature Flags / Rollback Engines:** Transactional database rollbacks or configuration management tools. (Prior art applied to DevOps/software deployment, not autonomous persona adaptation).
- **Agent Reflection Loops:** Automatic memory refinement without rollback governance. (Prior art is susceptible to jailbreak drift and permanent catastrophic persona corruption).

### 4.5 Points of Distinction
1. Tripartite architectural isolation of persona invariants where Tier 1 parameters do not exist as mutable model variables.
2. Transactional governance of autonomous persona adaptation featuring microsecond-latency deterministic rollback upon behavioral regression detection.

### 4.6 Categorization & Confidence
- **Classification:** Architectural mechanism with high practical IP/commercial relevance.
- **Confidence:** Moderate-High.
- **Search Vectors:**
  - "Governed transactional learning and rollback for autonomous agent persona"
  - "Three-tier persona architecture with immutable safety boundaries for conversational agents"
  - "Runtime regression gating and atomic rollback of learned agent traits"

---

## 5. IP Candidate 4: Decoupled Speech Intent Compiler with Expressive Loss Accounting

### 5.1 Technical Mechanism
A pragmatics-first communicative interface that completely separates cognitive speech planning from acoustic sound generation. The cognitive brain compiles its communicative goal into a vendor-neutral, versioned `SpeechIntent` schema carrying semantic text, dialogue acts, PAD emotional coordinates, epistemic uncertainty flags, relationship register, and timeline performance markers (pauses, emphasis, hesitations).

To interface with external TTS systems, the architecture utilizes capability-aware compiler adapters implementing a unified `VoiceCompilerProtocol`. When converting the intent into provider-specific API calls (e.g. ElevenLabs sliders, Sarvam Indic tags, GPT-SoVITS SSML tags):
- The compiler translates supported features.
- The compiler explicitly audits dropped or substituted expressive dimensions into a structured `IntentLossRecord`.
- A normalized fidelity score is computed and logged, making cognitive expressive degradation transparent and observable across different vendors.

### 5.2 Implementation Location
- `app/cognitive/speech_intent.py` (`SpeechIntent`, `SpeechAffect`, `SpeechEpistemics`)
- `app/voice/compiler.py` (`VoiceCompilerProtocol`, `ElevenLabsVoiceCompiler`, `GPTSoVITSVoiceCompiler`, `IntentLossRecord`)

### 5.3 Empirical Evidence & Benchmarks
- Validated in BM-LOC-02 and BM-LOC-P7-02: sub-millisecond dispatch latency.
- Validated in BM-GPU-02: zero spoken chunk leakage on WAIT silence intents.
- Successfully audited across ElevenLabs (cloud) and GPT-SoVITS (local) rendering pipelines with deterministic loss accounting.

### 5.4 Nearest Known Prior Art
- **W3C SSML (Speech Synthesis Markup Language):** Standardized XML tags (`<prosody>`, `<break>`) embedded in text. (Prior art intermingles acoustic markup directly with textual dialogue and lacks loss accounting).
- **TTS API Wrappers:** Python SDKs for ElevenLabs, Polly, or Azure Speech. (Prior art translates text without communicative intent models, affect mapping, or expressive loss calculation).
- **Dialogue Act Modeling:** Academic schemas for conversational dialogue acts (DAMSL). (Prior art describes linguistics, not runtime compilation to synthesis engines with fidelity tracking).

### 5.5 Points of Distinction
1. Decoupling of cognitive intention from acoustic realizing markup, ensuring zero vendor lock-in in the brain core.
2. Automatic generation of an `IntentLossRecord` that calculates expressive degradation when compiling complex cognitive speech intents for limited voice providers.

### 5.6 Categorization & Confidence
- **Classification:** Architectural mechanism with high commercial integration utility.
- **Confidence:** Moderate.
- **Search Vectors:**
  - "Decoupled speech intent compiler for conversational AI"
  - "Expressive loss accounting and fidelity scoring in text to speech compilation"
  - "Vendor-neutral speech intent schema for humanoid robotics"

---

## 6. Summary Comparison Table

| Candidate ID | Core Architectural Mechanism | Primary Code Seams | Validated Metric | Prior Art Risk | Recommended Action |
|---|---|---|---|---|---|
| **IP-01** | Endocrine Generative Sampling Modulation | `cognitive/action.py` `state/agent_state.py` | Latency < 0.2 ms, dynamic T/top_p | Moderate | Prior-Art Search & Paper Publication |
| **IP-02** | Bi-Temporal Memory & Dream Quarantine | `cognitive/temporal_store.py` `agents/subconscious_agent.py` | 100% quarantine, 0 contradictions | Low-Moderate | Comprehensive Prior-Art Patent Search |
| **IP-03** | Governed Persona & Atomic Rollback | `cognitive/learning_governance.py` `persona/profile.py` | 14.28 us rollback, 100% fidelity | Moderate | Commercial IP Evaluation |
| **IP-04** | Speech Intent Compiler & Loss Accounting | `cognitive/speech_intent.py` `voice/compiler.py` | Sub-ms dispatch, auditable loss | Moderate | Open Specification / Commercial Asset |

---

## 7. Recommended Next Steps for Legal & IP Counsel
1. Conduct formal patentability and prior-art searches on Candidates IP-01 and IP-02 focusing on the USPTO, EPO, and WIPO databases.
2. Review public disclosures and commit history on the repository to verify statutory bar dates and public disclosure timelines.
3. Coordinate potential defensive publication or provisional patent applications prior to open-sourcing or external partner licensing discussions.
