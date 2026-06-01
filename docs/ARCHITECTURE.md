# 🏗️ Architecture Documentation - CVS-3.5

> **Deep dive into the AI Friend platform architecture, design decisions, and the Cognitive Voice System (CVS-3.5)**

---

## Table of Contents

1. [System Overview](#system-overview)
2. [CVS-3.5 Architecture (Perceptual Mastery)](#cvs-20-hardened-architecture)
3. [Cognitive Layer (Identity & State)](#1-cognitive-layer-identity--state)
4. [Subconscious Engine (Tier-5 Autonomy)](#2-subconscious-engine-tier-5-autonomy)
5. [Visual Appraisal (Tier-4 Multimodal)](#3-visual-appraisal-tier-4-multimodal)
6. [Sovereign Memory Surfacing](#4-sovereign-memory-surfacing)
7. [Perceptual Intelligence (STT Agent)](#5-perceptual-intelligence-stt-agent)
8. [Signal Rendering (Voice Agent)](#6-signal-rendering-voice-agent)
9. [System Flow Diagram](#system-flow-diagram)

---

## System Overview

AI Friend is built on the **Sovereign Mesh Architecture**. It uses a decentralized ecosystem of specialized micro-agents coordinated via a high-performance **NATS JetStream** event bus. In the finalized **v6.0.0 (CVS-3.5 Rust Native Edition)**, the signal bus was expanded to include 9 core subjects covering system heartbeats, active memory recall, and identity synchronization.

In **CVS-3.5**, we have achieved **Identity Continuity**. The system is no longer a reactive "Think-Speak" pipeline; it is now a **State-Driven Identity Mesh** coached by a continuous NATS heartbeat. It anticipates context through memory surfacing and expresses emotion through deterministic temporal markers.

The architecture should be evaluated by conversational realism rather than only by model intelligence. A technically correct answer that arrives with unnatural timing, forgets recent emotional state, repeats memories mechanically, or fails to recover from a false interruption is considered a behavioral failure. Every layer exists to preserve the illusion of a continuous person: perception, state, memory, decision, and voice all contribute to that outcome.

---

## 🏗️ CVS-3.5 Hardened Architecture

### 🧠 1. Cognitive Layer (Identity & State)

The BrainAgent orchestrates a **State-Driven Identity** with a hardened relational foundation.

- **Neo4j State Persistence**: Mood, energy, trust, and attachment are persistent and evolve via mesh heartbeats.
- **Live State Safety**: Live emotional state is hydrated without TTL cache and graph cache is invalidated after writes, preventing recent mood/trust updates from being rewound by stale reads.
- **Relational Seeding (Prisma 7.7.0)**: On first-boot, the identity mesh hydrates the PostgreSQL relational store with the AI's "Seed Genome" (Personality & History), ensuring zero-drift identity across restarts.
- **Identity Heartbeat (`system.tick`)**: A 60s NATS pulse ensures the agent's internal state matures even when user interaction is idle.
- **Hybrid Identity Model**: Separates an **Immutable Core** (base tone, values) from **Adaptive Variables** (habits, relationship status).
- **Single Identity Owner**: Reflection and response generation share the same `IdentityManager`, so adaptive evolution affects the active personality without requiring restart.
- **Endocrine Modulation**: LLM generation parameters (temperature, top_p, frequency_penalty) are dynamically adjusted based on the agent's current PAD state (e.g., high cortisol/stress → lower temperature for more focused/rigid responses).

### 💭 2. Subconscious Engine (Tier-5 Autonomy)

Introduced the **Subconscious Agent** to manage background cognition during periods of inactivity.

- **Internal Monologue**: Generates proactive "thoughts" based on the current context, recent memories, and emotional state when the system is idle.
- **Cognitive Injection**: Subconscious thoughts are published to `chat.input` (source: `subconscious`), allowing the Brain Agent to process them as internal prompts without contaminating the external chat history.
- **Idle-State Proactivity**: Triggers reflection or proactive reaching out based on the psychological state (e.g., high "Attachment" + high "Energy" → reaching out to the user).

### 👁️ 3. Visual Appraisal (Tier-4 Multimodal)

Introduced the **Vision Agent** to provide spatial and visual grounding for the cognitive mesh.

- **Host-Native Bridge**: Screen and camera processing operate outside Docker constraints using a native Windows/macOS bridge to bypass container limitations.
- **Visual Appraisal**: The VisionAgent captures frames and queries local `moondream:latest` via Ollama. It publishes `vision.description` back to the BrainAgent for context-aware grounding without sending raw image blobs over the mesh.

### 📖 4. Sovereign Memory Surfacing & 4-Tier Hybrid Storage

CVS-3.5 Premium Edition structures its memory across a **4-Tier Hybrid Storage System** that balances ultra-fast cached access, relational episodic retention, and structured long-term reflection:

1.  **Tier 1: Dynamic Working Memory & Identity Cache**:
    *   *Identity cache*: Fast-access SQLite database managed via `IdentityCoreStore` which holds immutable core parameters.
    *   *Dynamic session cache*: Active dialogue turns, VAD parameters, and recent conversational history are kept in a Redis key-value cache (`WorkingMemoryStore`) for sub-millisecond dynamic session retrieval.
2.  **Tier 2: Relational Episodic Memory & Subconscious HSL Hybrid Archive**:
    *   Episodic memories are scored using **ACT-R base activation decay** ($A = \ln(\sum t_j^{-d})$) and emotional PAD congruence. To eliminate Python overhead, memory decay math is offloaded directly to database queries.
    *   *Subconscious pgvector Archive (`halfvec(768)`)*: As memories decay from active storage, they are pruned to `archived_memories`. To enable sub-millisecond similarity scans on this cold pool, PostgreSQL compiles vector embeddings using a quantized `halfvec(768)` type, indexed by a disk-backed `HNSW` using `halfvec_cosine_ops`.
    *   *HSL Hybrid Retrieval (Semantic + Lexical + Synonym)*: To bypass synonym-mismatch failures, subconscious lookup uses a true hybrid query combining HNSW semantic proximity with Porter-style root-lemma stem extraction (`_get_stem`) and a contextual thesaurus map (`SYNONYM_MAP`) executing ILIKE keyword lookups.
    *   *ACT-R Spreading Activation & Goal Buffer*: Maintains concepts across a 3-turn sliding window `GoalBuffer`. Subconscious cueing applies a mathematical spreading activation boost ($W_j \cdot S_{ji}$) to associated candidates. If the cosine similarity between consecutive user prompts drops below `0.15`, the Goal Buffer flushes instantly to model organic attention shifts.
    *   *SQL Dialect Abstraction*: The database engine integrates a dual-dialect routing layer (`sqlite_fallback.py`) which translates Postgres `pgvector` operators to SQLite fallback queries automatically when running in offline/local dev modes.
3.  **Tier 3: Semantic Recall Index (Qdrant Vector DB)**:
    *   The `SemanticRecallStore` manages a dense vector representation of knowledge points inside **Qdrant**, allowing fast semantic distance searches.
4.  **Tier 4: Subconscious Knowledge Graph (Neo4j)**:
    *   Long-term facts and associative graph relationships are managed in **Neo4j** (e.g., `User -[LIKES]-> Coffee`). The subconscious reflection agent executes idle sweeps to build associative paths.

- **O(1) L1 Memory Activation Cache**: An ultra-fast local dictionary cache intercepts hot memory hits, bypassing vector database calls when memory is requested within short temporal windows (<15s TTL).

### ⏱️ 5. Perceptual Intelligence (STT Agent)

Interruption is now handled as a **Temporal Intent Problem** powered by binary PCM transport.

- **Dual-STT Pipeline**: Uses Whisper for deep context and `sherpa-onnx` (SenseVoice) for low-latency temporal intent.
- **Paralinguistic Perception**: Non-speech events (laughter, coughs) are captured and added to PAD metadata to influence emotional trajectories.
- **Speculative Intent Object**: SenseVoice publishes a structured hypothesis with intent name, keywords, confidence, text, timestamp, and utterance id.
- **Whisper Validation**: Whisper final transcript confirms or rejects the speculative stop. Rejected false positives publish `audio.resume`; confirmed commands publish final `audio.stop`.
- **Ambient Noise Floor Telemetry**: In between speech chunks, the STT Agent calculates the baseline RMS energy of silent frames and publishes it to `ambient.noise.telemetry` at 500ms intervals.

### 🔊 6. Signal Rendering (Voice Agent)

A persistent synthesis runtime with direct binary transport, accelerated local synthesis, and expressive behavior.

- **Rust Native Audio & Hybrid TTS Core**: The FFI layer handles pure PCM payloads. The Voice Agent dynamically coordinates speech synthesis using an ONNX-based **LocalTtsEngine** with fallback capability.
- **Dual-Model Fallback Resolution**: If custom voice models are present under `models/custom/`, they are loaded. Otherwise, the engine seamlessly falls back to a base Piper VITS model (`vits-piper-en_US-amy-low`) under `models/base/`, or routes to the HTTP REST endpoint if local models are unprovisioned.
- **Hardware-Accelerated Execution Providers**: Initializes ONNX Runtime sessions by dynamically binding to the most performant execution provider (TensorRT or CUDA on NVIDIA hardware, CoreML on Apple Silicon, or optimized multi-threaded CPU execution).
- **Quality-Prioritized Look-Ahead Pacing**: The `BrainAgent` groups generated text into chunks of **7 words** (or splits on clause punctuation), allowing the VITS acoustic model to capture semantic context and produce natural, expressive prosody contours.
- **Speculative Filler Interruption Masking**: Under quality-prioritized segmentation, to hide compilation/synthesis latency, the system utilizes a **250ms speculative pause filler threshold** (`VOICE_FILLER_THRESHOLD`). If the first audio chunk is not generated within 250ms, immediate vocal fillers (e.g. *"Hmm"*, *"Accha"*) are dispatched to maintain turn flow.
- **Direct Binary Bus**: Publishes raw PCM bytes via `orjson` serialization at 80,000 OPS.
- **Expressive Temporal Layer**: Interprets `<pause=300ms>` and `<hesitate>` tags by injecting silent PCM buffers directly into the 32kHz stream.
- **Adaptive Gain Control (Volume Mirroring)**: The Voice Agent subscribes to `ambient.noise.telemetry` and tracks a moving average of the background noise. It dynamically scales the amplitude of outgoing PCM samples.
- **Dialogue Truncation**: When playback progress is reported on `audio.playback.progress`, the Brain Agent tracks spoken length and truncates database logs on interruption.

---

## 📊 System Flow Diagram

```mermaid
graph TB
    subgraph Client ["User Client"]
        MIC["Audio Capture"]
        PCM_PLAYER["PCM Stream Player"]
    end

    subgraph CVS_Mesh ["CVS-3.5 - Identity Mesh"]
        STT["STT Agent<br/>Temporal Intent"]
        VISION["Vision Agent<br/>Visual Appraisal"]

        subgraph Brain_Core ["State & Identity"]
            SYSTEM_TICK["System Agent<br/>Mesh Heartbeat"]
            SUBCO["Subconscious Agent<br/>Idle Thoughts"]
            SURFACING["Surfacing Agent<br/>Active Memory"]
            DECISION["Cognitive Service<br/>State-Driven BDI"]
        end

        subgraph Voice_Core ["Signal Rendering"]
            VOICE_CONTROLLER["Voice Agent<br/>Temporal Injection"]
            AUDIO_ENGINE["Audio Engine<br/>Rust PyO3 Transport"]
        end
    end

    MIC -->|audio.captured| STT
    STT -->|audio.perception| DECISION
    STT -->|audio.stop speculative| VOICE_CONTROLLER
    STT -->|ambient.noise.telemetry| VOICE_CONTROLLER
    STT -->|chat.input| DECISION
    VISION -->|vision.description| DECISION
    SYSTEM_TICK -->|system.tick| DECISION
    SUBCO -->|chat.input| DECISION
    SURFACING -->|memory.surfaced| DECISION
    DECISION -->|chat.output| VOICE_CONTROLLER
    DECISION -->|audio.resume / final audio.stop| VOICE_CONTROLLER
    VOICE_CONTROLLER --> AUDIO_ENGINE
    AUDIO_ENGINE -->|audio.stream (PCM)| PCM_PLAYER
    PCM_PLAYER -->|audio.playback.progress| DECISION
```

## 🛡️ Sovereign Mesh Hardening & High Availability

To ensure resilient operations in production and distributed environments, the core event mesh incorporates the following stability enhancements:

### 1. Zero-Crash NATS IPC Auto-Reconnection
All dynamic micro-agents subclassing the `BaseAgent` connection lifecycle are hardened with infinite auto-reconnection settings (`max_reconnect_attempts=-1`) and a 2.0-second delay sleep interval (`reconnect_time_wait=2.0`). This guarantees that if the NATS event broker goes down temporarily during heavy load or container reboots, active Python agents will seamlessly suspend operations and restore state/subscriptions automatically upon recovery, without crash-looping Python threads.

### 2. Multi-Process Cache Synchronization (`cache.sync`)
CVS-3.5 Premium incorporates cross-process cache invalidation on the `cache.sync` channel. When changes are written to the static identity parameters (`IdentityCoreStore`), a broadcast payload is dispatched to NATS:
```json
{
  "store": "identity_core",
  "action": "invalidate"
}
```
All connected ASGI processes and agent runners handle this NATS message and instantly reload database values into their memory cache (`load_into_cache()`), eliminating state-drift across multiple Python-worker processes.

---

## 🔁 Real-Time Turn-Taking Flow

The interruption loop is deliberately two-phase:

1. **Fast perception**: SenseVoice sees a possible stop/wait/quiet command and publishes `audio.stop` with `speculative=true`.
2. **Voice behavior**: VoiceAgent enters a reversible `SPECULATIVE_PAUSE` and holds output rather than clearing all buffers immediately.
3. **Backbone validation**: Whisper produces the final transcript and BrainAgent checks whether the stop keyword was actually a command or just conversational context.
4. **Resolution**: False positives publish `audio.resume`; confirmed commands publish final `audio.stop` with `speculative=false`.

This is closer to human overlap behavior: people often pause briefly when another person starts speaking, then continue if the interjection was not meant to stop them.

---

## 🧭 Agent Handoff Context

Future agents should read [../.agents/CONTEXT.md](../.agents/CONTEXT.md) before changing the architecture. It records durable project intent, recent runtime changes, verification commands, and next recommended work. Update it after architecture, behavior, or test changes so context survives beyond any single conversation window.

## ⚙️ Resource Matrix (CVS-3.5)

| Agent | Context | CPU (Min) | RAM (Target) | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Brain Agent** | Cognitive Core | 1.0 Cores | 2.0 GiB | Increased for Segmenter heuristics. |
| **STT Agent** | Whisper Core | 2.0 Cores | 2.0 GiB | Local realtime inference. |
| **Voice Agent** | CVS Runtime | 1.5 Cores | 4.0 GiB | Includes Normalizer & Cache Clustering. |
| **Vision Agent** | Vision Mesh | 1.0 Cores | 1.0 GiB | Multi-sourceframe sync. |

---

## 🍏 Latest iMac Optimization Audit (Backend + Docker + Architecture)

### Verdict

The current system design is **architecturally strong** for a latest iMac (decoupled agents, asynchronous NATS mesh, tiered backend images), but it is **not fully optimized out-of-the-box** for smooth Mac-first operation.

### What is already optimized well

- **Decoupled mesh topology** keeps CPU-bound and I/O-heavy workloads isolated by agent.
- **Tiered backend Docker build** (`slim` and `full`) avoids shipping heavy AI dependencies where not required.
- **Non-root containers + healthchecks** improve runtime safety and recovery behavior.

### Gaps for iMac smoothness

- Heavy voice/STT services are still CPU-expensive on macOS and should be started only when needed for real-time audio sessions.

### Implemented hardening for macOS stability

1. Infra image tags were pinned (via `.env` variables) to remove `latest` drift across environments.
2. Added `docker-compose.light.yml` for lightweight runs (heavy voice/STT services disabled by default).
3. Added `docker-compose.heavy.yml` for heavier runs (CPU-safe defaults for Ollama/STT, with CUDA-only GPT-SoVITS excluded).

### Platform-Agnostic run profiles

```bash
# Light profile (faster boot, lower RAM/CPU pressure)
docker compose \
  -f docker-compose.infra.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.light.yml \
  up -d

# Heavy profile (STT-enabled; CUDA-only voice services remain excluded)
docker compose \
  -f docker-compose.infra.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.heavy.yml \
  up -d --build
```

---

**For implementation details, see:**

- [LATENCY_IMPROVEMENT.md](../_archive/docs/LATENCY_IMPROVEMENT.md) - Timing deep-dive
- [VOICE_CLONING.md](../_archive/docs/VOICE_CLONING.md) - Voice identity guide
- [DEPLOYMENT.md](../_archive/docs/DEPLOYMENT.md) - Infrastructure setup
