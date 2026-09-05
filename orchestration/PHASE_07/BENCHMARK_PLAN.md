# Phase 07 Benchmark Plan: Production Runtime Consolidation

Phase: PHASE_07
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 1-41)
Audit Reference: FINAL_SYSTEM_VALIDATION_REPORT.md (2026-09-04)
Baseline Git Commit: c474470
Status: READY_FOR_DISPATCH

---

## 1. Local Micro-Benchmarks (Apple Silicon Mac)

### BM-LOC-P7-01: Runtime Composition & Initial Turn Overhead
- **Target:** Measure overhead of composing all Phase 01-06 services into `CognitiveService` and executing a live turn.
- **Protocol:** 1,000 iterations initializing `CognitiveService` with full workspace, temporal store, scheduler, verifier, governor, and role negotiator.
- **Metric:** Mean initial deliberation overhead < 5.0 ms.

### BM-LOC-P7-02: Action Selection & WAIT Action Silence Fidelity
- **Target:** Verify that candidate selection generates WAIT under appropriate conditions, maps it to `action_type="WAIT"`, and yields 0 spoken tokens.
- **Protocol:** 1,000 iterations scoring and executing WAIT actions through `ActionService.execute`.
- **Metric:** 100% silence compliance (0 text chunks emitted), execution latency < 1.0 ms.

### BM-LOC-P7-03: Epistemic Dream Quarantine Verification
- **Target:** Verify that `SubconsciousAgent._run_dream_sequence` never commits dream text to `MemoryStore`.
- **Protocol:** 500 simulated dream cycles with active knowledge graph entities.
- **Metric:** 100% quarantine enforcement (0 `subconscious_dream` memories committed to `MemoryStore`).

### BM-LOC-P7-04: Governed Learning & Reflection Proposal Review Latency
- **Target:** Verify that reflection proposals pass through `LearningGovernor` risk-tiered gate and can be rolled back atomically.
- **Protocol:** 1,000 proposal evaluations across LOW/MEDIUM/HIGH risk tiers.
- **Metric:** Mean governance latency < 50.0 us, 100% rollback fidelity.

---

## 2. Remote GPU Benchmarks (NVIDIA GeForce RTX 2060 Super 8GB)

### BM-GPU-P7-01: Composed Production Turn TTFT with Active Candidate Selection
- **Target:** Measure real end-to-end cognitive turn latency through the fully composed `BrainAgent` and `CognitiveService` with `PHASE_02_MEMORY_TRUTH=True` and `PHASE_03_AFFECT_CONTROL=True` active.
- **Model:** `qwen2.5:3b` (Ollama runtime on RTX 2060 Super).
- **Protocol:** 10 live cognitive turns with warm-up; measure pre-generation deliberation overhead, TTFT, and state continuity.
- **Metric:** Mean TTFT < 120.0 ms, p95 TTFT < 200.0 ms, Authoritative State Continuity = 100% INTACT.

### BM-GPU-P7-02: True Cross-Provider Behavioral Invariance
- **Target:** Measure behavioral conformance across distinct model provider interfaces on identical persona prompts and state snapshots.
- **Models:** `qwen2.5:3b` vs `llama3.2:3b` / Provider Interface.
- **Protocol:** 10 standardized probing prompts evaluating value adherence, tone consistency, and boundary enforcement.
- **Metric:** Persona adherence score > 90%, zero boundary violations across providers.
