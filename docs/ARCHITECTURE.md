# 🏗️ Architecture Documentation

> **Deep dive into the AI Friend platform architecture and design decisions**

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Cognitive Layer (Identity & State)](#1-cognitive-layer-identity--state)
3. [Subconscious Engine](#2-subconscious-engine)
4. [Visual Appraisal (Multimodal)](#3-visual-appraisal-tier-4-multimodal)
5. [Memory Surfacing](#4-sovereign-memory-surfacing)
6. [Perceptual Intelligence (STT Agent)](#5-perceptual-intelligence-stt-agent)
7. [Signal Rendering (Voice Agent)](#6-signal-rendering-voice-agent)
8. [System Flow Diagram](#system-flow-diagram)

---

## System Overview

AI Friend is built on a decentralized ecosystem of specialized micro-agents coordinated via a **NATS JetStream** event bus, not function calls — see `CLAUDE.md`'s "The mesh" section for the ground-truth summary future agents should read first.

The system is not a reactive "Think-Speak" pipeline; it is a **state-driven identity mesh** coordinated by a continuous NATS heartbeat (`system.tick`). It anticipates context through memory surfacing and expresses emotion through deterministic temporal markers.

The architecture should be evaluated by conversational realism rather than only by model intelligence. A technically correct answer that arrives with unnatural timing, forgets recent emotional state, repeats memories mechanically, or fails to recover from a false interruption is considered a behavioral failure. Every layer exists to preserve the illusion of a continuous person: perception, state, memory, decision, and voice all contribute to that outcome.

---

## 🏗️ Architecture

### 🧠 1. Cognitive Layer (Identity & State)

The BrainAgent orchestrates a state-driven identity with a hardened relational foundation.

- **Neo4j State Persistence**: Mood, energy, trust, and attachment are persistent and evolve via mesh heartbeats.
- **Live State Safety**: Live emotional state is hydrated without TTL cache and graph cache is invalidated after writes, preventing recent mood/trust updates from being rewound by stale reads.
- **Relational Seeding (Prisma)**: On first-boot, the identity mesh hydrates the PostgreSQL relational store with the AI's "Seed Genome" (Personality & History), ensuring zero-drift identity across restarts. `db/schema.sql` is the schema of record — Prisma covers only 3 of the 9 tables.
- **Identity Heartbeat (`system.tick`)**: A 60s NATS pulse ensures the agent's internal state matures even when user interaction is idle.
- **Hybrid Identity Model**: Separates an **Immutable Core** (base tone, values) from **Adaptive Variables** (habits, relationship status), enforced at the schema level, not by convention.
- **Single Identity Owner**: Reflection and response generation share the same `IdentityManager`, so adaptive evolution affects the active personality without requiring restart.
- **Endocrine Modulation**: LLM generation parameters (temperature, top_p, num_predict) are dynamically adjusted based on the agent's current PAD state and tonic+phasic cortisol/dopamine (e.g., high cortisol/stress → lower temperature for more focused/rigid responses). See `CLAUDE.md`'s "Endocrine layer" section for the tonic/phasic distinction — it's the part worth understanding before touching this code.

### 💭 2. Subconscious Engine

Background cognition during periods of inactivity, owned by the **Subconscious Agent**.

- **Internal Monologue**: Generates proactive "thoughts" based on the current context, recent memories, and emotional state when the system is idle.
- **Cognitive Injection**: Subconscious thoughts are published to `chat.input` (source: `subconscious`), allowing the Brain Agent to process them as internal prompts without contaminating the external chat history.
- **Idle-State Proactivity**: Triggers reflection or proactive reaching out based on the psychological state (e.g., high "Attachment" + high "Energy" → reaching out to the user). If nobody is connected when the thought fires, it's queued (`state/proactive_queue.py`, capped at 5) and replayed on the next real reconnect (`state.presence` edge) rather than discarded.

### 👁️ 3. Visual Appraisal (Multimodal)

The **Vision Agent** provides spatial and visual grounding for the cognitive mesh — present in-tree, commented out in `docker-compose.prod.yml` by default; treat as opt-in/experimental.

- **Visual Appraisal**: The VisionAgent captures frames and queries local `moondream:latest` via Ollama. It publishes `vision.description` back to the BrainAgent for context-aware grounding without sending raw image blobs over the mesh.
- **Somatic Homeostasis**: `SomaticAppraiser` (`app/cognitive/somatic.py`) matches that description against comfort objects the agent has *learned* — facts `learning.py` tagged `somatic` and wrote to Neo4j — and lifts valence/arousal through `StateService.apply_somatic_perception`. Dopamine is a derived property (`max(0, V) × Ar`), so it rises by construction rather than being assigned. This is the visual mirror of the acoustic path, where SenseVoice emotion feeds `apply_sensory_perception`. Nothing is hardcoded: with no learned somatic facts the agent recognises nothing and no spike fires.
- **Capture runs on the host, not in a container.** This is a platform constraint, verified rather than assumed: inside a Linux container there is no `/dev/video*`, no `/tmp/.X11-unix`, `DISPLAY` is unset, and `mss` fails with `Library libxcb.so not found`. On a Windows or macOS host the container runs in a Linux VM with no route to the host display or USB webcam, so no configuration fixes it — run `python -m app.vision.agent` on the host. On a **Linux** host the containerised path does work with `--device=/dev/video0` and/or an X11 socket mount; the `vision` compose profile ships both, commented out. The agent runs a capture preflight at startup and says loudly when it is blind, and its healthcheck probes a sentinel touched on each successful capture rather than process liveness.

### 📖 4. Memory Surfacing & Hybrid Storage

`state/memory_store.py` structures memory across a hybrid storage system balancing fast cached access, relational episodic retention, and structured long-term reflection — the largest and riskiest file in the codebase (`CLAUDE.md`); read that file's own module docstring before extending it.

1.  **Tier 1: Dynamic Working Memory & Identity Cache**:
    *   *Identity cache*: Fast-access SQLite database managed via `IdentityCoreStore` which holds immutable core parameters.
    *   *Dynamic session cache*: Active dialogue turns, VAD parameters, and recent conversational history are kept in a Redis key-value cache (`WorkingMemoryStore`) for low-latency dynamic session retrieval.
2.  **Tier 2: Relational Episodic Memory & Archive**:
    *   Episodic memories are scored using **ACT-R base activation decay** ($A = \ln(\sum t_j^{-d})$) and emotional PAD congruence. Memory decay math is largely offloaded to database queries to avoid Python-side iteration overhead.
    *   *pgvector Archive (`halfvec(768)`)*: As memories decay from active storage, they are pruned to `archived_memories`. PostgreSQL compiles vector embeddings using a quantized `halfvec(768)` type, indexed by a disk-backed `HNSW` using `halfvec_cosine_ops`.
    *   *Hybrid Retrieval (Semantic + Lexical + Learned Priming)*: To reduce synonym-mismatch failures, lookup uses a hybrid query combining HNSW semantic proximity with Porter-style root-lemma stem extraction (`_get_stem`) and **learned lexical priming** executing ILIKE keyword lookups. Cue expansion does not read a hardcoded thesaurus; it draws on the `MentalLexicon` (`lexicon_store.py`) — a vocabulary that boots with a small generic innate seed and then acquires words and distributional co-occurrence associations from lived conversation, persisted in the `vocabulary` / `lexical_associations` tables.
    *   *ACT-R Spreading Activation & Goal Buffer*: Maintains concepts across a 3-turn sliding window `GoalBuffer`. Cueing applies a mathematical spreading activation boost ($W_j \cdot S_{ji}$) to associated candidates. If the cosine similarity between consecutive user prompts drops below `0.15`, the Goal Buffer flushes instantly to model organic attention shifts.
    *   *SQL Dialect Abstraction*: `MemoryStore.is_sqlite` (a read-only property) routes to a dual-dialect layer (`sqlite_fallback.py`) which translates Postgres `pgvector` operators to SQLite fallback queries automatically when running in offline/local dev modes.
3.  **Tier 3: Semantic Recall Index (Qdrant Vector DB)**:
    *   The `SemanticRecallStore` manages a dense vector representation of knowledge points inside **Qdrant**, allowing fast semantic distance searches.
4.  **Tier 4: Knowledge Graph (Neo4j)**:
    *   Long-term facts and associative graph relationships are managed in **Neo4j** (e.g., `User -[LIKES]-> Coffee`). The subconscious reflection agent executes idle sweeps to build associative paths.

- **L1 Memory Activation Cache**: A local dictionary cache intercepts hot memory hits, bypassing vector database calls when memory is requested within short temporal windows (<15s TTL).

### ⏱️ 5. Perceptual Intelligence (STT Agent)

Interruption is handled as a **temporal intent problem** powered by binary PCM transport (Rust, not Python — the Python STT predecessor is dead code in `_archive/`).

- **Dual-STT Pipeline**: Uses Whisper for deep context and `sherpa-onnx` (SenseVoice) for low-latency temporal intent.
- **Paralinguistic Perception**: Non-speech events (laughter, coughs) are captured and added to PAD metadata to influence emotional trajectories.
- **Speculative Intent Object**: SenseVoice publishes a structured hypothesis with intent name, keywords, confidence, text, timestamp, and utterance id.
- **Whisper Validation**: Whisper final transcript confirms or rejects the speculative stop. Rejected false positives publish `audio.resume`; confirmed commands publish final `audio.stop`.
- **Ambient Noise Floor Telemetry**: In between speech chunks, the STT Agent calculates the baseline RMS energy of silent frames and publishes it to `ambient.noise.telemetry` at 500ms intervals.

### 🔊 6. Signal Rendering (Voice Agent)

A persistent synthesis runtime with direct binary transport and expressive behavior, rendered through a single cloned-voice engine — no fallback to a different voice.

- **Rust Native Audio, Single-Engine Synthesis**: The FFI layer handles pure PCM payloads. The Voice Agent renders every utterance through one self-hosted GPT-SoVITS endpoint. A local ONNX `LocalTtsEngine` with dual-model fallback existed through 2026-07 and was removed: its fallback path degraded to a *different, uncloned* voice on failure, which is worse than silence under a no-fallback requirement — see `.agents/CONTEXT.md` for the removal entry.
- **Emotion-Selected Reference Clips**: Delivery register (calm/warm/concerned/excited/neutral) is chosen per turn from the agent's own PAD affect state (`select_emotion_bucket`) and determines which GPT-SoVITS reference clip carries the request — steering delivery, not identity, which stays permanently baked into the server's loaded weights (`CUSTOM_GPT_PATH`/`CUSTOM_SOVITS_PATH`).
- **Same-Engine Resilience**: A circuit breaker with bounded retry wraps every synthesis call, and a background readiness probe independently proves the engine renders real audio (not just answers HTTP) so an outage is caught even during silence. A confirmed failure plays a same-voice fallback vocalization rather than dropping the turn or switching voices.
- **Quality-Prioritized Look-Ahead Pacing**: The `BrainAgent` groups generated text into chunks of **7 words** (or splits on clause punctuation), allowing the VITS acoustic model to capture semantic context and produce natural, expressive prosody contours.
- **Speculative Filler Interruption Masking**: To hide compilation/synthesis latency, the system uses a **400ms speculative pause filler threshold** (`VOICE_FILLER_THRESHOLD`), measured from when generation actually starts (after conversational pacing, not before it). If the first audio chunk is not generated within 400ms, a single vocal filler (e.g. *"hmm"*, *"let's see"*) is dispatched to maintain turn flow — suppressed if one already fired within `VOICE_FILLER_MIN_INTERVAL_SECONDS` (1.5s) or if a previous turn's audio is still backed up past `VOICE_FILLER_MAX_PLAYBACK_BACKLOG` (4 queued frames).
- **Binary Bus**: Publishes raw PCM bytes rather than base64-in-JSON, avoiding text-encoding overhead on the hot audio path — see `API_SPEC.md`'s note on why this doc doesn't cite a specific ops/sec figure.
- **Expressive Temporal Layer**: Interprets `<pause=300ms>` and `<hesitate>` tags by injecting silent PCM buffers directly into the 32kHz stream.
- **Adaptive Gain Control (Volume Mirroring)**: The Voice Agent subscribes to `ambient.noise.telemetry` and tracks a moving average of the background noise. It dynamically scales the amplitude of outgoing PCM samples.
- **Dialogue Truncation**: When playback progress is reported on `audio.playback.progress`, the Brain Agent tracks spoken length and truncates database logs on interruption.
- **Visemes**: `audio.playback.visemes` is forwarded by `transport_agent` onto the LiveKit room's data channel; the frontend's `AssistantCircle` aura pulses with it. See `.agents/CONTEXT.md`'s Phase 5.3 entry for the one open gap — `local_sfu` currently rejects WebRTC joins with a 404 in this environment, so this path is unverified live in a browser.

---

## 📊 System Flow Diagram

```mermaid
graph TB
    subgraph Client ["User Client"]
        MIC["Audio Capture"]
        PCM_PLAYER["PCM Stream Player"]
    end

    subgraph Mesh ["The Mesh"]
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

## 🛡️ Mesh Hardening & High Availability

### 1. Zero-Crash NATS IPC Auto-Reconnection
All dynamic micro-agents subclassing the `BaseAgent` connection lifecycle are hardened with infinite auto-reconnection settings (`max_reconnect_attempts=-1`) and a 2.0-second delay sleep interval (`reconnect_time_wait=2.0`). This guarantees that if the NATS event broker goes down temporarily during heavy load or container reboots, active Python agents will seamlessly suspend operations and restore state/subscriptions automatically upon recovery, without crash-looping Python threads.

### 2. Multi-Process Cache Synchronization (`cache.sync`)
Cross-process cache invalidation on the `cache.sync` channel. When changes are written to the static identity parameters (`IdentityCoreStore`), a broadcast payload is dispatched to NATS:
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

## ⚙️ Resource Matrix (target, not yet individually measured)

The per-agent breakdown below is a design target, not a live measurement — the one real measurement that exists (`backend/tools/measure/out/m17_pressure_scenarios.json`, see `.agents/CONTEXT.md`'s Phase 6.2 entry) measured aggregate RAM across composite scenarios on one 17.18GB host, not per-agent CPU/RAM in isolation. Treat these numbers as targets until a per-agent measurement exists.

| Agent | Context | CPU (Min) | RAM (Target) | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Brain Agent** | Cognitive Core | 1.0 Cores | 2.0 GiB | Increased for Segmenter heuristics. |
| **STT Agent** | Whisper Core | 2.0 Cores | 2.0 GiB | Local realtime inference. |
| **Voice Agent** | Runtime | 1.5 Cores | 4.0 GiB | Includes Normalizer & Cache Clustering. |
| **Vision Agent** | Vision Mesh | 1.0 Cores | 1.0 GiB | Multi-source frame sync. |

---

## 🍏 macOS Optimization Notes

### What is already optimized well

- **Decoupled mesh topology** keeps CPU-bound and I/O-heavy workloads isolated by agent.
- **Tiered backend Docker build** (`slim` and `full`) avoids shipping heavy AI dependencies where not required.
- **Non-root containers + healthchecks** improve runtime safety and recovery behavior.

### Gaps for smoothness on lower-RAM Macs

- Heavy voice/STT services are still CPU-expensive on macOS and should be started only when needed for real-time audio sessions.

### Run profiles

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
