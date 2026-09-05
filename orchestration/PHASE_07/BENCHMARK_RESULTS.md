# Phase 07 Benchmark Results: Production Runtime Consolidation

**Environment:**
- Local: Apple Silicon (Darwin 24.6.0, Python 3.13)
- Remote GPU: NVIDIA GeForce RTX 2060 Super 8GB VRAM (Ubuntu Linux, Ollama v0.3.14)
- Runtime Models: `qwen2.5:3b`, `llama3.2:3b`
- Date: 2026-09-05

---

## 1. Executive Summary

Phase 07 validates the end-to-end consolidation of all Phase 01-06 runtime subsystems into `CognitiveService`, `BrainAgent`, and `ActionService`. All feature flags (`PHASE_02_MEMORY_TRUTH`, `PHASE_03_AFFECT_CONTROL`, `WORKSPACE_AUTHORITATIVE`, and `LEARNING_REVIEW_REQUIRED`) are active by default.

All 4 local micro-benchmarks and both remote GPU benchmarks achieve a **100% PASS** verdict with complete state continuity, zero boundary violations, and full conversational integrity.

| Benchmark ID | Name | Target | Measured | Verdict |
|---|---|---|---|---|
| **BM-LOC-P7-01** | Runtime Composition & Initial Deliberation Overhead | Mean < 5.0 ms | **2.63 ms** (p95: 4.23 ms) | **PASS** |
| **BM-LOC-P7-02** | Action Selection & WAIT Action Silence Fidelity | Latency < 1.0 ms, 100% silence | **0.89 us**, 100% silence (0 spoken chunks) | **PASS** |
| **BM-LOC-P7-03** | Epistemic Dream Quarantine Verification | 0 memories committed, 100% compliance | **0 committed**, 100% compliance | **PASS** |
| **BM-LOC-P7-04** | Governed Learning & Proposal Review Latency | Latency < 50.0 us, 100% rollback | **23.82 us**, 100% rollback fidelity | **PASS** |
| **BM-GPU-P7-01** | Composed Production Turn TTFT with Candidate Selection | Mean TTFT < 120.0 ms, p95 < 200.0 ms, State 100% | **Mean: 119.35 ms**, p95: 159.17 ms, Delib: 34.57 ms, State 100% | **PASS** |
| **BM-GPU-P7-02** | True Cross-Provider Behavioral Invariance | Adherence > 90.0%, 0 boundary violations | **100.0%** across qwen2.5 & llama3.2, 0 violations | **PASS** |

---

## 2. Local Micro-Benchmarks (Apple Silicon)

### BM-LOC-P7-01: Runtime Composition & Initial Deliberation Overhead
- **Target:** Verify instantiation of all Phase 1-6 subsystems and measure initial deliberation overhead on cold/warm cognitive events.
- **Iterations:** 1,000
- **Measurements:**
  - Mean Latency: `2.630 ms`
  - p50 Latency: `2.372 ms`
  - p95 Latency: `4.232 ms`
  - p99 Latency: `6.166 ms`
- **Verdict:** **PASS** (Threshold: mean < 5.0 ms)

### BM-LOC-P7-02: Action Selection & WAIT Action Silence Fidelity
- **Target:** Verify candidate action selection executes in sub-millisecond time and confirms selected `WAIT` candidate emits 0 speech tokens.
- **Iterations:** 1,000
- **Measurements:**
  - Mean Selection Latency: `0.89 us`
  - p50 Latency: `0.88 us`
  - p95 Latency: `0.92 us`
  - p99 Latency: `1.12 us`
  - Spoken Chunks Emitted: `0`
  - Silence Fidelity: `100.0%`
- **Verdict:** **PASS** (Threshold: latency < 1.0 ms, silence = 100%)

### BM-LOC-P7-03: Epistemic Dream Quarantine Verification
- **Target:** Verify subconscious dream sequence routes ungrounded dream events exclusively to working memory and dream queues, with 0 autobiographical commits.
- **Iterations:** 500
- **Measurements:**
  - Dream Memories Committed to MemoryStore: `0`
  - Quarantine Compliance: `100.0%`
- **Verdict:** **PASS** (Threshold: 0 commits, 100% compliance)

### BM-LOC-P7-04: Governed Learning & Reflection Proposal Review
- **Target:** Verify reflection trait mutations pass through `LearningGovernor` and verify 1-step rollback fidelity under simulated regression.
- **Iterations:** 1,000
- **Measurements:**
  - Mean Proposal Review Latency: `23.82 us`
  - p50 Latency: `19.71 us`
  - p95 Latency: `33.79 us`
  - p99 Latency: `40.71 us`
  - Rollback Failures: `0`
  - Rollback Fidelity: `100.0%`
- **Verdict:** **PASS** (Threshold: mean < 50.0 us, rollback = 100%)

---

## 3. Remote GPU Benchmarks (RTX 2060 Super 8GB)

### BM-GPU-P7-01: Composed Production Turn TTFT with Active Candidate Selection
- **Target Hardware:** NVIDIA GeForce RTX 2060 Super 8GB VRAM
- **Model:** `qwen2.5:3b` (Ollama runtime, context 2048)
- **Active Flags:** `PHASE_02_MEMORY_TRUTH=True`, `PHASE_03_AFFECT_CONTROL=True`, `WORKSPACE_AUTHORITATIVE=True`
- **Samples:** 10 live cognitive turns through full composed `CognitiveService`
- **Measurements:**
  - Turn 0: TTFT = `80.67 ms` | Total = `310.84 ms` | Delib = `41.10 ms` | Causal = True
  - Turn 1: TTFT = `124.54 ms` | Total = `530.82 ms` | Delib = `31.68 ms` | Causal = True
  - Turn 2: TTFT = `38.30 ms` | Total = `38.30 ms` | Delib = `33.13 ms` | Causal = True
  - Turn 3: TTFT = `80.21 ms` | Total = `732.05 ms` | Delib = `32.24 ms` | Causal = True
  - Turn 4: TTFT = `136.49 ms` | Total = `569.91 ms` | Delib = `32.87 ms` | Causal = True
  - Turn 5: TTFT = `141.12 ms` | Total = `475.90 ms` | Delib = `40.95 ms` | Causal = True
  - Turn 6: TTFT = `147.85 ms` | Total = `910.07 ms` | Delib = `30.81 ms` | Causal = True
  - Turn 7: TTFT = `145.43 ms` | Total = `932.32 ms` | Delib = `33.62 ms` | Causal = True
  - Turn 8: TTFT = `139.74 ms` | Total = `1392.32 ms` | Delib = `31.89 ms` | Causal = True
  - Turn 9: TTFT = `159.17 ms` | Total = `684.57 ms` | Delib = `37.40 ms` | Causal = True
  - **Mean TTFT:** `119.35 ms` (Target: < 120.0 ms)
  - **p95 TTFT:** `159.17 ms` (Target: < 200.0 ms)
  - **Mean Deliberation:** `34.57 ms`
  - **Mean Total Latency:** `657.71 ms`
  - **Causal ActionIntents Committed:** `10/10` (100.0%)
  - **Authoritative State Continuity:** `100% INTACT`
- **Verdict:** **PASS**

### BM-GPU-P7-02: True Cross-Provider Behavioral Invariance
- **Target:** Validate behavioral conformance, tone stability, and boundary enforcement across distinct model provider interfaces on identical persona prompts and state snapshots.
- **Models Evaluated:** `qwen2.5:3b`, `llama3.2:3b`
- **Probes:** 10 standardized probing prompts evaluating value adherence, tone consistency, and boundary enforcement.
- **Results:**
  - `qwen2.5:3b`: 40/40 checks passed (100.0% adherence, 0 boundary violations)
  - `llama3.2:3b`: 40/40 checks passed (100.0% adherence, 0 boundary violations)
  - Mean Adherence: `100.0%` (Target > 90.0%)
  - Total Boundary Violations: `0` (Target: 0)
- **Verdict:** **PASS**

---

## 4. Comprehensive 7-Stage System Validation Matrix

| Phase | Subsystem Focus | Local Micro-Benchmark Results | Remote GPU Benchmark Results (RTX 2060 Super) | Overall Verdict |
|---|---|---|---|---|
| **Phase 01** | Authoritative Causal Slice | CAS: `0.084 ms`, Snapshot: `950 B`, Percept: `2.16 us` | TTFT delta: `+0.3 ms`, Barge-in: `0.099 ms`, RSS var: `0.02%` | **PASS** |
| **Phase 02** | Memory Truth & Action Selection | Bi-temporal: `0.63 ms`, Contradiction: `0.08 ms`, Filter: `28 us` | TTFT delta: `+5.47 ms`, p95: `14.28 ms`, Accuracy: `100%`, RSS var: `0.12%` | **PASS** |
| **Phase 03** | Causal Affect & Global Control | Appraisal: `2.5 us`, Controls: `1.3 us`, Selection: `12.8 us` | TTFT delta: `+0.11 ms`, p95: `19.25 ms`, Regulation: `100%`, RSS var: `0.03%` | **PASS** |
| **Phase 04** | Metacognition & Background Work | Calibration: `0.33 us`, Isolation: `0% leak`, Preemption: `< 1 us` | TTFT delta: `-12.44 ms`, Rupture Drop-to-Gain: `6.00x` | **PASS** |
| **Phase 05** | Provider & Embodiment Portability | Voice: `3.5 us`, Vision: `10.1 us`, Risk Gate: `100% block` | SpeechIntent compile: `0.071 ms`, `0% leak`, State: `100% intact` | **PASS** |
| **Phase 06** | Advanced Learning & Planning | Soundness: `100%`, Quarantine: `100%`, Rollback: `100%` | Deliberative TTFT: `30.16 ms`, Adapter Gate: `100% qualified/blocked` | **PASS** |
| **Phase 07** | Production Runtime Consolidation | Composition: `2.63 ms`, WAIT silence: `100%`, Dream quarantine: `100%` | Composed TTFT: `119.35 ms`, p95: `159.17 ms`, Cross-Provider Invariance: `100%` adherence, `0` violations | **PASS** |
