# Phase 06 Benchmark Plan: Optional Advanced Learning and Planning

Phase: PHASE_06
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 16, 21, 38, 40)
Baseline Git Commit: 9203f55
Status: READY_FOR_DISPATCH

---

## 1. Local Micro-Benchmarks (Apple Silicon)

### BM-LOC-P6-01: Deterministic Plan Verifier Latency and Soundness
- **Objective:** Measure verification throughput of `DeterministicPlanVerifier` across valid and invalid multi-step DAG plans.
- **Methodology:** 1,000 iterations evaluating complex plan topologies (linear, branching DAGs, cyclic graphs, unfulfilled preconditions, budget overruns).
- **Target Metrics:**
  - Mean verification latency < 50.0 us
  - Soundness check: 100.0% rejection of invalid/cyclic plans
  - p95 latency < 100.0 us

### BM-LOC-P6-02: Episodic Simulation Sandbox Quarantine and Throughput
- **Objective:** Verify speed and quarantine enforcement of `EpisodicSimulator` during prospective rollouts.
- **Methodology:** 1,000 rollout steps in sandboxed workspace clones; attempt synthetic write commits to mock memory store.
- **Target Metrics:**
  - Mean rollout step latency < 20.0 us
  - Quarantine enforcement: 100.0% detection and blocking of live memory commit attempts (`SimulationQuarantineViolationError`)
  - 0% pollution of live state

### BM-LOC-P6-03: Learning Governance Gate and Rollback Latency
- **Objective:** Benchmark throughput and safety invariants of `LearningGovernor` and `LearningApprovalGate`.
- **Methodology:** 1,000 iterations processing proposals across all risk tiers (LOW, MEDIUM, HIGH, CRITICAL, and illegal IMMUTABLE_CORE modifications), followed by 1-step atomic rollback.
- **Target Metrics:**
  - Mean gating + rollback latency < 50.0 us
  - Immutable core rejection: 100.0% blocked
  - Rollback fidelity: 100.0% accurate state restoration

### BM-LOC-P6-04: Learning-Progress Curiosity Signal Computation
- **Objective:** Benchmark computation latency and ranking accuracy of `LearningProgressCuriosity`.
- **Methodology:** 1,000 iterations evaluating learning progress deltas across synthetic active, stagnant, and chaotic domains over sliding windows.
- **Target Metrics:**
  - Mean computation latency < 10.0 us
  - Ranking correctness: 100.0% (Progress > Noise and Progress > Mastery)

---

## 2. Remote GPU Benchmarks (home-gpu / RTX 2060 Super 8GB)

### BM-GPU-P6-01: Deliberative Planning Overhead and State Continuity
- **Objective:** Measure L2 deliberative planning proposal generation with local GPU model (`qwen2.5:3b` or `llama3.2:3b`), verifying state preservation and latency boundaries.
- **Target Metrics:**
  - TTFT within registered L2 budget (target < 80.0 ms)
  - 100% authoritative workspace state continuity

### BM-GPU-P6-02: Offline Adapter Qualification and Behavioral Regression Check
- **Objective:** Verify `OfflineAdapterGate` execution against held-out probe suite using real Ollama instance.
- **Target Metrics:**
  - 100% detection of simulated behavioral regressions
  - Safe abstention and zero memory leak during evaluation
