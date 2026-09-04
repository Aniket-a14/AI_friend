# Claude Final Cognitive Audit

**Auditor:** Claude (independent pass, completed before reading Codex's audit)
**Scope:** `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`, `orchestration/MASTER_STATE.md`, all six phase gates/acceptance criteria/benchmark results, `.agents/CONTEXT.md`, and direct inspection of `backend/app/` (cognitive, state, agents, llm, voice, vision) plus git history.
**Method:** Seven parallel code-verification passes (one per major mechanism family) instructed to falsify causal-wiring claims by tracing actual call graphs and grepping for production callers, cross-checked against my own direct reads of config, benchmarks, and the engineering ledger. Every claim below cites file:line evidence gathered this way.

---

## Executive Verdict

**The system is not, today, the coherent integrated cognitive architecture that `orchestration/MASTER_STATE.md` declares ("ALL PHASES COMPLETE (6/6). Humanoid Brain Architecture Fully Integrated & Verified").** It is two things layered on top of each other, and they should be evaluated separately:

1. **A pre-existing causal substrate** (built before this six-phase effort) that is genuinely, measurably wired into the live cognitive turn: endocrine (dopamine/cortisol tonic+phasic) state shaping LLM sampling parameters; ACT-R-style memory decay/mood-congruent retrieval that measurably changes what gets recalled; somatic-vision-driven affect bursts; a real (if narrow) predict-then-compare loop for affect valence; trust-gated goal scoring; immutable-persona-tier enforcement; and a genuine non-LLM reflex/barge-in path with turn-ID fencing across the Python/Rust boundary. This part is real cognition-adjacent engineering and deserves to be described as such.

2. **A large, freshly-built layer** (the "six phases" completed in a single 11.5-hour window on 2026-09-04) consisting of well-designed, individually unit-tested, schema-correct modules — bi-temporal memory truth, global-control-modulated candidate selection, calibrated metacognition, governed learning, deterministic planning, episodic simulation, a background-work scheduler — that is **either feature-flagged off by default with no environment override anywhere in the repo, or has zero production callers outside its own module and test file.** In the shipped, default configuration, most of what the architecture document and phase gates describe as "built" and "PASSED" does not run when a user talks to the agent.

Answering the central question directly: **for the newly-built Phase 02-06 material, the answer is "labels/state variables around an LLM pipeline" — the labels (typed dataclasses, enums, schemas) are real and well-engineered, but the causal wiring into behavior is, in the large majority of cases, either absent or permanently starved of the signal that would make it do anything.** For the older substrate, the answer is closer to "genuinely causal," though narrower in scope than the architecture document implies (e.g., the "world model" is a relabeled knowledge graph plus a valence-only prediction loop, not the entity/event/causal model claimed).

This is not primarily a code-quality problem — ruff/radon/mypy/mutation gates are legitimately clean, per the ledger. It is an **integration-verification gap**: the phase-gate process verifies that isolated functions are fast, correct, and unit-tested, and treats that as evidence the corresponding cognitive mechanism is real in the running system. It is not, in most of the cases documented below.

---

## Cognitive Architecture Conformance

Per-mechanism verdict (CAUSAL = genuinely wired into a live turn; SCAFFOLD = real code, no live path; ABSENT = claimed but does not exist; NARROW = real but scoped much smaller than claimed):

| Mechanism | Verdict | Basis |
|---|---|---|
| Perception integration | CAUSAL (narrow) | `PerceptEnvelope` normalization is real (Phase 01, GPU-benchmarked, low overhead); percepts do reach appraisal/attention. |
| Attention/salience | CAUSAL (narrow) | Deterministic-response short-circuit and facial-reflex urgency check genuinely gate what happens before generation; no unified salience-weighted admission arbiter as §7 describes. |
| Working mental state | CAUSAL | Workspace CAS store (Phase 01) is real, tested under 20-writer contention, restart-epoch-fenced. |
| Memory | CAUSAL for the pre-existing RAG/decay layer; SCAFFOLD for bi-temporal belief truth | See Memory section. |
| Appraisal | CAUSAL (legacy path only) | Legacy keyword/ALMA appraisal is live; the newer spec-compliant `appraise_event`/`AppraisalRecord` path has zero production callers. |
| Emotion/mood | CAUSAL | PAD + endocrine tonic/phasic genuinely shape sampling params and memory retrieval. |
| Global control/neuromodulation | SCAFFOLD (off by default) | `derive_global_controls` real; consumption gated behind `Config.PHASE_03_AFFECT_CONTROL=False`, no override found; `learning_gain` is a dead variable even when on. |
| Goals | NARROW | `GoalRecord`/due-goal review exist (Phase 04) but goal-driven candidate generation is thin; only WAIT/SPEAK/ASK-class goals actually compete. |
| World model | ABSENT (as claimed) / NARROW (what exists) | No state-transition/affordance/causal-hypothesis structures anywhere; only a valence-prediction loop is real. See World Model section. |
| Self model | ABSENT (operational tier) / CAUSAL (persona/identity tier) | See Self Model section. |
| Social cognition | NARROW | Trust causal via a collapsed average; richer PersonModel fields unread. |
| Reasoning | CAUSAL but LLM-mediated | No structured non-LLM reasoning layer beyond deterministic reflex/keyword rules. |
| Fast cognition | CAUSAL (narrow, real) | Deterministic responses and facial-startle barge-in genuinely bypass the LLM and preempt in-flight generation, with exact-offset transcript truncation. |
| Slow cognition | CAUSAL (= ordinary LLM call) | Real, but not meaningfully differentiated from "the rest of the pipeline"; L1/L2/L3 lane vocabulary (`interruption_policy`) is write-only. |
| Background cognition | SCAFFOLD (governed) / CAUSAL-BUT-UNGOVERNED (actual) | `BackgroundScheduler` never instantiated in production; the loop that does run (`subconscious_agent`) is ungoverned and still writes dream content into memory. |
| Metacognition | SCAFFOLD | Scoring logic real; the directive it consumes is permanently the neutral default; calibration engine never observes anything in production. |
| Learning | SCAFFOLD (governed) / MEMORY-RELABELED (actual) | Phase 06 governance apparatus 100% unwired; the one channel that runs bypasses review by default. |
| Action selection | SCAFFOLD (off by default) / CAUSAL-BUT-PARTIAL (when on) | See Action Selection section. |
| Expression planning | UNVERIFIED | `SpeechIntent`/voice compilers exist and are unit-tested; no confirmed caller found in `brain_agent.py`/`action.py`/`pipeline.py` (grep returned zero hits) — flagged NEEDS_EXPERIMENT rather than asserted either way, since this audit did not exhaustively trace the voice-agent boundary. |

The pattern that recurs across nearly every "SCAFFOLD" row: the class/schema/enum exists, has a docstring citing the correct architecture section, has a clean unit test, and is completely absent from `grep -rn "<ClassName>" backend/app/` outside its defining file and `backend/tests/`. This is a specific, checkable signature, not a subjective impression — it was independently rediscovered by five of the seven research passes without being told to look for it.

---

## Emotion and Appraisal

**Internal state is genuinely causal, but only through one specific channel, and generated emotional language is not grounded in it.**

- `StateService` (`backend/app/state/agent_state.py:290-410`) implements tonic+phasic dopamine/cortisol exactly as documented in CLAUDE.md: `cortisol_tonic`/`dopamine_tonic` are pure, anti-correlated functions of valence; `release_cortisol`/`release_dopamine` measure burst peaks against the tonic floor, correctly locked via `StateService` wrappers (`agent_state.py:1648-1679`). One minor gap: `release_cortisol`/`release_dopamine` do not immediately refresh `global_controls` inside the lock, unlike `release_adrenaline` (`agent_state.py:1689`) — a brief staleness window, not a correctness break.
- This state flows live into behavior: `core.py:549-550` puts cortisol/dopamine into `plan.payload`; `action.py::_compute_endocrine_options` (867-926) maps them to real `temperature`/`top_p`/`num_predict` used at the actual streaming call site (`action.py:1416-1432`). `_prepended_affect_tag` (`action.py:929-935`) gates literal `<breath_fast>`/`<sigh_soft>` prefixes off numeric arousal/valence — genuine, not LLM free-styling.
- Memory retrieval is mood-congruent and load-bearing: `memory_store.py` threads `current_valence`/`current_arousal`/`current_cortisol` into ACT-R-style scoring (`ACTR_VALENCE_GAIN`, lines 125-126, ~783-794) and a stress-gated embedding-dimensionality truncation (`stress_index`, line 1630) — narrower search under stress, a real behavioral effect, independent of any Phase 03 flag.
- Somatic vision → affect is real: `SomaticAppraiser.appraise` (`somatic.py:168-207`) called from `brain_agent.py:371`, feeding `apply_somatic_perception` which lifts valence/arousal and fires `release_dopamine` inside the same lock.
- **A second, spec-compliant appraisal path exists and is decorative.** `appraise_event`/`AppraisalRecord` (`appraisal.py:31-138`) plus `StateService.appraise_and_apply_event` are real, correctly locked, and pass their own unit tests (`test_causal_affect.py:206`) — but have **zero callers in `brain_agent.py`, `pipeline.py`, or `core.py`**. The live path is still the older keyword/ALMA appraisal.
- **Generated emotional language is not grounded beyond the sampling-parameter shift.** The system constrains *how* text is sampled (temperature/top_p narrows under cortisol) but not *which* emotion words the LLM chooses to write. A model can say "I'm really worried about you" under any PAD state; nothing checks the word against the number. This is the theatrical-emotion risk the task asked to flag — it is present, but bounded (the sampling constraint is real, so it's not *purely* theatrical, just partially).

**Verdict: PARTIALLY SUPPORTED.** Internal state is causal through endocrine sampling and memory retrieval. It does not reach decisions, risk/persistence weighting, or social behavior through the mechanism the architecture document describes (global controls) because that mechanism is off by default (see next section).

---

## Global Control / Neuromodulation

For each of the four claimed controls:

| Control | Computed from | Actually consumed by | Status |
|---|---|---|---|
| `urgency_gain` | `derive_global_controls` (`global_controls.py:51-97`), refreshed at ~10 call sites in `agent_state.py` | `action_candidate.py::_control_modulation` (173-202), read via `decision.py:1076` | **PARTIALLY-WIRED** — real, behaviorally tested (`test_global_control_selection.py:145-168` shows the winning candidate literally changes), but gated behind `Config.PHASE_03_AFFECT_CONTROL: bool = False` with no `.env`/compose override anywhere in the repo |
| `exploration_budget` | same | same | same gating |
| `effort_budget` | same | same | same gating |
| `learning_gain` | `global_controls.py:94-96`, stored in snapshots | **nothing** — full-repo grep found zero consumers | **DECORATIVE / DEAD VARIABLE** |

The tracked state (`derive_global_controls`) is computed correctly and the modulation code that *would* consume it is real and behaviorally tested — this is not vaporware, it is a genuinely built mechanism sitting behind an off switch nobody flips in the shipped configuration. `decision.py:832` gates entry into the whole candidate-selection branch on `Config.PHASE_02_MEMORY_TRUTH or Config.PHASE_03_AFFECT_CONTROL`; both default `False` (`config.py:232,243`); no override exists in any `.env*` or `docker-compose*.yml` in the repo.

**Reproducible behavior change, when enabled:** yes — `test_high_urgency_favors_fast_low_risk_candidate` demonstrably flips the winning candidate. **Is the mechanism useful without biological naming?** Yes, the design (bounded [0,1] engineering knobs) is sound. **Is it decorative in the product today?** For three of four controls: yes, because the switch is off. For the fourth (`learning_gain`): yes, unconditionally.

**Verdict: PARTIALLY SUPPORTED**, contingent on a configuration change nobody has made.

---

## Memory

Two systems coexist and are largely disconnected:

**(A) The pre-existing RAG/decay pipeline (`memory_store.py`, `lexicon_store.py`, `semantic_recall_store.py`) — genuinely more than plain RAG, production-wired.**
- `_base_activation` (`memory_store.py:717-750`, ACT-R formula: `ln(recall_count) − d·ln(hours_since+1) + importance + emotional-proximity + spacing_bonus`) is the shared scoring function across every retrieval branch (Postgres/SQLite/Qdrant) — decay measurably changes ranking, not a dead field.
- `_compute_actr_decay`/`_archive_and_delete_decayed_memories` (4114-4166) run from the real background tick (`subconscious_agent.py:512,815`), not just available-but-uncalled.
- Provenance is real and consumed: `source` is stored, surfaced, and branches presentation logic (`action.py:733`, biography-source handling) to prevent self/user attribution errors.
- Contradiction detection exists (`find_contradiction`, `memory_store.py:1336-1386`) but is **detection-only**: nothing in `search_memories` filters or downweights a contradicted row using `contradicts_id` — old and new stand with equal weight at retrieval.

**(B) The spec-compliant bi-temporal belief system (`memory_records.py`, `temporal_store.py`) — real, well-tested, and not reachable from a live turn.**
- `ExperienceRecord`/`BeliefRecord` genuinely implement immutability, `valid_from`/`valid_until` intervals, and correct supersede-don't-erase semantics for all four contradiction classes (UPDATE/CORRECTION/CONFLICT/ELABORATION), verified against `test_memory_truth.py:168` (CONFLICT halves confidence on both records — exactly as coded).
- `TemporalMemoryStore` is **never instantiated anywhere in `backend/app/`** — only in its own module and its test file. It sits behind `Config.PHASE_02_MEMORY_TRUTH: bool = False`, no override found.
- The one production constructor of `MemoryActivation` (`memories_to_activations`, `memory_activation.py:151-205`) **always sets `contradiction_state="NONE"`** by explicit design ("a legacy dict carries no belief-contradiction information") — so even if the flag were flipped on, the contradiction-driven ASK branch in `decision.py:971-994` would remain unreachable until the two systems are actually connected.
- Anti-injection: retrieved text is always delimiter-wrapped (`_wrap_retrieved`, `action.py:367-377`, always-on, real), but active pattern-based sanitization (`AntiInjectionGate.sanitize_memory_text`) only runs `if Config.PHASE_02_MEMORY_TRUTH` — the repo's own test (`test_build_shared_history_leaves_text_unsanitized_when_flag_off`) documents that an injected instruction string survives verbatim into the prompt under default configuration.

**Causal influence on decisions:** a real code path exists (`search_memories` → `memories_to_activations` → `decision.py::_build_candidates`, which can append a scored ASK candidate competing against SPEAK/WAIT) — but it requires the default-off flag *and* a `contradiction_state` value the production adapter never produces. `test_high_relevance_disputed_memory_shifts_selection_to_ask` proves the wiring works only because it hand-constructs the `MemoryActivation` bypassing the real adapter.

**Verdict:** episodic/semantic memory-as-*truth-tracking* is REAL-ARCHITECTURE in isolation and PROMPT-RETRIEVAL-ONLY in production. The system currently answers "what do I currently believe" correctly (via decay-weighted RAG) but cannot answer "what did I used to believe, and why did that change" in any way that reaches behavior — the machinery to do so exists, built and tested, switched off.

---

## Self Model and Identity

- **Durable, provider-independent state is real for the narrative/persona tier.** Name, values, tone, boundaries, adaptive traits, relationship label, and memories persist to disk/DB (`identity.py:628-670`, `IdentityCoreStore` with NATS cache invalidation, `identity_core_store.py:183-214`) and survive restarts independent of any single LLM call.
- **The IMMUTABLE tier is genuinely enforced in code, twice over**, not just documented: `IMMUTABLE_CORE` (`profile.py:143-149`) is deliberately outside `PersonaProfile.model_fields`; `_reject_immutable_overrides` (`profile.py:485-501`) and `IdentityManager._refresh_immutable_core` (`identity.py:477-510`) both independently reject a persona file attempting to set `values`/`boundaries`. This fixed a real historical bug (a shipped `personality.json` once carried `"boundaries": []`, silently disabling the toxicity check).
- **Adaptive trait cap (5) is Pydantic-enforced** (`profile.py:266`, `validate_assignment=True`), but governance beyond the cap is weak: `Config.LEARNING_REVIEW_REQUIRED` defaults `False`, so `evolve_persona` applies a sufficiently self-confident (LLM-self-reported ≥0.8) trait proposal directly, with no rollback mechanism found anywhere.
- **The claimed "operational self model" (§13-14: measured capabilities/limitations, calibrated uncertainty) does not exist.** Zero matches anywhere in `backend/app/` for capability statistics or domain-scoped success/fail tracking. The actual `self_knowledge_store.py` is a hallucination-grounding gate: it checks self-assertions against a seeded biography vocabulary and can surface a gap as a question — a real and useful mechanism, but categorically different from what is claimed.
- **Provider independence is asserted and not demonstrated.** All of the durable state above would survive a provider swap (it lives in Postgres/SQLite/JSON, not in any LLM's context). But the *behavior* the identity produces is entirely a function of one specific model reading and complying with a flattened prompt string (`get_persona_prompt`, `identity.py:735-790`) — nothing measures or bounds this. The only benchmark labeled "Provider Swap" (`BM-GPU-P5-01`) tests two Ollama models, not two providers, and its "authoritative state continuity" assertion is a **tautology**: it compares local Python variables (`person.trust_competence`, `authoritative_affect["valence"]`) that are constructed once and never mutated anywhere in the loop — it cannot fail, and would report "100% INTACT" even if `StateService` did not exist. No test anywhere runs the same persistent identity through two distinct LLM providers and measures behavioral variance, contrary to §40's stated evaluation design.

**Verdict:** Durable identity state is real and correctly gated; its *behavioral expression* remains entirely LLM-compliance-dependent and this dependence is currently unmeasured, not merely under-measured — the one artifact that claims to measure it does not.

---

## World Model

**The claimed world model does not exist; what exists is narrower and mislabeled.**

- A repo-wide grep for the architecture's own vocabulary — `affordance`, `causal_hypothes*`, `expected_next_event`, `state_assertion`, `action_conditioned`, `WorldModel` — returns **zero hits** anywhere in `backend/app/`.
- `graph_db.py` (Neo4j) is confirmed, by its own docstring, plain entity/relationship storage ("Manages persistent entities and relationships"), with only `Agent`/`Entity` uniqueness constraints — no event, transition, or prediction node types. This is precisely the "knowledge graph relabeled as world model" failure mode the task asked to check for.
- `tom.py`'s `UserMentalModel` is a flat dict of inferred valence/arousal/goals/beliefs, compared once against ground truth — no persistence of predicted-vs-actual, no forward transitions.
- **One genuine predict→observe→compare→adapt loop does exist**, in `reappraisal.py` + `pipeline.py`: `record_expected_outcome` sets an expected valence pre-response (`pipeline.py:657-661`); `evaluate_outcome` computes actual outcome and prediction error post-response (`pipeline.py:258`), feeding a hormone-burst adaptation (`pipeline.py:969-1004`). This is real and correctly wired — but its scope is the affective valence of the *next turn*, not entity states, events, or affordances in the world.
- `DomainCalibration.record_observation` (a real Brier-score predict/observe comparator) exists but is never called from the live pipeline (see Metacognition).
- `ActionCandidate.predicted_outcomes` is never compared to what actually happened; its only consumer extracts a string label for a follow-up prompt, not a prediction-error signal.

**Verdict: UNSUPPORTED for the claim as written** ("a model earns the name only when it predicts" — nothing predicts entity/event state and checks itself against reality). **PARTIALLY SUPPORTED for a narrower, legitimate claim** ("the system predicts the affective trajectory of a turn and adapts appraisal weights from the error") — which is a real and defensible mechanism, just not a world model.

---

## Social Cognition

- `PersonModel.trust_competence`/`trust_benevolence` are genuinely separate scalars with asymmetric updates from reliance outcomes (`person_model.py:33-51`) and rupture/repair (`53-78`, rupture drop > 2× repair gain, matching the tested acceptance criterion).
- **But downstream, they are immediately collapsed.** `agent_state.py:223-227` averages `trust_benevolence`, `trust_competence`, and `trust_integrity` into a single `trust` scalar, and it is only this average that reaches behavior: it gates a goal score (`decision.py:476,538`) and buckets into a `relational_stance` label. The competence/benevolence distinction is computed correctly and then discarded before it can matter.
- `PersonModel.current_knowledge`, `disclosures`, `observed_goals`, `obligations`, `rupture_repair_history`, and `can_disclose()` are written and persisted but **never referenced anywhere in `cognitive/*.py` or `agents/*.py`** — no disclosure policy, register choice, or action selection reads them.
- The GPU benchmark's "6.00x drop-to-gain ratio" (Phase 04) is a genuine, real, live-model behavioral measurement of the trust scalar's dynamics — this specific claim holds up.

**Verdict: PARTIALLY SUPPORTED.** Trust is causally wired but only as an undifferentiated average; the richer relationship model the architecture describes (knowledge tracking, disclosure policy, obligations) is decorative. Avoid overstating: there is no theory-of-mind here beyond a single scalar and a flat belief-comparison dict.

---

## Fast and Slow Cognition

**A genuine, narrow fast path exists and is architecturally real — this is one of the system's stronger results.**

- `deterministic_responses.py::evaluate_deterministic_response` is pure keyword matching, zero LLM calls, wired as a real pre-classification short-circuit in `decision.py:405-413` that returns before appraisal or intent classification run.
- Facial-startle barge-in is real end-to-end: `brain_agent.py:312-356` (`is_facial_reflex_interruption_worthy` — literally `reflex_name == "startle"`, no LLM) publishes a confirmed `AudioStop(interrupt=True)`, which cancels the in-flight generation task, truncates the persisted transcript to the exact heard offset (`conversation_store.update_last_assistant_message`), and emits a terminal `OutcomeRecord` into the same ledger normal turns use. On the Rust side, `voice-agent/src/main.rs:699-726` stops actual audio output on turn-ID-fenced `audio.stop` without waiting on Python or an LLM. This satisfies the architecture's invariant that fast and slow actions update the same causal history (#13), and the GPU benchmark (sub-millisecond stop-to-outcome latency, exact byte-offset match) is a credible, real measurement.
- **The causal loop-back is weak:** the truncated-transcript write is the one plausible path for a reflex event to influence later deliberation (it's what memory/persona prompt read back later, per its own docstring), but no confirmed read site was found for it or for the outcome-history ledger — they appear to be write-only audit trails today, not consumed by appraisal.
- **Most of the broader "4-lane" vocabulary is decorative.** `interruption_policy` (meant to route a turn as "reflex" vs "deliberative") is computed and written onto `CommunicativeIntent` but never read anywhere in the app — no dispatcher branches on it. `bt.py` (a behavior-tree framework) has exactly one real consumer (the deterministic-response check above), not a general L0-L3 dispatcher.

**Verdict: GENUINE COGNITIVE LAYERING for the narrow reflex/barge-in case (real, tested, causally wired, cross-language); ORDINARY ASYNC SOFTWARE for the rest of the claimed lane structure.** This is a case where the honest, narrower claim ("we built a real interrupt/reflex system for startle events") is defensible and should be kept; the broader "L0-L3 rate lanes" framing oversells what's there.

---

## Background Cognition

**The governed apparatus the architecture requires is unwired; the apparatus that actually runs is ungoverned and still contaminates memory.**

- `BackgroundScheduler` genuinely implements budget enforcement (`asyncio.wait_for`), idempotency (dedupe keys), priority ordering, and reentrant preemption — real, well-tested code. But `grep -rn "BackgroundScheduler("` across `backend/app` returns **zero production instantiations**; `CognitivePipeline` is built without a `scheduler=` argument, so `self.scheduler` is `None` in production and the preempt/resume hooks are permanent no-ops.
- The background work that actually runs is `subconscious_agent.py::_continuous_monologue_loop`, a separate, older, ungoverned `asyncio.create_task` poller — outside the budget/watermark/idempotency system entirely.
- **This loop still writes ungrounded dream content directly into memory.** `_run_dream_sequence` (lines ~723-779) samples random graph entities, asks the LLM to "synthesize a brief, insightful, and slightly surreal dream description... format it as a personal reflection," and writes it via `memory_store.add_memory(..., source="subconscious_dream")` with **no proposal object, no review queue, no approval step**. `search_memories` applies no filter that distinguishes `subconscious_dream`-sourced content from a real memory at retrieval time. This is precisely the failure mode the architecture document explicitly rejects (§19: "Dream/monologue generation is removed"; §37: "Reject: ... dream memories") and which `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`'s own Appendix B describes as a *pre-remediation* problem — **it is not remediated; it is present on `main` today.**
- `LearningReviewQueue`, which *does* gate persona-trait proposals, is backed only by an in-memory `dict`, despite its docstring claiming "durable" — a restart silently drops any pending review.
- The one acceptance-criteria latency claim checked (AC-P4-07, "<5ms preemption") cites `test_background_governed_learning.py`, which **contains no timing assertion whatsoever** — the cited evidence for a specific quantitative claim does not measure that quantity, and the class the separate (real) micro-benchmark measures is never instantiated in production regardless.

**Verdict: UNBOUNDED-OR-DECORATIVE.** The bounded, reviewable system was built and tested but never turned on; the system actually running today does not meet the architecture's own bounded-execution and epistemic-quarantine requirements, and produces autobiographically-contaminating output as a matter of routine operation.

---

## Metacognition

**Decorative in production, with the specific mechanism of failure being "starved input," not "missing logic."**

- The consumer logic is real: `action_candidate.py`'s ABSTAIN hard-filter (104-132, 476-509) genuinely disqualifies SPEAK candidates, and `decision.py:971-994`'s contradiction-triggered ASK candidate genuinely competes in scoring.
- **But nothing ever produces a non-default signal for either to consume.** `blackboard["metacognitive_directive"]` is never set anywhere in `pipeline.py`/`core.py` — the code's own comment concedes this: *"PROCEED (the default whenever no calibration engine is wired in yet)."* And the sole production `MemoryActivation` constructor always sets `contradiction_state="NONE"`.
- `DomainCalibration.record_observation`/`evaluate_directive` (the empirical Brier-score calibration engine, real and correctly implemented) are called **only from their own unit test**, never from live code. `CapabilityLimitationModel` lives on `AgentState` but nothing ever writes an observation into it.
- Net effect: the four-step calibration loop the architecture requires (predict → observe outcome → update statistic → later decision reads it) has steps 3 and 4 built and tested; steps 1 and 2 never happen in production. Any uncertainty the user perceives today is unconstrained LLM text ("I'm not sure..."), exactly the failure mode this section was designed to catch.

**Verdict: UNSUPPORTED in production.** Reflection text is not metacognition, and the codebase agrees with that principle in its design (it built a real gate) while failing to feed the gate anything.

---

## Learning

**Be strict, as instructed — under that standard, almost nothing in this codebase is "learning" per the architecture's own definition, and the one thing that runs is explicitly the category the architecture says learning must be separated from.**

- Two incompatible `LearningProposal` schemas exist. The live one (`learning_review.py`, invoked from `learning.py:236-286`) is bypassed by default: `Config.LEARNING_REVIEW_REQUIRED=False` means a confident reflection-LLM proposal calls `identity.evolve_persona(suggestions)` **directly**, with no held-out test, no counterfactual baseline, no post-activation measurement, no rollback. Even when a proposal *is* submitted to the queue, `approve()`/`reject()`/`rollback()` are never called by any production code path — proposals sit in `pending()` forever, and no route or agent exposes them.
- The Phase 06 governance apparatus (`learning_governance.py`: `LearningGovernor`, risk-tiered approval, atomic bit-for-bit rollback — genuinely well-built and correctly tested, including a real rollback test that verifies `state_applier` gets called with `rollback_value`) is imported by **nothing** in `backend/app/` outside its own file.
- The Offline Adapter Gate (`adapter_gate.py`) is a real, correct metadata state machine — but it swaps only an internal version-string record. **No `.safetensors` or LoRA artifact exists anywhere in the repository**, and its only non-test caller (a GPU benchmark script) hand-authors fabricated held-out results and a synthetic adapter name. "Qualifies an adapter" currently means "qualifies a simulation of an adapter."
- What actually happens in production is fact/vector storage (`ReflectionService._consolidate_facts`/`_consolidate_episodic_memory`) and direct trait mutation (`evolve_persona`) — the architecture's own taxonomy (§21) calls this "preference adaptation" and "storage," and explicitly states "storage is evidence collection, not automatically learning." By the architecture document's own standard, **the system does not currently learn** in the sense claimed; it accumulates and occasionally mutates a trait string based on unverified self-reported confidence.

**Verdict: UNSUPPORTED for governed learning (Phase 06: built, zero integration). MEMORY-RELABELED for the channel that actually runs.** No held-out/retention/rollback flow has ever executed from a live pipeline path.

---

## Action Selection

**Real machinery, off by default, and incomplete even when on — the most nuanced finding in the audit.**

- When `Config.PHASE_02_MEMORY_TRUTH` or `Config.PHASE_03_AFFECT_CONTROL` is true, `decision.py::_select_action_candidate` genuinely builds 2-5 candidates (SPEAK, WAIT, conditionally ASK/REAPPRAISE/REDIRECT_ATTENTION), runs constraint filtering *before* scoring (`action_candidate.py:300-344`), and scores them — this happens **before any LLM call**, satisfying the core architectural requirement that language should not automatically equal the decision. `test_unsafe_speak_topic_is_rejected_by_constraint_filtering` shows a real case: SPEAK is rejected for boundary violation and WAIT wins, with the rejection reason logged.
- **In the shipped default configuration (both flags off), this entire branch is skipped.** `_plan_social_response` falls through to `action_type = "RESPOND_CHAT"` unconditionally — the default system's language output *is* the chosen action, always, exactly the failure mode §22 warns against.
- **Even with flags on, WAIT is currently non-functional.** A turn where the selector picks WAIT still has `ActionIntent.kind="WAIT"` in the causal trace, but `action.py`'s Stage 8 dispatcher has no `WAIT` branch — it falls through to `_execute_respond_chat` and speaks anyway. The decision and the realized behavior diverge.
- **Only 3 of the architecture's 12 canonical kinds are ever producible** (SPEAK, WAIT, ASK), plus two Phase-03 additions (REAPPRAISE, REDIRECT_ATTENTION). EXTERNAL_ACT, OBSERVE, RETRIEVE, VERIFY, REFLECT, UPDATE_GOAL, UPDATE_STATE, INTERRUPT, and CONTINUE have no generator anywhere in the codebase — the modules' own comments concede this ("a schema ceiling, not a claim that every kind is reachable today").
- `ExternalActionDispatcher` has real authorization/timeout/risk-gating logic, correctly unit-tested in isolation, but is never called by any candidate generator or decision path.

**Verdict: does language output automatically equal the chosen action, in practice? For the shipped default: yes, effectively. With both flags enabled: mostly no for SPEAK/ASK/REAPPRAISE/REDIRECT_ATTENTION (genuinely selected before generation), yes for WAIT (selected but not realized), and 9 of 12 kinds are simply unreachable.**

---

## Provider Independence

Durable state (name, values, boundaries, traits, relationship, memories, trust, affect, endocrine parameters) lives outside any LLM's context and would survive a provider swap by construction — this part is architecturally sound. What is **not** established is behavioral conformance: the sole artifact purporting to test this (`BM-GPU-P5-01`, "Provider Swap TTFT Delta & Continuity") tests two models on the same provider (Ollama) and asserts a tautology (see Self Model section) that cannot fail regardless of what the system does. No test anywhere compares behavioral variance across genuinely different providers (e.g., Ollama vs. the `AnthropicClient` `llm/__init__.py` already supports), and no test compares between-persona vs. between-provider variance as §40 specifies. The claim that "the brain owns the action; the model realizes it" is undermined for exactly the mechanisms (global controls, memory truth, candidate selection) that would make identity survive a weaker model's non-compliance — those are the parts that are off by default.

**Verdict: UNSUPPORTED.** Not falsified — simply never actually tested, despite a benchmark that reports as if it had been.

---

## Behavioral Evidence

Using the §40 evaluation framework's claim list:

| Claim | Status | Basis |
|---|---|---|
| Memory influence | UNSUPPORTED (in shipped config) / PARTIALLY SUPPORTED (flag-on, hand-constructed inputs only) | Real ablation test exists but only via hand-built `MemoryActivation`; production adapter never produces the triggering value; flag off by default |
| Emotional influence | PARTIALLY SUPPORTED | Endocrine→sampling real and unconditional; global-control→selection real but off by default |
| Global control | PARTIALLY SUPPORTED | 3/4 controls real-but-gated; 1/4 (`learning_gain`) fully dead |
| Personality stability / Provider independence | UNSUPPORTED | Only "test" is tautological and same-provider |
| Identity persistence | PARTIALLY SUPPORTED | State persists; expression fidelity across models unmeasured |
| Relationship continuity | PARTIALLY SUPPORTED | Trust dynamics real (6.00x rupture ratio, live-measured); richer fields unread |
| Self-model consistency | UNSUPPORTED | No operational self model exists |
| World-model prediction | UNSUPPORTED (as claimed) | Only a valence-prediction loop exists, out of scope of the claim |
| Metacognitive calibration | UNSUPPORTED | Calibration engine never observes anything live |
| Learning improvement | UNSUPPORTED | No held-out/retention/rollback ever exercised from a live path |
| Fast-path latency | **SUPPORTED** | Real GPU-measured sub-ms barge-in with exact-offset truncation |
| Action-selection quality | NOT YET TESTED (shipped config) / PARTIALLY SUPPORTED (flag-on) | Real when enabled; WAIT non-functional; most kinds unreachable |
| Background value | UNSUPPORTED (negative finding, not merely untested) | Governed scheduler unwired; actual loop contaminates memory |
| Voice boundary | NOT YET TESTED by this audit | No confirmed production caller found; not exhaustively traced (F16) |
| Vision boundary | NOT YET TESTED by this audit | Out of scope of the seven dispatched research passes (F17) |

Only **fast-path latency/barge-in** clears a clean SUPPORTED bar with real, live, GPU-measured behavioral evidence end to end. Everything else is either unmeasured, measured only on unwired code, or measured with an invalid instrument (the provider-swap tautology).

---

## Scientific Defensibility

Flags, with evidence:

- **Biological/consciousness overclaiming:** none found in current code identifiers (the "hormone" names were already being retired per the architecture doc, and code comments elsewhere show awareness of the distinction). Not a live issue.
- **"World model" overclaiming:** confirmed — see World Model section. The architecture document's own falsification test ("a model earns the name only when it predicts") was applied and the claim fails it for entity/event state.
- **"Learning" overclaiming:** confirmed — the architecture document's own definition ("storage is evidence collection, not automatically learning") is violated by MASTER_STATE.md and the Phase 06 gate calling the shipped `evolve_persona` mechanism part of a "learning" architecture, when governed learning is unwired and the live channel is exactly the un-governed preference mutation the spec warns against.
- **Metacognition-as-reflection overclaiming:** confirmed — the architecture document explicitly warns "reflection text alone is not metacognition," and the shipped system currently has no other kind.
- **Process/pace defensibility (new finding, not in the original per-mechanism checklist but load-bearing for how much confidence to place in every "PASS"):** all six phases — each independently gated with acceptance criteria, benchmark suites, GPU validation, and phase-gate sign-off — were implemented, tested (2,332 total tests, mutation-tested, radon/ruff/bandit clean per the ledger), and merged within an **11.5-hour single-day window** (`git log`: first phase-01 commit `bad24de` at 09:46, final phase-06 commit `f0333fc` at 21:15, both 2026-09-04), adding **22,283 insertions across 76 files** (`git diff --shortstat bad24de f0333fc`). This is not, by itself, proof of low quality — the per-mechanism unit tests that exist are generally real and well-constructed, as the seven research passes confirmed repeatedly. But it is directly consistent with, and likely explanatory of, the dominant pattern found throughout this audit: code, schema, and isolated tests were produced at a pace that did not leave room for the separate, slower step of wiring each mechanism into the live pipeline and verifying it there — and the phase-gate process itself does not check for that gap, so it was never caught before being declared "PASS" and "fully integrated" six times in a row.
- **Benchmark-as-behavioral-evidence overclaiming:** the large majority of "PASS" benchmarks (BM-LOC-*, most BM-GPU-*) measure microsecond-scale latency of isolated pure functions or standalone unwired classes — they are legitimate performance benchmarks but were repeatedly cited in phase gates as if they were behavioral/integration evidence. A benchmark showing `derive_global_controls` runs in 1.3μs says nothing about whether it's ever called with a live turn's data (it mostly isn't, by default).

---

## Strongest Research Contributions

Genuinely worth keeping and building on:

1. **The endocrine sampling-parameter pathway.** Correctly locked, mathematically well-specified (burst-relative-to-tonic-floor), and causally reaches LLM generation parameters unconditionally. This is a real, if modest, instance of internal state changing model behavior without the model having to read and obey a sentence about it.
2. **ACT-R-style memory decay/mood-congruent retrieval**, load-bearing across all three storage backends. Real cognitive-science grounding, measurably changes retrieval, and is production-wired.
3. **The reflex/barge-in path.** Cross-language (Python↔Rust), turn-ID-fenced, exact-byte-offset transcript truncation, sub-millisecond GPU-measured latency. This is hard real-time systems engineering done correctly and is a legitimate technical differentiator.
4. **Three-tier persona schema with code-enforced (not conventional) immutability**, including a documented case where the enforcement caught a real production bug (an empty `boundaries` list silently disabling a safety check).
5. **The unwired-but-well-designed governance schemas** (`LearningGovernor`, `SimulationQuarantine`, `DeterministicPlanVerifier`) are worth explicitly noting as *close* rather than worthless — their internal correctness (atomic rollback, cycle detection, quarantine tagging) is real engineering that would become valuable the moment they are actually called from the live pipeline. This is different from decorative code that would need to be redesigned; it mostly needs to be *connected*.

## Weak/Unsupported Claims

1. "Operational self model" — does not exist.
2. "World model" — does not exist as specified; relabeled graph storage plus a narrow valence-prediction loop.
3. "Provider independence, demonstrated" — the demonstration is invalid (same-provider swap, tautological check).
4. "Metacognition" — decorative; consumer logic exists, is permanently fed the neutral default.
5. "Trusted, governed learning" — the governance is unwired; the live channel is the ungoverned case the spec explicitly separates learning from.
6. "Background cognition, bounded and grounded" — the bounded system is unwired; the actual background loop still writes ungrounded dream content into memory, the specific failure the target architecture rejects by name.
7. "General action selection before language" — real only behind an off-by-default flag, and incomplete (WAIT non-functional) even then.
8. "Six-phase architecture fully integrated and verified" (MASTER_STATE.md) — contradicted by the above; "fully implemented and unit-tested, partially integrated" is the defensible claim.

---

## Findings

**F1 [BLOCKER]** Phase 02 (memory truth) and Phase 03 (global control/candidate selection) are gated behind `Config.PHASE_02_MEMORY_TRUTH`/`Config.PHASE_03_AFFECT_CONTROL`, both `bool = False` (`backend/app/config.py:232,243`), with no override anywhere in the repo's `.env*`/compose files. In the default, shipped configuration, `decision.py:832` never enters candidate selection; the LLM's generated reply is unconditionally the action. Everything downstream of this flag (contradiction-driven ASK, constraint-first SPEAK rejection, urgency/exploration/effort-modulated scoring, anti-injection active filtering) is inert by default.

**F2 [BLOCKER]** Dream synthesis into memory, explicitly rejected by `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` §19/§37 and previously flagged as a pre-remediation problem, is still live: `subconscious_agent.py::_run_dream_sequence` (~723-779) writes LLM-generated "dream" text directly into `memory_store.add_memory(source="subconscious_dream")` with no proposal, review, or approval step, and `search_memories` applies no filter distinguishing it from a real memory.

**F3 [BLOCKER]** The only benchmark presented as evidence of provider independence (`BM-GPU-P5-01`, "Provider Swap TTFT Delta & Continuity," reported PASS in `orchestration/PHASE_05/BENCHMARK_RESULTS.md`) tests two models on the same provider (Ollama: `llama3.2:3b` vs `qwen2.5:3b`) and its "continuity" assertion compares local Python variables that are never mutated in the benchmark loop — a tautology that cannot fail. No genuine cross-provider or persona-vs-provider-variance test exists anywhere in the repository.

**F4 [HIGH]** `BackgroundScheduler` (Phase 04's bounded/preemptible/idempotent background-work system, §19) has zero production instantiations; `CognitivePipeline` is built without a `scheduler=` argument. The background work that actually runs (`subconscious_agent`'s monologue loop) is outside this governance entirely, compounding F2.

**F5 [HIGH]** Phase 06's complete learning-governance apparatus (`LearningGovernor`, `LearningApprovalGate`, atomic rollback) and deterministic planning/simulation apparatus (`DeterministicPlanVerifier`, `DeterministicPlanExecutor`, `EpisodicSimulator`) have zero callers anywhere in `backend/app/` outside their own module and test file — confirmed by grep and corroborated by the project's own ledger entry ("NOT done: no production memory/store, NATS, or action-service wiring was introduced"). The Phase 06 gate nonetheless records an unqualified PASS and MASTER_STATE.md calls the mechanism "fully realized."

**F6 [HIGH]** Metacognition is decorative in production. The consumer logic (ABSTAIN hard-filter, contradiction-triggered ASK) is real, but `blackboard["metacognitive_directive"]` is never set away from its default ("PROCEED") anywhere in the live pipeline, and the sole production `MemoryActivation` constructor always sets `contradiction_state="NONE"`. `DomainCalibration.record_observation`/`evaluate_directive` are called only from their own unit test.

**F7 [HIGH]** The only learning channel that runs by default (`ReflectionService.evolve_persona`) bypasses governance: `Config.LEARNING_REVIEW_REQUIRED` defaults `False`, so a self-confidence-gated (self-reported by the same LLM, ≥0.8) persona-trait proposal applies directly with no held-out test, counterfactual baseline, or rollback — violating the architecture's own "storage/reflection is not learning" distinction in the one place it actually matters.

**F8 [HIGH]** The claimed "operational self model" (measured capabilities/limitations, calibrated uncertainty, §13-14) does not exist anywhere in the codebase (zero grep matches). The actual `self_knowledge_store.py` is a hallucination-grounding gate against seeded biography vocabulary — real, useful, and categorically different from the claim.

**F9 [HIGH]** The claimed world model (state transitions, causal hypotheses, affordances, action-conditioned prediction, §12) does not exist (zero grep matches for the architecture's own vocabulary). `graph_db.py` is confirmed plain entity/relationship storage. The one real predict-then-compare loop (`reappraisal.py`) is scoped to next-turn affect valence, not environment state.

**F10 [MEDIUM]** Action selection's WAIT candidate can win scoring/constraint-filtering and appear in the causal trace as `ActionIntent.kind="WAIT"`, but `action.py`'s Stage 8 dispatcher has no `WAIT` branch, so the turn still executes `_execute_respond_chat` and speaks. Of 12 canonical `ActionCandidate` kinds, only SPEAK/WAIT/ASK (+ Phase-03's REAPPRAISE/REDIRECT_ATTENTION) are ever producible; the other 7 have no generator anywhere.

**F11 [MEDIUM]** `PersonModel`'s disclosure/knowledge/obligation/rupture-repair-history fields are written and persisted but never read by any decision logic; only a collapsed 3-way trust average reaches behavior, discarding the competence/benevolence distinction the model otherwise correctly maintains.

**F12 [MEDIUM]** A second, spec-compliant appraisal path (`appraise_event`/`AppraisalRecord`) exists, is correctly built and tested, and has zero callers in the live pipeline — the older keyword/ALMA path is what actually runs. `learning_gain`, one of four headline global-control signals, is computed and stored but read by nothing anywhere in the codebase.

**F13 [MEDIUM]** The Offline Adapter Gate (Phase 06) never touches a real inference backend; no LoRA/adapter artifact exists anywhere in the repository, and its only non-test caller fabricates held-out results and a synthetic adapter identifier.

**F14 [LOW]** `interruption_policy`, meant to route a turn into a reflex vs. deliberative lane (§17), is computed and written but never read by any dispatcher; the broader L0-L3 vocabulary is descriptive labeling except for the genuine reflex/barge-in path.

**F15 [LOW]** `AntiInjectionGate.sanitize_memory_text` (active pattern-based filtering of retrieved text) only runs when `Config.PHASE_02_MEMORY_TRUTH` is true (default off); the repo's own test documents that an injected instruction string survives verbatim into the prompt under default configuration. Passive delimiter-wrapping is always-on and reduces but does not eliminate the exposure.

**F16 [NEEDS_EXPERIMENT]** Whether `SpeechIntent`/voice compilers (Phase 05) are actually invoked in the live `brain_agent` → voice output path was not conclusively traced by this audit (a spot-check grep found no reference in `brain_agent.py`/`action.py`/`pipeline.py`, consistent with the dominant pattern elsewhere, but not exhaustively confirmed). Recommend a dedicated trace before relying on this claim either way.

**F17 [NEEDS_EXPERIMENT]** Vision boundary claims (§24: structured percepts, anti-emotion-fact invariant) were not directly audited in this pass; Phase 05's `StructuredVisionPercept`/adapters were confirmed to exist and pass unit tests via the ledger only, not independently traced for live-turn reachability.

**F18 [HIGH]** Process finding bearing on how much confidence any individual phase-gate "PASS" should carry: all six phases were implemented, unit/mutation/complexity-tested, GPU-benchmarked, and gated PASS within an 11.5-hour single-day window (2026-09-04, 09:46-21:15 per `git log`), adding 22,283 lines across 76 files. Combined with F1-F13, this indicates the phase-gate process verifies code construction and isolated correctness, not behavioral integration — and did not catch, across six consecutive gates, that its own headline mechanisms were not reachable from a live turn.

---

## Recommended Fixes or Experiments

*(Recommendations only — no implementation performed in this audit, per task instructions.)*

1. **Before any further phase work:** add an integration-reachability check to the phase-gate template itself — for every new class/module a phase introduces, require a grep-verifiable production call site (not just a test), or an explicit, justified "NOT YET INTEGRATED" entry in the acceptance criteria rather than a bare PASS.
2. Decide, explicitly, whether `PHASE_02_MEMORY_TRUTH`/`PHASE_03_AFFECT_CONTROL` should default `True` now that their mechanisms are unit-tested; if yes, re-run the GPU/behavioral benchmarks with the flags on (the existing PASS numbers were measured with them off, in the default path, for most of the "E2E turn latency" benchmarks) before claiming production readiness.
3. Fix or remove F2 (dream-to-memory) immediately given it directly contradicts an explicit architecture rejection and contaminates autobiographical memory in the running system today — this is the one finding with a plausible real-world integrity cost independent of any flag.
4. Wire `contradiction_state` from the real bi-temporal contradiction classifier (system B in Memory section) into the production `MemoryActivation` adapter, or retire one of the two parallel memory-truth systems — maintaining both indefinitely doubles review surface for no behavioral benefit.
5. Add a `WAIT` branch to `action.py`'s Stage 8 dispatcher, or remove WAIT from the selectable candidates until one exists — a decision that is computed, logged, and then silently overridden is worse than not making the decision.
6. Connect `DomainCalibration`/`CapabilityLimitationModel` to at least one real observation source (e.g., record an observation whenever a claim is later confirmed/contradicted by the user) before citing metacognition as a capability.
7. Run the §40-specified provider-independence experiment for real: same persistent state through Ollama and a second, architecturally different provider (e.g., `AnthropicClient`), measuring behavioral variance against between-persona variance — the current benchmark should be relabeled or removed, not cited as evidence.
8. Either wire `BackgroundScheduler` into `CognitivePipeline` and migrate `subconscious_agent`'s loop onto it, or explicitly document that background cognition currently runs ungoverned and scope its risk accordingly.
9. For Phase 06 specifically: either invest the integration work to connect `LearningGovernor`/`DeterministicPlanVerifier`/`EpisodicSimulator` to the live pipeline, or reclassify Phase 06 in `MASTER_STATE.md` as "designed and unit-verified, not integrated" rather than "PASS."
10. Independently trace F16/F17 (voice and vision boundary reachability) before the next audit round, since this pass did not cover them with the same rigor as the other twelve sections.

---

## Final Cognitive Verdict

The repository contains a smaller, older, genuinely causal cognitive substrate (endocrine-modulated sampling, decay-weighted mood-congruent memory retrieval, a real cross-language reflex/interrupt path, enforced identity immutability) surrounded by a much larger, newly-built layer of architecturally correct, individually well-tested, but almost entirely disconnected scaffolding that was produced across six phases in a single day and certified "fully integrated" without a check that would have caught the disconnection. Where the architecture document asks "does this mechanism affect cognition or behavior" (§1) for global control, memory truth, metacognition, learning, background governance, and most of action selection, the honest answer today is **no, not in the shipped system** — and where a mechanism *would* affect behavior if enabled, the switch is off and no deployment artifact turns it on.

This is a recoverable state, not a design failure: the code that exists is mostly the right code, correctly built, and the fix for the majority of findings here is integration wiring and configuration, not a rewrite. But `orchestration/MASTER_STATE.md`'s claim of "Humanoid Brain Architecture Fully Integrated & Verified" is not supported by the evidence gathered in this audit and should not be treated as accurate until the findings above — particularly F1, F2, and F3 — are resolved and re-verified against a live, default-configuration turn rather than an isolated unit test or a flag-enabled benchmark.
