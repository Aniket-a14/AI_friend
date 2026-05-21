# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-05-18

### Added
- **Subconscious Engine**: A dedicated microservice (`SubconsciousAgent`) that generates internal monologue and triggers proactive engagement during idle periods.
- **Endocrine System**: Synthetic hormones (Cortisol for stress, Dopamine for reward) now modulate LLM generation parameters (temperature, top_p) based on PAD emotional vectors.
- **Vision Agent**: Host-native visual appraisal using `moondream:latest` via Ollama, integrated into the cognitive loop.
- **Sovereign Memory Hierarchy**: Transitioned from flat vector storage to scoped retrieval (Wings/Rooms/Drawers).
- **L1 Memory Activation Cache**: O(1) cache for ACT-R memory retrievals with a 15-second TTL, dropping query latency to sub-microsecond levels.
- **16-Metric Performance Suite**: Comprehensive benchmarking suite (`test_performance.py`) and logarithmic decade profile analytics (`scripts/diagnostics/human_readable_benchmarks.py`).

### Changed
- **Rust Migration Finalized (CVS-3.0)**: The signaling API, audio playback rings, and NATS payload serialization are now fully migrated to high-performance Rust Native audio agents.
- **Binary NATS Serialization**: Swapped JSON with `orjson` inside `BaseAgent.publish` to write UTF-8 binary bytes directly, accelerating throughput to 80,000 OPS.
- **PostgreSQL PL/pgSQL Offloading**: ACT-R memory decay formulas and emotional alignment evaluations are now compiled and executed directly inside database CPU registers (`surface_actr_memories`).
- **Telemetry Logging**: Migrated the synchronous logging engine to a lock-free asynchronous background worker, dropping telemetry overhead from 661 µs to < 0.5 µs (1300x speedup).
- **Paralinguistic Perception**: The `STTAgent` now extracts non-speech events (laughter, cough, breath) from the fast-path SenseVoice engine.

### Security
- **LAN/PCM Contracts**: The signaling API is now LAN-only by default (`LAN_ONLY=true`). `audio.inbound` rejects JSON/base64 payloads and accepts only PCM.
- **Mesh Contract Hardening**: Replaced raw Python dictionaries with strictly typed Pydantic models (`ChatInput`, `ChatOutput`, `ChatOutputAffect`) at the NATS boundary.
