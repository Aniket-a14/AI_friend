# Agent Context Ledger

This file is the persistent handoff note for agents working on this repository.
Read it before making architecture or behavior changes, and update it after every
meaningful change.

## Update Protocol

After an agent changes code, docs, tests, architecture, prompts, or runtime
behavior, append or update the relevant sections below.

Each update should include:

- Date and agent/session summary.
- Files changed.
- Behavior changed and why.
- Tests or verification run.
- Remaining risks or next recommended work.

Keep this file concise. It should preserve project intent and decision history,
not duplicate full diffs.

## System Intent

This project is a Cognitive Voice System (CVS), not a generic chatbot.

The target experience is a persistent human-like conversational identity with:

- Consistent identity over long sessions.
- Emotional continuity across turns and idle time.
- Natural timing, pauses, hesitation, pacing, and interruption behavior.
- Memory that surfaces organically rather than as rigid database recall.
- Local-first execution with modular agents connected through the NATS mesh.
- Future compatibility with robotics, without sacrificing current voice realism.

Core design principles:

- Perception-driven, not request-response.
- State-first, not prompt-first.
- Behavior emerges from internal state, identity, memory, and timing.
- Latency is measured by perceived conversational flow, especially first-audio
  response and interruption recovery.
- Components should stay replaceable and hardware-agnostic.

## Architecture Snapshot

Main modular layers (Refactored 2026-04-19):

- **Sensory (STT) Layer (`app/stt/`)**: Houses perception engines (Whisper, SenseVoice) and the `STTAgent`. Decoupled from core logic via structured hypotheses.
- **Cognitive Layer (`app/cognitive/`)**: BDI orchestrator (`CognitiveService`), identity management, and behavioral reflection. Injects State services via package facade.
- **State Layer (`app/state/`)**: The "Shared Kernel." Houses persistent mood/energy dynamics (`AgentState`), vector memory (`MemoryStore`), conversation history, and Neo4j graph state.
- **Voice Layer (`app/voice/`)**: Signal rendering engine. Houses `VoiceAgent`, SoVITS runtime, and extracted signal helpers (`AudioNormalizer`, `AudioCache`).
- **Mesh**: NATS JetStream subjects provide the only cross-layer integration point, ensuring a hardware-agnostic and decoupled runtime.

## Recent Review Findings

The recent code review identified seven realism/continuity risks:

- State hydration used cached Neo4j reads and could rewind fresh mood/trust.
- Speculative pauses could not be rejected because fast STT did not publish
  structured intent to cognition.
- Reflection mutated a separate `IdentityManager` from the one used for replies.
- `BrainAgent.start()` could open two NATS connections by subscribing before
  explicit connection.
- `VoiceAgent` buffered full SoVITS output before playback, increasing perceived
  latency.
- Emotion XML/control wrappers could leak into spoken TTS text.
- Memory surfacing could repeatedly surface and refresh the same memory.

## 2026-04-19 CVS Runtime Fixes

Implemented fixes for the seven review findings.

Changed files:

- `backend/app/agents/brain_agent.py`
- `backend/app/agents/stt_agent.py`
- `backend/app/agents/surfacing_agent.py`
- `backend/app/agents/voice_agent.py`
- `backend/app/cognitive/action.py`
- `backend/app/cognitive/core.py`
- `backend/app/cognitive/identity.py`
- `backend/app/cognitive/learning.py`
- `backend/app/cognitive/state.py`
- `backend/app/knowledge/graph_db.py`
- `backend/app/memory_store.py`
- `backend/tests/test_regressions.py`

Behavior changes:

- `StateService.hydrate_state()` no longer uses cached graph reads for live agent
  state.
- `StateService.persist_state()` invalidates graph cache after writes.
- `GraphDB` exposes `invalidate_cache()` for stateful services.
- STT publishes structured speculative interruption hypotheses containing intent
  name, keywords, confidence, text, timestamp, and utterance ID.
- `CognitiveService` stores speculative intent, rejects false positives with
  `audio.resume`, confirms real stop commands with final `audio.stop`, and skips
  unnecessary per-turn state rehydration.
- `CognitiveService` and `ReflectionService` share one `IdentityManager`, so
  persona evolution affects active replies without restart.
- `BrainAgent` connects before cognitive subscriptions, avoiding split NATS
  connections.
- Brain segmentation no longer sleeps per word. It flushes based on semantic
  boundaries and a short adaptive formation window.
- `VoiceAgent` queues SoVITS PCM chunks as they arrive instead of waiting for
  full synthesis completion.
- `ActionService` strips legacy `<emotion ...>` wrappers while preserving
  `<pause=...>` and `<hesitate>` timing markers.
- Identity prompting now tells the model not to emit XML/emotion wrappers.
- Memory surfacing adds novelty suppression and disables passive recall refresh
  for surfaced memories.

Verification:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Latest result:

- `48 passed`
- One non-blocking `.pytest_cache` permission warning remains.

## Current Test Environment Notes

Use the project-local backend virtual environment. The global Anaconda Python
environment could not import `nats` or activate `pytest-asyncio` reliably.

Preferred command:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## Next Recommended Work

- Run a real voice session and measure perceived first-audio latency, speculative
  pause duration, false-positive resume latency, and memory surfacing frequency.
- Add structured affect/expression side-channel metadata so timing, affect,
  rate, and intensity do not depend on text markers.
- Add live session identity hydration from the durable database layer so JSON
  persona files are not the only active identity source.
- Add observability around `audio.stop`, `audio.resume`, `chat.output`, and
  `voice.segmentation_feedback` to evaluate natural conversation flow.
- Review the transport bridge with real LiveKit audio for frame sizing,
  backpressure, and overlap behavior.

## 2026-04-19 Documentation Refresh

Updated public documentation to better reflect the CVS runtime design and the
recent continuity fixes.

Changed files:

- `README.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/API_SPEC.md`
- `docs/IDENTITY_SYSTEM.md`
- `docs/LATENCY_IMPROVEMENT.md`
- `docs/DEPLOYMENT.md`
- `docs/docker_verification.md`
- `docs/VOICE_CLONING.md`
- `docs/GPT_SOVITS_INSTALL.md`
- `docs/UPDATES.md`
- `.agents/CONTEXT.md`

Documentation changes:

- Added a docs map in `docs/README.md` so readers and future agents know where
  to start.
- Expanded the root README with CVS goals, runtime guarantees, current test
  command, documentation map, and updated roadmap.
- Updated architecture docs with live state safety, shared identity ownership,
  structured speculative interruption flow, streaming voice output, and memory
  novelty suppression.
- Updated API specs for `audio.perception`, speculative/final `audio.stop`,
  `audio.resume`, raw binary `audio.stream`, and the expression contract.
- Updated identity docs to explain runtime identity ownership, cache boundaries,
  affect metadata, and organic recall behavior.
- Updated latency docs to describe first-audio streaming, adaptive segmentation,
  Whisper validation, and behavioral latency metrics.
- Updated deployment and Docker verification docs with regression test commands
  and mesh subjects to monitor for interruption arbitration.
- Updated voice/GPT-SoVITS docs to describe chunk-first playback and the text
  vs expression boundary.
- Prepended `UPDATES.md` with the Apr 19 CVS runtime continuity fix summary.

Verification:

- `git diff --check` passed with only line-ending warnings.
- Documentation-only change; backend tests were not rerun during this docs pass.

## 2026-04-19 Runtime Latency and Continuity Fixes

Implemented the follow-up fixes from the architecture pass.

Changed files:

- `backend/app/agents/base.py`
- `backend/app/agents/transport_agent.py`
- `backend/app/agents/stt_agent.py`
- `backend/app/agents/brain_agent.py`
- `backend/app/agents/voice_agent.py`
- `backend/app/cognitive/core.py`
- `backend/app/cognitive/identity.py`
- `backend/app/cognitive/state.py`
- `backend/app/config.py`
- `backend/app/conversation_history_store.py`
- `backend/scripts/bench_latency.py`
- `backend/tests/test_regressions.py`
- `.agents/CONTEXT.md`

Behavior changes:

- `BaseAgent.publish()` now accepts explicit metadata for binary subjects.
- `TransportAgent` publishes inbound LiveKit audio as raw PCM bytes with metadata
  headers instead of base64 JSON.
- `STTAgent` queues Whisper and SenseVoice work on bounded workers so NATS audio
  callbacks do not block on transcription or perception inference.
- STT, cognition, brain, and voice now propagate utterance/turn correlation so
  speculative `audio.stop`, `audio.resume`, and final stops can be fenced.
- `VoiceAgent` increments a generation on final stop, drains queues with proper
  `task_done()` accounting, ignores stale resume events, drops stale synthesis
  chunks, and uses a sequence number in its priority queue.
- `BrainAgent` connects before cognitive subscriptions, avoiding split NATS
  connections.
- `IdentityManager` can hydrate from and persist back to `agent_configs`, making
  JSON files seed/export storage rather than the only active runtime identity
  source.
- `StateService` now confidence-gates acoustic emotion updates, uses a lower
  confidence-scaled sensory weight, and debounces Neo4j persistence for repeated
  400ms perception chunks.
- `bench_latency.py` understands binary `audio.stream` payloads.

Verification:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app tests
.\.venv\Scripts\python.exe -m pytest
```

Latest result:

- `54 passed`
- One non-blocking `.pytest_cache` permission warning remains.

Remaining risks:

- Real LiveKit/SoVITS session testing is still needed to validate frame sizing,
  perceived first-audio latency, stop/resume timing, and stale synthesis fencing
  under live audio pressure.

## 2026-04-19 Docker Infrastructure Hardening

Hardened the production container orchestration to support the 'Solid State' mesh requirements.

Changed files:

- `backend/Dockerfile`
- `.env.example`
- `docker-compose.prod.yml`
- `docker-compose.infra.yml`

Infrastructure changes:

- **Phased Startup Mesh**: Implemented `depends_on` conditions with `service_healthy`. The mesh now graduates in stages (Infra -> Brain -> Sensory Agents) to eliminate startup race conditions.
- **Mesh Surveillance**: Added `netcat-openbsd` to the base image. All agents now perform automated health probes (`nc -z nats_mesh 4222`) to monitor signal bus connectivity.
- **Performance Exposure**: Mapped CVS-1.0 performance variables (`VOICE_SYNTH_CONCURRENCY`, `MAX_VOICE_QUEUE_SIZE`, `STT_WHISPER_QUEUE_SIZE`, `STATE_SENSORY_WEIGHT`) to the `.env` layer for production tuning.
- **Identity Persistence**: Synchronized weight volumes (`GPT_weights`, `SoVITS_weights`) across the agent mesh to support permanent voice identity.
- **Resilience**: Orchestrated SoVITS API health diagnostics using `/docs` probes to ensure dependent agents only start when the inference engine is ready.

Verification:

- `docker compose -f ...infra.yml -f ...prod.yml up -d`
- `docker ps` confirmed all agents reached `Healthy` status (with Voice Agent auto-starting after SoVITS settled).

## 2026-04-19 CI/CD Automation (Solid State Workflows)

Added five specialized GitHub Actions workflows to protect CVS-1.0 architectural
invariants. These are not generic linters — each one guards a specific failure
mode encountered or identified during the infrastructure hardening session.

New files:

- `.github/workflows/cognitive-regression.yml`
- `.github/workflows/mesh-integrity.yml`
- `.github/workflows/persona-guard.yml`
- `.github/workflows/security-audit.yml`
- `.github/workflows/docker-health.yml`

Workflow purposes:

- **Cognitive Regression Gate**: Boots a live NATS service container, sets up
  JetStream streams, and runs the full `pytest` regression suite. Catches broken
  subscriptions, stale state hydration, and persona drift. Uploads test results
  as artifacts for debugging.
- **Mesh & Schema Integrity**: Validates all compose files (including unified
  phased-startup config), runs `prisma validate`, and checks that every `${VAR}`
  in compose files is documented in `.env.example`. Would have caught the
  `nats_mesh` vs `nats` service name mismatch from the hardening session.
- **Persona & Prompt Guard**: Triggers only when cognitive/identity code changes.
  Runs identity-specific tests, validates emotion markup stripping preserves
  timing markers, and checks all persona JSON seed files are parseable.
- **Security & Secrets Audit**: Scans for hardcoded credentials, default Neo4j
  passwords in production code, committed `.env` files, and runs `pip-audit` for
  known Python dependency vulnerabilities.
- **Docker Image Health**: Builds all five agent images in a matrix, smoke-tests
  each by importing the agent module, verifies `netcat` is installed for health
  probes, and validates the unified compose config.

All workflows use `paths:` filters so they only trigger on relevant file changes.

Verification:

- All 11 workflow files (6 existing + 5 new) pass YAML syntax validation.

## 2026-04-19 Modular Architectural Refactor

Refactored the monolithic CVS-1.0 backend into a 4-layer decoupled architecture to improve maintainability and strictly enforce structural boundaries.

Changed files:

- Created `app/stt/`, `app/state/`, `app/voice/`.
- Moved 15+ files and updated 60+ internal import paths.
- Extracted `app/voice/normalizer.py` and `app/voice/cache.py` from `VoiceAgent`.
- Updated `docker-compose.prod.yml` with modular entry points.

Behavior changes:

- **Strict Layering**: No direct cross-imports between stores and agents; integration is now handled via package facades (`__init__.py`).
- **State as Shared Kernel**: `StateService` is now the single source of truth for all identity-related dynamics, injected into the Cognitive layer.
- **Hardware Agnostic STT/Voice**: Sensory perpection and audio rendering are now physically isolated modules.
- **Frontend-Mesh Synchronization**: Replaced legacy Supabase database links with local Docker PostgreSQL connectivity. The Frontend and Backend now share the same "Sovereign" data layer for consistent history and personality state.
- **Frontend Docker Hardening**:
    - Updated `Dockerfile` with `libc6-compat` for Alpine stability and disabled Next.js telemetry.
    - Implemented `ARG` support for `NEXT_PUBLIC_BACKEND_URL` to allow build-time mesh configuration.
- **Connectivity Refactor**: Externalized all backend and LiveKit signal URLs into environment variables, removing hardcoded localhost dependencies.

Verification:

```powershell
# Backend Verification
cd backend
python -m compileall app
pytest --ignore=scripts

# Frontend Verification
cd frontend
docker build -t ai-friend-frontend .
docker run -p 3000:3000 ai-friend-frontend
```

Latest result:

- **54 passed (Backend)**. 
- **Frontend Health**: Build finished successfully and server initialized using the standalone production runtime.
- **Mesh Connectivity**: All 13 containers (12 Backend/Infra + 1 Frontend) are now verified for interoperability.

Next Recommended Work:

- Implement per-layer latency telemetry to measure overhead of modular facades.
- Transition `BrainAgent` logic into a more generic `MeshOrchestrator` if further layers (e.g., Vision, Motor) are added.
- Review `StateService` for thread-safety under high-frequency mesh updates from multiple agents.

## 2026-04-20 Mesh Service Activation (System + Surfacing)

Activated the two missing runtime agents in production orchestration so heartbeat evolution and background surfacing processes are scheduled by default in Docker deployments.

Changed files:

- `docker-compose.prod.yml`

Infrastructure changes:

- Added `system_agent` service (`python -m app.agents.system_agent`) with mesh heartbeat environment and standard NATS health check.
- Added `surfacing_agent` service (`python -m app.agents.surfacing_agent`) with NATS/Postgres/Neo4j environment wiring and startup dependencies on `brain_agent` and `system_agent`.
- Kept service conventions aligned with existing mesh services (`restart: always`, `nc -z nats_mesh 4222` health check, shared `ai_mesh_network`).

Verification:

```powershell
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml config
```

Latest result:

- Compose merge and validation succeeded.

Remaining risks:

- `SurfacingAgent` entrypoint wiring has been completed (`ConversationHistoryStore` pool injection into `MemoryStore`, plus `GraphDB` lifecycle). Continue validating this under full Docker runtime with real Postgres/Neo4j connectivity and measure surfacing cadence in live sessions.

## 2026-04-20 Surfacing Bootstrap Wiring Follow-up

Completed the surfacing process bootstrap wiring so the newly orchestrated container can construct runtime dependencies instead of running in memory-only mode.

Changed files:

- `backend/app/agents/surfacing_agent.py`
- `.agents/CONTEXT.md`

Behavior changes:

- `SurfacingAgent.main()` now initializes `ConversationHistoryStore`, injects `MemoryStore(pool=...)`, and instantiates `GraphDB` before starting mesh subscriptions.
- Added explicit resource shutdown path in `SurfacingAgent.stop()` for `GraphDB` and `ConversationHistoryStore`.
- Added cancellation-safe shutdown handling in `main()` (`asyncio.CancelledError` + `KeyboardInterrupt`).

Verification:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_regressions.py -k surfacing_agent_suppresses_recently_recalled_memories
```

Latest result:

- `1 passed, 12 deselected`

Remaining risks:

- Local direct import validation currently fails in this workstation venv due `asyncpg` binary module load error (`asyncpg.protocol.protocol` missing). Regression tests that mock asyncpg still pass. Docker runtime validation remains the source-of-truth check for end-to-end startup.

## 2026-04-20 Memory Surfacing Runtime Fixes (Embed Endpoint + Timezone Safety)

Patched the surfacing retrieval path so memory queries work reliably in container runtime and validated end-to-end subject flow for both `system.tick` and `memory.surfaced`.

Changed files:

- `backend/app/state/memory_store.py`
- `docker-compose.prod.yml`
- `.agents/CONTEXT.md`

Behavior changes:

- `MemoryStore` now consumes `Config.OLLAMA_URL` (with optional constructor override) instead of hardcoded localhost, so containerized agents can reach mesh Ollama.
- Embedding calls now support modern Ollama `/api/embed` with fallback to legacy `/api/embeddings`.
- Memory scoring now handles offset-aware and offset-naive timestamps safely when computing decay.
- `surfacing_agent` compose env now includes `OLLAMA_URL=http://local_brain:11434`.

Runtime verification and enablement:

- Applied `backend/db/schema.sql` in Postgres to ensure `memories` table/function exist.
- Pulled embedding model in Ollama container: `nomic-embed-text`.
- Seeded one memory entry through runtime `MemoryStore.add_memory(...)` path.
- Recreated `surfacing_agent` container after code updates.
- Active NATS probe observed:
  - `system_tick`: 1
  - `memory_surfaced`: 1

Latest probe result:

- `MEMORY_SURFACED` event emitted with seeded memory content.

Remaining risks:

- Local host Python venv still has asyncpg binary import issue (`asyncpg.protocol.protocol`) for non-mocked local test paths, but container runtime path is functioning for surfacing validation.

## 2026-04-20 LLM Runtime Stabilization (Fallback + Completion Guard)

Hardened LLM generation reliability for CPU-constrained runtime by adding endpoint fallback, robust stream parsing, and bounded completion behavior.

Changed files:

- `backend/app/llm/ollama_client.py`
- `backend/app/cognitive/action.py`
- `backend/app/config.py`
- `backend/app/agents/brain_agent.py`
- `backend/app/cognitive/core.py`
- `backend/app/cognitive/decision.py`
- `backend/app/cognitive/learning.py`
- `backend/tests/test_resilience.py`
- `docker-compose.prod.yml`

Behavior changes:

- Ollama client now supports resilient fallback across `/api/chat` and `/api/generate` for both non-streaming and streaming calls.
- Streaming parser now handles fragmented chunk transport via newline-delimited JSON buffering.
- Generation and stream calls now include timeout-aware retries and structured endpoint error accumulation.
- Added model routing controls via config/env (`LLM_FAST_MODEL`, `LLM_CHAT_MODEL`, `LLM_REFLECTION_MODEL`).
- Cognitive runtime channels moved to live-only durable consumers (`deliver_policy="new"`) to avoid replay storms on restarts.
- Added bounded stream duration guard in action execution. On timeout, the runtime emits graceful fallback content and a terminal done event.

Verification:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_resilience.py
```

Latest result:

- `10 passed`

Runtime probe notes:

- Deterministic `chat.input -> chat.output` probes produced successful `done=true` completions on multiple turns.
- Under sustained load, intermittent turn timeouts still occur due to upstream model latency pressure.

Remaining risks:

- Ollama CPU-only runtime still shows long tail latency and occasional timeout cascades under mixed chat/embed pressure.

## 2026-04-20 Audio Mesh Backpressure Hardening (NATS + Transport + Voice)

Stabilized high-throughput `audio.stream` handling by decoupling transport callback work, increasing NATS pending limits, and reducing filler burst pressure from voice.

Changed files:

- `backend/app/agents/base.py`
- `backend/app/agents/transport_agent.py`
- `backend/app/voice/agent.py`
- `backend/app/config.py`
- `docker-compose.prod.yml`

Behavior changes:

- `BaseAgent.subscribe()` now supports `pending_msgs_limit` and `pending_bytes_limit` overrides.
- Transport audio subscription switched to live durable `transport_agent_audio_stream_live` with high pending limits for PCM burst tolerance.
- Transport now uses a bounded queue + dedicated playback worker so NATS callbacks remain fast and non-blocking.
- On queue saturation, transport drops oldest buffered frames to preserve near-real-time playout.
- Transport startup now retries LiveKit connection with bounded backoff instead of immediate crash on transient SFU refusal.
- Voice resilience loop now throttles filler cadence and suppresses filler emission when playback backlog is already high.
- Compose tuning envs added for transport queue size and voice filler controls.

Verification:

```powershell
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml config
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_resilience.py
```

Latest result:

- Compose config validation passed.
- `10 passed` on resilience tests.
- Synthetic burst publish to `audio.stream` completed (`401` messages) with no fresh slow-consumer signatures in recent NATS or transport log scans.

Remaining risks:

- LiveKit may still briefly refuse transport connection during SFU restart windows; retry path now allows recovery without manual intervention.
- Host-side access to NATS monitoring endpoint (`:8222/varz`) is intermittently unavailable in this environment; broker log scans remain the practical validation path.
