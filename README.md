# 🎙️ AI Friend: Cognitive Voice System (v6.5.0 / CVS-3.5 Premium Edition)

**A high-fidelity, state-driven cognitive identity emulator built on a hardened Sovereign Mesh for ultra-low latency conversational realism.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)
[![Latency: Perceived <250ms](https://img.shields.io/badge/Latency-Perceived%20%3C250ms-green.svg)](#performance-perceived-slos)
[![Architecture: CVS-3.5 Premium](https://img.shields.io/badge/Architecture-CVS--3.5--Premium-orange.svg)](#️-technical-architecture-the-sovereign-mesh)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](<https://colab.research.google.com/github/Aniket-a14/AI_friend/blob/main/notebooks/ai_friend_voice_training.ipynb>)
[![Continuous Integration](https://github.com/Aniket-a14/AI_friend/actions/workflows/ci.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/ci.yml>)
[![🛡️ Mesh Integrity](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml>)
[![🧠 Cognitive Regression](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml>)
[![🎭 Persona Guard](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml>)
[![🔒 Security Audit](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml>)
[![📦 Docker Build](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-build.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-build.yml>)
[![🩺 Docker Health](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml>)
[![🔗 Link Validator](https://github.com/Aniket-a14/AI_friend/actions/workflows/links.yml/badge.svg)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/links.yml>)
[![🚀 Release Status](https://github.com/Aniket-a14/AI_friend/actions/workflows/release.yml/badge.svg?branch=main)](<https://github.com/Aniket-a14/AI_friend/actions/workflows/release.yml>)
[![Platforms: Windows | macOS | Linux](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-blueviolet.svg)](#-release-package-selection-guide)
[![Arch: Multi-Platform](https://img.shields.io/badge/Architectures-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)](#-release-package-selection-guide)
[![Release Assets: 3 Packages](https://img.shields.io/badge/Release%20Assets-3%20Packages-success.svg)](#-release-package-selection-guide)

**CALIBRATION: EXPERT** — *This documentation assumes proficiency in asynchronous event-driven architectures, NATS JetStream protocols, and computational cognitive modeling (BDI, PAD, ACT-R, MAUT).*

---

## 🌟 The Philosophy of Perceptual Mastery

AI Friend is not a reactive "turn-based" chatbot. It is a **Sovereign Mesh** of specialized agents synchronized through a hardened signal bus. In the **CVS-3.5 (Premium Edition)** release, the architecture shifted from legacy Python audio loops to a **High-Performance Rust Signal Mesh**, guaranteeing sub-50ms deterministic execution and true temporal identity continuity.

### 🧠 Reactive vs. Sovereign Intelligence

| Feature | Reactive Chatbot (Legacy) | Sovereign Mesh (CVS-3.5) |
| :--- | :--- | :--- |
| **Execution** | Python Interpreter | PyO3 FFI / Native Rust Crates |
| **Cognitive Loop** | Synchronous Request-Response | Asynchronous Event-Driven |
| **State** | Session-based / Stateless | Persistent / Self-Maturing |
| **Emotion** | Prompt-driven labels | Deterministic mathematical drift (PAD) |
| **Timing** | Playback delay | Physically injected PCM silent buffers |
| **Memory** | Passive search (RAG) | Proactive activation (ACT-R) |
| **Topology** | Centralized API | Decentralized Local Mesh |

### Why Perceptual Mastery?

The success of a cognitive voice system is measured by **conversational realism**, not just linguistic correctness. A technically accurate answer that arrives with unnatural timing or forgets recent emotional context is a behavioral failure. AI Friend solves this through **speculative perception** and **deterministic affect**:

* **Identity Continuity**: Personality, values, and relationship state survive long sessions and hardware restarts.
* **Organic Timing**: Pauses and hesitations are physically injected as silent PCM buffers, not just text tags.
* **Privacy Sovereignty**: 100% local execution ensures your identity genome never leaves your hardware.

---

## 🏗️ Technical Architecture: The Sovereign Mesh

### 1. System Topology Map

The platform utilizes **NATS JetStream** as its central nervous system, routing typed Pydantic messages between autonomous agents.

> [!NOTE]
> **Architecture Description**:
> The system follows a decoupled "Signal Bus" pattern. The **NATS JetStream** serves as the message backbone, enforcing strict communication contracts across nine core subjects.
>
> * **Sensory Agents**: The **STT Agent** and **Vision Agent** publish perceptual signals to the bus.
> * **Cognitive Agents**: The **Brain Agent** (Decision Core), **Subconscious Agent** (Idle reflection), and **Surfacing Agent** (Memory) process these signals asynchronously.
> * **Infrastructure**: **Neo4j** stores the high-dimensional knowledge graph, while **PostgreSQL** with `pgvector` manages episodic memories and relational identity state.
> * **Signal Rendering**: The **Voice Agent** consumes decision events to produce high-fidelity 32kHz PCM audio.

```mermaid
graph TD
    User((User)) <--> |"WebRTC / PCM"| Frontend["Next.js Frontend"]
    Frontend <--> |"FastAPI"| Signaling["Signaling Server"]

    subgraph "WebRTC Bridge"
        Transport["TransportAgent"]
    end

    Signaling <--> LK["LiveKit SFU"]
    LK <--> Transport

    subgraph "Sovereign Mesh — Typed Contract Layer"
        Transport <--> |"audio.inbound / audio.stream"| Bus{"NATS JetStream"}
        Bus <--> |"chat.input / audio.perception"| STT["STT Agent: Dual-Path"]
        Bus <--> |"chat.input / chat.output"| Brain["Brain Agent: BDI Cognition"]
        Bus <--> |"chat.output / audio.stop/resume"| Voice["Voice Agent: Rust PyO3 Audio"]
        Bus <--> |"vision.control / vision.description"| Vision["Vision Agent: Host-Native VLM"]
        Bus <--> |"system.tick"| Pulse["System Agent: Heartbeat"]
        Bus <--> |"memory.surfaced / state.update"| Recall["Surfacing Agent: Memory"]
        Bus <--> |"chat.input (subconscious)"| Subconscious["Subconscious Agent: Autonomy"]
    end

    subgraph "Cognitive Core"
        Perception["PerceptionService"]
        Appraisal["AppraisalEngine — OCC/Lazarus"]
        Decision["DecisionService — MAUT + BT"]
        Action["ActionService — LLM Stream"]
        State["StateService — PAD + ALMA"]
        Learning["ReflectionService"]
        Identity["IdentityManager"]
    end

    Brain --> Perception --> Appraisal --> Decision --> Action
    Brain --> State
    Brain --> Learning --> Identity

    subgraph "Voice Subsystem — Rust crate: backend/crates/voice-agent"
        Prosody["Prosody — PAD → rate/pitch/volume"]
        Playback["Playback — OLA crossfade + reverb DSP"]
        Resilience["Resilience — speculative fillers"]
    end

    Voice --> Prosody
    Voice --> Playback
    Voice --> Resilience

    subgraph "Infrastructure"
        Brain <--> Neo4j[("Neo4j: Knowledge Graph")]
        Brain <--> Postgres[("Postgres + pgvector")]
        Action --> Ollama["Ollama: Local LLM"]
        Voice --> SoVITS["GPT-SoVITS (voice cloning, no fallback engine)"]
    end
```

### 2. Perceptual Interruption Protocol

CVS-3.5 utilizes a **Dual-STT fan-out** with a 3-stage interruption arbitration protocol.

> [!WARNING]
> **Implemented and build-verified; not yet heard.** The `stt-agent` crate embeds
> real speech recognition (whisper.cpp via `whisper-rs` for the accurate path,
> SenseVoice via `sherpa-onnx` for the fast path), with 16 kHz sinc resampling and
> VAD endpointing, defaulting to `STT_BACKEND=whisper`. Two caveats:
>
> 1. **SenseVoice requires host-side provisioning.** Run
>    `python backend/scripts/bootstrap/provision_models.py` once; docker-compose
>    bind-mounts the result. Without it the fast path falls back to a small Whisper
>    model: barge-in keeps working, but the emotion / paralinguistic fields stay
>    empty — the agent hears words, not tone — and the logs say so loudly.
> 2. **No live transcription has been observed.** Both backends compile, link and
>    pass the crate's unit tests (including cross-language wire-shape tests), but
>    no audio has been transcribed end-to-end and no acoustic emotion has been
>    classified on a live utterance. Treat accuracy and latency as **unmeasured**.
>    Building requires `libclang` (`cmake` + `clang`); `Dockerfile.rust` installs both.

<!-- -->

> [!WARNING]
> **The Vision Agent must run on the host on Windows and macOS.** It is excluded
> from the default compose stack and gated behind the `vision` profile. Capture is
> host-bound, verified empirically rather than assumed: inside a Linux container
> there is no `/dev/video*`, `--device=/dev/video0` is rejected by the daemon,
> `/tmp/.X11-unix` is absent with `DISPLAY` unset, and `mss` fails outright with
> `Library libxcb.so not found`. On a Windows/macOS host the container runs in a
> Linux VM with no route to the host's display or webcam, so no configuration
> resolves this.
>
> ```bash
> pip install -r backend/requirements-ai.txt   # mss + opencv-python
> NATS_URL=nats://127.0.0.1:4222 python -m app.vision.agent
> ```
>
> On a **Linux** host the containerised path does work — uncomment the `devices`
> and/or X11 entries in the `vision_agent` service and run
> `docker compose --profile vision up vision_agent`.
>
> The agent probes capture at startup and logs prominently when it is blind, and
> its healthcheck reads a sentinel touched on each successful capture rather than
> `pgrep python`, which passes just as happily when every frame returns `None`.
>
> **Somatic response is learned, and starts empty.** Recognising a comfort object
> lifts valence/arousal (and so dopamine) only for objects the agent has actually
> learned about — facts `learning.py` tagged `somatic` in Neo4j. A fresh agent, or
> one running without Neo4j, recognises nothing and no spike fires. That cold start
> is deliberate: no comfort vocabulary is hardcoded.

<!-- -->

> [!IMPORTANT]
> **Protocol Description**:
> Audio arriving via WebRTC is fanned out to two paths: **SenseVoice**
> (`STT_SENSEVOICE_DIR`; classifies speech emotion and audio events alongside the
> words) for speculative temporal intent, and **Whisper** (`STT_ACCURATE_MODEL`,
> default `base.en`) for semantic accuracy. When no SenseVoice model is provisioned
> the fast path degrades to a small Whisper model (`STT_FAST_MODEL`, default
> `tiny.en`) and no emotion is inferred.
>
> * **Stage 1 (Reflexive Soft-Attenuation)**: The fast path transcribes a speculative partial and publishes a speculative `audio.stop` if it detects an interruption marker. The Voice Agent immediately executes a **System 1 soft-attenuation**, ducking the volume by 70% within 10ms to allow duplex listening. Partials are only emitted once the endpointer confirms speech, so a cough cannot trigger this. Detection latency is **unmeasured** — see the warning above.
> * **Stage 2 (Symbolic Interruption Validation)**: The Brain Agent evaluates the speculative perception text. If confirmed, it commits a hard `audio.stop` (aborting playback and LLM generation). If rejected as noise or a non-interruption, it publishes `audio.resume`, causing the Voice Agent to smoothly ramp output volume back to 100%.
> * **Stage 3 (Resolution)**: Once Whisper produces the final transcript, the Brain Agent performs a deep cognitive turn to update state and generate the response.

```mermaid
sequenceDiagram
    participant U as User
    participant H as Host (Windows)
    participant T as TransportAgent (Docker)
    participant WF as "SenseVoice (Fast Path)"
    participant W as "Whisper base.en (Accurate Path)"
    participant VA as "Vision Agent (VLM)"
    participant B as Brain Agent (Decision)
    participant V as Voice Agent (CVS)

    Note over U, H: Multimodal Input (Sight & Sound)
    par Visual Appraisal (Host-Resident)
        H->>VA: Screen/Cam Buffer (Host-Native)
        VA->>VA: VLM Inference (moondream)
        VA->>B: vision.description (nc.publish)
    and Audio Perception (Mesh)
        U->>T: WebRTC Audio
        T->>T: PCM → audio.inbound
        par Dual-STT Fan-Out
            T->>WF: 400ms chunks (Speculative)
            T->>W: Full utterance (Semantic)
        end
    end

    Note over WF, B: Stage 1 — Speculative Perception
    WF->>B: AudioPerception (intent + emotion + audio events)
    WF-->>V: audio.stop (speculative=true)
    V->>V: Immediate OLA Pause

    Note over W, B: Stage 2 — Semantic Resolution
    W->>B: ChatInput (Typed Contract)
    B->>B: Multimodal Context Merge (Audio + Vision)

    Note over B, V: Stage 3 — Cognitive Action
    B-->>V: audio.stop (confirmed) / audio.resume
    B->>V: ChatOutput (Segments + Affect Vector)

    Note over V, U: Stage 4 — Signal Rendering
    V->>V: prosody mapping → OLA playback (Rust)
    V->>T: 32kHz PCM → audio.stream
    T->>U: WebRTC Audio
    V-->>B: voice.segmentation_feedback (Telemetry)
    Note over B,V: Closed-Loop Pulse Adjustment
```

---

## 🧠 Detailed Agent Registry

The Sovereign Mesh consists of specialized agents, each serving a distinct role in the cognitive lifecycle.

| Agent | Technology | Primary Responsibility | NATS Subjects |
| :--- | :--- | :--- | :--- |
| **Brain Agent** | Python / Ollama | Cognitive core; manages BDI loops and decision state. | `chat.*`, `state.*`, `knowledge.*` |
| **Voice Agent** | Rust / GPT-SoVITS | CVS-3.5 synthesis runtime; renders affect-aware 32kHz audio through a single cloned-voice engine, no fallback to a different voice. | `chat.output`, `audio.stream`, `audio.stop` |
| **STT Agent** ⚠️ | Rust / whisper.cpp + sherpa-onnx | Real speech recognition, dual-path: whisper.cpp (`whisper-rs`) produces the final transcript; SenseVoice (`sherpa-onnx`) serves the fast path with speech-emotion + audio-event classification (falls back to a small Whisper model — words, no tone — when unprovisioned). Scripted transcript is opt-in behind `STT_BACKEND=mock`. Build-verified (both backends compile and link; 30 unit tests pass), but **no live transcription or emotion classification has been observed** — accuracy and latency are unmeasured. | `audio.inbound`, `chat.input`, `audio.perception` |
| **Transport Agent**| Node / LiveKit | WebRTC gateway; raw PCM chunking and stream bridging. | `audio.inbound`, `audio.stream` |
| **Surfacing Agent**| Python / pgvector | ACT-R episodic memory retrieval and proactive recall. | `memory.surfaced`, `chat.input` |
| **Subconscious** | Python / Neo4j | Background reflection, internal monologue generation (Tier-5). | `chat.input`, `system.tick`, `knowledge.*` |
| **Vision Agent** ⚠️ | Ollama / moondream | Host-native visual appraisal and spatial reasoning (Tier-4). **Experimental — currently commented out in `docker-compose.prod.yml` and not deployed by default.** | `vision.frames`, `vision.control`, `vision.description` |
| **Pulse Agent** | Python / Cron | Mesh heartbeat emitter; triggers maturation cycles. | `system.tick` |

---

## 🔄 The Cognitive Lifecycle

Every interaction follows a strictly governed loop through the mesh:

1. **Perception**: Transport Agent publishes raw PCM to `audio.inbound`.
2. **Speculation**: STT Agent (SenseVoice fast path, or Whisper fallback) identifies high-confidence intent and publishes `audio.perception` with any classified emotion/audio events.
3. **Reflex**: Voice Agent receives `audio.perception` and triggers an immediate speculative pause.
4. **Appraisal**: Brain Agent receives final transcript, computes emotional valence via **OCC/Lazarus**, and updates **PAD** state.
5. **Deliberation**: Decision Service selects the optimal intent using **MAUT** scoring.
6. **Synthesis**: Voice Agent renders segments using the current **Affect Vector**, injecting timing markers.
7. **Closure**: Voice Agent publishes `voice.segmentation_feedback` to the Brain for pulse adjustment.

---

## 🧠 Core Cognitive Models (Mathematical Specification)

### 1. Affective Dynamics (PAD + ALMA)

The agent's emotional state is a 3D coordinate in **PAD Space** (Pleasure, Arousal, Dominance).

* **Mood Pull**: Emotional events "pull" the current state toward target coordinates.
* **Logarithmic Decay**: During idle periods, the state drifts back to a neutral baseline following the ALMA formula: $I(t) = I_0 \cdot e^{-\lambda t}$.

### 2. Neuromodulatory Memory Gating (CVS-3.5)

Semantic memory search incorporating dynamic physiological bias gates memory retrieval based on emotional relevance:

```math
S_i = \text{CosineSimilarity} \cdot (1 + 0.1 \cdot \text{valence} \cdot \text{emotional-weight} - 0.2 \cdot \text{arousal} \cdot \text{cortisol})
```

* **Positive reinforcement**: $\text{valence} \cdot \text{emotional-weight}$ increases matching scores for positive memories.
* **Stress inhibition**: arousal $\cdot$ cortisol suppresses high-stress memories during hyper-arousal, avoiding repetitive trauma loops.

```math
A_i = \ln(\text{recall-count}) - d \cdot \ln(\text{hours-since-created} + 1)
```

### 3. Dimensional Trust Matrix (Marsh Model - CVS-3.5)

The agent's trust model deconstructs the legacy trust scalar into three distinct sub-dimensions:

1. **Benevolence** ($T_b$): Direct relationship warmth, modulated by Relationship Impact ($RI$).
2. **Competence** ($T_c$): Pragmatic task capability, modulated by Goal Congruence ($G$) and Relevance ($R$).
3. **Integrity** ($T_i$): Moral/ethical alignments, modulated by Norm Alignment ($NA$).

The overall trust score returned for backward compatibility is:

```math
\text{trust} = \frac{T_b + T_c + T_i}{3.0}
```

Appraisal-driven trust evolution updates individual sub-dimensions:

* $T_b \leftarrow \text{clamp}(T_b + \delta \cdot RI)$
* $T_c \leftarrow \text{clamp}(T_c + \delta \cdot (0.6 \cdot G + 0.4 \cdot R))$
* $T_i \leftarrow \text{clamp}(T_i + \delta \cdot NA)$

### 4. Memory Activation & ACT-R Pruning (CVS-3.5)

The subconscious memory agent runs background reflection sweeps after 5 minutes of user silence to apply ACT-R base activation decay:

```math
A_i = \ln(\text{recall-count}) - d \cdot \ln(\text{hours-since-created} + 1)
```

* **ACT-R Pruning**: Memories where base activation falls below the retention threshold ($A_i < -2.0$) are permanently pruned from local SQLite/PostgreSQL stores.
* **Decay**: Surviving memories have their importance scores scaled by `0.8` on each consolidation tick.

### 5. Endocrine LLM Parameter Modulation (CVS-3.5)

Action execution dynamically modulates Ollama inference parameters independently:

* **Cortisol (Stress)**: Controls `temperature` ($0.9 - 0.6 \cdot \text{cortisol}$).
* **Dopamine (Reward)**: Controls exploration `top_p` ($0.70 + 0.25 \cdot \text{dopamine}$).
* **Fatigue**: Truncates response length `num_predict` ($40 - 25 \cdot \text{fatigue}$ tokens, strictly bounded in $[15, 40]$).

### 6. Decision Utility (MAUT)

The Decision Service uses Multi-Attribute Utility Theory to score intent candidates:

```math
U(\text{Intent}) = w_{\text{goal}} \cdot G + w_{\text{emotion}} \cdot E + w_{\text{identity}} \cdot I + w_{\text{context}} \cdot C
```

### 7. Dynamic Continuous Prosody Mapping & OLA Crossfade (CVS-3.5 / Phase 4)

Vocal parameters (speaking rate, pitch, volume, and pause bias) are continuously modulated in Rust based on emotional PAD state, fatigue $F$, user distance $d$, and signal continuity window:

* **Fatigue Slowdown**: $\text{fatigue-slow} = 0.25 \cdot F$
* **Fatigue Pitch Drop**: $\text{fatigue-pitch-drop} = 0.1 \cdot F$
* **Distance Modifiers**:
  * If $d < 0.6\text{m}$ (close range): $\text{dist-vol-mod} = -0.15, \quad \text{dist-pitch-mod} = -0.05$
  * If $d > 1.5\text{m}$ (far range): $\text{dist-vol-mod} = 0.2, \quad \text{dist-pitch-mod} = 0.1$
  * Otherwise: $\text{dist-vol-mod} = 0.0, \quad \text{dist-pitch-mod} = 0.0$

#### Prosody Equations

```math
\text{SpeedFactor} = \text{clamp}(1.0 + \tanh(0.20 \cdot \text{arousal} - 0.10 \cdot \text{valence} - \text{fatigue-slow}), 0.6, 1.8)
```

```math
\text{Pitch} = \text{clamp}(1.0 + \tanh(0.05 \cdot \text{valence} + 0.15 \cdot \text{arousal} - 0.10 \cdot \text{dominance} - \text{fatigue-pitch-drop} + \text{dist-pitch-mod}), 0.5, 2.0)
```

```math
\text{Volume} = \text{clamp}(0.40 + 0.60 \cdot \text{dominance} + \text{dist-vol-mod}, 0.1, 1.0)
```

```math
\text{PauseBias} = \text{clamp}(1.0 - \text{arousal}, 0.0, 1.0)
```

#### Overlap-Add (OLA) Sample-Accurate Linear Crossfade
During prosody-shift boundaries, a linear crossfade is applied over a **10ms window** ($\text{fade-len} = \lfloor 0.010 \cdot \text{SampleRate} \rfloor$ samples, i.e., 320 samples at 32kHz), blending the previous prosody segment into the new one to eliminate switching clicks:

```math
y[i] = (1 - t) \cdot x_{\text{prev}}[i] + t \cdot x_{\text{curr}}[i], \quad t = \frac{i}{\text{fade-len}}, \quad 0 \le i < \text{fade-len}
```

#### Spatial Reverb DSP Blend
Acoustic environmental reflection utilizes a comb filter with a 50ms delay and 0.5 feedback gain, dynamically blended via $\text{wet-gain}$ linear interpolation based on user distance:

```math
\text{wet-gain} = \text{clamp}\left(\frac{d - 2.5}{3.5 - 2.5}, 0.0, 1.0\right)
```

```math
y[n] = (1 - \text{wet-gain}) \cdot x[n] + \text{wet-gain} \cdot d_{\text{buffer}}[n \pmod M]
```

### 8. SOTA Comparative Benchmarking Matrix & Academic Mappings

CVS-3.5 is benchmarked against 7 other state-of-the-art and legacy humanoid, expressive, or cognitive systems across 8 core dimensions:

| Performance Axis | SOTA Humanoid: Figure 02 (In-House AI) [1] | SOTA Humanoid: Tesla Optimus Gen 2 [2] | Compact Humanoid: Unitree G1 [3] | SOTA Expressive: Ameca Gen 3 [4] | Kyoto Android: ERICA [5] | SOTA Graph Memory: AriGraph/HippoRAG [6] | SOTA Embodied: ACT-R/E [7] | **Ours: CVS-3.5 (Physical)** | **Ours: CVS-3.5 (Accelerated)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Speech Barge-in Stop** | Cloud VLM Delay (~300ms) | N/A (Secondary audio) | Cloud VAD (~400ms) | Tritium Stream Buffer (~250ms) | 200.0 ms | N/A | N/A | **~104 ms**¹ | *(mode retired)*⁶ |
| **Cognitive Gating Latency** | Cloud VLM reasoning | Onboard task planning | Cloud LLM reasoning | Cloud LLM reasoning | 100.0 ms | N/A | 50.0 ms | **5.44 ms**² | *(mode retired)*⁶ |
| **Speech-to-Speech TTFT** | ~350 ms | Cloud speech delays | ~500 ms | ~400 ms | 200.0 ms | N/A | N/A | *(not yet measured)*³ | *(mode retired)*⁶ |
| **Memory Scaling Complexity** | N/A | N/A | N/A | N/A | N/A | $O(\log M_{\text{total}})$ | Linear search | *(not yet measured)*³ | *(mode retired)*⁶ |
| **Memory Recall (Recall@5)** | N/A | N/A | N/A | N/A | N/A | ~92.0% | ~85.0% | **87.5%**⁴ | *(mode retired)*⁶ |
| **Theory of Mind MAE** | N/A | N/A | N/A | N/A | N/A | N/A | 0.280 MAE | **0.032 (valence) / 0.041 (arousal)**⁴ | *(mode retired)*⁶ |
| **Autonomic Somatic State** | Static Response | Static Response | Static Response | Static Response | Static Response | N/A | N/A | **Dynamic** (PAD + cortisol/dopamine coupling) | *(mode retired)*⁶ |
| **System Idle Memory** | High (Onboard OS) | High (Optimus FSD) | High (ROS2 Mesh) | High (Tritium Stack) | High Cloud | N/A | N/A | **1,266 MB**⁵ (8-agent mesh + DB stack) | *(mode retired)*⁶ |
| **Active Edge Power** | High (Onboard GPU) | High (Tesla FSD Core) | Moderate | High (Onboard NUC) | High Cloud | N/A | N/A | **0.99 W**⁵ | *(mode retired)*⁶ |
| **Structural Novelties** | End-to-End VLM | Vision-Motor NN | Local VLM Plan | Gaze-to-Speech Tritium | Attentive VAP Frame | Associative Graph | Symbolic Decays | **Live Localized Mind Mesh** | *(mode retired)*⁶ |

> [!NOTE]
> **Provenance of "Ours: CVS-3.5 (Physical)" values.** All figures are read from `scripts/results/*.json` and independently re-derived from the underlying raw per-sample arrays (1000 intent samples, 88 recall probes) rather than trusted at face value — see `scripts/results/benchmark_results_summary.md` for the full verification notes and caveats. **Not every figure below is a raw stopwatch measurement**: figures marked ¹² are *composed estimates* (sums of independently measured sub-components, not live end-to-end trials) and figures marked ⁴ are *independently recomputed aggregates* rather than newly measured — see the numbered notes for the exact provenance class of each metric.
> 1. **Composed estimate**, not a live end-to-end stopwatch trial: 100ms audio-buffer assumption + 3.85ms measured NATS RTT + 0.04ms measured DSP extraction + 0.02ms measured soft-ducking transition.
> 2. **Composed estimate** summing seven independently measured component latencies (audio ingest/DSP, working-memory read/write, ACT-R vector search, prosody generation, ducking, NATS RTT); excludes LLM token generation, so it is not a full turn latency.
> 3. No true first-token or complexity-scaling telemetry currently exists — a prior figure attributed to LLM inference here was mislabeled (it was actually memory-retrieval latency) and has been retracted; a benchmark fallback that silently fabricated latency-scaling numbers has been fixed to fail loudly instead. See the results summary for detail.
> 4. Independently recomputed from the raw ground-truth/prediction arrays (N=1000 for ToM MAE, N=88 recall probes for Recall@5); matches the reported aggregate exactly.
> 5. Full 8-agent cognitive mesh + Postgres/Neo4j/Qdrant/NATS/Redis stack, measured via `human_realism_eval.py`.
> 6. Non-physical "accelerated" simulation mode is intentionally disabled in `hard_benchmark.py` ("Accelerated simulation mode is disabled as requested by the user. Only rigorous Physical live benchmarking ... is supported") — this column cannot be populated under the current benchmarking harness.

#### 📚 Reference Mapping

> [!NOTE]
> **Provenance.** [1]–[4] are **vendor product materials, not peer-reviewed
> publications** — they were previously formatted as formal papers (e.g. a
> "Technical Report"), overstating their standing, and are now listed as what they
> are. [5]–[7] are **real, verified publications**; their titles were previously
> paraphrased into non-existent variants and have been corrected against the
> published record (links below). The *comparative performance figures* attributed
> to these sources in the table above remain **unverified** and should be checked
> against each paper before being relied upon.

**Vendor / product materials (non-peer-reviewed):**

* **[1] Figure AI** — Figure 02 humanoid platform, product materials ([figure.ai](https://figure.ai/)).
* **[2] Tesla** — Optimus (Gen 2) humanoid, product materials ([tesla.com/optimus](https://tesla.com/optimus)).
* **[3] Unitree Robotics** — Unitree G1 humanoid, product materials ([unitree.com/g1](https://unitree.com/g1)).
* **[4] Engineered Arts** — Ameca / Tritium orchestration layer, product materials ([engineeredarts.co.uk/ameca](https://engineeredarts.co.uk/ameca)).

**Peer-reviewed publications:**

* **[5] Inoue, K., Jiang, B., Ekstedt, E., Kawahara, T., & Skantze, G. (2024)**, *"Multilingual Turn-taking Prediction Using Voice Activity Projection"*, in *Proceedings of LREC-COLING 2024*, pp. 11873–11883, Torino, Italy. ([arXiv:2403.06487](https://arxiv.org/abs/2403.06487))
* **[6] Gutiérrez, B. J., Shu, Y., Gu, Y., Yasunaga, M., & Su, Y. (2024)**, *"HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models"*, in *Advances in Neural Information Processing Systems (NeurIPS 2024)*. ([arXiv:2405.14831](https://arxiv.org/abs/2405.14831) · [proceedings](https://papers.nips.cc/paper_files/paper/2024/hash/6ddc001d07ca4f319af96a3024f6dbd1-Abstract-Conference.html))
* **[7] Wu, S., Oltramari, A., Francis, J., Giles, C. L., & Ritter, F. E. (2024)**, *"Cognitive LLMs: Toward Human-Like Artificial Intelligence by Integrating Cognitive Architectures and Large Language Models for Manufacturing Decision-making"*, *Neurosymbolic Artificial Intelligence* (IOS Press). ([arXiv:2408.09176](https://arxiv.org/abs/2408.09176))

---

## 📡 Signal Bus Communication Contracts

Communication is strictly governed by a **Typed Contract Mesh** (Pydantic). Every subject has a specific schema defined in `backend/app/contracts.py`.

### Example: `chat.output` Schema

```json
{
  "content": "Hey, I remember that!",
  "affect": {
    "valence": 0.8,
    "arousal": 0.6,
    "dominance": 0.5
  },
  "timing": {
    "pause_ms": 250,
    "hesitate": false
  },
  "utterance_id": "uuid-v4"
}
```

| Subject | Payload Model | Purpose |
| :--- | :--- | :--- |
| `chat.input` | `ChatInput` | User utterances and manual injections. |
| `chat.output` | `ChatOutput` | Cognitive responses with affect metadata. |
| `audio.perception` | `AudioPerception` | Real-time emotional bias and speculative intent. |
| `audio.stop` | `ControlEvent` | Speculative or final interruption commands. |
| `state.update` | `StateUpdate` | Broadcast of PAD/Relational coordinate shifts. |
| `memory.surfaced` | `MemoryEvent` | Proactive episodic or semantic recall triggers. |
| `system.tick` | `PulseEvent` | The 60s mesh-wide maturation heartbeat. |
| `user.voice.properties` | `UserVoiceProperties` | Real-time user pitch, energy, and speech rate telemetry. |
| `agent.voice.modulation` | `AgentVoiceModulation` | Continuous frame-wise time-series trajectory of `ProsodyFrame`s (ordered ascending by `time_offset_ms` [integer, ms >= 0] at exactly 50ms intervals, containing `rate` [float], `pitch` [float], and `volume` [float]) representing fine-grained vocal dynamics driven by the emotional appraisal loop. |
| `audio.playback.visemes` | `PlaybackVisemes` | Sample-accurate mouth shape triggers for synchronized rendering. |

---

## 🛡️ Infrastructure & Hardening

### 1. Solid State Signal Hardening

In version **CVS-3.5**, the mesh implements "Solid State" principles to ensure portability and security:

* **Zero-Drift Persistence**: On-demand relational seeding via Prisma 7.7.0 ensures the "Identity Genome" is identical across container restarts.
* **Health Surveillance**: Automated probes (`nc -z nats_mesh 4222`) trigger self-healing for disconnected agents.
* **State Read-Safety**: Live emotional state is never hydrated from stale Neo4j TTL cache. After state persistence, graph cache is invalidated to prevent "memory rewinding."

### 2. Voice Subsystem Runtime

The **Voice Agent** handles the high-fidelity rendering of cognitive intent:

* **Single-Engine Synthesis (GPT-SoVITS)**: All speech renders through one self-hosted GPT-SoVITS endpoint carrying the cloned voice's identity in its trained weights. A local ONNX fallback engine existed through 2026-07 and was removed: it fell back to a *different, uncloned* voice on outage, which is strictly worse than silence under a no-fallback requirement — see the ledger.
* **Emotion-Selected Reference Clips**: Delivery register (calm/warm/concerned/excited/neutral) is chosen per turn from the agent's own affect state and sent as GPT-SoVITS's per-request reference clip — steering *how* a line is delivered, not re-cloning identity, which stays permanently baked into the server's loaded weights.
* **Same-Engine Resilience**: A circuit breaker plus bounded retry wrap the SoVITS call; a background readiness probe proves the engine can render real audio (not just answer HTTP) independently of live traffic. A confirmed failure plays a same-voice fallback vocalization instead of dropping the turn — never a different voice, never silence.
* **Quality-Prioritized Look-Ahead**: Segments speech into 7-word chunks to preserve prosodic context and emotional inflection quality.
* **Speculative Pause Fillers**: Injects early speculative fillers (hmm, um, accha) if decision generation latency exceeds 250ms, keeping the conversation alive while high-fidelity audio chunks are prepared in the background.
* **OLA Signal Continuity**: Uses Overlap-Add (OLA) algorithms to ensure zero-click transitions between streaming PCM chunks.

---

## 📂 Clean Directory Tree (Scalable Layout)

```text
AI_friend/
├── backend/                         # Unified backend workspace (Python + Rust)
│   ├── app/                         # Python runtime (agents, cognition, state, vision, stt)
│   ├── crates/                      # Rust runtime crates
│   │   ├── contracts/               # Shared signal contracts
│   │   ├── cognitive-rust/          # Rust cognitive engine components
│   │   ├── stt-agent/               # Rust STT agent
│   │   └── voice-agent/             # Rust voice agent
│   ├── tests/                       # Python tests and benchmarks
│   ├── scripts/                     # Bootstrap, diagnostics, db/audio/testing utilities
│   ├── tools/                       # Tool registry and support modules
│   └── db/                          # Backend-local database artifacts
├── frontend/                        # Next.js WebRTC/UI application
│   ├── app/                         # App Router pages
│   ├── components/                  # Shared UI components
│   ├── hooks/                       # Reusable client hooks
│   └── prisma/                      # Frontend-side Prisma schema/client config
├── docs/                            # Architecture and operational documentation
├── scripts/                         # Root-level host/integration/research utilities
├── _archive/                        # Legacy/archived implementations (read-only reference)
├── .agents/                         # Local skill and agent metadata
├── notebooks/                       # Experimental notebooks
├── docker-compose.infra.yml         # Shared infra services
├── docker-compose.prod.yml          # Production composition
├── docker-compose.light.yml         # Platform-agnostic Light profile (Windows/Linux/macOS)
└── docker-compose.heavy.yml         # Platform-agnostic Heavy profile (Windows/Linux/macOS)
```

---

## ⚡ Performance Perceived SLOs

| Pipeline Stage | Metric | Strategy | Target (p99 / Budget) | Actual (Empirical Mean / Min) | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Mesh Telemetry** | Speed | orjson / NATS Binary | <0.5 µs | *(not yet measured)* | **Pending** |
| **Data Throughput**| Scale | PyO3 FFI Audio | 80,000 OPS | *(not yet measured)* | **Pending** |
| **STT Perception** | Latency | Fast Whisper CPU Fan-out | <50ms | *(not yet measured — no real STT backend exists yet; see §STT status)* | **Pending** |
| **Cognitive Turn** | Turnaround | BDI Mesh + State Hydration | <120ms | **5.44 ms** | ✅ **Met** |
| **First Audio** | Response | Streaming PCM Chunking | <180ms | *(not yet measured)* | **Pending** |
| **Total Perceived** | **End-to-End**| **CVS-3.5 Premium Mesh** | **<250ms** | *(not yet measured — no live stopwatch E2E trial exists)* | **Pending** |

*"Cognitive Turn" sums seven independently measured component latencies (audio ingest/DSP, working-memory read/write, ACT-R vector search, prosody generation, ducking, NATS RTT) from `scripts/results/human_realism_results.json`; it excludes LLM token generation. All other "Actual" values remain unmeasured until a live end-to-end harness exists — see `scripts/results/benchmark_results_summary.md` for what is and isn't verified today.*

---

## 🛠️ Hardware Tier Matrix

| Tier | Purpose | CPU | GPU | RAM |
| :--- | :--- | :--- | :--- | :--- |
| **Mini** | Evaluation | 4-Core | None (CPU Whisper) | 8GB |
| **Standard** | Real-time | 8-Core | RTX 3060 (12GB) | 16GB |
| **High-End** | Research | 16-Core | RTX 4090 / M2 Ultra | 64GB |

---

## 📦 Release Package Selection Guide

Every release of **AI Friend** provides high-quality, pre-packaged standalone archives for major operating systems (Windows, macOS, and Linux) so you can get started instantly without administrative installation headaches.

### 📦 Available Release Packages

| Platform | Format | Filename | Description |
| :--- | :--- | :--- | :--- |
| 🪟 **Windows** | Portable ZIP | `ai-friend-windows.zip` | Extract and run on any modern 64-bit Windows PC. |
| 🍏 **macOS** | Portable ZIP | `ai-friend-macos.zip` | Highly optimized standalone archive for Intel and Apple Silicon Macs. |
| 🐧 **Linux** | Standard Tarball | `ai-friend-linux.tar.gz` | Gzipped archive containing all source files and backend components. |

### 🔑 Checksums & Verification Manifest

Each package is built automatically in a secure containerized environment and includes:

* **`.sha256` File**: Contains the SHA256 checksum for cryptographic verification (e.g. `ai-friend-windows.zip.sha256`).
* **`ai-friend-release-manifest.json`**: A structured JSON manifest mapping the filenames, precise byte sizes, and SHA256 hashes of all release packages for automated deployment tools.

---

## ⚙️ Quick Start

Follow this standardized, cross-platform sequence to initialize the Sovereign Mesh:

### **Step 1: Bootstrap Shared Network & Infrastructure**

1. Recreate the external shared network required by the mesh:

   ```bash
   docker network create ai_mesh_network
   ```

2. Launch the infrastructure containers (PostgreSQL, Neo4j, Redis, NATS, and LiveKit):

   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d postgres neo4j redis nats livekit
   ```

### **Step 2: Hydrate the Database Schema**

To prevent database port contentions and host network routing bugs, the containerized PostgreSQL database is mapped to the isolated external port **`5433`** on your host.

#### **On macOS / Linux (Bash/Zsh)**

```bash
# 1. Set the direct database connection path using your custom password
export DIRECT_URL="postgresql://ai_friend:YOUR_DB_PASSWORD@127.0.0.1:5433/ai_friend_db"

# 2. Navigate to the frontend, generate the Prisma Client, and sync the schema
cd frontend
npx prisma generate
npx prisma db push
cd ..
```

#### **On Windows (PowerShell)**

```powershell
# 1. Set the direct database connection path using your custom password
$env:DIRECT_URL="postgresql://ai_friend:YOUR_DB_PASSWORD@127.0.0.1:5433/ai_friend_db"

# 2. Navigate to the frontend, generate the Prisma Client, and sync the schema
cd frontend
npx prisma generate
npx prisma db push
cd ..
```

### **Step 3: Private Seeding & Agent Launch**

The Sovereign Mesh is designed with **Privacy by Default**. The baseline agent identity genome and conversation history are kept secure and local using two private, Git-ignored files in the backend:

* `backend/app/personality.json`
* `backend/app/history.json`

You do not need to run manual SQL inserts or standalone scripts. On startup, the backend cognitive agents **automatically hydrate and seed the relational PostgreSQL database** using your private local configurations!

Select your launching profile based on your operating system and hardware resources:

#### **A. Standard Production Launch (Linux / Windows Host)**

This command boots up the entire 14-container real-time voice, STT, and voice cloning mesh:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build
```

#### **B. Platform-Agnostic Light & Heavy Launch (Windows / Linux / macOS)**

For Apple Silicon MacBooks (M1/M2/M3/M4) or Windows/Linux systems that want to bypass heavy real-time CUDA-based voice cloning (saving RAM/CPU/GPU overhead), you can choose between **Light** (Cognitive-Only) and **Heavy** (Local Cognitive + STT) modes:

* **⚡ Universal Light Mode** (Cognitive-Only):
  Focuses strictly on cognitive processing, memory graphs, and text agents. Excludes heavy real-time WebRTC media streams, Whisper STT, and voice synthesis:

  ```bash
  docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.light.yml up -d --build
  ```

* **⚡ Universal Heavy Mode** (Cognitive + Whisper STT):
  Enables the advanced cognitive mesh and local real-time audio Whisper STT, optimized for CPU/host-Ollama performance:

  ```bash
  docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.heavy.yml up -d --build
  ```

##### **Solving macOS compilation bottlenecks via layered builds**

If Apple Silicon arm64 PyTorch or C++ dependencies cause compilation timeouts during standard compose builds, compile the secure, cached build layers sequentially using the dedicated Mac Dockerfiles:

```bash
# 1. Compile and cache base arm64 dependencies
docker build -t ai-friend/base:v1 -f backend/Dockerfile.base ./backend

# 2. Compile and cache advanced AI, Torch, and STT libraries on top of the base image
docker build -t ai-friend/full:v1 --build-arg BASE_IMAGE=ai-friend/base:v1 -f backend/Dockerfile.full ./backend
```

### **Step 4: Health Audit**

Confirm all active containers are running and communicating:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps
```

---

## 🛠️ Operating System & WSL2 Troubleshooting Guide

Review these common OS-specific configurations if you run into boot bottlenecks:

### **1. Port Conflicts (e.g. Port 5432/5433 already in use)**

If you have a native database installation running on your host machine (outside of Docker), it will block container port bindings.

* **On macOS/Linux**: Stop the native Postgres service via systemctl or brew:

  ```bash
  brew services stop postgresql
  # OR
  sudo systemctl stop postgresql
  ```

* **On Windows**: Forcefully stop all native Postgres database services and active background processes:

  ```powershell
  Stop-Service -Name "postgresql*" -Force -ErrorAction SilentlyContinue
  Get-Process -Name "postgres" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  ```

* Restart the container to capture the port bind:

  ```bash
  docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml restart postgres
  ```

### **2. Dynamic WSL2 Disk Bloat (Windows Host)**

WSL2 virtual disk files (`ext4.vhdx`) grow dynamically but **never shrink automatically** even after you prune Docker caches and volumes.

* **Empty the Recycle Bin**: Deleted WSL virtual folder contents are temporarily held in the host Recycle Bin, retaining their size on disk.
* **WSL shutdown**: Clear WSL memory locks to force Windows to reclaim released space:

  ```powershell
  wsl --shutdown
  ```

---

## 🛠️ Environmental Configuration Reference

Grouped by domain. Refer to `backend/app/config.py` for all 50+ tunable parameters.

### 🛡️ Infrastructure

| Parameter | Default | Purpose |
| :--- | :--- | :--- |
| `NATS_URL` | `nats://127.0.0.1:4222` | Central signal bus endpoint. |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Knowledge graph endpoint. |
| `DATABASE_URL` | `postgresql://...` | Identity and memory state store. |

### 🧠 Cognition & Affect

| Parameter | Default | Purpose |
| :--- | :--- | :--- |
| `SYSTEM_TICK_INTERVAL` | `60s` | Frequency of mesh-wide identity maturation. |
| `PSYCH_ALPHA` | `0.3` | **Valence Drift**: Rate of mood change toward target. |
| `ACTR_DECAY_RATE` | `0.5` | **Forgetting Rate** ($d$) for episodic memory. |
| `INTENT_THRESHOLD` | `0.75` | Required confidence for speculative interruption. |

---

## 🛠️ Troubleshooting & Debugging

### Symptom: Mesh Communication Silence

* **Check**: Verify NATS stream state.

* **Action**: `docker exec -it nats_mesh nats stream info AI_MESSAGES`

### Symptom: Stale Emotional State

* **Check**: Verify Neo4j TTL cache invalidation.

* **Action**: Run `pytest backend/tests/test_regressions.py::test_state_hydration_avoids_stale_cache`.

---

## 🧪 Research Instrumentation

For controlled experiments, use the dedicated research toolkit located in `scripts/research/`.

* **`monitor.py`**: Real-time signal mesh latency profiling.
* **`collector.py`**: High-frequency PAD state trajectory logger.
* **`injector.py`**: Automated standardized pulse injection to eliminate human timing noise.
* **`visualizer.py`**: Generates publication-ready Matplotlib plots of emotional evolution.

---

## 📚 Glossary

* **BDI**: Belief-Desire-Intention cognitive framework.
* **CVS**: Cognitive Voice System.
* **MAUT**: Multi-Attribute Utility Theory.
* **PAD**: Pleasure, Arousal, Dominance emotional model.
* **OLA**: Overlap-Add signal processing.
* **ACT-R**: Adaptive Control of Thought—Rational.

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for details.

**Designed for Perception. Built for Identity.**
