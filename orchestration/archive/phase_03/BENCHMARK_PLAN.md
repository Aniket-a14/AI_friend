# Phase 03: Benchmark Plan & Measurement Protocol

Phase: PHASE_03 -- Causal Affect and Global Control
Target Hardware (GPU): NVIDIA GeForce RTX 2060 Super (8 GB VRAM, Home GPU Server)
Target Hardware (Local): Apple Silicon Mac (ARM64 Development Environment)
Evaluation Stage: Scheduled for Phase 03 integration

---

## 1. Benchmark Suite Summary

| ID | Title | Environment | Target Metric | Success Threshold |
|---|---|---|---|---|
| **BM-LOC-P3-01** | Event Appraisal Throughput | Local Mac | Latency per appraisal | p95 <= 20.0 us |
| **BM-LOC-P3-02** | Global Controls Derivation Latency | Local Mac | Derivation time in microseconds | p95 <= 10.0 us |
| **BM-LOC-P3-03** | Modulated Candidate Selection | Local Mac | Latency per 10 candidates with controls | p95 <= 50.0 us |
| **BM-GPU-P3-01** | E2E Turn Latency with Causal Affect | GPU Server | TTFT delta on live qwen2.5:3b | Mean delta <= 10.0 ms, p95 delta <= 20.0 ms |
| **BM-GPU-P3-02** | Multi-Turn Regulation & Soak Test | GPU Server | 20-turn regulation selection and VmRSS | 100% regulation trigger, RSS variance <= 5.0% |

---

## 2. Local Mac Benchmark Protocols

### BM-LOC-P3-01: Event Appraisal Throughput
* **Hypothesis:** Structured appraisal mapping `(event, active_goals, expectation)` to `AppraisalRecord` completes within sub-20 microseconds.
* **Test Condition:** 10,000 sequential event evaluations through `appraise_event`.
* **Metric:** Execution time in microseconds.
* **Threshold:** p50 <= 10.0 us, p95 <= 20.0 us.

### BM-LOC-P3-02: Global Controls Derivation Latency
* **Hypothesis:** Deriving the 4 bounded global controls from PAD affect, load, urgency, and prediction error takes negligible CPU time.
* **Test Condition:** 10,000 iterations of `derive_global_controls`.
* **Metric:** Execution time in microseconds.
* **Threshold:** p50 <= 5.0 us, p95 <= 10.0 us.

### BM-LOC-P3-03: Modulated Candidate Selection Latency
* **Hypothesis:** Scoring and selecting among 10 candidates with active global controls modulation runs within 50 microseconds.
* **Test Condition:** 10,000 iterations through `CandidateSelector.score_and_select(..., global_controls=...)`.
* **Metric:** Execution time in microseconds.
* **Threshold:** p95 <= 50.0 us.

---

## 3. Remote GPU Benchmark Protocols (RTX 2060 Super 8GB)

### BM-GPU-P3-01: End-to-End Turn Latency with Causal Affect (Live Ollama qwen2.5:3b)
* **Hypothesis:** Integrating appraisal, global controls derivation, and modulated candidate selection adds <= 10.0 ms mean TTFT overhead to a baseline turn.
* **Test Condition:** 15 standardized conversational prompts evaluated with Phase 3 affect control active vs baseline.
* **Metric:** TTFT (Time to First Token in milliseconds) and Total Turn Duration (ms).
* **Threshold:** Mean TTFT delta <= 10.0 ms, p95 TTFT delta <= 20.0 ms.

### BM-GPU-P3-02: Multi-Turn Regulation & Soak Test
* **Hypothesis:** Under induced distress turns, the agent selects regulation actions (`REAPPRAISE`, `REDIRECT_ATTENTION`), returns to baseline affect, and maintains flat process memory.
* **Test Condition:** 20 scripted live turns against Ollama with distress injections at turns 5 and 12.
* **Metric:** Regulation selection accuracy (100% when distressed), affect mean reversion, VmRSS variance <= 5.0%.
* **Threshold:** 100% regulation accuracy on distress turns, RSS variance <= 5.0%.

