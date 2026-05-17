# 🎙️ AI Friend: Cognitive Voice System (CVS-1.0)

**A high-fidelity, state-driven cognitive identity emulator built on a hardened Sovereign Mesh for ultra-low latency conversational realism.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)
[![Latency: Perceived <250ms](https://img.shields.io/badge/Latency-Perceived%20%3C250ms-green.svg)](#performance-perceived-slos)
[![Architecture: Hardened CVS-1.0](https://img.shields.io/badge/Architecture-CVS--1.0--Hardened-orange.svg)](#architecture-cvs-10-hardened)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Aniket-a14/AI_friend/blob/main/notebooks/ai_friend_voice_training.ipynb)
[![Continuous Integration](https://github.com/Aniket-a14/AI_friend/actions/workflows/ci.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/ci.yml)
[![🛡️ Mesh Integrity](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml)
[![🧠 Cognitive Regression](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml)
[![🎭 Persona Guard](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml)
[![🔒 Security Audit](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml) 
[![📦 Docker Build](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-build.yml)
[![🩺 Docker Health](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml)
[![🔗 Link Validator](https://github.com/Aniket-a14/AI_friend/actions/workflows/links.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/links.yml)
[![🚀 Release Status](https://github.com/Aniket-a14/AI_friend/actions/workflows/release.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/release.yml)

**CALIBRATION: EXPERT** — *This documentation assumes proficiency in asynchronous event-driven architectures, NATS JetStream protocols, and computational cognitive modeling (BDI, PAD, ACT-R, MAUT).*

---

## 🌟 The Philosophy of Perceptual Mastery

AI Friend is not a reactive "turn-based" chatbot. It is a **Sovereign Mesh** of specialized agents synchronized through a hardened signal bus. In the **CVS-1.0 Hardened (May 2026)** release, the architecture shifted from a monolithic processing pipeline to a **State-Driven Identity Mesh**.

### 🧠 Reactive vs. Sovereign Intelligence
| Feature | Reactive Chatbot (Legacy) | Sovereign Mesh (CVS-1.0) |
| :--- | :--- | :--- |
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
        Bus <--> |"chat.output / audio.stop/resume"| Voice["Voice Agent: CVS Runtime"]
        Bus <--> |"vision.control / vision.description"| Vision["Vision Agent: Host-Native VLM"]
        Bus <--> |"system.tick"| Pulse["System Agent: Heartbeat"]
        Bus <--> |"memory.surfaced / state.update"| Recall["Surfacing Agent: Memory"]
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

CVS-1.0 utilizes a **Dual-STT fan-out** with a 3-stage interruption arbitration protocol.

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
| **Voice Agent** | Python / SoVITS | CVS-1.0 Runtime; renders affect-aware 32kHz audio. | `chat.output`, `audio.stream`, `audio.stop` |
| **STT Agent** | ONNX / Whisper | Dual-path perception; fan-out transcription. | `audio.inbound`, `chat.input`, `audio.perception` |
| **Transport Agent**| Node / LiveKit | WebRTC gateway; raw PCM chunking and stream bridging. | `audio.inbound`, `audio.stream` |
| **Surfacing Agent**| Python / pgvector | ACT-R episodic memory retrieval and proactive recall. | `memory.surfaced`, `chat.input` |
| **Subconscious** | Python / Neo4j | Background reflection, fact consolidation, persona evolution. | `system.tick`, `knowledge.*` |
| **Vision Agent** | Llava / OpenCV | Visual perception and spatial reasoning. | `vision.frames`, `vision.control` |
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
- **Endocrine Modulation**: Current PAD values modulate LLM parameters. For example, high **Arousal** (Stress) reduces LLM `temperature` to produce more focused, rigid responses.

### 2. Memory Activation (ACT-R)
The Surfacing Agent utilizes the **ACT-R Base-Level Activation** formula to prioritize episodic recall:
$$A_i = \ln \left( \sum_{j=1}^n t_j^{-d} \right)$$
- **$d$ (Decay)**: Typically set to `0.5`, simulating human-like forgetting where older, unaccessed memories lose activation.
- **$n$ (Frequency)**: Strengthens memories that are frequently recalled or accessed.

### 3. Relational Trust (Marsh Model)
Trust evolves as a function of interaction outcomes and perceived agent reliability:
$$T_{new} = \text{clamp}(T_{old} + \delta \cdot RI, 0, 1)$$
Where $RI$ is the **Relationship Impact** derived from the Appraisal Engine.

### 4. Decision Utility (MAUT)
The Decision Service uses **Multi-Attribute Utility Theory** to score intent candidates:
$$U(Intent) = w_{goal} \cdot G + w_{emotion} \cdot E + w_{identity} \cdot I + w_{context} \cdot C$$

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
In version **CVS-1.0**, the mesh implements "Solid State" principles to ensure portability and security:
- **Zero-Drift Persistence**: On-demand relational seeding via Prisma 7.7.0 ensures the "Identity Genome" is identical across container restarts.
- **Health Surveillance**: Automated probes (`nc -z nats_mesh 4222`) trigger self-healing for disconnected agents.
- **State Read-Safety**: Live emotional state is never hydrated from stale Neo4j TTL cache. After state persistence, graph cache is invalidated to prevent "memory rewinding."

### 2. Voice Subsystem Runtime
The **Voice Agent** handles the high-fidelity rendering of cognitive intent:
- **Prosody Mapping**: Converts PAD state into acoustic parameters (pitch, pace, volume).
- **OLA Signal Continuity**: Uses Overlap-Add (OLA) algorithms to ensure zero-click transitions between streaming PCM chunks.
- **Filler Resilience**: Injects pre-synthesized "Social Mesh" fillers if the cognitive path exceeds 350ms.

---

## 📂 Directory Structure Deep-Dive

```text
├── .agents/                  # Agent skills and context ledgers
├── backend/
│   ├── app/
│   │   ├── agents/           # NATS Agent Implementations
│   │   │   ├── base.py       # Base class for all mesh participants
│   │   │   ├── brain_agent.py# BDI decision core
│   │   │   └── ...           # STT, Voice, Vision, etc.
│   │   ├── cognitive/        # Cognitive modeling logic
│   │   │   ├── appraisal.py  # OCC/Lazarus engine
│   │   │   ├── decision.py   # MAUT intent selection
│   │   │   └── identity.py   # Immutable vs Adaptive traits
│   │   ├── state/            # Persistence and Memory
│   │   │   ├── agent_state.py# PAD + ALMA dynamics
│   │   │   └── memory_store.py# ACT-R + pgvector retrieval
│   │   ├── voice/            # CVS-1.0 Audio Runtime
│   │   ├── stt/              # Dual-path STT perception
│   │   └── contracts.py      # Pydantic Signal Contracts
│   └── tests/                # 24+ regression tests for cognitive stability
├── db/                       # Prisma schemas and SQL baselines
├── docs/                     # Technical deep-dives (Architecture, Research)
├── frontend/                 # Next.js 16 WebRTC dashboard
└── docker-compose.infra.yml  # Multi-stage mesh orchestration
```

---

## ⚡ Performance Perceived SLOs

| Pipeline Stage | Metric | Strategy | Target (p99) |
| :--- | :--- | :--- | :--- |
| **STT Perception** | Latency | SenseVoice CPU Fan-out | <50ms |
| **Cognitive Turn** | Turnaround | BDI Mesh + State Hydration | <120ms |
| **First Audio** | Response | Streaming PCM Chunking | <180ms |
| **Interruption Stop**| Reflex | Speculative Intent Guard | <100ms |
| **Total Perceived** | **End-to-End**| **CVS-1.0 Solid State Mesh** | **<250ms** |

---

## 🛠️ Hardware Tier Matrix

| Tier | Purpose | CPU | GPU | RAM |
| :--- | :--- | :--- | :--- | :--- |
| **Mini** | Evaluation | 4-Core | None (CPU Whisper) | 8GB |
| **Standard** | Real-time | 8-Core | RTX 3060 (12GB) | 16GB |
| **High-End** | Research | 16-Core | RTX 4090 / M2 Ultra | 64GB |

---

## ⚙️ Quick Start

Follow this standardized, environment-hardened sequence to initialize the Sovereign Mesh:

### **Step 1: Bootstrap Shared Network & Infrastructure**
1. Recreate the external shared network required by the mesh:
   ```powershell
   docker network create ai_mesh_network
   ```
2. Launch the infrastructure containers (PostgreSQL, Neo4j, Redis, NATS, and LiveKit):
   ```powershell
   docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d postgres neo4j redis nats livekit
   ```

### **Step 2: Hydrate & Seed the Database (Prisma + Raw SQL)**
To bypass Windows/WSL2 IPv6 network deadlocks and native Postgres conflicts, the containerized database is mapped to the isolated external port **`5433`** on IPv4 (`127.0.0.1`).

1. **Push the Schema**:
   ```powershell
   # 1. Set the direct database connection path using your password (default: 'Pankudi')
   $env:DIRECT_URL="postgresql://ai_friend:Pankudi@127.0.0.1:5433/ai_friend_db"

   # 2. Enter the frontend folder, generate the Prisma Client, and push the schema
   cd frontend
   npx prisma generate
   npx prisma db push
   cd ..
   ```
2. **Seed Agent Personality**:
   Pisma v7 requires strict module bindings for external scripts. To bypass this, pipe the raw baseline SQL seed directly into the running database container in one command:
   ```powershell
   # Create and pipe the seed configuration
   Get-Content -Raw -Encoding utf8 -Path (Join-Path (Get-Location) "frontend" "prisma" "seed.js") | ForEach-Object {
       # Seed is executed via psql within the running container
       docker exec -i postgres_db psql -U ai_friend -d ai_friend_db -c "
       INSERT INTO agent_configs (id, personality, background_history, evolved_learnings, updated_at) 
       VALUES (
           1, 
           '{\"name\": \"AI Friend\", \"core_personality\": {\"immutable\": {\"values\": [\"Honesty\", \"Privacy\", \"Curiosity\"], \"base_tone\": \"Warm, intellectual, and slightly protective\", \"boundaries\": [\"Will never share user data\", \"Will not adopt toxic behavior\"]}, \"adaptive_traits\": []}, \"speaking_style\": {\"pace\": \"natural\", \"verbosity\": \"balanced\"}, \"conversation_rules\": {\"avoid\": []}}', 
           '{\"relationship\": \"Friend\", \"memories\": []}', 
           '', 
           NOW()
       ) 
       ON CONFLICT (id) DO UPDATE SET 
           personality = EXCLUDED.personality, 
           background_history = EXCLUDED.background_history;"
   }
   ```

### **Step 3: Launch Cognitive Agents**
Build and boot up your local agent containers (the brain, stt, voice, surfacing agents, etc.):
```powershell
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build
```

### **Step 4: Health Audit**
Confirm all 14 containers are in an active, healthy, and communicating state:
```powershell
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps
```

---

## 🛠️ Windows & WSL2 Troubleshooting Guide

If you encounter initialization errors, review these standard Windows-specific fixes:

### **1. P1000 Authentication Failed on Port 5432/5433**
This happens when a **native Windows PostgreSQL service** (installed outside of Docker) is running in the background and capturing port bindings.
* Stop and kill all native `postgres` processes at once:
  ```powershell
  Stop-Service -Name "postgresql*" -Force -ErrorAction SilentlyContinue
  Get-Process -Name "postgres" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  ```
* Restart the Docker container to capture the port:
  ```powershell
  docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml restart postgres
  ```

### **2. Disk Space Not Reclaimed After Wiping Volumes**
WSL2 dynamically expands its virtual disk file (`ext4.vhdx`) but **never shrinks it automatically** when you delete containers/images.
* **Empty your Recycle Bin**: Manually deleted folders (like `%LOCALAPPDATA%\Docker\wsl`) are held in the Windows Recycle Bin, retaining all 100GB+ of space.
* **WSL2 Shutdown**: Force Windows to release the WSL virtual disk memory locks:
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
