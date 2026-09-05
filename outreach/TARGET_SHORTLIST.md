# Partnership Outreach: Target Shortlist & Scoring Model

## Document Status
- **Classification:** Strategic Outreach Prioritization & Tiering
- **Audience:** Core Engineering Team, Partnership Leads
- **Character Encoding:** Strict 7-bit ASCII
- **Authoritative System Commit:** Merged on `main` (`156f3b7`)
- **Evidence Sources:** `evidence/`, `partnership/`

---

## 1. Target Scoring Model

To avoid subjective prioritization, potential partners are evaluated across five objective criteria (max 100 points):

1. **Technical Alignment (Weight: 25%):** Degree to which the partner stack naturally interfaces with our cognitive boundaries (`VoiceCompilerProtocol`, `StructuredVisionPercept`, `ExternalActionDispatcher`).
2. **Integration Feasibility (Weight: 20%):** Ease of completing a 2-to-3 week PoC using public/developer APIs or standard protocols (WebRTC, ROS2, WebSocket) without custom hardware.
3. **Pain Point Relevance (Weight: 20%):** Urgency of their need for persistent state, bi-temporal memory truth, sub-millisecond barge-in, or governed learning.
4. **Accessibility & Engagement Speed (Weight: 15%):** Likelihood of reaching a technical decision-maker and obtaining a technical discovery call.
5. **Strategic Credibility & Ecosystem Value (Weight: 20%):** Commercial leverage, reference-customer impact, and joint demonstration visibility.

---

## 2. Ranked Target Summary Table

| Rank | Organization | Category | Score / 100 | Tier | Primary Technical Seam | Recommended Target Role |
|---|---|---|---|---|---|---|
| **1** | **Sarvam AI** | Voice AI / Indic Multilingual | **92** | **Tier 1** | `SarvamVoiceCompiler` (Bulbul v3 / Indic TTS) | Co-founder / CTO / Head of Speech Research |
| **2** | **ElevenLabs** | Voice AI / Conversational Platform | **89** | **Tier 1** | `ElevenLabsVoiceCompiler` (Turbo v2 / WebSockets) | Head of Conversational AI / Applied Research Lead |
| **3** | **Unitree Robotics**| Humanoid Robotics OEM | **84** | **Tier 1** | `ExternalActionDispatcher` (ROS2 / G1 Humanoid) | Head of Embodied AI / Robotics Software Director |
| **4** | **1X Technologies** | Domestic Humanoid Androids | **82** | **Tier 1** | `StructuredVisionPercept` + ROS2 Action Servers | VP of AI / Embodied HRI Research Lead |
| **5** | **Cartesia** | Ultra-Low Latency Streaming Voice | **78** | **Tier 2** | LiveKit / WebSocket Streaming Sink | Founder / Head of Engineering |
| **6** | **Alibaba (Qwen)** | Open-Weights Edge LLMs | **76** | **Tier 2** | `OllamaClient` / vLLM KV-Cache Pinning | Qwen Edge / On-Device Lead |
| **7** | **Figure AI** | Commercial Humanoid Robotics | **72** | **Tier 2** | High-Level Task Scheduler Bridge | AI Interaction / Autonomous Behavior Lead |
| **8** | **Stanford HAI** | Academic Cognitive Agents | **70** | **Tier 3** | Empirical Memory & Affect Testbed | Faculty / Postdoctoral Lead (Generative Agents) |
| **9** | **CMU Robotics** | Academic Social Robotics (HRI) | **68** | **Tier 3** | Sub-ms Barge-In & Turn-Taking HRI | Social Robotics Lab Director |
| **10**| **NVIDIA Isaac** | Simulation & Foundation Models | **67** | **Tier 3** | Omniverse ROS2 Bridge (GR00T) | Developer Relations / Embodied AI Lead |

---

## 3. Tier 1 High-Priority Targets

### 3.1 Rank 1: Sarvam AI
- **Category:** Voice AI, Speech Recognition, Multilingual Indian LLMs
- **Overall Score:** **92 / 100**
  - *Technical Alignment:* 24/25 | *Feasibility:* 19/20 | *Pain Point:* 19/20 | *Accessibility:* 13/15 | *Strategic Value:* 17/20
- **Why Relevant:** Sarvam has established leading Indic speech synthesis (Bulbul v3) and recognition (Saarika v2.5) models across 22 Indian languages. However, their conversational voice platforms operate as standard prompt wrappers. Combining their vernacular acoustic superiority with our persistent cognitive brain creates an unassailable multilingual embodied companion.
- **Recommended Role to Approach:** Co-founder / Head of AI Research (e.g. Pratyush Kumar or Vivek Raghavan) or Speech AI Tech Lead.
- **First Ask:** 30-minute technical architecture review to propose a 2-week PoC compiling `SpeechIntent` to Bulbul v3 with affect and code-mixed Hinglish preservation.
- **Recommended Channel:** Direct professional outreach via LinkedIn / academic research networks.

### 3.2 Rank 2: ElevenLabs
- **Category:** Voice AI & Conversational AI Platforms
- **Overall Score:** **89 / 100**
  - *Technical Alignment:* 24/25 | *Feasibility:* 19/20 | *Pain Point:* 18/20 | *Accessibility:* 11/15 | *Strategic Value:* 17/20
- **Why Relevant:** ElevenLabs is the global benchmark for expressive streaming voice synthesis (Turbo v2/v2.5) and has recently pushed into conversational agents. Their current conversational agents rely on standard LLM system prompts and stateless client-tools. Our brain provides lifelong memory continuity, bi-temporal contradiction resolution, sub-millisecond barge-in context truncation, and affective modulation.
- **Recommended Role to Approach:** Head of Conversational AI, Lead Applied Research Scientist, or CTO (Piotr Dabkowski).
- **First Ask:** 30-minute technical discussion demonstrating our `ElevenLabsVoiceCompiler` adapter and showing how `SpeechIntent` affect controls eliminate conversational flatness.
- **Recommended Channel:** Developer platform / Technical Discord / LinkedIn direct reach-out to conversational engineering leads.

### 3.3 Rank 3: Unitree Robotics
- **Category:** Humanoid Robotics Hardware OEM (Unitree G1, H1)
- **Overall Score:** **84 / 100**
  - *Technical Alignment:* 21/25 | *Feasibility:* 17/20 | *Pain Point:* 19/20 | *Accessibility:* 11/15 | *Strategic Value:* 16/20
- **Why Relevant:** Unitree has commoditized bipedal humanoid hardware with the G1 ($16k), featuring 23-43 degrees of freedom and onboard compute. While motor control is state-of-the-art, their conversational interaction is a generic cloud LLM wrapper. Our brain can run locally on the G1 onboard compute (8GB GPU footprint), providing autonomous offline social intelligence, memory of recurring users, and fail-closed action gating.
- **Recommended Role to Approach:** Head of Embodied AI / Robotics Software Director.
- **First Ask:** 30-minute technical demonstration in Gazebo/Isaac Sim showing our brain ingesting simulated camera percepts and driving high-level G1 behavioral actions.
- **Recommended Channel:** Professional outreach via technical robotics conferences (IROS/ICRA contacts) or developer relation channels.

### 3.4 Rank 4: 1X Technologies
- **Category:** Safe Domestic Humanoid Androids (NEO, EVE)
- **Overall Score:** **82 / 100**
  - *Technical Alignment:* 20/25 | *Feasibility:* 16/20 | *Pain Point:* 19/20 | *Accessibility:* 10/15 | *Strategic Value:* 17/20
- **Why Relevant:** 1X builds domestic androids designed to safely share homes with humans. Home environments require non-intrusive silence (`WAIT` action fidelity), multi-month memory of household preferences, and zero boundary drift. Our validated 14.28 microsecond rollback and 100% boundary invariance directly mitigate domestic safety liability.
- **Recommended Role to Approach:** VP of AI / Embodied HRI Research Lead.
- **First Ask:** 30-minute engineering exchange on conversational turn-taking and bi-temporal memory for domestic humanoid robots.
- **Recommended Channel:** Public technical email / LinkedIn outreach to AI software leadership.

---

## 4. Tier 2 Strong Alternative Targets

- **Cartesia (Score: 78):** Focused on ultra-low latency streaming voice (< 100 ms). High technical fit; provides an ideal testbed for combining sub-35 ms cognitive deliberation with ultra-fast audio rendering.
- **Alibaba Cloud / Qwen Team (Score: 76):** Developers of `qwen2.5:3b`, our reference validated model. Strong alignment on edge inference; potential for co-branded reference architecture benchmarks demonstrating enterprise safety boundaries around compact models.
- **Figure AI (Score: 72):** Leading commercial humanoid developer. Highly vertically integrated with OpenAI, making initial technical adoption more difficult, but highly aligned on embodied multi-turn task persistence.

---

## 5. Tier 3 Academic & Long-Term Targets

- **Stanford HAI (Score: 70):** Pioneers of generative agent simulations. Excellent fit for academic co-authorship on bi-temporal memory truth and closed-loop endocrine sampling neuromodulation.
- **CMU Robotics Institute (Score: 68):** World leaders in Human-Robot Interaction (HRI). Strong fit for empirical user studies evaluating social rapport and sub-millisecond barge-in pacing.
- **NVIDIA Isaac / Project GR00T (Score: 67):** Dominant simulation and foundation model stack for robotics. Target for integrating the cognitive deliberative layer above GR00T motor policies in Omniverse.

---

## 6. Outreach Execution Strategy & Sequencing

To maximize impact and refine our pitch with real feedback, outreach should follow a strict sequential cadence:

```
[Phase 1: Week 1]  ---> Reach out to Sarvam AI (High fit, regional agility)
                                |
[Phase 2: Week 2]  ---> Reach out to ElevenLabs (Voice platform standard)
                                |
[Phase 3: Week 3]  ---> Reach out to Unitree Robotics (Embodied hardware)
                                |
[Phase 4: Week 4]  ---> Reach out to 1X Technologies & Tier 2 Targets
```

**Rule of Discipline:** Do not contact more than two organizations concurrently in Week 1. Calibrate messaging and technical responses based on initial feedback before broadening the funnel.
