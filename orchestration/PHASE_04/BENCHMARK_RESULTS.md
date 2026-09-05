# Phase 04 Benchmark Results

Phase: PHASE_04
Date: 2026-09-04
Hardware Tested:
- Local Micro-benchmarks: Apple Silicon Mac (Python 3.13.15)
- Remote GPU Benchmarks: Dedicated Home GPU Server -- NVIDIA GeForce RTX 2060 Super 8GB VRAM (Ubuntu 24.04, Python 3.12.3, Ollama `qwen2.5:3b`)

---

## 1. Executive Summary

All 5 preregistered Phase 04 benchmarks passed their target criteria.
- Local micro-benchmarks confirmed that DomainCalibration evaluation latency is negligible (0.318 us mean vs target < 50.0 us), multi-person privacy isolation achieves 0.0% leakage across 1,000 queries, and background preemption executes instantly (< 0.05 ms vs target < 5.0 ms).
- Remote GPU benchmarks verified that end-to-end turn latency overhead with calibrated metacognition is bounded (+4.85 ms mean TTFT vs target <= 15.0 ms), and multi-turn social rupture/repair exhibits a 6.00x drop-to-gain ratio (exceeding the >= 2.0x target) with 100% stance trajectory adherence.

Overall Benchmark Verdict: **PASS**

---

## 2. Local Micro-Benchmarks (Apple Silicon)

### BM-LOC-P4-01: Calibration & Directive Evaluation Latency
- Description: 10,000 sequential evaluations through `DomainCalibration` and `CapabilityLimitationModel.evaluate_directive()`.
- Iterations: 10,000
- Mean Latency: 0.318 us (0.000318 ms)
- p50 Latency: 0.334 us
- p95 Latency: 0.416 us
- p99 Latency: 0.417 us
- Min Latency: 0.166 us
- Max Latency: 7.125 us
- Target: Mean latency < 50.0 us (< 0.05 ms)
- Verdict: **PASS**

### BM-LOC-P4-02: Multi-Person Privacy Isolation Verification
- Description: 1,000 synthetic disclosure queries across 10 simulated persons with private vs public facts testing `PersonModel.can_disclose()`.
- Total Queries: 1,000
- Simulated Persons: 10
- Leakage Occurrences: 0
- Measured Leakage Rate: 0.0000%
- Target: Strictly 0.0% cross-person leakage
- Verdict: **PASS**

### BM-LOC-P4-03: Background Preemption Latency
- Description: 500 preemption cycles testing cancellation latency upon simulated foreground arrival in `BackgroundScheduler`.
- Trials: 500
- Mean Latency: < 0.001 ms
- p50 Latency: < 0.001 ms
- p95 Latency: < 0.001 ms
- p99 Latency: < 0.001 ms
- Max Latency: 0.055 ms
- Target: p95 preemption latency < 5.0 ms
- Verdict: **PASS**

---

## 3. Remote GPU Benchmarks (NVIDIA RTX 2060 Super 8GB)

### BM-GPU-P4-01: End-to-End Latency Delta with Metacognition
- Model: `qwen2.5:3b` (FP16, Ollama runtime)
- Protocol: 15 standardized prompts; model unloaded and warmed up prior to both baseline and candidate measurements.
- Baseline Condition (Phase 03):
  - Mean TTFT: 23.39 ms
  - p95 TTFT: 26.15 ms
- Candidate Condition (Phase 04 with Metacognition & Privacy Filter):
  - Mean TTFT: 28.23 ms
  - p95 TTFT: 46.11 ms
- Measured Delays:
  - Mean TTFT Delta: +4.85 ms (Target: <= 15.0 ms)
  - p95 TTFT Delta: +19.96 ms
- Verdict: **PASS**

### BM-GPU-P4-02: Multi-Turn Social Rupture & Repair Trajectory
- Dialogue: 10 live conversational turns on RTX 2060 Super (`qwen2.5:3b`).
- Trajectory:
  - Initial Trust (Turns 1-3): 0.500 -> 0.506 (warm, open rapport)
  - Rupture Injected (Turn 4): Trust dropped to 0.206 (Drop: 0.300)
  - Cautious Dialogue (Turns 5-6): Stance held guarded, polite
  - Repair Injected (Turn 7): Trust recovered to 0.260 (Gain: 0.050)
  - Post-Repair Dialogue (Turns 8-10): Trust rose to 0.266
- Drop-to-Gain Ratio: 0.300 / 0.050 = 6.00x (Target: >= 2.0x per AC-P4-02)
- Trajectory Adherence: 100%
- Verdict: **PASS**

---

## 4. Benchmark Summary Table

| Benchmark ID | Title | Target Threshold | Measured Result | Verdict |
|---|---|---|---|---|
| **BM-LOC-P4-01** | Calibration & Directive Evaluation | Mean < 50.0 us | **0.318 us** | **PASS** |
| **BM-LOC-P4-02** | Multi-Person Privacy Isolation | 0.0% leakage | **0.0% (0 leaks)** | **PASS** |
| **BM-LOC-P4-03** | Background Preemption Latency | p95 < 5.0 ms | **< 0.001 ms** (max 0.055 ms) | **PASS** |
| **BM-GPU-P4-01** | Turn Latency Delta with Metacognition | Mean delta <= 15.0 ms | **+4.85 ms** | **PASS** |
| **BM-GPU-P4-02** | Social Rupture & Repair Trajectory | Drop-to-gain >= 2.0x | **6.00x** (100% adherence) | **PASS** |

