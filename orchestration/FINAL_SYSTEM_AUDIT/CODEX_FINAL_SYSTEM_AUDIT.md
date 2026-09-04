# Codex Final System Audit

Audit date: 2026-09-04  
Audited revision: `f0333fc063d4fb4b336b5fa517a55964ff7e26cc` (`main`, equal to `origin/main`)  
Audit boundary: independent engineering/runtime/integration audit. Claude's final cognitive audit was not read. No production fix, merge, commit, or push was performed.

## Executive Verdict

**REJECT final-system acceptance.** The repository contains substantial, generally well-tested implementations for all six phases, but it does not run them as the accepted architecture. It is component-complete, not runtime-integrated.

The production composition root, `CognitiveService.__init__`, constructs the legacy cognitive pipeline with `WorkingMemoryStore`, but no authoritative `SQLiteWorkspaceStore`, `TemporalMemoryStore`, `BackgroundScheduler`, verified planner/simulator, learning governor, model-role negotiator, voice compiler, vision adapter, or external-action dispatcher (`backend/app/cognitive/core.py:48-116`). `BrainAgent` passes a percept but no workspace to that pipeline (`backend/app/agents/brain_agent.py:776-852`). The core Phase 2 and Phase 3 behavior flags remain false, the workspace-authoritative flag is not declared and resolves false, and learning review remains false (`backend/app/config.py:220-243`, `backend/app/config.py:318-319`, `backend/app/state/session_state.py:126-128`). A direct composition probe confirmed those resolved values and `pipeline.scheduler is None`.

This leaves one **BLOCKER**: the accepted six-phase system is not the system executed by the production agent. The strongest local validation—2,332 passing Python tests and 179 passing Rust tests—proves component behavior, but there is no production-composition or all-phases-on end-to-end test that would detect this integration failure.

## Repository State

- `HEAD` and `origin/main`: `f0333fc063d4fb4b336b5fa517a55964ff7e26cc` (`feat(phase-06): integrate verified planning, episodic simulation, learning governance, and offline adapter gate`).
- Tracked worktree was clean at audit start. Numerous architecture/orchestration documents were already untracked; they were treated as user-owned and left untouched.
- `orchestration/MASTER_STATE.md` and all six phase gates report complete/pass, with a recorded total of 2,332 tests.
- All six acceptance-criteria files, phase gates, benchmark reports, the final architecture, current code, relevant tests, and relevant ledger entries were inspected.
- This report and the required engineering-ledger entry are the only intended audit writes.

## Architecture Conformance

| Domain | Current production behavior | Status |
|---|---|---|
| Perception | Chat, vision-description, facial-reflex, audio-stop, and playback inputs have `PerceptEnvelope` adapters. `BrainAgent` retains only `last_percept`, and the incoming chat overwrites it before the turn (`brain_agent.py:285-335`, `619-633`). | PARTIAL |
| Salience / attention | Novelty, somatic appraisal, and a startle interrupt exist, but there is no workspace focus/protected set, attention admission/defer/drop policy, or salience arbitration. | FAIL |
| Persistent mental state | `StateService` persists affect/person data and guards mutation with a lock. The accepted causal workspace is not constructed, passed, loaded, or epoch-advanced in production. | PARTIAL |
| Memory | The mature legacy `MemoryStore` and surfacing agent are live. Phase 2's typed bi-temporal `TemporalMemoryStore` has no production caller. | PARTIAL |
| Appraisal | `AppraisalEngine` is on the live pipeline and updates state (`pipeline.py:802-832`). | PASS |
| Affect / emotion | PAD, trust, fatigue, and endocrine channels are live and lock-owned. They are duplicated across brain and subconscious processes and do not share an authoritative workspace. | PARTIAL |
| Global control | Controls are derived and included in state snapshots, but candidate modulation is gated by `PHASE_03_AFFECT_CONTROL=False` (`pipeline.py:651-652`, `config.py:234-243`). | PARTIAL |
| Goals | Legacy per-turn goal/utility scoring is live. Durable `GoalRecord` review has no caller outside its module/tests. | PARTIAL |
| World model | No production world-model or prediction-record implementation was found. | FAIL |
| Self model | Narrative/numeric persona and a capability-limitation field exist. Operational capability calibration is not invoked by cognition. | PARTIAL |
| Social state | `PersonModel` is stored in `AgentState`, but production never calls active-person selection, reliance update, privacy disclosure, or rupture/repair methods. | PARTIAL |
| Reasoning | Intent classification, behavior-tree routing, MAUT goal scoring, and an async appraisal pass are live. Verified planning and episodic simulation are isolated modules. | PARTIAL |
| Fast cognition | Deterministic responses short-circuit model classification and reflex interruption is deterministic (`decision.py:405-421`; `brain_agent.py:312-355`). | PASS |
| Slow cognition | Model intent classification and async System-2 appraisal run, but Phase 6 planning/simulation do not. | PARTIAL |
| Background cognition | The accepted scheduler exists but is not constructed. The live subsystem is the older free-running monologue/dream loop. | FAIL |
| Action selection | A typed candidate/intent schema exists, but live candidate selection is off by default and most declared actions have no generator/executor. | FAIL |
| Learning / reflection | Legacy reflection/consolidation is live. Phase 6 governance, measured promotion, monitoring, and rollback are not invoked. | FAIL |
| Voice boundary | Production publishes legacy `ChatOutput`/`SpeechExpressionWire`; Rust directly builds GPT-SoVITS `/tts` requests. `SpeechIntent` and both compilers are not on this path. | FAIL |
| Vision boundary | Production vision publishes semantic `VisionDescription` plus reflex deltas. The accepted structured-observable adapters are unused. | FAIL |
| Provider abstraction | LLM construction is abstracted across Ollama/Anthropic. Embeddings, production TTS, and significant vision behavior remain provider/backend-specific. | PARTIAL |

## End-to-End Runtime Flow

| Scenario | Traced runtime | Result |
|---|---|---|
| Normal user interaction | `chat.input` -> `BrainAgent._on_chat_input` -> `CognitiveService.process_event` -> perception -> appraisal -> locked state update -> decision -> `ActionService` -> streamed `chat.output`. | Functional legacy flow; no authoritative workspace, true general action selection, or typed speech intent. |
| Memory retrieval | `SurfacingAgent` calls legacy `MemoryStore.search_memories`, publishes narrative `MemorySurfaced`, and `CognitiveService` reduces it to content/source/time/relevance (`core.py:342-385`). `ActionService` can do the same legacy search synchronously. | Functional retrieval, but typed truth/contradiction/outage semantics are bypassed. |
| Emotional-state change | Appraisal updates `StateService`; phasic and tonic endocrine state feeds response sampling. Global-control candidate modulation is disabled by default. | Core affect works; accepted causal control loop is partial. |
| High-salience event | Facial startle directly changes affect and can publish a turn-scoped `AudioStop` (`brain_agent.py:312-355`). | Useful deterministic reaction; not admitted to a persistent attention/workspace trace. |
| Interruption | Turn-scoped stop cancels generation, ignores stale turn IDs, truncates using playback offsets, records a terminal in-process outcome, and releases adrenaline (`brain_agent.py:950-1008`). | Strongest integrated path, but its intent/outcome history is not durable. |
| Fast reaction | Deterministic response precedes classifier/model work; visual startle bypasses the LLM. | Real fast path, but it does not update the same durable causal workspace as slow actions. |
| Slow reasoning | Intent classification and async System-2 appraisal run. The Phase 6 verifier/executor/simulator are never called from `app/`. | Deliberation is not the accepted verified planning path. |
| Background cognition | `SubconsciousAgent.start` starts `_continuous_monologue_loop`; it generates free monologues and dreams, and dreams are inserted as memories (`subconscious_agent.py:197`, `616-774`). | Direct conflict with the accepted bounded, attributable background design. |
| Action selection | With both phase flags false, legacy plan selection proceeds. Even when enabled, production candidates are SPEAK, WAIT, conditional ASK, and regulation; WAIT is not mapped to an executable wait action. | Generated response text remains the de facto action for ordinary turns. |
| Speech intent | Brain derives an expression from state with `intent=None` and publishes `ChatOutput`; Rust consumes content/affect/expression (`brain_agent.py:1028-1061`; `crates/contracts/src/lib.rs:170-186`). | `SpeechIntent` is bypassed. |
| Learning / reflection | High-confidence reflection suggestions directly evolve persona when review is disabled; LLM summaries are stored as `subconscious_consolidation` memories (`learning.py:272-280`, `299-360`). | Ungoverned change can propagate; storage is mislabeled/treated as learning. |
| Restart / restoration | State, reappraisal weights, decision weights, biography, and self-knowledge hydrate (`core.py:264-287`). Workspace epoch/revision, per-turn session state, outcomes, durable goals, scheduler jobs, and Phase 6 learning state are not restored by the composition root. | Partial recovery only. |

## Cross-Phase Integration

1. **Additive APIs never became composition.** Later phases added optional arguments and default-off gates to preserve older callers. The final production caller is still that older caller. `CognitivePipeline.execute` explicitly documents `(0, 0)` workspace fallback and default-off Phase 2/3 behavior (`pipeline.py:695-732`).
2. **Two memory architectures coexist.** The live path is `MemoryStore` + narrative dicts; the accepted typed path is `TemporalMemoryStore` + `MemoryActivation`. The adapter necessarily sets every legacy record to `experience`, contradiction `NONE`, and outage false (`memory_activation.py:151-204`).
3. **Two background architectures coexist.** `BackgroundScheduler` is optionally accepted by the pipeline but never supplied (`pipeline.py:76-109`); `SubconsciousAgent` independently schedules unbounded monologue/dream work.
4. **Two learning systems coexist.** `ReflectionService` uses the legacy in-memory review queue and direct persona evolution, while Phase 6's `LearningGovernor`/approval/rollback system has no runtime caller.
5. **Two voice boundaries coexist.** `SpeechIntent`/compiler/loss telemetry is an isolated Python boundary; production retains Python `ChatOutput` and hard-coded Rust GPT-SoVITS request construction (`crates/voice-agent/src/main.rs:1565-1595`).
6. **Two vision boundaries coexist.** `StructuredVisionPercept` adapters are isolated; production emits already interpreted VLM descriptions and affect-scored reflexes (`vision/agent.py:374-455`).
7. **Schemas overstate reachability.** `ActionKind` comments correctly call UPDATE_STATE, EXTERNAL_ACT, CONTINUE, and SUPPRESS_EXPRESSION a “schema ceiling,” not wired behavior (`action_intent.py:30-47`). The final gate treated schema conformance as system conformance.

No circular import failure was observed, and `compileall` passed. The dominant structural defect is disconnected parallel implementations, not an import cycle.

## State Integrity

Strengths:

- `StateService` centralizes in-process mutation behind `_state_lock`, persists revisions/writer IDs, derives global controls, and handles corrupt/missing optional data defensively.
- Turn generation/truncation fields are protected by dedicated locks; stale playback/stop events are rejected by turn ID.
- Workspace CAS, restart epoch, and transition-history code is well tested in isolation.

Failures and risks:

- Brain and subconscious each instantiate a `StateService`; synchronization occurs over broadcasts rather than through one state owner. Equal-revision writes from different writers are explicitly applied arbitrarily (`agent_state.py:959-974`).
- The authoritative workspace migration flag is absent from `AppSettings`; the helper therefore resolves false. `persist_session_state` receives no workspace store in production and writes a single legacy key (`session_state.py:83-128`; `pipeline.py:782-785`).
- No production caller of `load_session_state` or `WorkspaceStore.increment_epoch` was found. Restart cannot restore the causal slice or establish a new restart epoch.
- `BrainAgent` documents action intent, last outcome, and outcome history as in-process only (`brain_agent.py:143-158`). Proactive turns bypass the cognitive pipeline and therefore deliberately produce no outcome record (`brain_agent.py:378-399`).
- `last_percept` is a single mutable slot shared by unrelated event handlers; a chat event replaces earlier visual/reflex context before the chat turn, so evidence attribution is incomplete even though visual text is separately copied into prompt metadata.

## Memory

The legacy memory engine is substantial: L1 caching, Ollama embeddings, Qdrant/SQL candidates, Neo4j spreading activation, ACT-R scoring/decay, archive promotion, learned lexical cues, and Postgres/SQLite branches are live. Biography seeding and conversation persistence support some autobiographical continuity.

The architecture-specific truth model is not live:

- `TemporalMemoryStore` is referenced only by its module, tests, and benchmark scripts—not production application code.
- Typed belief/procedure/experience distinctions, bitemporal queries, and contradiction transitions therefore cannot affect a normal turn.
- The legacy-to-activation adapter discards the very contradiction/outage semantics needed for safe selection (`memory_activation.py:166-173`).
- `MemoryStore.search_memories` records an error but returns `[]` on embedding failure or any exception (`memory_store.py:3528-3568`, `3695-3705`). Production callers do not inspect `last_search_error`, so an outage is behaviorally indistinguishable from “no relevant memory.”
- Retrieved text is wrapped as memory data, but anti-injection sanitation is enabled only when the default-false Phase 2 flag is on (`action.py:736-749`).
- Free-generated dream insights and reflection summaries are written into the same memory system without a quarantined hypothesis type.

Forgetting/decay and consolidation routines exist, but their live generated-summary path is not evidence-gated. Relationship state exists separately in `PersonModel`; it does not mediate retrieval disclosure in production.

## Fast/Slow Cognition

The fast/slow distinction is partly real:

- Deterministic stop/reflex/safety responses return before LLM classification.
- Simple greetings select the configured fast model.
- Slow semantic intent classification and a cancellable async System-2 appraisal task exist.
- Barge-in cancellation and stale-turn rejection are carefully engineered and tested.

It is not the accepted multi-lane system:

- There is no common authoritative workspace, attention state, checkpoint, or durable outcome history across lanes.
- System-2 is an appraisal side task, not verified multi-step reasoning.
- Phase 6 planning/simulation never participates in action selection.
- The live subconscious path races through a different process/state owner rather than the accepted preemptible scheduler. Its task cancellation is useful but does not add idempotency, attribution, budgets, or workspace commits.

## Action Selection

General action selection is not operational.

- `ActionCandidateKind` declares SPEAK, ASK, WAIT, OBSERVE, RETRIEVE, VERIFY, REFLECT, UPDATE_GOAL, and regulation kinds, but the production generator emits only SPEAK/WAIT, conditional ASK, and conditional regulation (`decision.py:927-1003`).
- Candidate selection runs only when either default-false Phase 2/3 flag is enabled (`decision.py:820-845`).
- ASK and two regulation kinds are mapped to executable action types. WAIT is not; if selected, `action_type` remains the ordinary chat response (`decision.py:846-879`).
- `ActionService.execute` has executors for chat, deterministic response, clarify, reappraise, redirect, memory store, and a background no-op—not wait/silence, observe, retrieve, verify, reflect, update goal/state, interrupt, continue, or external act (`action.py:1793-1832`).
- `ExternalActionDispatcher` is never referenced outside its own module, tests, and benchmarks.
- An `ActionIntent` is committed before generation, but production always supplies no workspace, so every one cites epoch/revision `(0, 0)` (`pipeline.py:573-611`).

The system can produce a structured record describing a decision, but ordinary behavior remains “select a response plan, then generate text.” That does not satisfy independent action selection.

## Learning/Reflection

What actually changes today:

- Reappraisal weights and legacy goal utilities are persisted.
- Reflection can evolve adaptive persona traits.
- Generated consolidation summaries are stored in long-term memory.
- Memory decay/refresh and relationship graph decay occur in background routines.

What does not run:

- `LearningGovernor`, approval gates, version activation, monitoring, rollback, and learning-progress curiosity have no production caller.
- `OfflineAdapterGate` is not connected to model/provider selection.
- The Phase 4 review queue is in-memory despite its durability-oriented documentation.

With `LEARNING_REVIEW_REQUIRED=False`, a model-produced suggestion with confidence at least 0.8 directly calls `IdentityManager.evolve_persona`. Confidence is self-reported, not empirically calibrated. Incorrect learning can therefore alter the adaptive persona and generated summaries can contaminate memory without the accepted proposal/evidence/review/rollback sequence.

## Provider Independence

Positive evidence:

- `LLMClient` is a protocol and `build_llm_client` selects Ollama or Anthropic; application construction sites use it (`backend/app/llm/__init__.py:1-86`).
- Rust STT and voice code has real contract, retry, circuit-breaker, authentication, and partial-service tests.
- Speech and vision adapter schemas model explicit capability/loss boundaries in isolation.

Remaining coupling:

- `MemoryStore.get_embedding(s)` directly calls Ollama `/api/embed` and `/api/embeddings` (`memory_store.py:1038-1084`, `1126-1137`). Switching the chat provider does not switch the embedding boundary.
- Production Rust voice consumes legacy `ChatOutput`, derives prosody, and builds a GPT-SoVITS-specific `/tts` payload. It cannot consume `SpeechIntent`, negotiate capability, or emit `IntentLossRecord`.
- Production vision uses OpenCV/MediaPipe plus VLM-generated semantic descriptions rather than a provider-neutral structured observable boundary.
- `ProviderCapabilityNegotiator` and the six `ModelRole` contracts have no production call site.
- Database fallbacks are useful, but the cognitive meaning of memory differs between the legacy multi-store path and the unused temporal truth store.

Provider independence is therefore real for basic LLM client construction, but not for the integrated cognitive/embodiment system.

## Failure Recovery

Observed strengths:

- Model streaming, malformed typed realization, memory and graph calls, optional vision dependencies, and background tasks generally fail closed or degrade without crashing the agent.
- Voice TTS has retry, validation-rejection handling, a circuit breaker, and no replay after a mid-stream drop.
- NATS account enforcement and authentication are exercised against real local servers.
- Stale turn events and interrupted generation are correlated and rejected/cancelled carefully.
- State hydration, SQLite/Postgres fallback paths, and workspace CAS/restart behavior have focused tests.

Material gaps:

- Memory outage collapses to empty retrieval, defeating explicit capability-loss signaling.
- Workspace and outcome recovery is absent from the production composition.
- Queue publish/consumer durability cannot make in-process action/outcome history durable.
- Background generated writes are not transactional with an authoritative workspace and carry no idempotency key.
- Partial provider availability is represented unevenly: voice has an explicit breaker, while memory embedding failure silently removes recall from behavior.
- The accepted learning rollback path cannot protect production because it is never invoked.

## Tests

### Commands and results

| Validation | Result |
|---|---|
| `DEBUG=false ../.venv/bin/python -m pytest -q --junit-xml=/tmp/codex-final-audit-pytest-unsandboxed.xml` from `backend/` | **PASS**: 2,332 tests, 0 failures, 0 errors, 0 skipped, 64.330 s (JUnit). Initial sandbox run had eight NATS setup errors caused by denied socket creation; the socket-enabled rerun passed. |
| `cargo check --workspace` | **PASS**. |
| `cargo test --workspace` | **PASS** outside the socket sandbox: 21 cognitive-rust + 10 contracts + 70 STT + 78 voice = **179 passed**. Initial 13 voice failures were all denied loopback binds. |
| `npm run lint` | **PASS**. |
| `npm run build` | **PASS** outside the restricted sandbox; six static routes built. The sandboxed Turbopack run stalled after “Creating an optimized production build” and was interrupted. |
| `../.venv/bin/python -m compileall -q app` | **PASS**. |
| `../.venv/bin/python -m ruff check .` | **PASS**. |
| `../.venv/bin/python -m ruff format --check .` | **FAIL**: 80 files would be reformatted; 273 already formatted. |
| `../.venv/bin/python -m mypy app` | **FAIL**: 17 errors in 7 files. |

### Test-quality assessment

- Phase component suites are extensive and include adversarial, failure, concurrency, contract, and mutation-oriented cases. The real NATS and Rust wiremock coverage is valuable.
- The principal missing test is a production-composition test that instantiates `BrainAgent`/`CognitiveService` and proves authoritative workspace lifecycle, temporal retrieval, all required candidates/executors, scheduler preemption, structured voice/vision boundaries, and governed learning are active together.
- Most Phase 2-6 tests import the new class directly and construct it manually. Many explicitly monkeypatch Phase 2/3 flags true; none catches their production default-off state.
- Workspace tests inject a store and monkeypatch the undeclared `WORKSPACE_AUTHORITATIVE` attribute. No test verifies the real configuration schema declares/enables it.
- GPU scripts likewise build isolated classes manually. They are not substitutes for the missing runtime integration test.
- No current mutation campaign was run during this documentation-only audit. Historical phase reports claim mutation checks; this audit does not elevate those historical claims to current integrated evidence.

## Static/Structural Quality

- Ruff lint passes, but formatter drift spans 80 files.
- Mypy reports 17 errors across persona policy, intent classifier, vision, planning, and pipeline typing. The errors include optional-service dereferences in vision and an unannotated planning graph.
- Radon reports C-grade cyclomatic complexity up to 20 in `StateService._hydrate_locked` and memory candidate fetch, 20 in `SubconsciousAgent.stop`, 19 in metrics buffering, and 17 in candidate selection/background loops.
- Maintainability index is C for `app/cognitive/action.py` (5.90) and `app/state/memory_store.py` (0.00); planning and `agent_state.py` are B; other modules are A.
- The risk is not cosmetic. High complexity sits at state hydration, retrieval, action realization, agent shutdown, and candidate selection—the same reliability boundaries implicated by integration findings.
- Dependency direction from `app/` to `evals/` remains clean. The more important boundary problem is unused phase modules beside legacy production implementations.

## Performance

Local component benchmarks were invoked directly (without overwriting phase result artifacts) on Darwin arm64, Apple M5 8-core GPU. All pass in isolated runs:

| Phase | Selected current measurements | Result |
|---|---|---|
| 1 | Workspace CAS p95 0.2099 ms; snapshot mean 949.98 B; percept normalization p95 2.96 us | PASS |
| 2 | Bi-temporal query p95 1.1761 ms; contradiction transition p95 0.0984 ms; constraint filter p95 25.79 us | PASS |
| 3 | Appraisal p95 4.125 us; controls p95 1.625 us; modulated selection p95 30.708 us | PASS |
| 4 | Calibration mean 0.340 us; privacy leakage 0%; scheduler preemption p95 0.001 ms | PASS |
| 5 | Voice compiler mean 4.245 us; vision normalization mean 11.999 us; role negotiation mean 0.361 us; external-action gate mean 0.156 us | PASS |
| 6 | Verifier mean 3.933 us; simulator mean 6.827 us; learning governor mean 45.451 us; curiosity mean 3.087 us | PASS isolated |

When all phase microbenchmarks were launched concurrently, Phase 6 learning governance averaged 57.316 us and failed its `<50 us` target; rerunning Phase 6 alone averaged 45.451 us and passed. This is a workload-sensitivity observation, not an inflated architecture blocker, but the background-overhead target is not robustly demonstrated.

No valid current end-to-end latency, queue, CPU/RAM, model-call, or background-overhead measurement of the **production integrated six-phase runtime** exists, because that runtime is not composed.

GPU evidence was reviewed but not rerun as RTX evidence on this Apple M5 host. Ollama is available and the required `llama3.2:3b` and `qwen2.5:3b` models are installed; the six GPU scripts are callable. They are not acceptable final-system tests:

- Phase 1 manually normalizes, reads/commits a temporary workspace, constructs an intent, and calls `OllamaClient` directly (`run_gpu_benchmarks.py:60-115`).
- Phase 2 manually creates temporary workspace/temporal stores, flips the flag, builds candidates, and streams Ollama directly (`run_gpu_benchmarks_phase2.py:74-105`, `147-235`).
- Phase 3 manually builds candidates and directly applies affect mean reversion (`run_gpu_benchmarks_phase3.py:397-451`).
- Phase 4 manually constructs calibration/person/privacy state and invokes the selector (`run_gpu_benchmarks_phase4.py:59-84`, `154-173`).
- Phase 5 calls Ollama directly, uses a simulated workspace dict, then constructs `SpeechIntent` manually despite describing a “full pipeline” (`run_gpu_benchmarks_phase5.py:165-230`).
- Phase 6 calls Ollama directly and uses a synthetic authoritative-state dict; adapter qualification hard-codes baseline/candidate boolean verdicts rather than scoring responses (`run_gpu_benchmarks_phase6.py:51-115`, `197-205`).

The recorded RTX results are evidence for those isolated harnesses and hardware only. Before a final rerun, the GPU suite must be prepared by routing it through the real composition root and capturing model, persona, corpus, code SHA, real workspace/memory fixture, service versions, and mock/real status.

## Architecture Invariants

| # | Invariant | Verdict | Evidence |
|---:|---|---|---|
| 1 | Identity-bearing state is not only prompt/provider/model state | PASS | Persona/profile, biography, state, and adaptive weights have durable stores. |
| 2 | One owner per mutable domain; revision + restart epoch + idempotency | FAIL | Multiple `StateService` writers; arbitrary equal revisions; workspace/epoch/idempotency absent from live turns. |
| 3 | Provenance for beliefs, predictions, inferences, memory claims, learned updates | PARTIAL | Schemas carry provenance, but the live legacy adapter strips type/contradiction/outage and learning changes lack governed evidence. |
| 4 | Observation, user report, inference, imagination, accepted belief are distinct | FAIL | Typed records exist only in the unused temporal store; live narrative memory and generated dreams share the legacy store. |
| 5 | Modulation changes parameters/budgets, never truth/identity/safety | PASS | Endocrine and global-control implementations modulate sampling/scoring; no direct truth write was found in those modules. |
| 6 | Hard constraints filter before utility | PARTIAL | Candidate selector does so when invoked, but live selection is default-off and response validation occurs after a text action is chosen/generated. |
| 7 | Action selection is separable and commits structured intent first | FAIL | Intent exists, but selection is default-off, most actions are unreachable, and every live intent uses workspace `(0,0)`. |
| 8 | Retrieved memory is untrusted, never executable instruction | PARTIAL | Memory is labeled/wrapped, but anti-injection is default-off and generated dream/reflection text is promoted into the memory corpus. |
| 9 | Contradictions preserve evidence/history | PARTIAL | `TemporalMemoryStore` satisfies this in isolation; production retrieval cannot carry contradiction state. |
| 10 | Storage/reflection/training is not called learning without future improvement | FAIL | Reflection-driven persona/storage is the live “learning” path; Phase 6 measured-governance path is unused. |
| 11 | Model self-confidence requires empirical calibration | FAIL | Production accepts reflection confidence >=0.8; calibration directive code has no production caller. |
| 12 | Generated background content cannot self-promote to truth | FAIL | Dream insights and LLM consolidation summaries are directly inserted into legacy memory. |
| 13 | Fast actions update the same causal workspace/outcomes as slow actions | FAIL | No live workspace; reflex/proactive paths bypass it; outcomes are process-local. |
| 14 | Background work is bounded, preemptible, idempotent, attributable, stoppable | FAIL | Accepted scheduler unused; live 5-second monologue/dream loop lacks workspace attribution/idempotency/budgeting. |
| 15 | Voice owns sound; vision observables; brain meaning/high-level intent | PARTIAL | Voice owns synthesis, but receives legacy expression rather than high-level intent; vision publishes VLM semantic interpretation and affect deltas. |
| 16 | Provider capability loss is explicit | PARTIAL | Loss/negotiation schemas exist, but live voice/vision/embedding paths do not use them and memory outage becomes empty recall. |
| 17 | Provider swap requires behavioral/identity/safety/regression conformance | PARTIAL | LLM factory and isolated reports exist; no whole-system provider-swap conformance test runs through production. |
| 18 | Infrastructure does not define cognitive semantics; migration is measured | PARTIAL | Some protocols/fallbacks exist, but legacy and temporal stores have different live semantics and migration never completed. |
| 19 | Benchmark provenance includes model/persona/corpus/code/state fixture/mock-real | FAIL | Phase GPU scripts use synthetic/manual state; Phase 6 adapter scores are hard-coded; integrated fixture/provenance is absent. |
| 20 | No claim of consciousness, biological equivalence, general ToM, human-level cognition | PASS | No such engineering claim was required or relied upon by audited runtime evidence. |

Summary: **3 PASS, 8 PARTIAL, 9 FAIL, 0 NOT TESTABLE**.

## Findings

### F-01 — BLOCKER — The accepted six-phase architecture is not composed in production

**Evidence:** `CognitiveService` constructs only the legacy services and passes no workspace/scheduler (`core.py:48-116`); `BrainAgent` supplies no workspace (`brain_agent.py:850-852`); resolved Phase 2, Phase 3, workspace-authoritative, and learning-review switches are false; phase-specific modules have no production callers.

**Impact:** The system advertised as fully integrated executes a substantially different architecture. Final acceptance cannot be truthful until the production composition and lifecycle are verified end to end.

### F-02 — HIGH — Authoritative causal state and restart recovery are absent

**Evidence:** Live intents use `(0,0)` fallback (`pipeline.py:573-611`); workspace load/epoch methods have only tests; outcomes are in-process; two state writers can apply equal revisions arbitrarily (`agent_state.py:959-974`).

**Impact:** Decisions, actions, interruptions, recovery, and cross-process state cannot be reconstructed as one deterministic causal history.

### F-03 — HIGH — General action selection is schema-only for most required actions

**Evidence:** Default-off selection, narrow generators (`decision.py:927-1003`), missing WAIT mapping (`decision.py:846-879`), and missing executors (`action.py:1793-1832`).

**Impact:** The model-generated response remains the effective action; stay silent, observe, retrieve, verify, reason further, update state/goal, interrupt, and external action are not general selectable/executable choices.

### F-04 — HIGH — Temporal memory truth, contradiction, provenance, and outage semantics are bypassed

**Evidence:** No production caller of `TemporalMemoryStore`; legacy adapter forces experience/NONE/non-outage; `MemoryStore` returns `[]` on failures and callers ignore `last_search_error`.

**Impact:** The agent cannot distinguish conflicting belief, historical belief, absent memory, or failed retrieval in its live decisions.

### F-05 — HIGH — Live background cognition violates the accepted safety model

**Evidence:** `BackgroundScheduler` is not supplied; the live free-running loop generates monologue and persists dream text as memory (`subconscious_agent.py:616-774`).

**Impact:** Background work is not causally attributable/idempotent and generated content can become autobiographical evidence.

### F-06 — HIGH — Governed learning, review, regression monitoring, and rollback are disconnected

**Evidence:** `LearningGovernor`/offline adapter gate have no production caller; learning review defaults false; confidence >=0.8 directly mutates adaptive persona (`learning.py:272-280`).

**Impact:** Incorrect model inference can alter future identity/behavior without the accepted evidence, approval, observation, or rollback controls.

### F-07 — HIGH — Voice, vision, model-role, and external-action portability boundaries are not live

**Evidence:** Production uses legacy `ChatOutput`, GPT-SoVITS `/tts`, VLM descriptions/reflex deltas, and no role negotiator/dispatcher. Embeddings call Ollama directly.

**Impact:** Provider swaps can silently lose or reinterpret behavior; accepted loss telemetry and risk gates do not protect real execution.

### F-08 — HIGH — “End-to-end” benchmark evidence does not execute the production system

**Evidence:** All phase GPU scripts manually assemble isolated components and call Ollama directly; Phase 5 uses a simulated workspace; Phase 6 hard-codes adapter evaluation verdicts.

**Impact:** Phase gates establish micro/component performance, not integrated correctness, provider conformance, state continuity, or system latency.

### F-09 — MEDIUM — Perception lacks an integrated attention/world-model causal path

**Evidence:** Single-slot `last_percept`, no attention arbiter/protected focus/defer/drop path, and no world-model/prediction-record implementation. Visual context is separately copied as prompt metadata.

**Impact:** Cross-modal events can affect prompt/state without a durable account of what was attended, inferred, or predicted.

### F-10 — MEDIUM — Test strategy misses production composition and default configuration

**Evidence:** 2,332 tests pass, but new services are predominantly directly instantiated; tests monkeypatch flags and inject stores; no all-phase production runtime test exists.

**Impact:** A green suite permits an entirely disconnected architecture to ship.

### F-11 — MEDIUM — Static/type/complexity debt clusters at critical boundaries

**Evidence:** 17 mypy errors/7 files; 80 unformatted files; C-grade complexity in state hydration, memory, background shutdown/loop, action, and selection; MI C for action and memory store.

**Impact:** Future integration work is more likely to introduce subtle state, optional-service, and failure-path regressions.

### F-12 — LOW — Phase 6 learning-governance latency is load-sensitive

**Evidence:** Concurrent microbenchmark mean 57.316 us failed `<50 us`; isolated rerun mean 45.451 us passed.

**Impact:** The threshold has little headroom under concurrent CPU work. This does not block architecture integration but warrants a realistic background-load benchmark.

## Recommended Fixes

No fixes were implemented. Recommended arbitration order:

1. Build one explicit production composition root for `CognitiveWorkspace`, temporal memory, attention, scheduler, calibrated selection, planning/simulation, governed learning, role negotiation, structured vision/voice, and external actions. Remove default-off ambiguity from a “complete” deployment.
2. Make workspace load/epoch/CAS the entry and commit boundary for every foreground, fast, slow, interruption, and background event. Persist intent/outcome history and assign one writer/owner per state domain.
3. Replace the legacy memory bridge with typed retrieval results that preserve record type, provenance, valid/system time, contradictions, and explicit outage. Quarantine generated hypotheses/reflections.
4. Implement and test executable action semantics for wait/silence, observe, retrieve, verify/reason, goal/state update, interrupt, continue, and external act. Unknown/unimplemented candidates must be rejected before selection.
5. Retire or place the live subconscious loop under `BackgroundScheduler`; prohibit dream/summary promotion into factual/autobiographical memory without evidence and review.
6. Route persona adaptation and adapter promotion exclusively through the Phase 6 proposal/approval/activation/monitor/rollback lifecycle; default review fail-closed.
7. Put `SpeechIntent`, capability negotiation/loss records, structured vision observables, and external-action authorization on the actual mesh contracts. Abstract embeddings and TTS as real provider interfaces.
8. Add a production-composition integration test and a real service-backed scenario suite covering all flows in this audit, including restart and partial outages.
9. Rewrite GPU benchmarks to drive that composition root rather than direct component calls; remove synthetic state and hard-coded evaluation verdicts; record complete provenance.
10. After runtime correctness, clear mypy errors and reduce critical-path complexity with behavior-preserving extraction and regression coverage.

## Remaining Engineering Risks

- A future wiring-only patch may expose incompatible assumptions currently hidden by unused code: session identity, database lifecycle, async cancellation, NATS delivery ordering, and Pydantic/Rust contract drift.
- Enabling Phase 2/3 flags without replacing the legacy memory bridge will create an appearance of integration while contradiction/outage information remains fabricated as NONE/false.
- Enabling the scheduler without retiring the subconscious loop creates two competing background controllers.
- Enabling learning review without durable proposal storage still loses decisions across restart.
- Provider-specific integration may fail only under real streaming, partial delivery, or capability loss; schema conformance alone is insufficient.
- Historical RTX measurements remain useful component evidence, but none can be generalized to the not-yet-composed production architecture.
- The initial integration should be treated as high-risk and verified under real NATS, databases, Ollama/provider swap, TTS, STT, and restart—not only mocks.

## Final Engineering Verdict

The repository is **not ready to be declared a complete implementation of the accepted humanoid-brain architecture**. It has a strong foundation, a large passing test suite, and many individually credible components, but the final integration claim is falsified by the current production wiring.

Final status: **BLOCKED ON ARCHITECTURE INTEGRATION**. Gemini should assign integration/fix work before any merge or acceptance action. This audit stops here; no fixes, merge, commit, or push were performed.
