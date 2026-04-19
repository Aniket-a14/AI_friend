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

Main runtime layers:

- Sensory layer: Whisper for final transcription, SenseVoice for fast perception,
  emotion, and speculative interruption.
- Cognitive layer: BDI-style `CognitiveService`, identity management, state
  service, action generation, and reflection.
- State layer: persistent mood, energy, trust, attachment, acoustic bias, and
  idle heartbeat evolution.
- Memory layer: Postgres/vector memory plus Neo4j graph state and relationships.
- Voice layer: GPT-SoVITS streaming PCM, temporal markers, filler audio, and
  NATS audio transport.
- Mesh: NATS JetStream subjects including `chat.*`, `audio.*`, `state.*`,
  `memory.*`, `system.*`, `voice.*`, and related channels.

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
