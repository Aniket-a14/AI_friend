# Phase 02: Benchmark Plan & Measurement Protocol

**Phase:** `PHASE_02` -- Memory Truth and General Action Selection
**Target Hardware (GPU):** NVIDIA GeForce RTX 2060 Super (8 GB VRAM, Home GPU Server)
**Target Hardware (Local):** Apple Silicon Mac (ARM64 Development Environment)
**Evaluation Stage:** Scheduled for Phase 02 integration

---

## 1. Benchmark Suite Summary

| ID | Title | Environment | Target Metric | Success Threshold |
|---|---|---|---|---|
| **BM-LOC-P2-01** | Bi-temporal Query Throughput | Local Mac | As-of query latency | p95 $\le 2.0$ ms |
| **BM-LOC-P2-02** | Contradiction Transition Latency | Local Mac | Atomic state transition time | p95 $\le 3.0$ ms |
| **BM-LOC-P2-03** | Constraint-First Filter Latency | Local Mac | Microseconds per 10 candidates | p95 $\le 50.0\ \mu\text{s}$ |
| **BM-GPU-P2-01** | E2E Turn Latency with Memory Truth | GPU Server | TTFT delta on live `qwen2.5:3b` | Mean delta $\le 10.0$ ms, p95 $\le 20.0$ ms |
| **BM-GPU-P2-02** | Multi-Turn Memory Truth Soak | GPU Server | 20-turn truth resolution & memory RSS | 100% accurate truth, RSS variance $\le 5.0\%$ |

---

## 2. Local Mac Benchmark Protocols

### BM-LOC-P2-01: Bi-temporal Query Throughput
* **Hypothesis:** Evaluating bi-temporal validity intervals (`valid_from <= t < valid_until`) on indexed SQLite tables adds $\le 1.0$ ms p50 and $\le 2.0$ ms p95 overhead per retrieval query.
* **Test Condition:** 1,000 sequential as-of queries across a database seeded with 1,000 historical beliefs.
* **Metric:** Query execution time in milliseconds.
* **Threshold:** p50 $\le 1.0$ ms, p95 $\le 2.0$ ms.

### BM-LOC-P2-02: Contradiction Transition Latency
* **Hypothesis:** Atomic execution of contradiction transitions (closing old validity interval + inserting new active belief record) completes within $\le 3.0$ ms p95.
* **Test Condition:** 1,000 sequential transitions distributed evenly across UPDATE, CORRECTION, CONFLICT, and ELABORATION.
* **Metric:** Transition latency in milliseconds.
* **Threshold:** p50 $\le 1.5$ ms, p95 $\le 3.0$ ms.

### BM-LOC-P2-03: Constraint-First Filter Latency
* **Hypothesis:** Filtering 10 action candidates against 20 forbidden boundary claims takes negligible CPU time.
* **Test Condition:** 10,000 iterations of candidate set filtering through `CandidateSelector.filter_constraints`.
* **Metric:** Execution time in microseconds.
* **Threshold:** p95 $\le 50.0\ \mu\text{s}$.

---

## 3. Remote GPU Benchmark Protocols (RTX 2060 Super 8GB)

### BM-GPU-P2-01: End-to-End Turn Latency with Memory Truth (Live Ollama `qwen2.5:3b`)
* **Hypothesis:** Generating action candidates, filtering hard constraints, retrieving activated memories, and committing `ActionIntent` maintains TTFT within 10 ms of the baseline turn.
* **Test Condition:** 15 standardized prompts evaluated with memory truth active vs Phase 1 baseline.
* **Metric:** TTFT (Time to First Token in milliseconds) and Total Turn Duration (ms).
* **Threshold:** Mean TTFT delta $\le 10.0$ ms, p95 TTFT delta $\le 20.0$ ms.

### BM-GPU-P2-02: Multi-Turn Memory Truth Live Soak Test
* **Hypothesis:** Running a 20-turn live conversation where user facts evolve (e.g. user updates their job, favorite beverage, weekend plans) resolves current facts correctly, preserves historical auditability, and exhibits flat process memory.
* **Test Condition:** 20 scripted turns against live Ollama on RTX 2060 Super with intermediate contradiction updates.
* **Metric:** Fact resolution accuracy (100%), 0 spurious stale-write conflicts, process VmRSS variance $\le 5.0\%$.
* **Threshold:** 20/20 turns accurate, RSS variance $\le 5.0\%$.

