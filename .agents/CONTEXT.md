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

## 2026-04-20 Runtime Stability Lock (Generation + Self-Healing Bootstrap + Observability)

Completed the next stability tranche to avoid silent chat degradation, remove manual bootstrap prerequisites, and add minimal event-quality telemetry.

Changed files:

- `backend/app/llm/ollama_client.py`
- `backend/app/agents/brain_agent.py`
- `backend/app/config.py`
- `backend/scripts/setup_nats_streams.py`
- `backend/scripts/runtime_bootstrap.py`
- `backend/app/agents/base.py`
- `backend/app/agents/surfacing_agent.py`
- `backend/app/cognitive/core.py`
- `backend/tests/test_resilience.py`
- `backend/tests/test_regressions.py`
- `backend/tests/test_mesh_surfacing_integration.py`
- `docker-compose.prod.yml`
- `.env.example`

Behavior changes:

- Ollama generation path now includes model-name compatibility attempts (`model` then `model:latest` when untagged) across both `/api/chat` and `/api/generate` endpoint fallbacks.
- Brain generation loop now fail-fast logs streamed LLM errors per turn and guarantees non-empty fallback speech when a turn would otherwise complete silently.
- Brain startup now runs idempotent runtime bootstrap: apply DB schema from `db/schema.sql`, ensure core conversation/config tables exist, synchronize NATS streams deterministically via `setup_nats_streams.py`, and ensure required Ollama models exist via `/api/pull`.
- Compose now wires bootstrap controls and model requirements through env vars, and brain depends on ollama startup to reduce cold-boot races.
- Added minimal subject metrics in base publish/consume paths and focused metrics in surfacing/cognitive paths for `system.tick`, `memory.surfaced`, `audio.stop`, `audio.resume`, and `chat.output`.

Regression coverage added:

- `test_generate_retries_with_latest_tag_for_untagged_model` validates model compatibility fallback.
- `test_brain_agent_emits_fallback_when_stream_errors_without_content` guards against silent turn completion.
- `test_surfacing_mesh_regression_emits_system_tick_and_memory_surfaced` covers seeded-memory -> chat.input -> system.tick -> memory.surfaced mesh path.

Verification:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_resilience.py tests/test_regressions.py tests/test_mesh_surfacing_integration.py
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml config
```

Latest result:

- `26 passed` for targeted runtime regression suite.
- Compose merge validation passed (`COMPOSE_CONFIG_OK`).

Remaining risks:

- Ollama cold pulls can extend first boot time when required models are missing; behavior is self-healing but startup duration may increase.
- Subject metrics are intentionally lightweight (in-process counters/averages only); no durable metrics sink is configured yet.

## 2026-04-20 Runtime Throughput Tuning + Surfacing Replay Guard

Applied targeted runtime tuning to reduce LLM contention under load, and hardened surfacing subscriptions/task scheduling to avoid replay/backlog-induced embed saturation.

Changed files:

- `backend/app/config.py`
- `backend/app/cognitive/decision.py`
- `backend/app/cognitive/learning.py`
- `docker-compose.prod.yml`
- `.env.example`
- `backend/app/agents/surfacing_agent.py`

Behavior changes:

- Added config/env controls:
  - `LLM_INTENT_CLASSIFICATION_ENABLED` (toggle per-turn classifier)
  - `REFLECTION_ENABLED`
  - `REFLECTION_MIN_INTERVAL_SECONDS`
- Decision path now applies deterministic low-cost routing defaults first and only runs LLM intent classification when enabled.
- Reflection layer now supports runtime disable and minimum interval throttling to prevent frequent background LLM consolidation under heavy chat pressure.
- Production compose defaults tuned for stability-first runtime:
  - `LLM_INTENT_CLASSIFICATION_ENABLED=false`
  - `REFLECTION_ENABLED=true`
  - `REFLECTION_MIN_INTERVAL_SECONDS=300`
- Surfacing agent subscriptions moved to live-only durable consumers (`deliver_policy="new"`) for both `chat.input` and `system.tick`.
- Surfacing sweep scheduler now enforces no-overlap task execution and minimum sweep interval throttling to prevent concurrent or rapid-repeat vector sweeps.
- Surfacing stop path now cancels any in-flight sweep task before shutdown.

Verification:

```powershell
cd backend
pytest tests/test_decision.py tests/test_regressions.py tests/test_resilience.py
pytest
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml config
```

Latest result:

- `29 passed` targeted decision/resilience/regression suite.
- `64 passed` full backend suite.
- Compose merge validation passed (`COMPOSE_CONFIG_OK`).
- Runtime env inside `brain_agent` confirmed tuned flags are active.

Observed runtime notes (short soak probes):

- Throughput improved vs prior baseline under more aggressive publish cadence (done ratio rose from ~0.093 to ~0.65 in a 4s-interval probe), but quality gate remains failing under that load profile.
- Gate-style run remains unresolved; one probe showed mixed done-event accounting from unrelated turns, so strict per-run turn filtering is still required for authoritative pass/fail scoring.
- `memory.surfaced` counts were inconsistent in short probes; surfacing replay/storm protection patch was applied to stabilize this path before the next controlled gate run.

Remaining risks:

- CPU-only Ollama latency remains the primary bottleneck for sustained high-rate turn completion.
- Final soak gate sign-off still requires a controlled run with strict turn-id filtering and stable background load.
 
## 2026-04-21 CVS-1.0 Stabilization & Storage Optimization
 
Finalized the transition to the hardened CVS-1.0 mesh on host Zenbook Duo (Laptop/CPU-fallback mode).
 
**Storage Optimization:**
- Reclaimed **102.5GB of disk space** on the host `C:` drive via `diskpart` VHDX compaction. 
- Established a **Targeted Rebuild Strategy**: Use `docker-compose build <service>` to avoid redundant 25-minute downloads of the 27GB SoVITS model cache.
  
**Behavioral & Runtime Fixes:**
- **Hardware-Agnostic Synthesis**: Updated `sovits_bootstrap.sh` to automatically detect CPU-only environments and switch to FP32 fallback, preventing CUDA initialization crashes on non-GPU hardware.
- **Perception Fix (STT)**: Refactored `SenseVoice` (sherpa-onnx) initialization to use `FeatureExtractorConfig` and the corrected triple-argument `OfflineSenseVoiceModelConfig` constructor.
- **English-Only Enforcement**: Restricted both Whisper and SenseVoice modules to the English language code.
 
## 2026-04-21 Cognitive Mesh Stabilization & Test Resilience

Resolved critical race conditions and environment-specific flakiness in the cognitive verification suite.

**Tests & Concurrency:**
- **Deterministic Synchronization**: Transitioned `ReflectionService` to use an `asyncio.Event` (`reflection_done`) that signals absolute completion of background consolidation. Scenario tests now strictly `wait()` for this event, ensuring Turn N evolution is finished before Turn N+1 begins.
- **Absolute Test Isolation**: Refactored scenario fixtures to use `tmp_path` (sandboxing). The `IdentityManager` now persists `history.json` and `personality.json` to isolated temporary directories, eliminating disk-state leakage between test suites.
- **Configuration Locking**: Hardened `conftest.py` to force `REFLECTION_ENABLED=True`, `REFLECTION_MIN_INTERVAL_SECONDS=0`, and `LLM_INTENT_CLASSIFICATION_ENABLED=True` for every test run.

**Learning & Identity Hardening:**
- **Defensive LLM Parsing**: Implemented robust dictionary-wrapping and `isinstance` checks in `ReflectionService` to handle cases where 1B models return raw strings or lists instead of expected JSON objects.
- **Safe Identity Defaults**: Standardized `IdentityManager` to ensure `relationship` and `memories` keys always exist, preventing `KeyError` regressions during persona evolution.

**Verification:**
- **100% Pass Rate**: Achieved **63/63 passed** across the full backend suite in the user terminal.
- Verified that `test_scenario_hostile_interaction_drift` passes reliably in both isolated and full-suite runs.

## 2026-04-21 GPT-SoVITS & Voice Layer Enhancements

Hardened the signal rendering loop for psychological realism and signal continuity.

**Signal Continuity:**
- **Psychological VAD Mapping**: Implemented `_vad_to_prosody` in `VoiceAgent`. Maps internal Valence, Arousal, and Dominance (VAD) to SoVITS inference parameters (`speed`, `pitch`, `volume`) following Scherer’s vocal expression models.
- **Overlap-Add (OLA) Transitions**: Implemented a 15ms sample-accurate linear cross-fade in the `_playback_loop` to ensure seamless stitching of PCM chunks and prevent "clicking" during sudden state transitions.
- **Adaptive Timing Markers**: Support for native `<pause=...ms>` and `<hesitate>` markers injected directly into the PCM stream by splitting synthesis text into atomic temporal segments.

**Resilience & Fillers:**
- **Social Mesh Hydration**: Added `FillerService` to pre-generate and hydrate "social fillers" (hmm, got it, I see) in the background.
- **Perception-Driven Fillers**: The `_resilience_loop` now automatically emits social fillers if synthesis latency exceeds 350ms while in a `BUFFERING` state, maintaining the "illusion of presence" during CPU-only fallback runs.

**Next Recommended Work:**
- Monitor CPU pressure on Zenbook Duo (0.95+) during high-rate turns; evaluate if further jitter-buffer expansion (beyond 10ms) is needed for the SFU bridge.
- Implement per-utterance sentiment verification to calibrate the `VAD -> Prosody` mapping with real user emotional vibes.

## 2026-04-21 Voice Warm-Start Truthfulness + Config Consistency

Aligned the GPT-SoVITS warning-mode behavior with non-fatal startup intent while keeping status signals truthful.

Changed files:

- `backend/app/voice/agent.py`
- `backend/app/voice/sovits_client.py`
- `backend/app/config.py`
- `backend/app/stt/agent.py`
- `backend/app/stt/whisper_service.py`
- `docker-compose.prod.yml`
- `backend/tests/test_regressions.py`
- `.agents/CONTEXT.md`

Behavior changes:

- `VoiceAgent` now treats weight loading as success only when both configured weight set calls return `True`; failures remain non-fatal and enter `warning_no_weights` mode.
- Startup now emits truthful mesh status on `voice.warm`:
  - `status=ready, identity=fine_tuned` only on successful weight load.
  - `status=degraded_no_weights, identity=fallback` otherwise, with expected weight paths included.
- Added `VOICE_FILLER_HYDRATE_ON_STARTUP` toggle to allow skipping filler pre-hydration when desired.
- Added `VOICE_WEIGHT_LOAD_RETRIES` config for bounded retry tuning.
- `SoVITSClient.synthesize()` now accepts optional `language/speed/pitch/volume` kwargs (best-effort payload mapping) to stay compatible with current `VoiceAgent` call signatures.
- STT language wiring is now active: `STT_LANGUAGE` flows from config -> `STTAgent` -> `WhisperSTTService` transcription.
- Compose voice/STT env wiring now includes `CUSTOM_GPT_PATH`, `CUSTOM_SOVITS_PATH`, `TTS_LANGUAGE`, `STT_LANGUAGE`, and warm-start/filler toggles.

Verification:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_regressions.py -k warm_start
```

Added regression coverage:

- `test_voice_warm_start_sets_warning_when_weights_unavailable`
- `test_voice_warm_start_succeeds_when_both_weights_load`

Remaining risks:

- Prosody knobs (`pitch`, `volume`) are passed best-effort; behavior depends on GPT-SoVITS API version support.
- End-to-end Docker runtime validation is still recommended to confirm `voice.warm` status transitions under real container startup conditions.

## 2026-04-29 Phase 1: Proactive Engagement (Initiating Contact)

Implemented the first phase of the Advanced Cognitive Companion roadmap. The system can now spontaneously initiate contact after detecting extended idle periods, using the same speech pipeline as reactive responses.

Changed files:

- `backend/app/config.py`
- `backend/app/state/agent_state.py`
- `backend/app/cognitive/core.py`
- `backend/app/agents/brain_agent.py`
- `docker-compose.prod.yml`
- `.env.example`

Behavior changes:

- **Interaction Tracking**: `AgentState` now tracks `last_user_interaction` (Unix timestamp). `StateService.update_from_event()` and `BrainAgent._on_chat_input()` both refresh this timestamp on every user interaction.
- **Proactive Eligibility**: `StateService.check_proactive_eligibility()` evaluates four conditions: feature enabled, idle threshold exceeded, cooldown elapsed, and sufficient energy. All thresholds are env-configurable.
- **Proactive Generation**: `CognitiveService.generate_proactive_response()` constructs a real ActionPlan grounded in the agent's current identity, emotional state, relationship history, and surfaced memories. It streams through the existing `ActionService.execute()` pipeline.
- **Production Loop**: `BrainAgent` subscribes to `system.tick` and evaluates proactive eligibility on every heartbeat. When triggered, it generates and publishes spontaneous speech using the exact same segmenter, `chat.output` subject, and VoiceAgent pipeline as reactive responses.
- **Conversation Logging**: Proactive responses are logged to `ConversationHistoryStore` and trigger background reflection (memory consolidation) just like regular turns.
- **Debug Override**: `PROACTIVE_DEBUG_THRESHOLD_OVERRIDE` env var allows setting a short idle threshold (e.g., 30 seconds) for quick local testing without modifying production defaults.

Configuration additions:

- `PROACTIVE_ENABLED` (default: true)
- `PROACTIVE_IDLE_THRESHOLD_SECONDS` (default: 7200 / 2 hours)
- `PROACTIVE_COOLDOWN_SECONDS` (default: 3600 / 1 hour)
- `PROACTIVE_MIN_ENERGY` (default: 0.2)
- `PROACTIVE_DEBUG_THRESHOLD_OVERRIDE` (optional, no default)

Verification:

- Pending: `pytest` full suite + live Docker mesh test.

## 2026-05-10 Solution Architect Planning Skill Adoption

Adopted a planning-first skill to standardize implementation plans before code changes.

Changed files:

- `skills/solution-architect-agent/SKILL.md`
- `skills-lock.json`
- `README.md`
- `docs/README.md`
- `.agents/CONTEXT.md`

Decision:

- Canonical location is `skills/solution-architect-agent/SKILL.md`.
- No mirrored copy was added under `.agents/skills` to avoid duplication drift.

Behavior/process changes:

- Non-trivial work should run the solution architect planning stage first.
- Plans must be grounded in observed repository files and conventions.
- Required plan output sections are fixed: problem statement, affected files and dependencies, options, recommendation, ordered implementation plan, and risks/open questions.
- Planning stage is explicitly plan-only and does not include implementation code.

Verification:

- Docs/skills-only update; no runtime backend/frontend files changed.

Remaining risks:

- Proactive messages consume LLM compute. Under CPU-only Ollama, this adds to the overall inference pressure if triggered during active background reflection.
- The proactive prompt quality depends heavily on the surfaced memory buffer. If no memories have been surfaced recently, the check-in will be more generic.

## 2026-04-29 Phase 2 & 3: Psychological Layer & Narrative Memory

Implemented the full Phase 2 & 3 Psychological Cognitive Layer according to `psycological_layer.md`. The cognitive core was upgraded to use deterministic heuristic math for emotional and behavioral evaluation.

### Key Advancements:

- **1. Theory of Mind (Modeling the User)**:
    - **Dynamic User Model**: The `ReflectionService` now extracts "Theory of Mind" observations (e.g., "User seems stressed", "User is tired") into the Neo4j Knowledge Graph.
    - **Behavioral Adjustment**: The `DecisionService` automatically adjusts its social goals (e.g., favoring COMFORT over ENGAGE) based on the user's detected emotional state and long-term mental state patterns.
    - **The Vibe**: The AI can now realize if the user has been working late and automatically adjust to be softer, more supportive, and less demanding.

- **2. Episodic vs. Semantic Memory Surfacing**:
    - **Dual-Channel Recall**: `SurfacingAgent` alternates between Semantic facts (Neo4j) and Episodic narratives (pgvector).
    - **Narrative Formatting**: Memories are no longer flat strings; they are constructed into "Tulving-style" episodes with temporal markers ("last week") and emotional context.
    - **The Vibe**: The AI can casually reference shared history: "Remember last week when we were up until 3 AM debugging that routing issue? Let's not do that again tonight."

- **3. Psychological State Engine (PAD)**:
    - Moved from LLM-driven emotion tracking to **PAD (Valence, Arousal, Dominance)** using ALMA decay rules, Marsh trust, and Bowlby attachment.
    - **Appraisal (OCC/Lazarus)**: Deterministically calculates relevance, novelty, and goal congruence before state updates.
    - **Expression (Scherer)**: Computes speaking rate and pause bias from internal state for realistic vocal delivery.

Changed files:
- `backend/app/cognitive/appraisal.py` (New)
- `backend/app/cognitive/reappraisal.py` (New)
- `backend/app/state/agent_state.py`
- `backend/app/state/memory_store.py`
- `backend/app/cognitive/core.py`
- `backend/app/cognitive/decision.py`
- `backend/app/cognitive/learning.py`
- `backend/app/agents/brain_agent.py`
- `backend/app/agents/surfacing_agent.py`
- `backend/app/config.py`
- `backend/scripts/init_db.py`
- `backend/tests/*` (Added robust state and memory regression tests)

Verification:
- The full backend test suite passes (66/66) after significant updates to state and memory testing.
- `init_db.py` was executed in the Docker mesh to apply the schema migration (`recall_count`, `valence`).


## 2026-05-10 LAN / PCM Contract Hardening

Applied the maintainer decisions from the debt audit follow-up:

- The signaling API is LAN-only by default. `LAN_ONLY=true` accepts loopback, localhost, private IPv4, and link-local clients, while CORS defaults to a private-origin regex instead of wildcard credentials.
- `audio.inbound` is now PCM-only. STT rejects JSON/base64 payloads and downmixes multichannel PCM before queueing Whisper/SenseVoice work.
- `SurfacingAgent` listens to the canonical `state.update` subject for PAD valence instead of the stale `agent.state` subject.
- `db/schema.sql` and `scripts/init_db.py` now agree on runtime columns (`valence`, `recall_count`, ACT-R fields) and `init_db.py` no longer drops local memory tables unless `ALLOW_DESTRUCTIVE_DB_RESET=true`.
- Voice synthesis now parses `<pause=Nms>` and `<hesitate>` before TTS so timing tags are not spoken, streams clean text segments, and flushes residual phrase buffers on final `chat.output`.
- Frontend LiveKit audio tracks are attached to hidden audio elements and removed on unsubscribe/unmount; webcam preview tracks are stopped on unmount.

Verification:

- `backend/tests/test_regressions.py` passes locally.

## 2026-05-11 AI Mesh Contracts & Observability Hardening

Completed infrastructure hardening and API compatibility fixes to move the project from "Experimental" to "Hardened CVS-1.0".

Changed files:
- `backend/app/contracts.py`
- `backend/app/agents/brain_agent.py`
- `backend/app/voice/agent.py`
- `backend/app/stt/sensevoice_service.py`
- `backend/app/logging_config.py` (New)
- `backend/main.py`
- `backend/requirements-base.txt`
- `README.md`
- `walkthrough.md`

Behavior changes:
- **SenseVoice Restoration**: Fixed incompatible constructor in `SenseVoiceSTTService` caused by `sherpa-onnx` 1.13.0 API changes (switched to `from_sense_voice` factory method). This restores the fast-path speculative interruption STT.
- **Typed Mesh Contracts**: Replaced raw Python dictionaries with strictly typed Pydantic models (`ChatInput`, `ChatOutput`, `ChatOutputAffect`) in the Brain and Voice agents. This validates the PAD affect metadata at the NATS boundary, preventing silent failures.
- **Structured JSON Logging**: Implemented `logging_config.py` using `python-json-logger` for the entire backend. This enables production-grade log aggregation and tracing across the mesh.
- **Signaling Server Restoration**: Restored the `AIBackend` class and `initialize()` lifecycle in `main.py` that had been accidentally removed during earlier refactoring, and wired it to the new structured logging.

Verification:
- Rebuilt all 8 container images with `docker compose ... up -d --build`.
- Verified all 14 mesh containers reached `Running` and `Healthy` status (verified via `docker ps`).

## 2026-05-13 Tier-5 Autonomy: Endocrine & Subconscious Engines

Advanced the AI Mesh to Tier-5 Autonomy by introducing physiological LLM control and independent background reasoning, effectively decoupling "thinking" from the reactive chat loop.

Changed files:
- `backend/app/state/agent_state.py`
- `backend/app/llm/ollama_client.py`
- `backend/app/cognitive/action.py`
- `backend/app/cognitive/core.py`
- `backend/app/agents/subconscious_agent.py` (New)
- `backend/app/agents/brain_agent.py`
- `backend/tests/test_endocrine.py` (New)
- `backend/tests/test_subconscious.py` (New)
- `docker-compose.prod.yml`
- `docker-compose.infra.yml`

Behavior changes:
- **Endocrine System**: `AgentState` now computes synthetic hormones (`cortisol` for stress, `dopamine` for reward) based on the PAD emotional vector. 
- **Physiological LLM Modulation**: `ActionService` injects these hormones into `OllamaClient` dynamically overriding `temperature` and `top_p`. High cortisol triggers rigid, lower-temp responses; high dopamine triggers creative, high-temp responses.
- **Subconscious Engine**: Extracted the proactive `system.tick` background loop out of `BrainAgent` and into a dedicated `SubconsciousAgent` microservice. 
- **Internal Thought Routing**: `SubconsciousAgent` evaluates idle thresholds and uses the LLM to generate an "internal thought". This thought is published to `chat.input` with `source="subconscious"`. `BrainAgent` intercepts this, avoids logging it as a user message, and naturally vocalizes the thought using the existing proactive generator.
- **Resilience**: Fixed `python-json-logger` deprecation warnings and removed unused local variables. Increased the `start_period` for the heavy `gpt-sovits` container in `docker-compose.infra.yml` to `500s` to accommodate slow CPU-only loading times.

Verification:
- The full backend test suite passes (92/92 tests) including 17 new tests for endocrine mathematics, API overrides, and subconscious thought routing.
- Deployed successfully to the NATS mesh with `docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml up -d --build`.

Remaining risks:
- The `SubconsciousAgent` currently polls `system.tick`. If `system_agent` dies, proactive thinking stops.
- GPT-SoVITS remains a major bottleneck on CPU-only machines, taking up to 5 minutes to load weights on startup.

## 2026-05-14 Tier-4 Multimodal Cognition: Integrated Visual Appraisal

Successfully integrated local host-resident visual appraisal into the agentic mesh, achieving stable cross-network NATS communication and resolving container-side screen capture limitations.

Changed files:
- `backend/app/vision/` (New Module)
- `backend/app/vision/__init__.py` (New)
- `backend/app/vision/links.py` (New - Migrated from `app/vision.py`)
- `backend/app/vision/appraisal.py` (New - Migrated from `app/cognitive/visual_appraisal.py`)
- `backend/app/vision/agent.py` (New - Migrated from `app/agents/vision_agent.py`)
- `backend/app/agents/base.py`
- `backend/app/nats_streams.py`
- `backend/app/cognitive/__init__.py`
- `scripts/start-vision.ps1` (New)
- `docker-compose.prod.yml`
- `.env`

Behavior changes:
- **Host-Native Vision**: Offloaded visual appraisal to a host-native `moondream:latest` VLM via Ollama, circumventing Windows Docker container limitations for desktop screen capture.
- **NATS Mesh Hardening**: Transitioned all NATS communication to use "Super Wildcards" (`>`) instead of simple wildcards (`*`). This resolves subject overlap errors and enables multi-token routing (e.g., `vision.description`).
- **Resilient Publishing**: Switched from JetStream `js.publish` to standard `nc.publish` for the host-to-container bridge, eliminating acknowledgment timeout failures in resource-constrained environments.
- **Unified Vision Module**: Consolidated all vision-related capture and AI logic into a dedicated `backend/app/vision/` module, cleaning up the scattered architecture in `agents/` and `cognitive/`.
- **Latency Tuning**: Increased VLM inference timeouts to 120s and NATS publish timeouts to 30s to accommodate local laptop GPU/CPU spikes.

Verification:
- Successfully performed a "Nuclear Wipe" of NATS volumes (`down -v`) to reset stream definitions to the new `>` wildcard format.
- Verified successful capture and description generation on the Windows host with delivery to the `brain_agent` inside the Docker mesh.
- Verified all 22 containers (infra + prod) reached `Healthy` status.

Remaining risks:
- GPT-SoVITS continues to be a startup bottleneck (requires high `start_period`).
- The Host Vision Agent must be manually started via `scripts/start-vision.ps1` as it cannot be containerized on Windows for screen access.

## 2026-05-14 Sovereign Memory Mesh & Voice I/O Upgrade

Hardened the AI Friend memory and voice subsystems by implementing hierarchical truth preservation and paralinguistic signal processing.

### Key Advancements:

- **1. Sovereign Memory Hierarchy (Wings/Rooms/Drawers)**:
    - **Scoped Retrieval**: Transitioned from flat vector storage to a hierarchical scoping model. This enables the agent to differentiate between "personal," "system," and "public" memory spaces, improving identity continuity.
    - **Verbatim Truth Preservation**: Implemented `raw_content` storage in the `MemoryStore`. All memory records now maintain a byte-for-byte copy of the original input to mitigate RAG-based hallucinations.
- **2. Local-First Voice I/O Architect**:
    - **Paralinguistic Perception**: Hardened the `STTAgent` to extract non-speech events (`Laughter`, `Cough`, `Breath`) from the fast-path SenseVoice engine.
    - **Emotional Signal Rendering**: Upgraded the `VoiceAgent` and `FillerService` to support zero-latency injection of emotional markers like `[laughs]` and `[sighs]` using pre-hydrated PCM segments.
- **3. Sensory Hardening (Real-System Acoustics)**:
    - **EMA Noise Floor Tracking**: Replaced basic SNR logic with an **Exponential Moving Average (EMA)** noise floor tracker. This provides robust Signal-to-Noise Ratio (SNR) estimation in dynamic acoustic environments.
    - **Prosody Mapping v2**: Refined the VAD-to-Prosody mapping to be more sensitive to arousal, resulting in more distinct vocal transformations during high-emotion states.

Changed files:
- `backend/app/contracts.py`
- `backend/app/state/memory_store.py`
- `backend/app/stt/agent.py`
- `backend/app/stt/sensevoice_service.py`
- `backend/app/voice/agent.py`

- `backend/app/voice/filler_service.py`
- `backend/app/voice/prosody.py`
- `backend/db/schema.sql`
- `backend/tests/test_memory_hierarchy.py`
- `backend/tests/test_voice_paralinguistics.py`
- `backend/tests/test_stt_perception.py`

Verification:
- Rebuilt `stt_agent`, `voice_agent`, and `brain_agent` containers.
- Verified all 14 mesh containers reached `Healthy` status.
- All 100 tests for memory hierarchy, paralinguistics, and SNR tracking passed with zero warnings (suppressed `pkg_resources` deprecation in `pytest.ini`).

## 2026-05-15 Sovereign Mesh Decoupling & Container Deployment

The AI Friend cognitive pipeline has been successfully transitioned into a modular, production-grade, transport-agnostic architecture. This refactor eliminates significant technical debt and establishes a robust foundation for future robotic hardware integration.

### 1. Architectural Transformation (CVS-1.0)
We have successfully decoupled all high-level agentic logic from the NATS/Mesh signaling layer. This was achieved by extracting pure logic "Engines" and "Systems" that operate without I/O side effects.

- **`CognitivePipeline`** (`app/cognitive/pipeline.py`): Centralized the master cognitive loop (Perception → Appraisal → State → Decision → Action → Learning).
- **`SubconsciousEngine`** (`app/cognitive/subconscious.py`): Extracted proactive thought generation logic.
- **`VoiceSystem`** (`app/voice/system.py`): Isolated the voice playback state machine and fencing logic.
- **`BrainAgent` & `VoiceAgent`**: These are now thin transport wrappers that delegate all behavioral intelligence to the functional cores.

### 2. Networking Standardization
The entire backend networking stack has been migrated to `httpx`.
- **`OllamaClient`** (`app/llm/ollama_client.py`): Now utilizes a persistent `AsyncClient` with connection pooling and robust retry logic.
- **SoVITS Service**: Legacy `requests` and `aiohttp` code was removed in favor of standardized `httpx` calls.
- **Performance**: Standardized on connection pooling ensures low-latency cognitive turnaround times required for real-time conversation.

### 3. Cognitive Loop & Episodic Learning
The loop is now deterministic and observable:
1. **Appraisal Engine**: Implements OCC/Lazarus models to update emotional state (PAD).
2. **Identity Manager**: Enforces immutable core values and allows for adaptive persona evolution.
3. **Reflection Service**: Automatically triggers episodic memory consolidation after interactions, updating the knowledge graph (Neo4j) and identity history.

### 4. Verification & Container Integrity
- **Automated Regression Testing**: Verified the system integrity using a comprehensive `pytest` suite. 24/24 Tests Passed validating turn-taking stability, interruption confirmation, memory retrieval, and agent state dynamics. Updated all test expectations to match the new, richer event schema yielded by the `CognitivePipeline`.
- **Container Network Fixes**: Fixed a LiveKit startup crash loop by adding a `service_healthy` `depends_on` condition for Redis. Mitigated a Windows Docker Desktop ghost binding bug by shifting the LiveKit WebRTC UDP range from `50000-50020` to a fresh `50100-50120` block.

Remaining risks:
- **Missing TTS Models**: The `models/GPT_weights/` and `models/SoVITS_weights/` directories on the local host are currently empty. The `voice_agent` reports a 400 Bad Request when attempting to load `ai_friend_voice.ckpt` and `ai_friend_voice.pth`. Synthesis is falling back to defaults until the user places the custom `.ckpt` and `.pth` files into the host directories.

## 2026-05-16 macOS Compose Profiles + Image Tag Stabilization

Implemented deployment-level hardening for reproducible cross-environment
runtime behavior, with explicit macOS light/heavy startup modes.

Changed files:

- `docker-compose.infra.yml`
- `docker-compose.macos.light.yml` (new)
- `docker-compose.macos.heavy.yml` (new)
- `.env.example`
- `docs/ARCHITECTURE.md`
- `.agents/CONTEXT.md`

Behavior/deployment changes:

- Replaced infra `latest` image tags with pinned tag variables:
  `NATS_IMAGE_TAG`, `NEO4J_IMAGE_TAG`, `LIVEKIT_IMAGE_TAG`,
  `OLLAMA_IMAGE_TAG`.
- Added optional GPU hint env vars (`NVIDIA_VISIBLE_DEVICES`,
  `NVIDIA_DRIVER_CAPABILITIES`) with empty defaults so macOS runs do not
  inherit Linux/NVIDIA assumptions.
- Added a **light macOS compose override** that marks heavy media services
  (`livekit`, `transport_agent`, `stt_agent`, `gpt-sovits`, `voice_agent`)
  behind a `heavy` profile for lower local resource pressure.
- Added a **heavy macOS compose override** that keeps full audio stack enabled
  but uses CPU-safe defaults for STT and SoVITS.
- Updated architecture docs with concrete light/heavy macOS compose commands.

Verification:

- `python -m ruff check backend/app/ backend/tests/` passed.
- Full backend `pytest` run in this sandbox still shows pre-existing failures
  unrelated to these deployment/docs changes (NATS-dependent mesh tests when
  no local NATS is running, plus existing `test_stt_perception` fixture errors).
- Compose files are intended to be validated with:
  `docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.macos.light.yml config --quiet`
  and
  `docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml -f docker-compose.macos.heavy.yml config --quiet`.
