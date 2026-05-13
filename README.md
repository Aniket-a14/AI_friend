# 🎙️ AI Friend: Cognitive Voice System (CVS-1.0)

**A High-Fidelity, State-Driven Cognitive Identity Emulator.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)
[![Latency: Perceived <250ms](https://img.shields.io/badge/Latency-Perceived%20%3C250ms-green.svg)](#performance-perceived-slos)
[![Architecture: Hardened CVS-1.0](https://img.shields.io/badge/Architecture-CVS--1.0--Hardened-orange.svg)](#architecture-cvs-10-hardened)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Aniket-a14/AI_friend/blob/main/notebooks/ai_friend_voice_training.ipynb)
[![🧠 Cognitive Regression](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/cognitive-regression.yml)
[![🛡️ Mesh Integrity](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/mesh-integrity.yml)
[![🎭 Persona Guard](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/persona-guard.yml)
[![🔒 Security Audit](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/security-audit.yml)
[![📦 Docker Health](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml/badge.svg)](https://github.com/Aniket-a14/AI_friend/actions/workflows/docker-health.yml)

---

## 🌟 Overview

**AI Friend** is a next-generation AI architecture engineered for **ultra-low latency** conversational realism. Unlike traditional "request-response" voice agents, AI Friend uses the **CVS-1.0 (Cognitive Voice System)** runtime to synchronize reasoning, temporal pacing, and high-fidelity signal rendering into a single, cohesive identity.

The system is built for **Sovereign Privacy**, ensuring that identity evolution, semantic memory, and voice synthesis happen 100% locally on user-controlled hardware.

AI Friend should be read as a **software mind-and-voice layer**, not as a productivity assistant. Its success metric is not only correctness. The real target is whether conversation feels like speaking with a persistent person who has mood, memory, habits, timing, and a stable voice presence. That makes the project closer to a cognitive identity emulator than a conventional chatbot.

## ✅ Current Status (May 2026)

- Runtime and CI hardening are in place for JetStream startup, stream readiness, and fallback safety.
- Surfacing behavior is deterministic on `system.tick`, while preserving async scheduling for chat-triggered sweeps.
- Latency badges and targets refer to **perceived first reaction latency**, not full-turn completion latency.
- Forward-looking cognition upgrades (duplex partial cognition and tighter human turn-taking timing contracts) are documented in [_archive/docs/analysis_results.md](_archive/docs/analysis_results.md).

### What CVS-1.0 Optimizes For

- **Identity Continuity**: The same personality, values, boundaries, relationship state, and speaking habits should survive long sessions and restarts.
- **Emotional Stability**: Mood, energy, trust, and attachment should move smoothly instead of jumping every turn.
- **Perceptual Latency**: The system prioritizes when the user first hears a believable response, not only when the full response is complete.
- **Natural Interruption**: Fast perception can pause speech speculatively, while the final transcript confirms or rejects the interruption.
- **Organic Memory**: Memory influences conversation like human recollection. The agent alternates between Semantic (fact retrieval) and Episodic (mood-congruent narrative) channels, allowing it to bond over shared history ("Remember last week when we...") rather than acting like a rigid search engine.
- **Local-First Modularity**: Every major component remains replaceable for future robotics, sensors, and voice engines.

---

AI Friend uses a **Hardened Sovereign Mesh**. In version **CVS-1.0**, the architecture transitioned from a reactive "Think-Speak" pipeline to a persistent **Identity Mesh**. This ensures that the agent's internal state (mood, trust, energy) evolves continuously via a mesh heartbeat, even during idle periods.

### 1. System Topology

The platform is orchestrated as a **Solid State Agent Mesh** communicating over a hardened NATS JetStream signal bus. All inter-agent messages are validated through **typed Pydantic contracts** (`contracts.py`).

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
        Bus <--> |"vision.control / vision.frames"| Vision["Vision Agent: CV2/Llava"]
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

### 2. The Perceptual "Pulse" Path (Dual-STT)

To achieve sub-250ms perceived latency, the system utilizes a **dual-STT fan-out** with a 3-stage interruption protocol. All messages are validated through typed Pydantic contracts before publish.

```mermaid
sequenceDiagram
    participant U as User
    participant T as TransportAgent
    participant SV as "SenseVoice (Fast Path)"
    participant W as "Whisper (Accurate Path)"
    participant B as Brain Agent
    participant V as Voice Agent

    U->>T: WebRTC Audio
    T->>T: PCM → audio.inbound

    par Dual-STT Fan-Out
        T->>SV: 400ms chunks (CPU)
        T->>W: Full utterance (GPU)
    end

    SV->>B: AudioPerception (emotion + speculative intent)
    Note over SV,V: Stage 1 — Speculative pause if stop detected
    SV-->>V: AudioStop(speculative=true)

    W->>B: ChatInput (final transcript, typed contract)
    Note over B: Stage 2 — Cognitive confirms or rejects stop
    B-->>V: AudioResume (if rejected) / AudioStop (if confirmed)

    B->>V: ChatOutput (incremental segments + affect)
    V->>V: prosody.py → playback.py → resilience.py
    V->>T: Raw 32kHz PCM → audio.stream
    T->>U: WebRTC Audio
    V-->>B: voice.segmentation_feedback (Telemetry)
    Note over B,V: Closed-Loop Pulse Adjustment
```

---

### 🛡️ Solid State Mesh Hardening

In version **CVS-1.0 Hardened**, we achieved **Zero-Drift Resilience**.

- **9-Subject Signal Bus**: NATS now routes `chat`, `vision`, `state`, `cmd`, `voice`, `system`, `memory`, `identity`, and `knowledge`.
- **Fully Typed Contract Mesh**: 100% of inter-agent messages are now validated via Pydantic models in `contracts.py`, eliminating runtime key-mismatch bugs.
- **Infrastructure Phased Startup**: Implemented `depends_on` conditions with `service_healthy`. The mesh graduates in stages (Infra -> Brain -> Sensory Agents) to eliminate startup race conditions.
- **Mesh Surveillance**: Automated health probes (`nc -z nats_mesh 4222`) trigger self-healing for disconnected agents.
- **Identity Mesh (Prisma 7.7.0)**: On-demand relational seeding ensures the AI's "Deep Self" is preserved across any hardware or container restart.
- **State Cache Correctness**: Live emotional state is never hydrated from stale Neo4j TTL cache. State writes invalidate graph cache so mood, energy, trust, and attachment cannot rewind after a fresh interaction.
- **Single Identity Owner**: Reflection and response generation now share one live `IdentityManager`, ensuring adaptive persona evolution affects active conversation immediately.

### 🎭 Hybrid Identity Model

Introduced an **Immutable Core** (base values, boundaries) paired with **Adaptive Variables** (habits, style), preventing personality drift while allowing natural behavioral growth.

### ⏳ Expressive Temporal Phrasing

Voice synthesis now executes cognitive timing. The system parses `<pause>` and `<hesitate>` tags, injecting deterministic silent PCM buffers into the **32kHz raw binary stream** for human-like cognitive cues.

AI Friend utilizes **100% Raw Binary PCM** (16-bit, 32kHz) across the entire mesh. By eliminating WAV headers and Base64 encoding, we achieve a Solid State signal path that reduces perceived latency to **<250ms**.

### 🧪 Persistent Voice Identity

Instead of synthesizing from scratch each session, you can train a permanent voice model. These weights ensure the AI's "vocal fingerprint" remains consistent forever.

- **Phased Identity Loading**: `VoiceAgent` auto-detects and hydrates your custom `.ckpt` and `.pth` weights from the synchronized `models/` volumes during mesh startup.
- **Reference Guard**: Every synthesis call is fenced with a "Golden Reference" clip that must match your trained weights to prevent model hallucinations or "random lines."
- **Social Mesh**: Common fillers are pre-synthesized using your permanent identity and stored as local PCM files for 0ms access.

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
├── .agents/                  # Agent skills and memory systems
│   └── CONTEXT.md            # Persistent handoff ledger for future agents
├── .editorconfig             # Line ending + indent normalization
├── .env.example              # Environment variable template
├── .github/workflows/        # CI pipeline (pytest + ruff)
├── backend/
│   ├── app/
│   │   ├── agents/           # Mesh agents (Brain, Transport, Surfacing, Vision)
│   │   │   ├── base.py       # BaseAgent — NATS connection, subscribe, publish
│   │   │   ├── brain_agent.py
│   │   │   ├── surfacing_agent.py
│   │   │   └── transport_agent.py
│   │   ├── cognitive/        # BDI cognition pipeline
│   │   │   ├── core.py       # CognitiveService — master loop
│   │   │   ├── perception.py # Raw event → CognitiveEvent
│   │   │   ├── appraisal.py  # OCC/Lazarus 6-variable vector
│   │   │   ├── decision.py   # MAUT scoring + Behavior Tree
│   │   │   ├── action.py     # LLM stream + sanitizer
│   │   │   ├── learning.py   # Fact consolidation + persona evolution
│   │   │   └── identity.py   # Immutable core + adaptive traits
│   │   ├── state/            # Persistence layer
│   │   │   ├── agent_state.py    # PAD + ALMA decay
│   │   │   ├── memory_store.py   # ACT-R retrieval + pgvector
│   │   │   ├── conversation_store.py
│   │   │   └── graph_db.py       # Neo4j with Cypher injection defense
│   │   ├── voice/            # CVS-1.0 voice runtime (decomposed)
│   │   │   ├── agent.py      # State machine + synthesis loop
│   │   │   ├── prosody.py    # VAD → speech parameter mapping
│   │   │   ├── playback.py   # OLA signal continuity + PCM streaming
│   │   │   ├── resilience.py # Filler injection + drift correction
│   │   │   ├── cache.py      # Synthesis result cache
│   │   │   └── sovits_client.py
│   │   ├── stt/              # Dual-STT (SenseVoice + Whisper)
│   │   │   └── agent.py      # Fan-out with typed contract publishing
│   │   ├── contracts.py      # Pydantic models for NATS messages
│   │   ├── metrics.py        # Shared SubjectMetrics utility
│   │   └── config.py         # Centralized configuration
│   ├── tests/
│   │   └── test_regressions.py   # 24 targeted regression tests
│   └── requirements-base.txt     # Pinned dependencies
├── db/
│   └── schema.sql            # Relational schema baseline
├── docs/                     # Technical documentation suite
│   └── psychological_layer.md    # OCC/Lazarus/EMA/ACT-R reference
├── frontend/                 # Next.js 16 application
├── docker-compose.infra.yml  # Infra (NATS, Postgres, Neo4j, Ollama, SoVITS)
├── docker-compose.prod.yml   # Cognitive/agent services
└── _archive/                 # Deprecated files (quarantined)
```

---

## ⚙️ Getting Started

### 1. Prerequisites (Portability Standard)

- **OS**: Windows (WSL2) or Linux.
- **Hardware**: NVIDIA GPU (RTX 3060+) or Apple Silicon (M2+).
- **Software**: Docker Desktop, Python 3.11+, Node.js 20+ and npm.

### 2. Launch the Mesh (Solid State)

```bash
# A. Infrastructure (NATS, Postgres, Neo4j, Ollama, SoVITS)
docker compose -f docker-compose.infra.yml up -d

# B. Sync relational schema (Prisma 7.7.0)
$env:DIRECT_URL="postgresql://ai_friend:[PASSWORD]@localhost:5432/ai_friend_db"
cd frontend && npx prisma db push && cd ..

# C. Unified mesh build and launch (infra + cognitive agents)
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build
```

### 3. Verification & Audit

Run a mesh health snapshot and confirm services are running and healthy where health checks are defined:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Health}}"
```

Refer to the **[Installation Guide](docs/GPT_SOVITS_INSTALL.md)** and **[_archive/docs/DEPLOYMENT.md](_archive/docs/DEPLOYMENT.md)** for deep environment hardening.

### 4. Local Test Suite

Use the project-local backend virtual environment rather than the global Python installation:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

If your shell is not PowerShell, run the same command with the interpreter path for your environment.

---

## 🧭 Documentation Map

The full documentation suite lives in [docs](docs/README.md). Start there if you are helping another agent or developer understand the project.

- [Architecture](docs/ARCHITECTURE.md) explains the mesh, cognition, memory, voice, and feedback loops.
- [API Spec](docs/API_SPEC.md) documents REST endpoints and NATS subject contracts.
- [Identity System](_archive/docs/IDENTITY_SYSTEM.md) explains immutable identity, adaptive variables, state, and memory surfacing.
- [Latency Improvement](_archive/docs/LATENCY_IMPROVEMENT.md) explains perceived-latency strategy, streaming PCM, and timing markers.
- [Deployment](_archive/docs/DEPLOYMENT.md) covers local and production deployment (Phased Startup).
- [.agents/CONTEXT.md](.agents/CONTEXT.md) is the persistent context ledger future agents should read before modifying the system.

### Planning Agent Workflow

Before implementing non-trivial changes, run the Solution Architect planning skill at `skills/solution-architect-agent/SKILL.md`.

Use it for:

- Multi-file feature work and refactors.
- Runtime reliability fixes affecting mesh behavior.
- Changes that cross cognition, state, voice, or transport boundaries.

Expected output sections:

1. Problem statement
2. Affected files and dependencies
3. Options (at least two)
4. Recommendation with rationale
5. Implementation plan (ordered, file-specific)
6. Risks and open questions

Important: this stage produces a plan only. Code changes should be executed by an implementation agent after plan approval.

---

## 🗺️ Roadmap: The Path to CVS-1.1

- [x] **Dynamic Identity Evolution**: State-driven personality system with NATS heartbeat.
- [x] **Structured Interruption Arbitration**: SenseVoice publishes speculative intent, Whisper validates, and the brain confirms stop/resume behavior.
- [x] **Streaming Voice Runtime**: VoiceAgent queues raw PCM chunks as they arrive for lower perceived first-audio latency.
- [x] **Phased Startup Mesh**: Zero-race condition graduation with automated health surveillance.
- [ ] **Expression Side-Channel**: Move affect, rate, and intensity to a structured channel so only timing markers remain in text.
- [ ] **Emotion-Matched Interjection**: Soft-pause logic for more human-like overlap and backchanneling.
- [ ] **M4 CoreML Integration**: Native NPU support for zero-GPU voice synthesis.

---

## 📜 License & Community

Distributed under the **MIT License**. See `LICENSE` for details.

**Designed for Perception. Built for Identity.**
