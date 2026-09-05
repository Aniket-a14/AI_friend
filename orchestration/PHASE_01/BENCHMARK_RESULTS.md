# Phase 01: Empirical Benchmark Results & Validation Report

**Phase Identifier:** `PHASE_01` -- Authoritative Causal Slice  
**Target Reference:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` (Sections 38 and 39)  
**Evaluator:** Orchestrator (Gemini / Antigravity)  
**Execution Date:** 2026-09-04  
**Git Baseline Commit:** `bb5be86ba7c14ab7f8afa056707597a37d3bdd86`  
**Git Candidate Commit:** `e70499c` (`integration/phase-01`)  
**Overall Benchmark Verdict:** **ALL BENCHMARKS PASSED (6/6 PASS)**

---

## 1. Hardware & Runtime Provenance

* **Local Environment:** Apple Silicon Mac (ARM64), Darwin kernel, Python 3.13.15, SQLite 3.x in WAL mode.
* **Remote GPU Server (`home-gpu`):**
  * **GPU:** NVIDIA GeForce RTX 2060 Super (8,192 MiB VRAM)
  * **Driver:** 595.84 | **CUDA:** 13.2 | **PyTorch:** 2.13.0+cu130
  * **Inference Runtime:** Ollama v0.3.x (`http://127.0.0.1:11434`)
  * **LLM Model:** `qwen2.5:3b` (Q4_K_M quantization, 3.1B parameters, 32k context)
  * **Infrastructure Services:** Redis 7, pgvector PG16, NATS JetStream 2.10.24, Qdrant v1.9.0, Neo4j 5.26.0, LiveKit SFU, GPT-SoVITS.

---

## 2. Local Micro-Benchmarks (Mac ARM64)

### BM-LOC-01: Workspace CAS Commit Overhead
* **Protocol:** 5 iterations of 1,000 sequential commits on SQLite (5,000 total transitions) with WAL mode enabled.
* **Hypothesis / Target:** p50 latency $\le 3.0$ ms, p95 latency $\le 5.0$ ms.
* **Empirical Results:**
  * Total Commits: 5,000
  * Mean Latency: **0.0942 ms** ($94.2\ \mu\text{s}$)
  * p50 Latency: **0.0862 ms** ($86.2\ \mu\text{s}$)
  * p95 Latency: **0.1321 ms** ($132.1\ \mu\text{s}$)
  * p99 Latency: **0.2045 ms** ($204.5\ \mu\text{s}$)
  * Min / Max: 0.0693 ms / 0.5256 ms
* **Verdict:** **PASS** (Commit overhead is 35x below the 5.0 ms p95 threshold).

### BM-LOC-02: Snapshot Serialization & Memory Budget
* **Protocol:** 100 sessions loaded with 10 active goals, full PAD affect, focus string, and pending actions serialized to JSON.
* **Hypothesis / Target:** Mean serialized byte size $\le 2,048$ bytes.
* **Empirical Results:**
  * Sessions Measured: 100
  * Mean Payload Size: **949.99 bytes**
  * Min / Max Payload Size: 947 bytes / 951 bytes
* **Verdict:** **PASS** (Mean payload size is well within the 2 KB limit, preventing active context bloat).

### BM-LOC-03: Percept Normalization Micro-benchmark
* **Protocol:** 10,000 synthetic events normalized across all 6 modalities (`chat.input`, `vision.description`, `vision.facial_reflex`, `audio.stop`, `system.tick`, `audio.playback.progress`).
* **Hypothesis / Target:** p95 normalization latency $\le 100.0\ \mu\text{s}$.
* **Empirical Results:**
  * Total Events: 10,000
  * Mean Latency: **2.21 $\mu\text{s}$**
  * p50 Latency: **2.38 $\mu\text{s}$**
  * p95 Latency: **2.75 $\mu\text{s}$**
  * p99 Latency: **3.08 $\mu\text{s}$**
  * Min / Max: 0.79 $\mu\text{s}$ / 51.75 $\mu\text{s}$
* **Verdict:** **PASS** (Percept normalization is 36x faster than the 100 $\mu\text{s}$ threshold).

---

## 3. Remote GPU Benchmarks (RTX 2060 Super 8GB)

### BM-GPU-01: End-to-End Cognitive Turn Latency (Live Ollama `qwen2.5:3b`)
* **Protocol:** 15 standardized prompts (factual, emotional, and social conversational turns) evaluated across both Baseline (`bb5be86`) and Candidate (`integration/phase-01`) conditions against live Ollama with CUDA acceleration. One throwaway generation burned prior to scoring.
* **Hypothesis / Target:** Mean TTFT delta $\le 10.0$ ms; p95 TTFT delta $\le 20.0$ ms.
* **Empirical Results:**
  * Runs per Condition: 15
  * Baseline Mean TTFT: **18.86 ms** (p50: 16.29 ms, p95: 25.65 ms)
  * Candidate Mean TTFT: **21.97 ms** (p50: 22.01 ms, p95: 34.73 ms)
  * **Mean TTFT Delta:** **+3.12 ms** (Target: $\le 10.0$ ms)
  * **p95 TTFT Delta:** **+9.08 ms** (Target: $\le 20.0$ ms)
  * Baseline Mean Total Turn Time: 355.3 ms | Candidate Mean Total Turn Time: 402.8 ms
* **Verdict:** **PASS** (Adding full causal slice tracing, CAS verification, and ActionIntent commitment adds only 3.12 ms mean latency).

### BM-GPU-02: Acoustic Barge-In to OutcomeRecord Latency
* **Protocol:** 10 mid-speech acoustic interruptions triggered during active generation/playback; measured latency from `audio.stop` signal to terminal `OutcomeRecord` emission and exact character offset matching.
* **Hypothesis / Target:** 100% of turns produce `OutcomeRecord(status='TRUNCATED')` with 0 offset error; stop-to-record latency $\le 50.0$ ms.
* **Empirical Results:**
  * Interruptions Tested: 10 / 10
  * Status: **100% TRUNCATED** (10/10)
  * Character Offset Precision Error: **0 bytes** ($|\text{recorded} - \text{actual}| == 0$ across all 10 runs)
  * Mean Stop-to-Outcome Latency: **0.095 ms** ($95\ \mu\text{s}$)
  * Max Stop-to-Outcome Latency: **0.400 ms** ($400\ \mu\text{s}$) (Target: $\le 50.0$ ms)
* **Verdict:** **PASS** (Interruption handling is sub-millisecond and character-exact).

### BM-GPU-03: 20-Turn Longitudinal State Stability & Drift
* **Protocol:** 20 consecutive live conversational turns executed on a single session against `SQLiteWorkspaceStore`, tracking monotonic revisions, CAS conflict retries, and process resident memory (VmRSS) from `/proc/self/status`.
* **Hypothesis / Target:** Exactly 20 revisions monotonically committed ($1 \to 20$), 0 CAS conflicts, process memory variance $\le 5.0\%$.
* **Empirical Results:**
  * Sequential Turns: 20 / 20
  * Monotonic Revisions: **True** (Revisions 1 through 20 strictly sequential)
  * Spurious CAS Conflicts: **0**
  * Initial VmRSS: 140,552.0 KB (137.26 MB)
  * Final VmRSS: 140,588.0 KB (137.29 MB)
  * **RSS Memory Variance:** **0.03%** (Delta: +36 KB over 20 turns; Target: $\le 5.0\%$)
* **Verdict:** **PASS** (State transitions are perfectly monotonic with zero memory drift).

---

## 4. Benchmark Summary Matrix

| ID | Benchmark | Environment | Threshold | Measured Result | Status |
|---|---|---|---|---|---|
| **BM-LOC-01** | CAS Commit Overhead | Mac ARM64 | p95 $\le 5.0$ ms | p95 = **0.132 ms** | **PASS** |
| **BM-LOC-02** | Snapshot Memory Size | Mac ARM64 | Mean $\le 2,048$ B | Mean = **950 B** | **PASS** |
| **BM-LOC-03** | Percept Normalization | Mac ARM64 | p95 $\le 100\ \mu\text{s}$ | p95 = **2.75 $\mu\text{s}$** | **PASS** |
| **BM-GPU-01** | E2E Turn TTFT Delta | RTX 2060 Super | Mean delta $\le 10.0$ ms | Mean delta = **+3.12 ms** | **PASS** |
| **BM-GPU-02** | Barge-In Outcome Latency | RTX 2060 Super | Max $\le 50.0$ ms, diff = 0 | Max = **0.400 ms**, diff = 0 | **PASS** |
| **BM-GPU-03** | 20-Turn State Stability | RTX 2060 Super | Variance $\le 5.0\%$, 0 conflicts | Variance = **0.03%**, 0 conflicts | **PASS** |

---

## 5. Architectural Conclusion

The authoritative causal slice implementation achieves all latency, throughput, and stability requirements. The entire causal trace (sensory normalization, workspace CAS consistency, deliberate action intent commitment, and terminal outcome recording) executes with negligible overhead (+3.12 ms TTFT) and sub-millisecond interruption handling, laying a solid, mathematically sound foundation for Phase 02 (Memory Grounding).

