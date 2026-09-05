# Phase 02: Empirical Benchmark Results & Validation Report

**Phase Identifier:** `PHASE_02` -- Memory Truth and General Action Selection  
**Target Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (Sections 8, 11, 22, and 39)  
**Evaluator:** Orchestrator (Gemini / Antigravity)  
**Execution Date:** 2026-09-04  
**Git Baseline Commit:** `5fd816f75e84a1c1605cecff08477df8356d21a9`  
**Git Candidate Commit:** `df49f51` (`integration/phase-02`)  
**Overall Benchmark Verdict:** **ALL BENCHMARKS PASSED (5/5 PASS)**

---

## 1. Hardware & Runtime Provenance

* **Local Environment:** Apple Silicon Mac (ARM64), Darwin kernel, Python 3.13.15, SQLite 3.x in WAL mode.
* **Remote GPU Server (`home-gpu`):**
  * **GPU:** NVIDIA GeForce RTX 2060 Super (8,192 MiB VRAM)
  * **Driver:** 595.84 | **CUDA:** 13.2 | **PyTorch:** 2.13.0+cu130
  * **Inference Runtime:** Ollama v0.3.x (`http://127.0.0.1:11434`)
  * **LLM Model:** `qwen2.5:3b` (Q4_K_M quantization, 3.1B parameters, 32k context)
  * **Infrastructure Services:** Redis 7, pgvector PG16, NATS JetStream 2.10.24, Qdrant v1.9.0, Neo4j 5.26.0, LiveKit SFU.

---

## 2. Local Micro-Benchmarks (Mac ARM64)

### BM-LOC-P2-01: Bi-temporal Query Throughput
* **Protocol:** 1,000 sequential `as_of` queries executed against `TemporalMemoryStore` seeded with 1,000 historical beliefs (closed and open validity intervals).
* **Hypothesis / Target:** p50 latency $\le 1.0$ ms, p95 latency $\le 2.0$ ms.
* **Empirical Results:**
  * Queries Executed: 1,000
  * Mean Latency: **0.6343 ms** ($634.3\ \mu\text{s}$)
  * p50 Latency: **0.6270 ms** ($627.0\ \mu\text{s}$)
  * p95 Latency: **1.1373 ms** ($1,137.3\ \mu\text{s}$)
  * p99 Latency: **1.2507 ms** ($1,250.7\ \mu\text{s}$)
  * Min / Max: 0.0750 ms / 2.1680 ms
* **Verdict:** **PASS** (Bi-temporal queries evaluate validity intervals in ~0.6 ms on SQLite).

### BM-LOC-P2-02: Contradiction Transition Latency
* **Protocol:** 1,000 sequential atomic contradiction transitions distributed across UPDATE, CORRECTION, CONFLICT, and ELABORATION on `TemporalMemoryStore`.
* **Hypothesis / Target:** p50 latency $\le 1.5$ ms, p95 latency $\le 3.0$ ms.
* **Empirical Results:**
  * Transitions Executed: 1,000
  * Mean Latency: **0.0825 ms** ($82.5\ \mu\text{s}$)
  * p50 Latency: **0.0796 ms** ($79.6\ \mu\text{s}$)
  * p95 Latency: **0.0998 ms** ($99.8\ \mu\text{s}$)
  * p99 Latency: **0.1200 ms** ($120.0\ \mu\text{s}$)
  * Min / Max: 0.0622 ms / 0.3195 ms
* **Verdict:** **PASS** (Contradiction transitions execute atomically in sub-100 microseconds).

### BM-LOC-P2-03: Constraint-First Filter Latency
* **Protocol:** 10,000 iterations filtering 10 action candidates against 20 forbidden boundary claims through `CandidateSelector.filter_constraints`.
* **Hypothesis / Target:** p95 latency $\le 50.0\ \mu\text{s}$.
* **Empirical Results:**
  * Iterations Measured: 10,000
  * Candidates per Iteration: 10
  * Forbidden Claims Evaluated: 20
  * Mean Latency: **24.71 $\mu\text{s}$**
  * p50 Latency: **24.46 $\mu\text{s}$**
  * p95 Latency: **25.71 $\mu\text{s}$**
  * p99 Latency: **30.79 $\mu\text{s}$**
  * Min / Max: 22.79 $\mu\text{s}$ / 46.38 $\mu\text{s}$
* **Verdict:** **PASS** (Word-boundary phrase matching with substring pre-filtering runs in ~25 microseconds per 10 candidates).

---

## 3. Remote GPU Benchmarks (RTX 2060 Super 8GB)

### BM-GPU-P2-01: End-to-End Turn Latency with Memory Truth (Live Ollama `qwen2.5:3b`)
* **Protocol:** 15 standardized conversational prompts evaluated across Baseline (Phase 1 turn) and Candidate (Phase 2 turn with bi-temporal retrieval, `MemoryActivation`, `CandidateSelector` constraint filtering, and CAS commit) against live `qwen2.5:3b`.
* **Hypothesis / Target:** Mean TTFT delta $\le 10.0$ ms; p95 TTFT delta $\le 20.0$ ms.
* **Empirical Results:**
  * Prompts Evaluated: 15
  * Baseline Mean TTFT: **175.04 ms** (Baseline Total: 860.71 ms)
  * Candidate Mean TTFT: **146.08 ms** (Candidate Total: 811.05 ms)
  * **Mean TTFT Delta:** **-28.96 ms** (Target: $\le 10.0$ ms)
  * **p50 TTFT Delta:** **-5.18 ms**
  * **p95 TTFT Delta:** **+1.86 ms** (Target: $\le 20.0$ ms)
  * **p99 TTFT Delta:** **+1.86 ms**
* **Verdict:** **PASS** (Adding memory truth and action selection introduces no perceptible TTFT degradation; candidate selection and constraint filtering execute well within the prompt assembly window).

### BM-GPU-P2-02: Multi-Turn Memory Truth Live Soak Test
* **Protocol:** 20 consecutive live conversational turns executed against Ollama with intermediate belief contradiction transitions (Turn 1: Seattle; Turn 6: UPDATE to Tokyo; Turn 11: CORRECTION to Kyoto; Turn 16: NEW SLOT job=architect). Tracks factual truth, CAS conflicts, and process memory RSS.
* **Hypothesis / Target:** 100% accurate fact resolution, 0 CAS conflicts, process memory variance $\le 5.0\%$.
* **Empirical Results:**
  * Turns Executed: 20 / 20
  * Fact Checks Passed: 20 / 20 (**100.0% Accuracy**)
  * Spurious CAS Conflicts: **0**
  * Initial VmRSS: 145,850,368 KB (139.09 MB)
  * Final VmRSS: 145,850,368 KB (139.09 MB)
  * **RSS Memory Variance:** **0.0%** (Delta: 0 KB over 20 turns; Target: $\le 5.0\%$)
* **Verdict:** **PASS** (Belief updates, corrections, and additions resolve with 100% accuracy and perfectly flat process memory).

---

## 4. Summary Scorecard

| ID | Title | Environment | Metric | Threshold | Result | Verdict |
|---|---|---|---|---|---|---|
| **BM-LOC-P2-01** | Bi-temporal Query Throughput | Local Mac | p95 Latency | $\le 2.0$ ms | **1.14 ms** | **PASS** |
| **BM-LOC-P2-02** | Contradiction Transition Latency | Local Mac | p95 Latency | $\le 3.0$ ms | **0.10 ms** | **PASS** |
| **BM-LOC-P2-03** | Constraint-First Filter Latency | Local Mac | p95 Latency | $\le 50.0\ \mu\text{s}$ | **25.71 $\mu\text{s}$** | **PASS** |
| **BM-GPU-P2-01** | E2E Turn Latency with Memory Truth | GPU Server | Mean / p95 TTFT $\Delta$ | $\le 10$ ms / $\le 20$ ms | **-28.96 ms / +1.86 ms** | **PASS** |
| **BM-GPU-P2-02** | Multi-Turn Memory Truth Live Soak | GPU Server | Fact Accuracy & RSS Var | 100% / $\le 5.0\%$ | **100.0% / 0.0%** | **PASS** |

