# Phase 07 Acceptance Criteria: Production Runtime Consolidation

Phase: PHASE_07
Architecture Source: FINAL_HUMANOID_BRAIN_ARCHITECTURE.md (Sections 1-41)
Audit Reference: FINAL_SYSTEM_VALIDATION_REPORT.md (2026-09-04)
Baseline Git Commit: c474470
Status: READY_FOR_DISPATCH

---

## 1. Functional and Structural Criteria

| Criteria ID | Component | Requirement | Verification Target |
|---|---|---|---|
| **AC-P7-01** | Composition Root | CognitiveService composes WorkspaceStore, TemporalMemoryStore, BackgroundScheduler, DeterministicPlanVerifier, EpisodicSimulator, LearningGovernor, OfflineAdapterGate, ProviderCapabilityNegotiator, and ExternalActionDispatcher | test_runtime_composition.py verifies all services instantiated and wired |
| **AC-P7-02** | Causal Workspace | BrainAgent supplies authoritative WorkspaceStore to process_event; ActionIntent commits against valid non-zero (epoch, revision) tuple | 0 turns commit against (0, 0) fallback in live pipeline |
| **AC-P7-03** | Active Configuration | PHASE_02_MEMORY_TRUTH, PHASE_03_AFFECT_CONTROL, WORKSPACE_AUTHORITATIVE, and LEARNING_REVIEW_REQUIRED default to True | Config defaults confirmed active; 100% test suite passes |
| **AC-P7-04** | Epistemic Quarantine | SubconsciousAgent dream sequence never inserts ungrounded dream text into autobiographical memory | 0 subconscious_dream memories added to MemoryStore |
| **AC-P7-05** | Action Execution | Selected WAIT candidate is mapped to action_type="WAIT" and yields zero speech chunks in ActionService.execute | 100% silence compliance (0 spoken tokens emitted when WAIT wins) |
| **AC-P7-06** | Memory Truth Bridge | memories_to_activations propagates real contradiction states and explicit outage_flag rather than hardcoded NONE/False | Contradictions and outages correctly trigger ASK / degraded metadata |
| **AC-P7-07** | Governed Learning | ReflectionService routes persona mutations through LearningGovernor and LearningApprovalGate; unapproved proposals held in queue; 1-step rollback verified | 100% of trait mutations governed; 0 unverified auto-applies |
| **AC-P7-08** | Provider Portability | Cross-provider behavioral test validates persona fidelity across distinct provider clients (OllamaClient vs AnthropicClient) | Behavioral conformance verified across distinct provider interfaces |
| **AC-P7-09** | Quality & CI Gates | Pure 7-bit ASCII, 0 ruff errors, 0 radon D/E/F cyclomatic complexity findings, full test suite passes | 100% pass rate across 2,332+ tests locally and on home-gpu |
| **AC-P7-10** | Integrated GPU Gate | Full pipeline GPU turn execution through composed BrainAgent on RTX 2060 Super | Mean TTFT < 120.0 ms, 100% authoritative state continuity |

---

## 2. Invariant Checklist

1. **Composition Invariant:**
   - No phase service shall remain an uncalled standalone library. Every service specified in Sections 1-38 must be composed into `CognitiveService`, `CognitivePipeline`, or `BrainAgent`.
2. **Quarantine Invariant:**
   - Unverified background generative text (dreams, unreviewed reflections) must NEVER be committed to long-term memory as historical truth.
3. **Action Fidelity Invariant:**
   - When the agent selects `WAIT`, it must remain silent. Language output must never be generated when silence is chosen.
4. **Governed Adaptation Invariant:**
   - No learning update or persona trait modification shall be applied without passing through `LearningGovernor` or human review.
