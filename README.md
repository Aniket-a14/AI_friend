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

---

AI Friend uses a **Hardened Sovereign Mesh**. In version **CVS-1.0**, the architecture transitioned from a reactive "Think-Speak" pipeline to a persistent **Identity Mesh**. This ensures that the agent's internal state (mood, trust, energy) evolves continuously via a mesh heartbeat, even during idle periods.

### 1. System Topology
The platform is orchestrated as a **Parallel Agent Mesh** communicating over NATS JetStream.

```mermaid
graph TD
    User((User)) <--> |WebRTC / PCM| Frontend[Next.js Frontend]
    Frontend <--> |FastAPI| Signaling[Signaling Server]
    
    subgraph Sovereign Mesh
        Signaling <--> |NATS| Bus{NATS JetStream}
        Bus <--> STT[STT Agent: Whisper]
        Bus <--> Brain[Brain Agent: BDI Cognition]
        Bus <--> Voice[Voice Agent: CVS Runtime]
        Bus <--> Vision[Vision Agent: CV2/Llava]
        Bus <--> Pulse[System Agent: Heartbeat]
        Bus <--> Recall[Surfacing Agent: Memory]
    end
    
    subgraph Infrastructure
        Brain <--> Neo4j[(Neo4j: GraphRAG)]
        Brain <--> Ollama[Ollama: LLM]
        Voice <--> SoVITS[GPT-SoVITS API]
    end
```

### 2. The Perceptual "Pulse" Path
To achieve sub-280ms perceived latency, the system utilizes a non-linear signal path.

```mermaid
sequenceDiagram
    participant U as User
    participant S as STT Agent
    participant B as Brain Agent
    participant V as Voice Agent
    
    U->>S: Raw Audio Stream
    S->>B: chat.input (Text)
    B->>V: chat.output (Incremental Segment + Metadata)
    V->>V: Jitter Buffer & Atomic Phrasing
    V->>U: Raw 32kHz PCM
    V-->>B: voice.segmentation_feedback (Telemetry)
    Note over B,V: Closed-Loop Pulse Adjustment
```

---

### 🤖 Identity Continuity (State Heartbeat)
Implemented a mesh-wide `system.tick`. State variables (Mood, Energy, Trust) are persistent in Neo4j and evolve incrementally during interactions and idle time.

### 🎭 Hybrid Identity Model
Introduced an **Immutable Core** (base values, boundaries) paired with **Adaptive Variables** (habits, style), preventing personality drift while allowing natural behavioral growth.

### ⏳ Expressive Temporal Phrasing
Voice synthesis now executes cognitive timing. The system parses `<pause>` and `<hesitate>` tags, injecting deterministic silent PCM buffers into the 32kHz stream for human-like cognitive cues.

### 🐚 Active Memory Surfacing
Asynchronous background agent evaluates shared history vs. current intent to "surface" relevant past moments, allowing memory to color the current response without adding latency.

---

## ⚡ Performance Perceived SLOs

| Pipeline Stage | Raw Latency | Perceptual Strategy |
| :--- | :--- | :--- |
| **STT (Inference)** | <50ms | Whisper V3 Turbo |
| **Brain (Cognition)**| <80ms | BDI Mesh + TTL Cache |
| **TTS (Synthesis)** | <120ms | Direct Binary PCM 32kHz |
| **Pacing (Wait)** | 0-15ms | Temporal Intent Guard |
| **Perceived Turn** | **<250ms** | **Phase 2 Hardened Standard** |

---

## 🛠️ Technical Stack

- **Frontend**: Next.js 16, Tailwind CSS, Framer Motion, LiveKit WebRTC.
- **Backend Core**: FastAPI (Asynchronous Signaling).
- **Messaging**: NATS JetStream (Ultra-low latency event bus).
- **Agents**: Python asyncio (Atomic State Machines).
- **Storage**: Neo4j (GraphRAG), PostgreSQL (Identity State), Redis (Caching).
- **AI Models**: Ollama (Llama 3.2/Qwen 2.5), GPT-SoVITS V4 (32kHz), Whisper V3.

---

## 📂 Project Structure

```text
├── .agents/             # Agent skills and memory systems
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

### 1. Prerequisites (2026 Standards)
- **OS**: Windows (WSL2 recommended) or Linux.
- **Hardware**: NVIDIA GPU (RTX 3060+) or Apple Silicon (M2+).
- **Software**: Docker Desktop, Python 3.11+, NATS CLI.

### 2. Launch via Docker Sovereign Mesh
```bash
# A. infrastructure (NATS, Postgres, Neo4j)
docker compose -f docker-compose.infra.yml up -d

# B. Cognitive Agents (Brain, Voice, STT)
docker compose up -d --build
```

### 3. Manual Setup (For Developers)
Refer to the **[Installation Guide](docs/GPT_SOVITS_INSTALL.md)** for deep environment hardening (numpy < 2.0, libsox).

---

## 🗺️ Roadmap: The Path to CVS-1.1

- [x] **Dynamic Identity Evolution**: State-driven personality system with NATS heartbeat.
- [ ] **Emotion-Matched Interjection**: Soft-pause logic for more human-like interruptions.
- [ ] **M4 CoreML Integration**: Native NPU support for zero-GPU voice synthesis.

---

## 📜 License & Community

Distributed under the **MIT License**. See `LICENSE` for details.

**Designed for Perception. Built for Identity.**
