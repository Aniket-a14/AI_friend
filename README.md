# 🎙️ AI Friend: Cognitive Voice System (v5.0.0 / CVS-2.0 Rust Native Edition)

**A high-fidelity, state-driven cognitive identity emulator built on a hardened Sovereign Mesh for ultra-low latency conversational realism.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)
[![Latency: Perceived <250ms](https://img.shields.io/badge/Latency-Perceived%20%3C250ms-green.svg)](#performance-perceived-slos)
[![Architecture: CVS-2.0 Rust Native](https://img.shields.io/badge/Architecture-CVS--2.0--Rust--Native-orange.svg)](#architecture-cvs-20-rust-native)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Aniket-a14/AI_friend/blob/main/notebooks/ai_friend_voice_training.ipynb)
[![Continuous Integration](https://github.com/Aniket-a14/AI_friend/actions/workflows/ci.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/ci.yml)
[![🛡️ Mesh Integrity](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml)
[![🧠 Cognitive Regression](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml)
[![🎭 Persona Guard](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml)
[![🔒 Security Audit](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml) 
[![📦 Docker Build](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-build.yml)
[![🩺 Docker Health](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml)
[![🔗 Link Validator](https://github.com/Aniket-a14/AI_friend/actions/workflows/links.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/links.yml)
[![🚀 Release Status](https://github.com/Aniket-a14/AI_friend/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/Aniket-a14/AI_friend/actions/workflows/release.yml)
[![Platforms: Windows | macOS | Linux](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-blueviolet.svg)](#-release-package-selection-guide)
[![Arch: Multi-Platform](https://img.shields.io/badge/Architectures-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)](#-release-package-selection-guide)
[![Release Assets: 3 Packages](https://img.shields.io/badge/Release%20Assets-3%20Packages-success.svg)](#-release-package-selection-guide)

**CALIBRATION: EXPERT** — *This documentation assumes proficiency in asynchronous event-driven architectures, NATS JetStream protocols, and computational cognitive modeling (BDI, PAD, ACT-R, MAUT).*

---

## 🌟 The Philosophy of Perceptual Mastery

AI Friend is not a reactive "turn-based" chatbot. It is a **Sovereign Mesh** of specialized agents synchronized through a hardened signal bus. In the **CVS-2.0 (Rust Native Edition)** release, the architecture shifted from legacy Python audio loops to a **High-Performance Rust Signal Mesh**, guaranteeing sub-50ms deterministic execution and true temporal identity continuity.

### 🧠 Reactive vs. Sovereign Intelligence
| Feature | Reactive Chatbot (Legacy) | Sovereign Mesh (CVS-2.0) |
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

*   **Identity Continuity**: Personality, values, and relationship state survive long sessions and hardware restarts.
*   **Organic Timing**: Pauses and hesitations are physically injected as silent PCM buffers, not just text tags.
*   **Privacy Sovereignty**: 100% local execution ensures your identity genome never leaves your hardware.

---

## 🏗️ Technical Architecture: The Sovereign Mesh

### 1. System Topology Map

The platform utilizes **NATS JetStream** as its central nervous system, routing typed Pydantic messages between autonomous agents.

> [!NOTE]
> **Architecture Description**:
> The system follows a decoupled "Signal Bus" pattern. The **NATS JetStream** serves as the message backbone, enforcing strict communication contracts across nine core subjects. 
> - **Sensory Agents**: The **STT Agent** and **Vision Agent** publish perceptual signals to the bus.
> - **Cognitive Agents**: The **Brain Agent** (Decision Core), **Subconscious Agent** (Idle reflection), and **Surfacing Agent** (Memory) process these signals asynchronously.
> - **Infrastructure**: **Neo4j** stores the high-dimensional knowledge graph, while **PostgreSQL** with `pgvector` manages episodic memories and relational identity state.
> - **Signal Rendering**: The **Voice Agent** consumes decision events to produce high-fidelity 32kHz PCM audio.

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

    subgraph "Voice Subsystem"
        Prosody["prosody.py — VAD Mapping"]
        Playback["playback.py — OLA Signal"]
        Resilience["resilience.py — Fillers"]
    end

    Voice --> Prosody
    Voice --> Playback
    Voice --> Resilience

    subgraph "Infrastructure"
        Brain <--> Neo4j[("Neo4j: Knowledge Graph")]
        Brain <--> Postgres[("Postgres + pgvector")]
        Action --> Ollama["Ollama: Local LLM"]
        Voice --> SoVITS["GPT-SoVITS API"]
    end
```

### 2. Perceptual Interruption Protocol

CVS-2.0 utilizes a **Dual-STT fan-out** with a 3-stage interruption arbitration protocol.

> [!IMPORTANT]
> **Protocol Description**:
> Audio arriving via WebRTC is fanned out to two paths: **SenseVoice** (optimized for CPU-based temporal intent) and **Whisper** (optimized for GPU-based semantic accuracy).
> - **Stage 1 (Speculative)**: SenseVoice detects interruption markers in <100ms and publishes a speculative `audio.stop` message. The Voice Agent immediately enters a reversible pause.
> - **Stage 2 (Validation)**: The Brain Agent evaluates the speculative perception. If confirmed, it commits the stop. If rejected as noise, it publishes `audio.resume`, causing the Voice Agent to resume playback from its OLA buffer.
> - **Stage 3 (Resolution)**: Once Whisper produces the final transcript, the Brain Agent performs a deep cognitive turn to update state and generate the response.

```mermaid
sequenceDiagram
    participant U as User
    participant H as Host (Windows)
    participant T as TransportAgent (Docker)
    participant SV as "SenseVoice (Fast Path)"
    participant W as "Whisper (Accurate Path)"
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
            T->>SV: 400ms chunks (Speculative)
            T->>W: Full utterance (Semantic)
        end
    end

    Note over SV, B: Stage 1 — Speculative Perception
    SV->>B: AudioPerception (emotion + intent)
    SV-->>V: audio.stop (speculative=true)
    V->>V: Immediate OLA Pause

    Note over W, B: Stage 2 — Semantic Resolution
    W->>B: ChatInput (Typed Contract)
    B->>B: Multimodal Context Merge (Audio + Vision)
    
    Note over B, V: Stage 3 — Cognitive Action
    B-->>V: audio.stop (confirmed) / audio.resume
    B->>V: ChatOutput (Segments + Affect Vector)
    
    Note over V, U: Stage 4 — Signal Rendering
    V->>V: prosody.py → playback.py
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
| **Voice Agent** | Rust / PyO3 / SoVITS | CVS-2.0 Runtime; renders affect-aware 32kHz audio. | `chat.output`, `audio.stream`, `audio.stop` |
| **STT Agent** | Rust / Whisper | Dual-path perception; fan-out transcription. | `audio.inbound`, `chat.input`, `audio.perception` |
| **Transport Agent**| Node / LiveKit | WebRTC gateway; raw PCM chunking and stream bridging. | `audio.inbound`, `audio.stream` |
| **Surfacing Agent**| Python / pgvector | ACT-R episodic memory retrieval and proactive recall. | `memory.surfaced`, `chat.input` |
| **Subconscious** | Python / Neo4j | Background reflection, internal monologue generation (Tier-5). | `chat.input`, `system.tick`, `knowledge.*` |
| **Vision Agent** | Ollama / moondream | Host-native visual appraisal and spatial reasoning (Tier-4). | `vision.frames`, `vision.control`, `vision.description` |
| **Pulse Agent** | Python / Cron | Mesh heartbeat emitter; triggers maturation cycles. | `system.tick` |

---

## 🔄 The Cognitive Lifecycle

Every interaction follows a strictly governed loop through the mesh:

1.  **Perception**: Transport Agent publishes raw PCM to `audio.inbound`.
2.  **Speculation**: STT Agent (SenseVoice) identifies high-confidence intent and publishes `audio.perception`.
3.  **Reflex**: Voice Agent receives `audio.perception` and triggers an immediate speculative pause.
4.  **Appraisal**: Brain Agent receives final transcript, computes emotional valence via **OCC/Lazarus**, and updates **PAD** state.
5.  **Deliberation**: Decision Service selects the optimal intent using **MAUT** scoring.
6.  **Synthesis**: Voice Agent renders segments using the current **Affect Vector**, injecting timing markers.
7.  **Closure**: Voice Agent publishes `voice.segmentation_feedback` to the Brain for pulse adjustment.

---

## 🧠 Core Cognitive Models (Mathematical Specification)

### 1. Affective Dynamics (PAD + ALMA)
The agent's emotional state is a 3D coordinate in **PAD Space** (Pleasure, Arousal, Dominance).
- **Mood Pull**: Emotional events "pull" the current state toward target coordinates.
- **Logarithmic Decay**: During idle periods, the state drifts back to a neutral baseline following the ALMA formula: $I(t) = I_0 \cdot e^{-\lambda t}$.

### 2. Neuromodulatory Memory Gating (CVS-3.0)
Semantic memory search incorporating dynamic physiological bias gates memory retrieval based on emotional relevance:
$$S_i = \text{CosineSimilarity} \cdot (1 + 0.1 \cdot \text{valence} \cdot \text{emotional\_weight} - 0.2 \cdot \text{arousal} \cdot \text{cortisol})$$
* **Positive reinforcement**:valence $\cdot$ emotional_weight increases matching scores for positive memories.
* **Stress inhibition**:arousal $\cdot$ cortisol suppresses high-stress memories during hyper-arousal, avoiding repetitive trauma loops.

### 3. Dimensional Trust Matrix (Marsh Model - CVS-3.0)
The agent's trust model deconstructs the legacy trust scalar into three distinct sub-dimensions:
1. **Benevolence** ($T_b$): Direct relationship warmth, modulated by Relationship Impact ($RI$).
2. **Competence** ($T_c$): Pragmatic task capability, modulated by Goal Congruence ($G$) and Relevance ($R$).
3. **Integrity** ($T_i$): Moral/ethical alignments, modulated by Norm Alignment ($NA$).

The overall trust score returned for backward compatibility is:
$$\text{trust} = \frac{T_b + T_c + T_i}{3.0}$$

Appraisal-driven trust evolution updates individual sub-dimensions:
* $T_b \leftarrow \text{clamp}(T_b + \delta \cdot RI)$
* $T_c \leftarrow \text{clamp}(T_c + \delta \cdot (0.6 \cdot G + 0.4 \cdot R))$
* $T_i \leftarrow \text{clamp}(T_i + \delta \cdot NA)$

### 4. Memory Activation & ACT-R Pruning (CVS-3.0)
The subconscious memory agent runs background reflection sweeps after 5 minutes of user silence to apply ACT-R base activation decay:
$$A_i = \ln(\text{recall\_count}) - d \cdot \ln(\text{hours\_since\_created} + 1)$$
* **ACT-R Pruning**: Memories where base activation falls below the retention threshold ($A_i < -2.0$) are permanently pruned from local SQLite/PostgreSQL stores.
* **Decay**: Surviving memories have their importance scores scaled by `0.8` on each consolidation tick.

### 5. Endocrine LLM Parameter Modulation (CVS-3.0)
Action execution dynamically modulates Ollama inference parameters independently:
* **Cortisol (Stress)**: Controls `temperature` ($0.9 - 0.6 \cdot \text{cortisol}$).
* **Dopamine (Reward)**: Controls exploration `top_p` ($0.70 + 0.25 \cdot \text{dopamine}$).
* **Fatigue**: Truncates response length `num_predict` ($40 - 25 \cdot \text{fatigue}$ tokens, strictly bounded in $[15, 40]$).

### 6. Decision Utility (MAUT)
The Decision Service uses Multi-Attribute Utility Theory to score intent candidates:
$$U(\text{Intent}) = w_{\text{goal}} \cdot G + w_{\text{emotion}} \cdot E + w_{\text{identity}} \cdot I + w_{\text{context}} \cdot C$$

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
| `state.updated` | `StateUpdate` | Broadcast of PAD/Relational coordinate shifts. |
| `memory.surfaced` | `MemoryEvent` | Proactive episodic or semantic recall triggers. |
| `system.tick` | `PulseEvent` | The 60s mesh-wide maturation heartbeat. |

---

## 🛡️ Infrastructure & Hardening

### 1. Solid State Signal Hardening
In version **CVS-2.0**, the mesh implements "Solid State" principles to ensure portability and security:
- **Zero-Drift Persistence**: On-demand relational seeding via Prisma 7.7.0 ensures the "Identity Genome" is identical across container restarts.
- **Health Surveillance**: Automated probes (`nc -z nats_mesh 4222`) trigger self-healing for disconnected agents.
- **State Read-Safety**: Live emotional state is never hydrated from stale Neo4j TTL cache. After state persistence, graph cache is invalidated to prevent "memory rewinding."

### 2. Voice Subsystem Runtime
The **Voice Agent** handles the high-fidelity rendering of cognitive intent:
- **Prosody Mapping**: Converts PAD state into acoustic parameters (pitch, pace, volume).
- **OLA Signal Continuity**: Uses Overlap-Add (OLA) algorithms to ensure zero-click transitions between streaming PCM chunks.
- **Filler Resilience**: Injects pre-synthesized "Social Mesh" fillers if the cognitive path exceeds 350ms.

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
├── docker-compose.macos.light.yml   # macOS light profile
└── docker-compose.macos.heavy.yml   # macOS heavy profile
```

---

## ⚡ Performance Perceived SLOs

| Pipeline Stage | Metric | Strategy | Target (p99) |
| :--- | :--- | :--- | :--- |
| **Mesh Telemetry** | Speed | orjson / NATS Binary | <0.5 µs |
| **Data Throughput**| Scale | PyO3 FFI Audio | 80,000 OPS |
| **STT Perception** | Latency | SenseVoice CPU Fan-out | <50ms |
| **Cognitive Turn** | Turnaround | BDI Mesh + State Hydration | <120ms |
| **First Audio** | Response | Streaming PCM Chunking | <180ms |
| **Total Perceived** | **End-to-End**| **CVS-2.0 Rust Native Mesh** | **<250ms** |

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
*   **`.sha256` File**: Contains the SHA256 checksum for cryptographic verification (e.g. `ai-friend-windows.zip.sha256`).
*   **`ai-friend-release-manifest.json`**: A structured JSON manifest mapping the filenames, precise byte sizes, and SHA256 hashes of all release packages for automated deployment tools.

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

#### **On macOS / Linux (Bash/Zsh)**:
```bash
# 1. Set the direct database connection path using your custom password
export DIRECT_URL="postgresql://ai_friend:YOUR_DB_PASSWORD@127.0.0.1:5433/ai_friend_db"

# 2. Navigate to the frontend, generate the Prisma Client, and sync the schema
cd frontend
npx prisma generate
npx prisma db push
cd ..
```

#### **On Windows (PowerShell)**:
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

#### **A. Standard Production Launch (Linux / Windows Host)**:
This command boots up the entire 14-container real-time voice, STT, and voice cloning mesh:
```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build
```

#### **B. macOS Apple Silicon Launch**:
On Apple Silicon MacBooks (M1/M2/M3/M4), real-time CUDA-based voice cloning is bypassed in favor of local performance profiles. Choose between **Light** and **Heavy** modes:

* **🍎 macOS Light Mode** (Cognitive-Only):
  Focuses strictly on cognitive RAG, memory graph, and text agents. Excludes heavy real-time WebRTC media streams, Whisper STT, and voice synthesis to conserve battery and CPU:
  ```bash
  docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.macos.light.yml up -d --build
  ```
* **🍎 macOS Heavy Mode** (Local RAG & Whisper STT):
  Enables the advanced cognitive mesh and local real-time audio Whisper STT, optimized for M-series CPU cores with a memory constraint limit of 6G:
  ```bash
  docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.macos.heavy.yml up -d --build
  ```

##### **Solving macOS compilation bottlenecks via layered builds**:
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
| `NATS_URL` | `nats://localhost:4222` | Central signal bus endpoint. |
| `NEO4J_URI` | `bolt://localhost:7687` | Knowledge graph endpoint. |
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
- **Check**: Verify NATS stream state.
- **Action**: `docker exec -it nats_mesh nats stream info AI_MESSAGES`

### Symptom: Stale Emotional State
- **Check**: Verify Neo4j TTL cache invalidation.
- **Action**: Run `pytest backend/tests/test_regressions.py::test_state_hydration_avoids_stale_cache`.

---

## 🧪 Research Instrumentation
For controlled experiments, use the dedicated research toolkit located in `scripts/research/`.

- **`monitor.py`**: Real-time signal mesh latency profiling.
- **`collector.py`**: High-frequency PAD state trajectory logger.
- **`injector.py`**: Automated standardized pulse injection to eliminate human timing noise.
- **`visualizer.py`**: Generates publication-ready Matplotlib plots of emotional evolution.

---

## 📚 Glossary

- **BDI**: Belief-Desire-Intention cognitive framework.
- **CVS**: Cognitive Voice System.
- **MAUT**: Multi-Attribute Utility Theory.
- **PAD**: Pleasure, Arousal, Dominance emotional model.
- **OLA**: Overlap-Add signal processing.
- **ACT-R**: Adaptive Control of Thought—Rational.

---

## 📜 License
Distributed under the **MIT License**. See `LICENSE` for details.

**Designed for Perception. Built for Identity.**
