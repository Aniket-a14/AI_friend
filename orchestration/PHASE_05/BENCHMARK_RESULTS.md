# Phase 05 Benchmark Results

Phase: PHASE_05
Date: 2026-09-04
Hardware Tested:
- Local Micro-benchmarks: Apple Silicon Mac (Python 3.13.15)
- Remote GPU Benchmarks: Dedicated Home GPU Server -- NVIDIA GeForce RTX 2060 Super 8GB VRAM (Ubuntu 24.04, Python 3.12.3, Ollama `llama3.2:3b` and `qwen2.5:3b`)

---

## 1. Executive Summary

All 6 preregistered Phase 05 benchmarks passed their target criteria.
- Local micro-benchmarks confirmed that Voice Compiler throughput is exceptionally high (3.448 us mean vs target < 50.0 us) with 100.0% loss/substitution telemetry capture; Vision normalization into PerceptEnvelope executes in 10.155 us with strictly 0.0% corruption of brain affect/trust invariants; ModelRole capability negotiation executes in 0.262 us (target < 10.0 us); and ExternalAction risk/authorization gating achieves 100.0% block rate on unauthorized high-risk requests with 0.137 us evaluation latency.
- Remote GPU benchmarks on the RTX 2060 Super verified that swapping foundation model providers between `llama3.2:3b` and `qwen2.5:3b` exhibits a bounded TTFT delta of only 2.88 ms (target <= 25.0 ms) while maintaining 100% authoritative state continuity; and end-to-end SpeechIntent voice compilation executes in 0.085 ms (target < 5.0 ms) with strictly 0.0% provider tags leaked into the cognitive workspace.

Overall Benchmark Verdict: **PASS**

---

## 2. Local Micro-Benchmarks (Apple Silicon)

### BM-LOC-P5-01: Voice Compiler Throughput & Loss Telemetry
- Description: 1,000 iterations compiling rich SpeechIntent across ElevenLabsVoiceCompiler and GPTSoVITSVoiceCompiler.
- Iterations: 1,000
- Mean Latency: 3.448 us (0.003448 ms)
- p50 Latency: 3.417 us
- p95 Latency: 3.667 us
- p99 Latency: 5.125 us
- Telemetry Capture Rate: 100.0% (1,000/1,000)
- Target: Mean latency < 50.0 us (< 0.05 ms), capture rate = 100%
- Verdict: **PASS**

### BM-LOC-P5-02: Vision Adapter Normalization & Invariant Check
- Description: 1,000 visual inputs processed across VLMCaptionVisionAdapter and SpatialTrackingVisionAdapter, converting to PerceptEnvelope.
- Iterations: 1,000
- Mean Latency: 10.155 us (0.010155 ms)
- p50 Latency: 10.750 us
- p95 Latency: 11.333 us
- p99 Latency: 15.541 us
- Brain Invariant Corruption Rate: 0.0% (0 occurrences)
- Target: Mean latency < 50.0 us (< 0.05 ms), 0% corruption
- Verdict: **PASS**

### BM-LOC-P5-03: Model Role Capability Negotiation Latency
- Description: 1,000 capability checks across all 6 ModelRoles and synthetic capability profiles.
- Iterations: 1,000
- Mean Latency: 0.262 us (0.000262 ms)
- p50 Latency: 0.250 us
- p95 Latency: 0.292 us
- p99 Latency: 0.334 us
- Target: Mean latency < 10.0 us (< 0.01 ms)
- Verdict: **PASS**

### BM-LOC-P5-04: External Action Risk & Authorization Gating
- Description: 1,000 action requests evaluated across low, high, and critical risk levels and reversibility.
- Iterations: 1,000
- Mean Latency: 0.137 us (0.000137 ms)
- p50 Latency: 0.125 us
- p95 Latency: 0.167 us
- p99 Latency: 0.209 us
- Unauthorized High-Risk Block Rate: 100.0% (500/500 blocked)
- Target: Mean latency < 10.0 us (< 0.01 ms), block rate = 100%
- Verdict: **PASS**

---

## 3. Remote GPU Benchmarks (NVIDIA RTX 2060 Super 8GB)

### BM-GPU-P5-01: Model Provider Swap TTFT Delta & Continuity
- Models: `llama3.2:3b` and `qwen2.5:3b` (Ollama runtime on RTX 2060 Super)
- Protocol: 10 standardized prompts per model; warmup executed before measurements; ModelRole.REALIZATION capability negotiated; authoritative state (affect and PersonModel) checked for drift.
- Model 1 (`llama3.2:3b`) Mean TTFT: 32.10 ms
- Model 2 (`qwen2.5:3b`) Mean TTFT: 29.22 ms
- Measured TTFT Delta: 2.88 ms (Target: <= 25.0 ms)
- Authoritative State Continuity: 100.0% INTACT (trust competence: 0.82, benevolence: 0.78, valence: 0.25)
- Verdict: **PASS**

### BM-GPU-P5-02: SpeechIntent Compilation & Isolation
- Protocol: Real GPU generation via Ollama (`qwen2.5:3b`), assembled into SpeechIntent, compiled through both voice compilers, checked against cognitive workspace snapshot.
- Compilation Calls: 10 (5 turns x 2 compilers)
- Mean Voice Compilation Latency: 0.085 ms (Target: < 5.0 ms)
- Provider Tag Leak into Workspace: 0.0% (0 tags found in workspace snapshot)
- Verdict: **PASS**

---

## 4. Benchmark Summary Table

| Benchmark ID | Title | Target Threshold | Measured Result | Verdict |
|---|---|---|---|---|
| **BM-LOC-P5-01** | Voice Compiler Throughput & Loss Telemetry | Mean < 50.0 us, 100% capture | **3.448 us**, 100.0% capture | **PASS** |
| **BM-LOC-P5-02** | Vision Normalization & Invariant Check | Mean < 50.0 us, 0% corruption | **10.155 us**, 0.0% corruption | **PASS** |
| **BM-LOC-P5-03** | Model Role Capability Negotiation Latency | Mean < 10.0 us | **0.262 us** | **PASS** |
| **BM-LOC-P5-04** | External Action Risk & Authorization Gating | Mean < 10.0 us, 100% block | **0.137 us**, 100.0% block | **PASS** |
| **BM-GPU-P5-01** | Provider Swap TTFT Delta & Continuity | TTFT delta <= 25.0 ms, 100% invariant | **2.88 ms** delta, 100% invariant | **PASS** |
| **BM-GPU-P5-02** | SpeechIntent Compilation & Isolation | Latency < 5.0 ms, 0% leak | **0.085 ms**, 0.0% leak | **PASS** |
