# 🎙️ AI Friend: The Sovereign Cognitive Mesh (v3.1)

**A High-Performance, Privacy-First Multimodal AI Identity Simulator.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/license/MIT)
[![Latency: Sub-300ms](https://img.shields.io/badge/Latency-%3C300ms-green.svg)](#performance-slos)
[![Architecture: Parallel BDI](https://img.shields.io/badge/Architecture-Parallel%20BDI-orange.svg)](#architecture)

---

## 🌟 Overview

**AI Friend** is a sophisticated, decentralized AI platform engineered for **ultra-low latency** voice interaction and **autonomous persona evolution**. Built on the **Sovereign Mesh** pattern, it replaces monolithic backends with a real-time ecosystem of specialized micro-agents coordinated via the **NATS JetStream** event bus.

The system is designed for **Sovereign Privacy**, ensuring all reasoning, memory, and voice synthesis happen 100% locally on user-controlled hardware.

---

## 🏗️ Architecture: v3.1 Parallel Sovereign Mesh

The v3.1 architecture introduces the **Parallel Cognitive Loop**, which eliminates sequential bottlenecks by concurrently hydrating three core cognitive tiers: **Perception**, **State**, and **Memory**.

### 🚀 Key Innovations:
- **Parallel BDI Loop**: Perception, State Hydration, and Memory Retrieval fire in parallel via `asyncio.gather`, slashing cognitive overhead by **~73%**.
- **Behavior Tree (BT) Engine**: Uses a modular Selector/Sequence BT logic for robust, goal-oriented decision making.
- **Dual-Agent RAG**: A background "Slow Thinker" pre-fetches potential context into a fast in-memory cache for the "Fast Talker."
- **Zero-Header PCM**: Migrated to raw 16-bit PCM streaming (22.05kHz) to eliminate header parsing latency.

---

## ⚡ Performance & Latency SLOs

To achieve seamless human-like interaction, we enforce strict **Service Level Objectives (SLOs)** for every hop in the mesh.

### ⏱️ Stage Budget (p95 Targets)
| Pipeline Stage | Target Latency | Optimization Strategy |
| :--- | :--- | :--- |
| **STT (Inference)** | <50ms | Whisper V3 Turbo / Silero VAD |
| **RAG Retrieval** | <10ms | HNSW / PGVector Semantic Cache |
| **Cognitive Loop** | <50ms | Parallel BDI / BT Micro-Scaffold |
| **LLM Inference** | <100ms | 4-bit Quantization / RTX 4090 |
| **TTS Synthesis** | <60ms | PCM Streaming / Dia2-Turbo |
| **Total E2E** | **<270ms** | **v3.1 Sovereign Mesh Standard** |

---

## 🧠 Cognitive Engine: The BDI Framework

AI Friend operates on a **Belief-Desire-Intention (BDI)** model, ensuring that every response is grounded in persistent memory and persona goals.

### 1. Intent & Goal Dynamics
| Intent | Desires (Goals) | Latency Path |
| :--- | :--- | :--- |
| **CHAT** | `ENGAGE`, `COMFORT`, `TEASE` | **Smart Path** (7B Model) |
| **REMEMBER**| `INFORM`, `PROTECT` | **Fast Path** (1B Model) |
| **REFLECT** | `SELF_IMPROVE` | **Background Cycle** |
| **COMMAND** | `ACTIVATE_TOOLS` | **Fast Path** (1B Model) |

### 2. Memory Governance & Decay
Memory is prioritized using a recency-weighted decay formula to prevent "Context Bloat":
```math
Score = SemanticSimilarity * (Importance * exp(-\lambda * \Delta t))
```
- **Instant Memory**: Context window in local RAM.
- **Semantic Memory**: PGVector retrieval for factual grounding.
- **Relational Memory**: Neo4j Graph for identity-focused entity mapping.

### 3. Identity Evolution (Mood Update Rules)
The internal emotional state evolves dynamically based on interaction valence:
```math
Mood_{new} = Mood_{old} * exp(-\alpha\Delta t) + EventValence * (1-exp(-\alpha\Delta t))
```

---

## ⚙️ Advanced Configuration (Env Var Dictionary)

| Variable | Default Value | Technical Purpose |
| :--- | :--- | :--- |
| `NATS_URL` | `nats://nats:4222` | Internal event bus address for agent choreography. |
| `OLLAMA_URL` | `http://ollama:11434`| Reasoning LLM endpoint (Use `host.docker.internal` for host). |
| `NEO4J_URI` | `bolt://localhost:7687`| Relational Graph database connection string. |
| `STT_DEVICE` | `cpu` | Acceleration device for Whisper (`cpu` or `cuda`). |
| `STT_MODEL_SIZE`| `small` | Transcription model weight (`tiny` to `large`). |
| `SAMPLE_RATE` | `16000` | Native audio capture rate for transcription stability. |

---

## 🛠️ Hardware Optimization Profiles (RTX 4090 / M4 Native)

| Profile | Quantization | Model Split | Throughput |
| :--- | :--- | :--- | :--- |
| **Low-Spec** | 4-bit (GGUF) | 1B (Fast) + 1B (Smart) | ~140 tok/s |
| **Balanced** | 4-bit (AWQ) | 1B (Fast) + 7B (Smart) | ~90 tok/s |
| **Extreme** | 8-bit (FP8) | 3B (Fast) + 14B (Smart)| ~60 tok/s |

---

## ⚙️ Installation & Developer Guide

### Method 1: Docker Compose (Dual-Stack)
```bash
# Start Persistence Layer (NATS, Neo4j, Ollama)
docker compose -f docker-compose.infra.yml up -d

# Start Cognitive Mesh (Brain, Voice, Transport)
docker compose -f docker-compose.prod.yml up -d --build
```

### Method 2: Manual Developer Setup
**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 🖥️ Developer Tooling & Mesh Debugging

### NATS CLI Monitoring
Monitor the pulse of the mesh in real-time:
```bash
nats sub "chat.input"   # Watch transcriptions
nats sub "chat.output"  # Watch brain thoughts
nats sub "audio.stream" # Watch synthesis buffers
```

### Relational Mapping (Neo4j)
Visualize the friendship graph at `http://localhost:7474`.
```cypher
MATCH (p:Persona)-[r:EXPERIENCED]->(e:Episode) RETURN p,r,e LIMIT 25;
```

---

## 🖥️ Troubleshooting & Recovery

| Issue | Root Cause | Resolution |
| :--- | :--- | :--- |
| **SFU Timeout** | LiveKit signal delay | Check `LIVEKIT_URL` and ensures ports 7880/7881 are open. |
| **Brain Stutter** | LLM Context Bloat | Run `python scripts/reset_db.py` to clear short-term memory. |
| **Audio Resampling**| `soxr` CPU Spike | Reduce `SAMPLE_RATE` in Ear Agent or uses GPU offloading. |
| **Microphone blocked**| Browser Policy | Ensure **HTTPS** or `localhost` access for Secure Context. |

---

## 📂 Project Structure

```text
AI_Friend/
├── backend/app/
│   ├── agents/          # Decentralized Micro-Agents (Ear, STT, Brain, Voice)
│   ├── cognitive/       # Behavior Trees, State Dynamics, & Parallel Loop
│   ├── knowledge/       # Neo4j GraphRAG & Triple Extraction
│   ├── llm/             # Hybrid Routing & Multi-Tiered Clients
│   └── tts/             # PCM Synthesis & SoVITS Integration
├── scripts/             # Stress-testing, Benchmarking, & DB Reset
├── docs/                # Technical Whitepapers & Latency SLOs
└── docker-compose.yml   # Multi-Agent Stack Orchestration
```

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

**Designed for Latency. Built for Identity.**
