# Final System Benchmark and Validation Plan

Date: 2026-09-04
Orchestrator: Gemini (Antigravity)
Target Revision: main (f0333fc)

---

## 1. Objective
To empirically evaluate the Humanoid Brain Architecture as an integrated system, addressing the critical discrepancies identified by both Codex and Claude independent final audits:
1. Verify what happens when Phase 02/03 feature flags are active in the live pipeline.
2. Measure actual end-to-end cognitive latency with candidate selection, constraint filtering, and global control modulation.
3. Validate memory integrity: verify that dream memories are eliminated or quarantined, and that retrieval distinguishes between factual memory and hypothetical/untrusted content.
4. Verify action selection fidelity: ensure that selecting WAIT results in silence/non-utterance rather than speech.
5. Provide honest, non-tautological benchmarking with full provenance (hardware, models, configurations, and limitations).

---

## 2. Benchmark Suite Specification

### BM-FIN-01: Live Cognitive Turn Latency & Candidate Selection Overhead
- **Target:** Measure full pipeline turn execution with `PHASE_02_MEMORY_TRUTH=True` and `PHASE_03_AFFECT_CONTROL=True`.
- **Metrics:**
  - Candidate generation & constraint filtering latency (us)
  - Global control derivation & scoring modulation latency (us)
  - Selected action distribution across SPEAK, WAIT, ASK, REAPPRAISE, REDIRECT_ATTENTION
  - Total turn overhead added by cognitive deliberation before LLM streaming (ms)
- **Target Threshold:** Deliberative pre-generation overhead < 5.0 ms.

### BM-FIN-02: Action Execution Fidelity (The WAIT Invariant)
- **Target:** When the CandidateSelector selects `WAIT`, verify that the system produces no speech chunks (`action_type="WAIT"` produces done without content).
- **Target Threshold:** 100% compliance (0 speech chunks emitted when WAIT is selected).

### BM-FIN-03: Memory Epistemic Quarantine & Anti-Contamination
- **Target:** Verify that ungrounded dream sequences do not inject unverified assertions into autobiographical memory store.
- **Target Threshold:** 0 `subconscious_dream` memories committed without explicit quarantine/proposal gating.

### BM-FIN-04: End-to-End Fast-Path Barge-In & State Truncation
- **Target:** Re-verify the sub-millisecond reflex barge-in path (`is_facial_reflex_interruption_worthy`), verifying exact-offset transcript truncation and terminal outcome recording.
- **Target Threshold:** Interrupt-to-outcome latency < 2.0 ms, 100% transcript truncation fidelity.

### BM-FIN-05: Real Cross-Provider Behavioral & Conformance Check
- **Target:** Document the exact provenance and empirical status of provider portability. Specifically test `OllamaClient` vs `AnthropicClient` (or simulated distinct provider) on identical state snapshots and measure whether behavioral drift occurs.
- **Target Threshold:** Explicit disclosure of real vs mocked cross-provider evidence; zero unproven claims.
