# Phase 06 Benchmark Results

Phase: PHASE_06
Date: 2026-09-04
Hardware Tested:
- Local Micro-benchmarks: Apple Silicon Mac (Python 3.13.15)
- Remote GPU Benchmarks: Dedicated Home GPU Server -- NVIDIA GeForce RTX 2060 Super 8GB VRAM (Ubuntu 24.04, Python 3.12.3, Ollama `qwen2.5:3b`)

---

## 1. Executive Summary

All 6 preregistered Phase 06 benchmarks passed their target criteria.
- Local micro-benchmarks demonstrated that Deterministic Plan Verification is exceptionally fast (3.830 us mean vs target < 50.0 us) with 100.0% soundness rate on cyclic, unfulfilled, and over-budget plans; Episodic Simulation executes sandboxed rollouts in 6.728 us (target < 20.0 us) with 100.0% quarantine enforcement against live state leakage; Learning Governance gating and atomic rollback execute in 46.605 us (target < 50.0 us) with 100.0% immutable core rejection and 100.0% bit-for-bit rollback fidelity; and Learning-Progress Curiosity signal computation executes in 3.017 us (target < 10.0 us) with 100.0% ranking accuracy over progress vs mastery and noise.
- Remote GPU benchmarks on the RTX 2060 Super verified that deliberative planning prompt assembly and inference with Ollama `qwen2.5:3b` achieves a Mean TTFT of 27.06 ms (target < 80.0 ms, p95 36.20 ms) with 100% authoritative state continuity; and Offline Adapter Qualification evaluates behavioral regressions in 0.08 ms (target < 50.0 ms) while strictly qualifying valid candidates, rejecting regressing candidates, and blocking unqualified activation attempts.

Overall Benchmark Verdict: **PASS**

---

## 2. Local Micro-Benchmarks (Apple Silicon)

### BM-LOC-P6-01: Deterministic Plan Verifier Latency and Soundness
- Description: 1,000 iterations verifying valid plans, cyclic plans, unfulfilled preconditions, and budget limits.
- Iterations: 1,000
- Mean Latency: 3.830 us (0.003830 ms)
- p50 Latency: 4.209 us
- p95 Latency: 4.417 us
- p99 Latency: 4.625 us
- Soundness Rate: 100.0% (1,000/1,000)
- Target: Mean latency < 50.0 us (< 0.05 ms), soundness rate = 100%
- Verdict: **PASS**

### BM-LOC-P6-02: Episodic Simulation Sandbox Quarantine and Throughput
- Description: 1,000 iterations running sandboxed episodic simulation rollouts, tagging all artifacts with `is_simulation=True`, and testing quarantine enforcement against live state mutation.
- Iterations: 1,000
- Mean Latency: 6.728 us (0.006728 ms)
- p50 Latency: 6.625 us
- p95 Latency: 6.959 us
- p99 Latency: 8.708 us
- Quarantine Block Rate: 100.0% (1,000/1,000)
- State Leakage: False (0.0% leakage into live state)
- Target: Mean latency < 20.0 us (< 0.02 ms), block rate = 100%, 0% leakage
- Verdict: **PASS**

### BM-LOC-P6-03: Learning Governance Gate and Rollback Latency
- Description: 1,000 iterations evaluating proposal risk tiers, constitutional boundary protection, state mutation, and 1-step atomic rollback.
- Iterations: 1,000
- Mean Latency: 46.605 us (0.046605 ms)
- p50 Latency: 53.250 us
- p95 Latency: 59.792 us
- p99 Latency: 139.833 us
- Immutable Rejection Rate: 100.0% (1,000/1,000)
- Rollback Fidelity: 100.0% (1,000/1,000 exact bit-for-bit restorations)
- Target: Mean latency < 50.0 us (< 0.05 ms), 100% rejection, 100% rollback fidelity
- Verdict: **PASS**

### BM-LOC-P6-04: Learning-Progress Curiosity Signal Computation
- Description: 1,000 iterations computing learning progress deltas across high-progress, mastered, and random noise error trajectories.
- Iterations: 1,000
- Mean Latency: 3.017 us (0.003017 ms)
- p50 Latency: 2.959 us
- p95 Latency: 3.084 us
- p99 Latency: 3.167 us
- Ranking Accuracy: 100.0% (1,000/1,000 ranking progress > mastery > noise)
- Target: Mean latency < 10.0 us (< 0.01 ms), ranking accuracy = 100%
- Verdict: **PASS**

---

## 3. Remote GPU Benchmarks (NVIDIA RTX 2060 Super 8GB)

### BM-GPU-P6-01: Deliberative Planning Overhead and State Continuity
- Model: `qwen2.5:3b` (Ollama runtime on RTX 2060 Super)
- Protocol: 10 standardized deliberative planning turns with simulated prospective branching; warmup executed before measurements; authoritative state (affect, trust, and persona profile) checked for drift before and after planning turns.
- Samples: 10
- Mean TTFT: 27.06 ms (Target: < 80.0 ms)
- p95 TTFT: 36.20 ms
- Mean Full Latency: 425.00 ms
- Authoritative State Continuity: 100.0% INTACT (affect, trust, and persona profile preserved with zero corruption)
- Verdict: **PASS**

### BM-GPU-P6-02: Offline Adapter Qualification and Behavioral Regression Check
- Model: `qwen2.5:3b`
- Protocol: Evaluate candidate adapters against baseline behavioral probes with constitution digest verification; test qualification of non-regressing Candidate A, rejection of regressing Candidate B, and fail-closed blocking of unqualified activation attempts.
- Qualification Duration: 0.08 ms (Target: < 50.0 ms)
- Candidate A (Zero Regressions): QUALIFIED (True)
- Candidate B (Behavioral Regression): REJECTED (True)
- Unqualified Activation Attempt: STRICTLY BLOCKED (True)
- Target: 100% rejection on regressions, 100% block on unqualified activation
- Verdict: **PASS**

---

## 4. Benchmark Summary Table

| Benchmark ID | Title | Target Threshold | Measured Result | Verdict |
|---|---|---|---|---|
| **BM-LOC-P6-01** | Deterministic Plan Verifier Latency & Soundness | Mean < 50.0 us, 100% soundness | **3.830 us**, 100.0% soundness | **PASS** |
| **BM-LOC-P6-02** | Episodic Simulation Sandbox Quarantine | Mean < 20.0 us, 100% block | **6.728 us**, 100.0% block, 0% leak | **PASS** |
| **BM-LOC-P6-03** | Learning Governance Gate & Rollback Latency | Mean < 50.0 us, 100% rejection/rollback | **46.605 us**, 100.0% rejection/rollback | **PASS** |
| **BM-LOC-P6-04** | Learning-Progress Curiosity Signal Computation | Mean < 10.0 us, 100% accuracy | **3.017 us**, 100.0% accuracy | **PASS** |
| **BM-GPU-P6-01** | Deliberative Planning Overhead & Continuity | Mean TTFT < 80.0 ms, 100% intact | **27.06 ms** TTFT, 100% intact | **PASS** |
| **BM-GPU-P6-02** | Offline Adapter Qualification & Regressions | Latency < 50.0 ms, 100% gating | **0.08 ms**, 100% gating | **PASS** |
