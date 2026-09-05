# Technical Partnership Call Execution Guide

## Document Status
- **Classification:** Internal Engineering Protocol for Partner Discovery Calls
- **Target Call Duration:** 25 to 30 Minutes
- **Audience:** AI Friend Technical Lead / Presenter
- **Character Encoding:** Strict 7-bit ASCII
- **Authoritative System Commit:** Merged on `main` (`156f3b7`)

---

## 1. Call Objective & Guiding Mindset

### Primary Objective
Secure agreement on a **staged 2-to-3 week proof-of-concept (PoC)** using our pre-built adapter interfaces (`VoiceCompilerProtocol` or `ExternalActionDispatcher`).

### Guiding Mindset
- **Lead with Engineering, Not Sales:** Speak engineer-to-engineer. Show latency traces, logs, and benchmark tables rather than marketing slides.
- **Respect Partner Specialization:** Emphasize that we do NOT compete with their core specialization (speech synthesis, acoustic tokenization, motor control). We provide the persistent cognitive mind that sits above their stack.
- **Be Intellectually Honest:** Transparently acknowledge consumer GPU prompt evaluation bottlenecks and fail-closed actuator stubs rather than overstating production completeness.

---

## 2. Recommended 25-Minute Call Flow & Agenda

```
[00:00 - 03:00]  1. Context & The Core Problem (Prompt amnesia, boundary drift, clumsy turn-taking)
[03:00 - 07:00]  2. What We Built & Architectural Boundary (Externalized state kernel, model independence)
[07:00 - 13:00]  3. Live Demo Walkthrough (Model invariance, bi-temporal memory truth, sub-ms barge-in)
[13:00 - 17:00]  4. Empirical Validation & Benchmarks (TTFT 119 ms, barge-in 0.099 ms, 14 us rollback)
[17:00 - 21:00]  5. Partner Integration Seam & Proposed PoC (Voice compiler / ROS2 bridge)
[21:00 - 27:00]  6. Technical Q&A & Objection Handling (Citing FAQ)
[27:00 - 30:00]  7. Clear Next Step Agreement (PoC scope document & sandbox credentials)
```

---

## 3. Minute-by-Minute Speaking Script & Notes

### Phase 1: Context & The Core Problem (3 Minutes)
- *"Thank you for taking the time. To set context: Everyone in AI is trying to build persistent conversational agents and embodied humanoids. But virtually all of them rely on the same naive pattern: piping audio into an LLM system prompt and piping text out."*
- *"When deployed for more than a few minutes, that approach hits three fundamental walls: First, prompt context bloat makes real-time voice latency impossible. Second, vector RAG retrieves outdated facts, causing contradictions. Third, switching underlying foundation models destroys character identity and safety guardrails."*

### Phase 2: What We Built & Architecture Boundary (4 Minutes)
- *"We took an entirely different architectural path: We built an autonomous, state-first **Cognitive Humanoid Brain** that decouples identity, autobiographical memory truth, and emotional state from the foundation model."*
- *"The model performs linguistic generation, but the model is not the brain. The brain owns a continuous PAD affect state machine, bi-temporal memory validity intervals, and an active governance layer."*
- *[Share simplified architecture diagram from `INTEGRATION_BOUNDARIES.md`]*

### Phase 3: Targeted Live Demonstration Walkthrough (6 Minutes)
*Select 1 or 2 demos tailored to the partner:*

#### If Talking to a Voice Partner (Sarvam / ElevenLabs):
- **Demo A: Sub-Millisecond Barge-In & Endocrine Sampling:**
  - *"Watch what happens when user audio interrupts mid-turn: In 0.099 ms, audio playback cuts off and the cognitive turn is truncated. The agent does not talk over the user, and its internal state remembers exactly where it was interrupted."*
- **Demo B: Communicative Silence (`WAIT` Action Fidelity):**
  - *"Notice when the user pauses to think: The brain deliberates and selects a WAIT action with 100% silence fidelity. It emits zero spoken tokens, enabling natural human listening cadence."*

#### If Talking to a Robotics Partner (Unitree / 1X):
- **Demo A: Bi-Temporal Contradiction Resolution across Cold Reboots:**
  - *"User states 'I live in Seattle' in Turn 1, then 'I moved to Tokyo' in Turn 2. We kill the process and reboot. Upon restart, the robot immediately asserts Tokyo as current truth and Seattle as past truth, with zero semantic collision."*
- **Demo B: Governed Learning with 14-Microsecond Atomic Rollback:**
  - *"When an autonomous reflection updates adaptive traits, our transactional governor evaluates the update against immutable safety invariants. When a probe flags regression, the system rolls back to baseline in 14.28 microseconds."*

### Phase 4: Empirical Benchmark Evidence (4 Minutes)
- *Display benchmark highlights on consumer NVIDIA RTX 2060 Super (8GB VRAM):*
  - Composed Turn TTFT: **119.35 ms** (Deliberation: **34.57 ms**, Prompt eval: **84.78 ms**).
  - Cross-Provider Invariance: **100.0% adherence** across Qwen 2.5 and Llama 3.2 (40/40 checks passed).
  - Memory Soak Stability: **0.02% - 0.12% RSS variance** over thousands of turns.

### Phase 5: Where Their Technology Fits & Proposed PoC (4 Minutes)
- *"We are not here to sell you proprietary software or ask you to replace your stack. We want your engine to become the primary expression layer for our cognitive brain."*
- *Propose PoC:*
  - **For Voice Partners:** Subclass `VoiceCompilerProtocol` (`app/voice/compiler.py`) to compile `SpeechIntent` into their streaming TTS API over 2 weeks.
  - **For Robotics Partners:** Connect our `ExternalActionDispatcher` to their ROS2 high-level action servers in simulation over 3 weeks.

### Phase 6: Technical Q&A & Objection Handling (6 Minutes)
*(Refer to calibrated answers in Section 4 below).*

### Phase 7: Clear Next Step (3 Minutes)
- *"To keep this zero-friction: We will email you our 2-page Technical One-Pager and PoC Scope Document today. If you agree, we can spin up a container with the compiler adapter next week and schedule a 30-minute check-in."*

---

## 4. Tough Partner Objections & Field-Tested Responses

### Objection 1: "Why shouldn't we just build this memory and state layer in-house?"
**Field-Tested Response:**
*"You certainly have talented engineers who could try. But building a production-grade cognitive architecture that unifies bi-temporal relational intervals, dual-rate tonic/phasic affect equations, sub-millisecond barge-in, and transactional learning governance took us seven iterative implementation phases, formal peer reviews, and thousands of automated tests. Integrating with our pre-built adapter takes two weeks; building and verifying it in-house will take six to twelve months of specialized cognitive systems engineering."*

### Objection 2: "Doesn't adding a state machine and memory search blow up our TTFT latency budget?"
**Field-Tested Response:**
*"That was our primary engineering concern during Phase 07. We benchmarked every microsecond: our entire pre-generation cognitive deliberation (perception envelope, affect lock, bi-temporal memory search, and action planning) executes in **34.57 milliseconds** on consumer hardware. The foundation model prefill takes 84 ms. The cognitive overhead is negligible compared to network and acoustic generation times."*

### Objection 3: "Does your system require us to share our internal neural weights or proprietary code?"
**Field-Tested Response:**
*"Absolutely not. The entire integration boundary is strictly decoupled. We communicate with your service via public REST/WebSocket APIs or ROS2 topics. Your models, weights, and algorithms remain 100% proprietary and untouched."*

---

## 5. Security & IP Boundaries: What NOT to Disclose in Call 1

To maintain professional IP discipline, do NOT share:
1. **Raw System Prompts / Identity Seeds:** Do not share verbatim system prompt text or internal constitutional files.
2. **Unpublished IP Algorithmic Mathematical Formulations:** Do not walk through the exact differential equations used for the endocrine tonic/phasic sampling modulation or the internal database schemas.
3. **Repository Git Access:** Do not provide repository commit access or raw internal source archives during initial exploratory calls. Share packaged Docker containers or compiled binaries.
4. **Internal Test Credentials / API Keys:** Never display live API keys or internal database connection strings in terminal recordings.

---

## 6. Desired Next Step Agreement
Before concluding the call, confirm:
1. Designated technical POC on the partner side.
2. Agreement to review the 2-page PoC proposal.
3. Follow-up meeting scheduled 7 to 10 days out to review adapter integration progress.
