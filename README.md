# 🎙️ AI Friend: Cognitive Voice System (CVS-1.0)

**A High-Fidelity, State-Driven Cognitive Identity Emulator.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)
[![Latency: Perceived <250ms](https://img.shields.io/badge/Latency-Perceived%20%3C250ms-green.svg)](#performance-perceived-slos)
[![Architecture: Hardened CVS-1.0](https://img.shields.io/badge/Architecture-CVS--1.0--Hardened-orange.svg)](#architecture-cvs-10-hardened)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Aniket-a14/AI_friend/blob/main/notebooks/ai_friend_voice_training.ipynb)

---

## 🌟 Overview

**AI Friend** is a next-generation AI architecture engineered for **ultra-low latency** conversational realism. Unlike traditional "request-response" voice agents, AI Friend uses the **CVS-1.0 (Cognitive Voice System)** runtime to synchronize reasoning, temporal pacing, and high-fidelity signal rendering into a single, cohesive identity.

The system is built for **Sovereign Privacy**, ensuring that identity evolution, semantic memory, and voice synthesis happen 100% locally on user-controlled hardware.

AI Friend should be read as a **software mind-and-voice layer**, not as a productivity assistant. Its success metric is not only correctness. The real target is whether conversation feels like speaking with a persistent person who has mood, memory, habits, timing, and a stable voice presence. That makes the project closer to a cognitive identity emulator than a conventional chatbot.

### What CVS-1.0 Optimizes For

- **Identity Continuity**: The same personality, values, boundaries, relationship state, and speaking habits should survive long sessions and restarts.
- **Emotional Stability**: Mood, energy, trust, and attachment should move smoothly instead of jumping every turn.
- **Perceptual Latency**: The system prioritizes when the user first hears a believable response, not only when the full response is complete.
- **Natural Interruption**: Fast perception can pause speech speculatively, while the final transcript confirms or rejects the interruption.
- **Organic Memory**: Memory should influence conversation like recollection, not like a rigid search result list.
- **Local-First Modularity**: Every major component remains replaceable for future robotics, sensors, and voice engines.

---

AI Friend uses a **Hardened Sovereign Mesh**. In version **CVS-1.0**, the architecture transitioned from a reactive "Think-Speak" pipeline to a persistent **Identity Mesh**. This ensures that the agent's internal state (mood, trust, energy) evolves continuously via a mesh heartbeat, even during idle periods.

### 1. System Topology
The platform is orchestrated as a **Solid State Agent Mesh** communicating over a hardened NATS JetStream signal bus.

```mermaid
graph TD
    User((User)) <--> |"WebRTC / PCM"| Frontend["Next.js Frontend"]
    Frontend <--> |"FastAPI"| Signaling["Signaling Server"]
    
    subgraph "Sovereign Mesh [Solid State Mesh (9 Subjects)]"
        Signaling <--> |"NATS"| Bus{"NATS JetStream"}
        Bus <--> STT["STT Agent: Whisper/SenseVoice"]
        Bus <--> Brain["Brain Agent: BDI Cognition"]
        Bus <--> Voice["Voice Agent: CVS Runtime"]
        Bus <--> Vision["Vision Agent: CV2/Llava"]
        Bus <--> Pulse["System Agent: Heartbeat"]
        Bus <--> Recall["Surfacing Agent: Memory"]
    end
    
    subgraph "Infrastructure"
        Brain <--> Neo4j[("(Neo4j: GraphRAG)")]
        Brain <--> Postgres[("(Postgres: Relational Identity)")]
        Brain <--> Ollama["Ollama: LLM"]
        Voice <--> SoVITS["GPT-SoVITS API"]
    end
```

### 2. The Perceptual "Pulse" Path
To achieve sub-280ms perceived latency, the system utilizes a non-linear signal path with hardware-optimized `sherpa-onnx`.

```mermaid
sequenceDiagram
    participant U as User
    participant S as "STT Agent (SenseVoice)"
    participant B as Brain Agent
    participant V as Voice Agent
    
    U->>S: Raw Audio Stream
    S->>B: "chat.input (Hinglish/Text)"
    B->>V: "chat.output (Incremental Segment + Metadata)"
    V->>V: "Jitter Buffer & Atomic Phrasing"
    V->>U: Raw 32kHz PCM
    V-->>B: "voice.segmentation_feedback (Telemetry)"
    Note over B,V: Closed-Loop Pulse Adjustment
```

---

### 🛡️ Solid State Mesh Hardening
In version **CVS-1.0 Hardened**, we achieved **Zero-Drift Resilience**.
- **9-Subject Signal Bus**: NATS now routes `chat`, `vision`, `state`, `cmd`, `voice`, `system`, `memory`, `identity`, and `knowledge`.
- **Decentralized Credential Enforcer**: Hardcoded credentials are rejected; the mesh requires strict `.env` variables.
- **Identity Mesh (Prisma 7.7.0)**: On-demand relational seeding ensures the AI's "Deep Self" is preserved across any hardware or container restart.
- **State Cache Correctness**: Live emotional state is never hydrated from stale Neo4j TTL cache. State writes invalidate graph cache so mood, energy, trust, and attachment cannot rewind after a fresh interaction.
- **Single Identity Owner**: Reflection and response generation now share one live `IdentityManager`, ensuring adaptive persona evolution affects active conversation immediately.

### 🎭 Hybrid Identity Model
Introduced an **Immutable Core** (base values, boundaries) paired with **Adaptive Variables** (habits, style), preventing personality drift while allowing natural behavioral growth.

### ⏳ Expressive Temporal Phrasing
Voice synthesis now executes cognitive timing. The system parses `<pause>` and `<hesitate>` tags, injecting deterministic silent PCM buffers into the 32kHz stream for human-like cognitive cues.

The voice path streams GPT-SoVITS PCM chunks as they arrive instead of waiting for full synthesis completion. This keeps perceived response timing closer to live conversation and allows filler, hesitation, and interruption recovery to happen inside the signal runtime instead of after the fact.

### 🐚 Active Memory Surfacing
Asynchronous background agent evaluates shared history vs. current intent to "surface" relevant past moments, allowing memory to color the current response without adding latency.

Surfacing includes novelty suppression so the same memory is not repeatedly reintroduced in a short window. Passive surfacing also avoids refreshing `last_recalled_at`, preventing "compulsive recall" loops where a memory becomes more likely to appear just because it recently appeared.

---

## ⚡ Performance Perceived SLOs

| Pipeline Stage | Raw Latency | Perceptual Strategy |
| :--- | :--- | :--- |
| **STT (Inference)** | <50ms | Whisper V3 Turbo |
| **Brain (Cognition)**| <80ms | BDI Mesh + live state snapshot |
| **TTS (First Audio)** | <120ms | Streaming GPT-SoVITS raw PCM chunks |
| **Pacing (Wait)** | 0-15ms | Structured speculative intent guard |
| **Perceived Turn** | **<250ms** | **Phase 2 Hardened Standard** |

---

## 🛠️ Technical Stack

- **Frontend**: Next.js 16, Tailwind CSS, Framer Motion, LiveKit WebRTC.
- **Backend Core**: FastAPI (Asynchronous Signaling).
- **Messaging**: NATS JetStream (Ultra-low latency event bus).
- **Agents**: Python asyncio + `sherpa-onnx` (Robotic Perception).
- **Storage**: Neo4j (GraphRAG), PostgreSQL (Identity State), Prisma 7.7.0 ORM.
- **AI Models**: Ollama (Llama 3.2), GPT-SoVITS V4 (32kHz), Whisper V3 Turbo.

---

## 📂 Project Structure

```text
├── .agents/             # Agent skills and memory systems
│   └── CONTEXT.md       # Persistent handoff ledger for future agents
├── app/                 # Core logic
│   ├── agents/          # Agent implementations (Brain, Voice, STT)
│   ├── cognitive/       # BDI and decision services
│   ├── tts/             # Speech synthesis clients
│   └── main.py          # Signaling entry point
├── docs/                # Technical documentation suite
├── frontend/            # Next.js 16 application
├── GPT_SoVITS/          # Voice training submodule
├── notebooks/           # Training & Dev scripts
├── docker-compose.yml   # Orchestration
└── requirements.txt     # Python dependencies
```

---

## ⚙️ Getting Started

### 1. Prerequisites (Portability Standard)
- **OS**: Windows (WSL2) or Linux.
- **Hardware**: NVIDIA GPU (RTX 3060+) or Apple Silicon (M2+).
- **Software**: Docker Desktop, Python 3.11+, NPM.

### 2. Launch the Mesh (Zero-Drift)
```bash
# A. infrastructure (NATS, Postgres, Neo4j, Ollama, SoVITS)
docker compose -f docker-compose.infra.yml up -d

# B. Sync the Identity Genome (Prisma 7.7.0)
$env:DIRECT_URL="postgresql://ai_friend:[PASSWORD]@localhost:5432/ai_friend_db"
cd frontend && npx prisma db push && cd ..

# C. Cognitive Agents (Decision & Perception Layers)
docker compose -f docker-compose.prod.yml up -d --build
```

### 3. Verification & Audit
Run the automated mesh audit to ensure all 12 services are healthy:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```
Refer to the **[Installation Guide](docs/GPT_SOVITS_INSTALL.md)** and **[Deployment Guide](docs/DEPLOYMENT.md)** for deep environment hardening.

### 4. Local Test Suite
Use the project-local backend virtual environment rather than the global Python installation:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

The latest verified result after the CVS runtime fixes was `48 passed`, with one non-blocking `.pytest_cache` permission warning on the local machine.

---

## 🧭 Documentation Map

The full documentation suite lives in [docs](docs/README.md). Start there if you are helping another agent or developer understand the project.

- [Architecture](docs/ARCHITECTURE.md) explains the mesh, cognition, memory, voice, and feedback loops.
- [API Spec](docs/API_SPEC.md) documents REST endpoints and NATS subject contracts.
- [Identity System](docs/IDENTITY_SYSTEM.md) explains immutable identity, adaptive variables, state, and memory surfacing.
- [Latency Improvement](docs/LATENCY_IMPROVEMENT.md) explains perceived-latency strategy, streaming PCM, and timing markers.
- [Deployment](docs/DEPLOYMENT.md) covers local and production deployment.
- [.agents/CONTEXT.md](.agents/CONTEXT.md) is the persistent context ledger future agents should read before modifying the system.

---

## 🗺️ Roadmap: The Path to CVS-1.1

- [x] **Dynamic Identity Evolution**: State-driven personality system with NATS heartbeat.
- [x] **Structured Interruption Arbitration**: SenseVoice publishes speculative intent, Whisper validates, and the brain confirms stop/resume behavior.
- [x] **Streaming Voice Runtime**: VoiceAgent queues raw PCM chunks as they arrive for lower perceived first-audio latency.
- [ ] **Expression Side-Channel**: Move affect, rate, and intensity to a structured channel so only timing markers remain in text.
- [ ] **Emotion-Matched Interjection**: Soft-pause logic for more human-like overlap and backchanneling.
- [ ] **M4 CoreML Integration**: Native NPU support for zero-GPU voice synthesis.

---

## 📜 License & Community

Distributed under the **MIT License**. See `LICENSE` for details.

**Designed for Perception. Built for Identity.**
