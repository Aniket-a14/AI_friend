# Phase 01: Benchmark Plan & Measurement Protocol

**Phase:** `PHASE_01` — Authoritative Causal Slice  
**Target Hardware (GPU):** NVIDIA GeForce RTX 2060 Super (8 GB VRAM, Home GPU Server)  
**Target Hardware (Local):** Apple Mac (ARM64 Development Environment)  
**Evaluation Date:** Tomorrow upon GPU server power-up  
**GPU Status:** `PENDING_GPU — server expected online tomorrow`

---

## 1. Benchmark Suite Summary

| ID | Title | Environment | Hardware Dependency | Status |
|---|---|---|---|---|
| **BM-LOC-01** | Workspace CAS Commit Overhead | Local Mac | CPU / Memory | Ready for execution tomorrow |
| **BM-LOC-02** | Snapshot Serialization & Memory Budget | Local Mac | CPU / Memory | Ready for execution tomorrow |
| **BM-LOC-03** | Percept Normalization Micro-benchmark | Local Mac | CPU / Memory | Ready for execution tomorrow |
| **BM-GPU-01** | End-to-End Cognitive Turn Latency (Ollama) | GPU Server | RTX 2060 Super 8GB | **PENDING_GPU — server expected online tomorrow** |
| **BM-GPU-02** | Acoustic Barge-In to OutcomeRecord Latency | GPU Server | RTX 2060 Super 8GB + Audio Stack | **PENDING_GPU — server expected online tomorrow** |
| **BM-GPU-03** | 20-Turn Longitudinal State Stability & Drift | GPU Server | RTX 2060 Super 8GB | **PENDING_GPU — server expected online tomorrow** |

---

## 2. Local Mac Benchmark Protocols

### BM-LOC-01: Workspace CAS Commit Overhead
* **Hypothesis:** Committing a `WorkspaceCommand` through `SQLiteWorkspaceStore` with atomic CAS and transition logging adds $\le 3$ ms p50 and $\le 5$ ms p95 overhead compared to unversioned in-memory mutation.
* **Baseline:** In-memory `SessionState.to_dict()` serialization.
* **Metric:** Commit latency (microseconds / milliseconds), measured via `time.perf_counter_ns()`.
* **Test Condition:** 1,000 sequential commits on SQLite (WAL mode, memory/local temp disk) with full JSON payload.
* **Number of Runs:** 5 iterations of 1,000 commits (5,000 data points total).
* **Success Interpretation:** p50 latency $\le 3.0$ ms, p95 latency $\le 5.0$ ms.
* **Failure Interpretation:** p95 latency $> 10.0$ ms indicates database lock contention or excessive schema overhead requiring query optimization.
* **Hardware Dependency:** Apple Silicon Mac (Local CPU/Disk).

### BM-LOC-02: Snapshot Serialization & Memory Budget
* **Hypothesis:** The serialized size of `CognitiveWorkspaceSnapshot` remains below 2 KB under maximum active goals and focus payloads, preventing memory bloat.
* **Baseline:** Legacy `SessionState` JSON serialization (~250 bytes).
* **Metric:** Byte size of JSON serialized snapshot and memory footprint per session.
* **Test Condition:** 100 sessions loaded with 10 active goals, full PAD affect, and pending actions.
* **Number of Runs:** 100 iterations.
* **Success Interpretation:** Mean payload size $\le 2,048$ bytes.
* **Failure Interpretation:** Payload $> 5$ KB indicates improper storage of deep episodic data in active workspace.
* **Hardware Dependency:** Apple Silicon Mac.

### BM-LOC-03: Percept Normalization Micro-benchmark
* **Hypothesis:** Converting heterogeneous incoming dictionary payloads into typed `PerceptEnvelope` objects incurs negligible CPU cost ($\le 100\ \mu\text{s}$ per event).
* **Baseline:** Direct dictionary key lookups.
* **Metric:** Execution time per normalization call ($\mu\text{s}$).
* **Test Condition:** 10,000 synthetic events across all 6 modalities (chat, vision, reflex, audio stop, ticks, playback progress).
* **Number of Runs:** 10,000 runs.
* **Success Interpretation:** p95 conversion latency $\le 100\ \mu\text{s}$.
* **Failure Interpretation:** p95 latency $> 500\ \mu\text{s}$ indicates heavy validation bottlenecks.
* **Hardware Dependency:** Apple Silicon Mac.

---

## 3. Remote GPU Benchmark Protocols (PENDING_GPU)

> [!IMPORTANT]
> The RTX 2060 Super 8 GB GPU server is offline today. These benchmarks are fully specified and will be executed tomorrow when the server is powered on and connected. No benchmark data will be fabricated.

### BM-GPU-01: End-to-End Cognitive Turn Latency on Live Ollama
* **Status:** `PENDING_GPU — server expected online tomorrow`
* **Hypothesis:** The end-to-end time to first text token (TTFT) through the full cognitive pipeline (including PerceptEnvelope normalization, workspace CAS read, decision commitment, and live Ollama generation) remains within 10 ms of the baseline pipeline on the RTX 2060 Super.
* **Baseline:** Commit `bb5be86` running `qwen2.5:3b` on Ollama (CUDA).
* **Metric:** TTFT (Time to First Token in milliseconds) and Total Turn Duration (ms).
* **Test Condition:** 15 standardized prompts (factual, emotional, and social conversational turns) with warm-up generation discarded.
* **Number of Runs:** 15 runs per condition (30 runs total: baseline vs candidate).
* **Success Interpretation:** Mean TTFT delta $\le 10$ ms; p95 TTFT delta $\le 20$ ms.
* **Failure Interpretation:** TTFT regression $> 25$ ms indicates synchronous blocking on workspace I/O inside the streaming loop.
* **Expected Hardware:** NVIDIA GeForce RTX 2060 Super (8 GB VRAM), Ollama v0.3.x, Linux kernel 6.x.

### BM-GPU-02: Acoustic Barge-In to OutcomeRecord Latency
* **Status:** `PENDING_GPU — server expected online tomorrow`
* **Hypothesis:** Emitting an `audio.stop` event during live audio synthesis and playback reliably halts generation, truncates assistant history in the conversation store, and logs an `OutcomeRecord(status='TRUNCATED')` with the exact character offset within $\le 50$ ms of signal arrival.
* **Baseline:** Legacy interruption path in `brain_agent.py` without structured `OutcomeRecord`.
* **Metric:** 
  1. Latency from `audio.stop` arrival to `OutcomeRecord` persistence (ms).
  2. Character offset precision: $| \text{recorded\_offset} - \text{actual\_playback\_offset} | == 0$.
* **Test Condition:** 10 mid-speech interruptions triggered at random intervals (between 1.0s and 3.0s into speech).
* **Number of Runs:** 10 runs.
* **Success Interpretation:** 100% of interrupted turns emit an `OutcomeRecord` with `status="TRUNCATED"` and exact offset; stop-to-record latency $\le 50$ ms.
* **Failure Interpretation:** Any turn failing to record an outcome, or character offset mismatching the playback progress marker.
* **Expected Hardware:** RTX 2060 Super server with active Rust `voice-agent` and LiveKit WebRTC pipeline.

### BM-GPU-03: 20-Turn Longitudinal State Stability & Drift
* **Status:** `PENDING_GPU — server expected online tomorrow`
* **Hypothesis:** Running 20 sequential turns on a single session monotonically increments `revision` from 1 to 20 without CAS conflict, while workspace snapshot size and resident memory remain stable.
* **Baseline:** Single-turn execution.
* **Metric:** Monotonicity of revisions ($r_{i+1} = r_i + 1$), zero CAS rejections, process RSS memory (MB).
* **Test Condition:** 20-turn scripted multi-turn conversation executed through NATS on the live GPU environment.
* **Number of Runs:** 20 turns in 1 session.
* **Success Interpretation:** Exactly 20 revisions committed; 0 spurious conflict retries; memory variance $\le 5\%$.
* **Failure Interpretation:** Non-monotonic revision numbers, lost state, or memory growth $> 10\%$.
* **Expected Hardware:** RTX 2060 Super server running full Docker mesh (`brain_agent`, `system_agent`, `subconscious_agent`, `stt-agent`, `voice-agent`).

---

## 4. Benchmark Execution Command Template (For Tomorrow)

```bash
# When server is online tomorrow:
ssh home-gpu "nvidia-smi"

# Run local benchmarks on Mac
cd backend
../.venv/bin/python -m pytest tests/test_workspace_store.py -k "benchmark" -q

# Run GPU benchmarks remotely
ssh home-gpu "cd AI_friend/backend && ../.venv/bin/python -m pytest tests/test_causal_slice.py --gpu -q"
```

