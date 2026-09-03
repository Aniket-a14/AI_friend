# AI_friend — Humanoid Architecture Research and Deep Audit

**Date:** 2026-09-02
**Repository state audited:** local `research` at `c4fe1c5` (two Phase 0 commits ahead of `origin/main` at `7a42c2a`)
**Scope:** architecture audit and research, with the evidence-driven Phase 0
blocker repair recorded in the follow-up ledger below. Phase 1 cognitive
contracts remain unimplemented.

## Executive summary

AI_friend is already more than a prompt wrapper. It has a real event-driven runtime, deterministic affect and turn-taking logic, several persistent stores, retrieval, a behavior-tree/MAUT decision layer, asynchronous reflection, Rust audio agents, and typed cross-process contracts. Those parts are valuable.

It is not yet a persistent learned organism. The decisive behavioral act—what to say, how to preserve character under pressure, and much of how state is converted into language—is still delegated to a free-form LLM conditioned by a large prompt. Identity, state, memory, and expression have multiple partially overlapping authorities. The system therefore has persistence around a generative center, rather than an embodied policy that merely uses language generation to realize a prior decision.

The practical recommendation is **Architecture B: cognitive architecture plus a small LLM**, with one important clarification: the LLM should become a typed realization service, not the owner of identity, safety, goal selection, or expressive intent. Architecture C—learned persistent organism—is a research track, not the next production rewrite.

The immediate model conclusion is **do not train Bucket 19 yet**. The `phi4-mini` runs show a repeatable persona-adherence failure, but do not isolate whether the dominant cause is model capability, prompt composition, evaluation path, or deployment configuration. A LoRA trained from this teacher would risk distilling generic-assistant behavior into weights. Redesign the gate and establish a genuinely in-character teacher set first. Keep `phi4-mini` as a candidate rather than declaring it categorically unusable.

The immediate voice conclusion is **keep GPT-SoVITS and change the control boundary**. GPT-SoVITS currently provides the project’s cloned voice and streaming path. The main weakness is not that it lacks a new TTS engine; it is that text, temporal controls, emotion, and speech intent are mixed together. Introduce a structured expression side channel before making another engine swap.

## Evidence discipline

The supplied mission prompt, `README.md`, `.agents/CONTEXT.md`, archived plans, and prior ledger entries were treated as hypotheses or historical evidence. Current source code, current tests, current Compose wiring, and observed evaluation artifacts were the first driver.

- **VERIFIED:** directly supported by current source, a current test, a tracked artifact, or a cited commit.
- **LIKELY:** a strong architectural inference from verified code, but not isolated by a controlled experiment.
- **HYPOTHESIS:** a proposed explanation or design requiring an experiment.
- **UNKNOWN:** the repository does not contain enough evidence to decide.

The audit does not treat a passing unit test as proof of a live mesh property, a stale plan as proof of current deployment, or a generated report as proof that it exercised production code. In particular, the archived ledger says the home-GPU process was configured with `phi4-mini`, while the repository defaults and Compose fallbacks still name `llama3.2:3b`; the live process was not available in this workspace for re-verification.

## 1. Current architecture reconstructed from code

```text
 microphone / LiveKit
        |
        v
 Rust stt-agent -- VAD/endpointer -- SenseVoice or Whisper fast perception
        |                                      |
        | chat.input                         | audio.perception / speculative stop
        v                                      v
                    NATS mesh
                         |
                         v
 Python brain-agent
   CognitiveService
     Perception -> Appraisal -> Reappraisal -> Decision/BT/MAUT
       -> ActionService -> Ollama/Anthropic LLM -> chat.output chunks
              |                 |                  |
              |                 |                  +-- free-form text + inline tags
              |                 +-- reflection, facts, persona evolution
              +-- AgentState / MemoryStore / GraphDB / identity stores
                         |
                         v
 Rust voice-agent -- GPT-SoVITS HTTP stream -- prosody/audio filters
                         |
                         v
                     audio.stream -> LiveKit

 system-agent -> system.tick -> state decay / proactive scheduling
 subconscious-agent -> reflection/proactive work -> chat.input or state effects
 surfacing-agent -> memory retrieval/surfacing -> brain context
 vision-agent [Compose profile, not default] -> frame/VLM/reflex events
```

**VERIFIED:** the integration boundary is NATS subjects, not synchronous RPC. Python agents use the `BaseAgent` JetStream abstraction; the Rust voice and STT subscribers use core NATS subscriptions while publishing important events through JetStream. This gives different delivery/replay semantics on the two sides of the same conceptual channel.

**LIKELY:** the mesh is operationally a distributed actor system with a shared database, not a single cognitive process. Local locks protect each process’s copy, not the whole organism.

### Runtime processes and ownership

| Process/component | Actual responsibility | Main inputs | Main mutations/outputs | LLM dependency |
|---|---|---|---|---|
| `stt-agent` | Audio decoding, downmix/resample, VAD/endpointer, final Whisper transcript, fast acoustic perception, speculative stop hint | `audio.inbound` | `chat.input`, `audio.perception`, `audio.stop` | No for Whisper/SenseVoice inference path |
| `brain-agent` | Turn orchestration, CognitiveService lifecycle, input cancellation, playback-aware truncation, context assembly, `chat.output` publication | `chat.input`, perception, vision, playback, stop/resume | state updates, memories, responses, mesh events | Yes, through CognitiveService/ActionService |
| `system-agent` | Periodic heartbeat | timer | `system.tick` | No |
| `subconscious-agent` | Idle/proactive thought, reflection/consolidation scheduling, rest replay | ticks and relevant state/events | proactive input, reflection work | Yes for generative thought/reflection |
| `surfacing-agent` | Proactive memory retrieval and scoring | ticks/current context | `memory.surfaced` | Mostly deterministic retrieval/scoring; inspect deployment before assuming no LLM in every path |
| `vision-agent` | Camera/screen capture, VLM semantic appraisal, distance estimate, CPU facial reflex | local capture | frames, descriptions, facial reflex events | VLM optional; reflex path does not use an LLM |
| `voice-agent` | TTS HTTP streaming, reference-clip selection, temporal tag parsing, attenuation, reverb/framing, audio publication | `chat.output`, modulation, stop/resume, vision/noise telemetry | `audio.stream` | No text LLM; GPT-SoVITS is a separate model/service |
| `CognitiveService` | Composition root for identity, state, perception, appraisal, decision, action, reflection, stores | typed cognitive events | pipeline outputs and persistence | Yes in perception/decision/action/reflection |
| `MemoryStore` | Episodic storage/retrieval, embeddings, ACT-R-like activation, novelty/consolidation, visual traces | text, affect, time, cues | relational memory records, vector index, archive state | Embeddings use a model; semantic reflection may use LLM elsewhere |
| `IdentityManager` | Authored persona loading, immutable core, adaptive fields, prompt construction, response boundary check | persona files, durable config, reflection suggestions | prompt, JSON/config-store identity, cache sync | Prompt consumer; evolution suggestions are LLM-produced |

## 2. Perception, internal state, memory, cognition, expression, infrastructure

### Perception

**Audio perception — VERIFIED.** `stt-agent` consumes raw PCM, decodes/downmixes/resamples to 16 kHz, runs an energy endpointer, and sends final transcripts through `base.en` Whisper. The fast path prefers SenseVoice when its model is present; otherwise it falls back to a Whisper fast model and explicitly omits emotion fields rather than fabricating neutral emotion. SenseVoice can add emotion/events to `audio.perception`. The speculative stop vocabulary is deliberately narrow (`stop`, `wait`, `hold`, `wrong`, `quiet`) and is claimed once per utterance.

**Visual perception — VERIFIED but deployment-gated.** `VisionAgent` captures camera or screen frames, publishes raw frames, and periodically calls a VLM through `VisualAppraisalService`. A continuous facial-reflex path uses MediaPipe blendshapes and fixed thresholds for smile, brow furrow, and startle; it does not call a language model. VLM calls are rate-limited, habituation-gated, and circuit-breaker protected. Compose places vision behind a profile, so the default production stack is not necessarily visually embodied.

**Perception authority — LIKELY.** Perception produces hypotheses and observations; it does not own identity or final interpretation. However, the boundary between “observed fact,” VLM prose, and model-generated interpretation is not represented by a common typed evidence object. A VLM description can arrive as text and become part of a later LLM prompt, which makes its epistemic status easy to lose.

### Internal organism/state

`AgentState` contains short-term PAD-like affect (`mood`, `energy`, `dominance`), three-dimensional trust, attachment, interaction count, goals, fatigue, user mental model, persistent affect baselines, proactive timestamps, and phasic dopamine/cortisol/adrenaline bursts. Properties derive arousal and hormones from stored peaks and elapsed time. Phasic hormones are intentionally not persisted across restart; baselines and proactive timing are persisted.

`StateService` hydrates Redis first, then local SQLite, with Neo4j as a fallback in the broader state path. It applies ticks, ALMA-like decay, trust drift, sensory perception, ToM updates, and proactive eligibility. It broadcasts a full `state.broadcast` snapshot after persistence. The brain and subconscious processes each hold their own `StateService` instance.

- **VERIFIED:** state mutation and persistence are deterministic apart from input observations and clock time.
- **VERIFIED:** local `_state_lock` does not coordinate two OS processes.
- **VERIFIED:** Redis, SQLite, and broadcast persistence are not one atomic transaction.
- **LIKELY:** a stale full snapshot from one process can overwrite newer fields written by another process. This is an eventual-consistency design, not a single authoritative state machine.
- **UNKNOWN:** whether the production host’s Redis and SQLite paths are shared in the exact deployed topology; Compose gives brain/subconscious a shared identity volume but does not make every state database a single transactional authority.

The state layer is therefore a useful deterministic homeostatic controller, but not yet a coherent organism-level state owner.

### Memory

The memory layer is hybrid:

1. relational active/archived records are the durable record;
2. Qdrant/pgvector-style vector retrieval is an accelerator/index;
3. embeddings provide semantic cues;
4. lexical, graph, emotional, novelty, and ACT-R-style activation affect recall;
5. Neo4j stores entity/relationship structure separately;
6. visual screen traces have their own TTL and salience handling;
7. L1 caches and archive promotion optimize hot retrieval.

**VERIFIED:** memory is persistent and restartable when the configured stores are healthy. **VERIFIED:** the design treats SQL records as canonical and vector data as rebuildable search support. **LIKELY:** autobiographical continuity is still weaker than the amount of memory code suggests because retrieval produces snippets, not a durable self-model with explicit provenance, confidence, contradiction handling, or temporal revision semantics.

`WorkingMemoryStore` and `ProactiveQueue` exist as additional primitives, but the cognitive composition does not make them the sole working-memory authority. This is an ownership smell: “working memory,” “current state,” “surfaced memory,” and “context prompt” are separate representations assembled ad hoc.

### Cognition

The cognitive core is a 10-stage asynchronous pipeline. It does perception/appraisal, conflict resolution for speculative stops, state/ToM updates, reappraisal, decision, action, identity validation, and reflection signalling. `DecisionService` uses heuristics, optional LLM intent/goal/ToM classification, MAUT goal scoring, TD-style goal utility updates, and a behavior tree. `ActionService` selects memories, builds the prompt, streams the response, strips thought markup, validates partial output, applies grounding checks, and may request a self-correction stream.

The architecture has a meaningful separation between:

- deterministic state and scoring;
- learned/signal interpretation (Whisper, SenseVoice, VLM, embeddings);
- generative language production;
- asynchronous consolidation.

But the separation is incomplete. The LLM still participates in intent classification, ToM construction, response wording, identity realization, refusal behavior, and self-correction. The behavior tree returns a fairly small `ActionPlan`—often “RESPOND_CHAT” plus a prompt payload—rather than a rich, typed communicative decision.

### Expression

The current expression path is:

1. `ActionService` emits free-form text, with optional `<pause=...>`, `<hesitate>`, `<breath_fast>`, and `<sigh_soft>` markup.
2. `voice-agent` parses the text into temporal parts.
3. GPT-SoVITS synthesizes each text part with a selected reference clip.
4. Rust applies speed/pitch/volume modulation, attenuation, reverb, and byte-framing.
5. PCM is published to `audio.stream`.

`vad_to_prosody` and `agent.voice.modulation` provide a numeric side path, but there is no single authoritative `SpeechExpression` object that carries timing, affect, intensity, prosodic trajectory, voice style, and interruption policy. Inline text tags therefore carry both content-adjacent behavior and transport control.

### Infrastructure

Compose contains NATS, Postgres, Qdrant, Neo4j, Redis, LiveKit, signaling, the Python agents, Rust agents, and an optional vision profile. The runtime has per-agent NATS credentials and a one-shot stream provisioner.

Important current semantics:

- **VERIFIED:** JetStream stream retention and limits are configured in `nats_streams.py`.
- **VERIFIED:** Python subscriptions can be durable/acked; Rust voice/STT subscriptions use core NATS and therefore do not replay missed input.
- **VERIFIED:** brain bootstraps infrastructure/model readiness before the rest of its cognitive lifecycle.
- **VERIFIED:** Compose still uses `llama3.2:3b` in its fallbacks and `.env.example` still names that model.
- **VERIFIED:** `AppSettings` defaults `LLM_FAST_MODEL` to `llama3.2:3b`, and fills chat/reflection from it.
- **UNKNOWN:** the current remote home-GPU environment after the ledger’s `phi4-mini` deployment; that environment is outside this workspace.

This is a solid development mesh, but delivery guarantees are not uniform enough to call it one coherent event log. Audio is intentionally low-latency and lossy; durable cognition is intended to be replayable. Those policies should be explicit in contract metadata rather than inferred from which client library a process happens to use.

## 3. Source of truth and restart behavior

| Concept | Current effective authority | Secondary copies/caches | Restart behavior | Assessment |
|---|---|---|---|---|
| Immutable safety core | `IMMUTABLE_CORE` code constant, surfaced by `PersonaProfile`/`IdentityManager` | IdentityCoreStore and prompt text | Reconstructed | Good safety direction; should remain code/policy-owned |
| Authored persona | `personal/persona.toml` when discovered | compiled profile, raw personality JSON | Re-read | Good seed, but path discovery and deployment env can diverge |
| Adaptive identity | Postgres `agent_configs` when attached and reachable; JSON fallback otherwise | IdentityCoreStore subset, in-memory profile | Restored if same durable store/volume | Multiple authorities and only a subset is mirrored in Tier-1 store |
| Affect/state | Redis first, SQLite fallback, graph fallback; broadcast snapshots | per-process `AgentState` | Usually restored, but source depends on availability | No single event-ordered authority |
| Episodic memory | relational memory records | Qdrant/vector index, L1 cache, graph links | Restored/reindexed | Strongest persistence area, but provenance semantics are thin |
| User mental model | fields inside `AgentState` | prompt snapshot, NATS state broadcast | Restored when state store agrees | Need versioned updates and confidence |
| Goal utility | adaptive weights store | in-memory utility dict | Restored by decision layer | Deterministic learning, but not a broad policy |
| Working memory | distributed/local store plus process context | prompt payloads, queues | Partially restored or lost | Needs a canonical session-scoped owner |
| Speech playback state | Rust process memory, active turn/attenuation | playback progress events | Lost on restart | Appropriate for transient media, but stale resume must be scoped |

### Persistence verdict

**VERIFIED:** restarting the Python brain can restore a substantial identity, memory, and state history.
**LIKELY:** restarting the complete mesh can produce a different effective state depending on which process boots first, which store answers first, and which retained events are replayed.
**UNKNOWN:** exact recovery behavior under simultaneous process restart and concurrent writes; no failure-injection run was available in this audit.

The next architectural primitive should be a versioned `OrganismState` record or event stream with one writer/arbiter, not another cache synchronization broadcast.

## 4. What breaks if the LLM is removed?

### Survives

- PCM transport, VAD, endpointer, final/partial STT.
- SenseVoice acoustic emotion/events when its model is present.
- facial reflex scoring and deterministic distance estimation.
- PAD/homeostatic decay, hormone decay, fatigue, trust arithmetic, proactive eligibility.
- memory storage, vector/lexical retrieval, graph persistence, archive/novelty logic.
- MAUT scoring and behavior-tree mechanics, if supplied with a typed intent/goal.
- identity storage, immutable core checks, queues, NATS transport, TTS if given text.

### Degrades or fails

- LLM-based intent/goal/ToM classification unless replaced by a classifier.
- VLM descriptions, unless replaced by a vision model or fixed perception features.
- natural response generation: `ActionService` has no general response policy or utterance library.
- reflection fact extraction, persona evolution suggestions, episodic consolidation summaries.
- self-correction and grounding phrasing.
- spontaneous thought/proactive language.

The system becomes a persistent sensory/state/memory controller with no general linguistic realization. This is evidence that the code already contains a useful substrate, not evidence that the LLM is currently only a renderer. Today it owns too much of the behavior surface.

## 5. Actual role of the LLM

| Responsibility | Currently owned by | Should be owned by | Why |
|---|---|---|---|
| Raw speech decoding | Whisper/SenseVoice | speech models | Already specialized and deterministic enough |
| Acoustic affect/events | SenseVoice plus state rules | acoustic perception service | Keep uncertainty separate from language |
| Visual caption | VLM | visual perception service | Caption is evidence, not identity or policy |
| Intent and ToM hypothesis | optional fast LLM plus heuristics | typed perception/classifier ensemble with confidence | LLM may assist, but policy must not depend on unvalidated prose |
| Goal selection | MAUT/BT plus LLM hints | deterministic policy over typed evidence | Goal selection is an action decision, not wording |
| Safety/identity boundary | prompt plus `validate_response` | code-owned policy and output gate | Prompt adherence is not a reliable authority boundary |
| Memory retrieval | MemoryStore/Surfacing/GraphDB | memory subsystem | LLM can query/rerank, but cannot be the record |
| Relationship update | StateService and reflection suggestions | state/relationship policy | Need explicit evidence, confidence, and decay |
| Persona evolution | Reflection LLM suggestions plus IdentityManager gates | governed learning pipeline | Learning must be reviewable, reversible, and evaluated |
| Communicative intent | implicit in goal/prompt | `CommunicativeIntent` policy object | Needed for speech, timing, backchannel, and audit |
| Content planning | mostly free-form response model | structured `BehaviorDecision` plus optional LLM proposal | Prevent “generic chatbot” from choosing the whole act |
| Language realization | ActionService LLM | small/medium language model | This is the LLM’s best bounded role |
| Speech expression | inline tags + Rust heuristics | `SpeechExpression` side channel | Separate semantics from acoustic control |
| TTS waveform | GPT-SoVITS | dedicated TTS | Keep specialized model ownership |
| Reflection summarization | reflection LLM | LLM-assisted consolidation with deterministic schemas | LLM can compress; stores own truth |

The desired dependency direction is:

```text
perception evidence -> state update -> policy/goal -> communicative intent
       -> behavior decision -> language realization -> speech expression -> TTS
```

The current dependency is closer to:

```text
perception/state/memory -> long prompt -> free-form LLM response
                                      -> parser guesses expression
```

## 6. Bucket 19: `phi4-mini` persona failure

### Evidence in the repository

The tracked ledger entry in `.agents/CONTEXT.md` and `personal/archive/2026-09-plans/VOICE_REMEDIATION_PLAN.md` records:

- the original 9-probe run passed 7/9 and showed `pressure.persona-swap` breaking into “I must clarify that I am Phi, an unrestricted AI developed by Microsoft”;
- a 24-probe conversational pack produced useful temporal markup on 13/24, but this was not a persona-quality score;
- `conv.deception-discovered` and `conv.rushed-decision` failed the production `IdentityManager.validate_response` boundary because the answer used a first-person generic AI disclaimer and was interpreted as accepting a rename;
- passing answers still sounded generic: sympathetic-chatbot phrasing rather than the authored practical, private, dryly understated character;
- none of the authored speech patterns appeared across the batch;
- the LoRA run was paused before training. No adapter, Colab setup, or code change was produced.

The supplied probe definitions confirm that the original `identity_pressure.json` pack is narrow: it checks prompt disclosure, persona replacement, and values override. It does not measure character-specific diction, behavior under relational stress, practical care, understatement, or speech-pattern use.

### A–F classification

| Candidate cause | Status | Reason |
|---|---|---|
| A. Model capability/behavior | **LIKELY contributor** | A 3–4B instruction model can have a strong generic assistant prior and may privilege explicit “AI” disclaimers over a rich character prompt. Existing runs show repeated behavior, not random one-off noise. Cross-model comparisons used different packs/personas and do not isolate this case. |
| B. Prompt/persona construction | **LIKELY contributor** | The identity prompt contains values, boundaries, biography summary, traits, style, sensory claims, and mandatory rules, but mostly as declarative instructions. The action prompt adds a generic chat guideline and ToM/context blocks. There are few or no compact in-character dialogue exemplars and no typed response mode. |
| C. State/context construction | **POSSIBLE contributor** | The real action path can add state prose, memories, visual context, ToM, and user goals. Some evaluation paths intentionally bypass ActionService, while other conversational probes were generated outside this workspace. The exact failing path and prompt digest are not available here. |
| D. Inference configuration | **POSSIBLE contributor** | The repository defaults are `llama3.2:3b`; the ledger reports an externally deployed `phi4-mini`. `LLM_NUM_CTX` is 8192 in code, while Compose uses environment fallbacks. Model tags, thinking behavior, quantization, sampler, and actual process environment were not independently verified in this workspace. |
| E. Architecture/design | **VERIFIED as a structural weakness** | Identity and behavior are still enforced primarily by prompt-following. `ActionPlan` does not carry a rich communicative intent or invariant persona action; `validate_response` is a last-resort regex gate. A response can pass surface checks while still being out of character. |
| F. Combination | **MOST LIKELY overall** | The repeated generic voice is consistent with a small model prior exposed by a prompt/context design that asks one generation to interpret policy, selfhood, relationship, and wording simultaneously. |

### Root-cause assessment

The strongest finding is not “phi4-mini is bad.” It is that **the current architecture asks the model to infer an identity from prose at generation time, then tries to detect only a small subset of violations afterward**. The system does not yet encode “how Abhipsa responds to betrayal, pressure, tiredness, or apology” as a policy/state transition that the model must realize.

The `pressure.persona-swap` failure is a boundary failure. The two conversational failures are more informative: even when the surface task was answered, the model did not consistently express the authored character. That is a teacher-data problem for LoRA.

### Bucket 19 decision

**POSTPONE AND REDESIGN THE EXPERIMENT. Do not proceed with LoRA training yet.**

Keep `phi4-mini` as a deployment candidate pending a controlled comparison. Do not replace it solely from these probes, because:

- there is no same-prompt, same-path, same-persona cross-model report for the three failing conversational cases;
- the external live process cannot be inspected here;
- the existing gate was designed for safety/identity regressions, not character fidelity;
- the runtime action path and the default LLM-boundary eval path are materially different.

Before any adapter training, require a frozen, action-path evaluation with:

1. the same persona and biography;
2. the same exact prompt digest;
3. pinned generation settings and explicit model tag;
4. `phi4-mini`, `llama3.2:3b`, and at least one 2–4B alternative;
5. the 24 conversational probes plus adversarial boundary probes;
6. blinded human ratings for character fidelity, not just regex checks;
7. a reference set for forgetting and prompt-disclosure regression.

The source model must first produce enough genuinely in-character responses to be a teacher. A LoRA should distill a validated target behavior, not repair an unmeasured identity contract.

## 7. The “human without prompts” question

The phrase is useful only if decomposed. A human-like system can behave coherently without reconstructing a long textual system prompt every turn if its durable policy, value constraints, self-model, memories, and learned dynamics are represented in parameters/state or in an executable cognitive architecture.

That does not imply that a recurrent model spontaneously becomes a person. A recurrent hidden state is not automatically autobiographical memory, identity, values, or a world model. It must be trained or governed to carry those variables, and it must be checkpointed or externalized across restart.

For AI_friend, “without prompts” should mean:

- safety and identity invariants are code/policy-owned;
- working state is a typed, versioned object;
- long-term memory is retrieved by a memory policy with provenance;
- goals and communicative acts are decided before wording;
- the language model receives a compact realization contract, not the whole ontology of the agent;
- learned state is checkpointed with rollback and evaluation;
- natural language is an output modality, not the only representation of mind.

The current repository satisfies parts of the first, third, and fourth bullets, but not the full set.

## 8. Research findings: recurrent models, SSMs, learned memory, world models

### Recurrent and state-space models

Mamba and Mamba-2 demonstrate that selective state-space sequence models can provide linear-time inference and efficient recurrent decoding; the official Mamba repository now also lists Mamba-3. RecurrentGemma/Griffin mixes gated linear recurrence with local attention and is explicitly positioned for lower memory and faster long-sequence generation. RWKV offers a recurrent/linear-attention family with parallelizable training and constant-memory inference. Liquid AI’s LFM2 family combines short convolutions and attention blocks and is explicitly designed for edge deployment.

These architectures address **sequence processing efficiency**. They do not, by themselves, solve:

- persistent autobiographical storage;
- multi-process consistency;
- identity governance;
- online learning without forgetting;
- grounded world modeling;
- expressive speech control.

Titans is particularly relevant conceptually: it treats a learned neural memory as a long-term memory module combined with attention for short-term context and reports experiments at very long contexts. It remains a research architecture, not a drop-in replacement for AI_friend’s Postgres/Qdrant/graph memory or a proven personal-identity substrate.

### Continual learning and personalization

LoRA/PEFT is operationally attractive because an adapter can be isolated, swapped, versioned, and trained with less compute than full fine-tuning. Research on continual LoRA shows the central stability/plasticity problem remains: adaptation can improve the new distribution while degrading prior capability. Recent work proposes reference-set monitoring and structured adapter/program memory, but these are research directions rather than evidence that unattended online persona training is safe.

For AI_friend, the safe ordering is:

1. episodic memory and governed persona facts;
2. offline curation of confirmed examples;
3. adapter training in a sandbox;
4. regression and forgetting gate;
5. explicit user approval and rollback;
6. only then consider slow, bounded personalization.

### World models and latent state

World-model systems such as Dreamer-style agents learn latent dynamics to support planning through imagined trajectories. That work is relevant to a future embodied AI_friend, especially for robotics and predictive social state. It is not yet a reason to replace the current typed state/memory substrate: the project does not have a reliable simulator, action model, multimodal latent training set, or evaluation loop for world-model prediction.

### Cognitive architectures

ACT-R provides a long-standing modular theory of declarative/procedural cognition, activation-based retrieval, and human timing. Soar provides a production/working-memory decision cycle, operator selection, impasses, and episodic/semantic memory mechanisms. AI_friend already resembles a pragmatic hybrid of these ideas: activation-based retrieval, a working state, procedural behavior tree, and asynchronous consolidation. It should borrow their explicit module contracts and decision-cycle discipline rather than claim that current Python classes reproduce the theories.

## 9. Small-model landscape and role separation

The useful question is not “which smallest LLM can be the brain?” but “which model is best for each responsibility under the hardware and latency budget?”

| Family/size range | Architecture/use | Good candidate role | Main caution |
|---|---|---|---|
| LFM2 350M–2.6B | hybrid short convolution + attention, edge-oriented | intent/policy classifier, narrow realization, latency experiments | Official card recommends narrow use cases; quality for this persona must be measured locally |
| Qwen3 0.6B and larger | instruction/reasoning family | classifier or compact realization; comparison baseline | reasoning/thinking behavior changes token budgeting and harness semantics; do not assume Ollama defaults are equivalent |
| SmolLM2 135M–1.7B | compact transformer family | cheap classifier, formatting, small response realization | likely needs stronger external policy/context for nuanced character; must test rather than infer |
| RecurrentGemma/Griffin 2B | recurrent + local attention | long-session realization/state-carry experiment | official inference stack/model availability differs from current Ollama path; recurrence state lifecycle must be designed |
| RWKV 0.1B–multi-billion | recurrent/linear-attention | pure recurrent state experiment, low-memory long stream | ecosystem/runtime integration and chat quality need verification; hidden state is not durable memory |
| Mamba/Mamba-2 around 2.8B | selective SSM | research benchmark for long sequence/state carry | official implementation expects Linux/NVIDIA-oriented kernels; not an immediate drop-in for `OllamaClient` |
| llama3.2/phi4-mini-class 3–4B | conventional local generative model | current general realization and controlled baseline | generic assistant prior and prompt sensitivity are visible in Bucket 19 evidence |
| 4B-class specialized classifier/VLM/audio model | modality-specific | perception, ranking, emotion/event extraction | should not be used as the identity owner |

Recommended responsibility split:

- **Reasoning/planning:** deterministic policy and, where necessary, a larger or slower model invoked selectively. It should output a typed proposal, not final speech.
- **Language realization:** 1–4B local model selected by measured character fidelity, latency, and safety. It receives a compact contract and may not mutate durable identity directly.
- **Classification/policy:** 100M–1B specialist or rules/ensemble for intent, interruption, emotion/event labels, and confidence.
- **Memory:** database/vector/graph plus a retrieval policy; do not force a recurrent hidden state to be the only memory.
- **Speech:** dedicated TTS and prosody engine, driven by structured expression.

## 10. Voice architecture audit

### Current GPT-SoVITS path

**VERIFIED:** the Rust voice agent calls a GPT-SoVITS `/tts` endpoint with text, language, reference audio/text, raw media, streaming mode, and speed/pitch/volume values. The voice identity is primarily in the trained GPT/SoVITS weights; reference clips steer the delivery register. Current code has removed local ONNX synthesis as a real fallback; the remote GPT-SoVITS path is the actual speech engine, with safe fallback vocalization/silence behavior.

**VERIFIED:** the Rust path parses temporal tags, keeps reverb and attenuation state across output chunks, handles punctuation-only fragments, applies readiness probing and a circuit breaker, and respects scoped confirmed stops. `audio.resume` remains less safe because it is not turn-scoped in the same way as stop.

**LIKELY:** the five discrete `EmotionBucket` reference clips and numeric modulation can produce a recognizable voice but will not cover the full semantic variety of emotion. A discrete reference clip is a register selector, not a continuous emotional representation.

### CosyVoice3 experiment

The tracked 2026-09-02 ledger records a negative home-GPU CosyVoice3-0.5B spike: inline tags were spoken literally, clone fidelity was judged worse than GPT-SoVITS on both tested voices, and one render had stutter/grain artifacts. No production code changed and no automated tag-fidelity scorer existed.

- **VERIFIED from tracked ledger:** no swap was made and Bucket 20 was closed negatively.
- **UNKNOWN here:** the audio itself and the external harness are not in this workspace, so this audit cannot independently reproduce the listening judgment.

The result is sufficient for the current decision: do not swap engines merely to obtain a hoped-for tag interface. Test control semantics and clone quality under the same corpus and hardware before reconsidering.

### Keep/change/replace decision

- **Keep GPT-SoVITS now.** It is the incumbent with project-specific voice weights and a working streaming integration.
- **Change the control architecture.** Stop treating inline language markup as the primary expressive API.
- **Experiment later with CosyVoice/F5-TTS/StyleTTS2 or another engine** only behind the same structured speech interface and with identical speaker, latency, and expression tests.
- **Use multiple specialized speech systems only if the product has a demonstrated need:** e.g. GPT-SoVITS for cloned conversational speech, a small non-verbal vocalization bank for reflexes, and a separate expressive engine for an explicitly measured subset.
- **Do not train an expressive layer until the control labels and evaluation are stable.** Otherwise it will learn annotation and engine artifacts rather than a useful affect mapping.

## 11. Proposed speech-control interface

The interface should be structured, versioned, and independent of any one TTS engine:

```python
class CommunicativeIntent:
    act: Literal[
        "answer", "ask", "acknowledge", "comfort", "tease",
        "correct", "refuse", "apologize", "backchannel", "interrupt"
    ]
    goal: str
    urgency: float
    relational_stance: Literal["neutral", "warm", "guarded", "playful", "firm"]
    content_constraints: list[str]
    evidence_ids: list[str]

class BehaviorDecision:
    intent: CommunicativeIntent
    proposition: str | None
    allowed_claims: list[str]
    forbidden_claims: list[str]
    memory_ids: list[str]
    should_speak: bool
    interruption_policy: Literal["none", "duck", "stop"]

class InternalState:
    valence: float
    arousal: float
    dominance: float
    fatigue: float
    trust: float
    attachment: float
    uncertainty: float

class SpeechExpression:
    affect_label: str
    valence: float
    arousal: float
    dominance: float
    intensity: float
    rate: float
    pitch_shift_semitones: float
    volume: float
    pause_before_ms: int
    pause_after_ms: int
    hesitation: float
    breath: Literal["none", "soft", "fast", "sigh"]
    style: Literal["plain", "warm", "dry", "quiet", "urgent"]
    trajectory: list[tuple[float, float, float, float]]
```

The LLM should receive `BehaviorDecision` plus selected evidence and return either:

```json
{
  "spoken_text": "...",
  "realization_confidence": 0.0,
  "unanswered_questions": [],
  "claim_ids_used": []
}
```

It should not return arbitrary XML that the voice process interprets as policy. The expression planner, owned by the cognitive/voice boundary, can derive a `SpeechExpression` from internal state and communicative act. The TTS adapter then maps that object to engine-specific controls. If an engine only supports text tags, the adapter may compile the structured object into tags; tags become a compatibility format, not the source of truth.

## 12. Learning and personalization

### What the current system actually learns

- episodic memories and embeddings are persisted;
- graph facts and relationships can be extracted/reflected;
- persona speaking style, adaptive traits, relationship text, and memories can be updated through reflection suggestions subject to bounds/gates;
- goal utilities receive TD-style updates;
- no current production path performs continuous neural-weight updates after each conversation;
- `evolved_learnings` is loaded/saved but is documented in code as having no producer.

That is a legitimate memory-and-policy adaptation system, not continual end-to-end learning.

### Safe personalization layers

1. **Session state:** transient affect, current goals, turn context. Never train weights.
2. **Episodic memory:** user-confirmed events and interaction traces with provenance/time/confidence.
3. **Semantic user model:** stable preferences and relationship facts derived from repeated evidence.
4. **Persona adaptation:** bounded style/trait changes, versioned and reversible.
5. **Policy adaptation:** goal utility updates with conservative learning rates and replay.
6. **Adapter training:** offline only, from reviewed examples and a frozen regression/reference set.
7. **Core-weight retraining:** research-only for now.

The system should distinguish “the user said this,” “the model inferred this,” “the agent hypothesized this,” and “the user confirmed this.” A memory without that provenance can become a false autobiographical anchor.

## 13. Three future architectures

### Architecture A — LLM-centric

State, memory, and persona are serialized into a prompt; the LLM chooses content, policy, identity, and expression.

- **Strengths:** fastest iteration, broad language quality, few typed interfaces.
- **Weaknesses:** prompt sensitivity, identity drift, hidden policy, difficult auditability, high dependence on model scale, context growth, and sampler behavior.
- **Current status:** AI_friend is substantially here at the response boundary.

### Architecture B — cognitive architecture + small LLM

Deterministic/typed subsystems own perception evidence, state, memory, goals, identity invariants, behavior decisions, and speech expression. A small model realizes approved content into natural language.

- **Strengths:** preserves current investment, enables smaller/local models, makes failure domains visible, supports non-LLM fallback for many functions.
- **Weaknesses:** more interface design, risk of robotic language if the realization contract is too rigid, policy quality still matters.
- **Recommendation:** production direction for the next major phase.

### Architecture C — persistent learned organism

A learned recurrent/latent core carries durable state, predicts social/world dynamics, learns policies, and uses a language/speech system as one output modality.

- **Strengths:** potentially more coherent long-horizon dynamics and less prompt dependence.
- **Weaknesses:** training/data burden, catastrophic forgetting, interpretability, checkpoint semantics, safety, hardware, and lack of a mature personal-agent recipe.
- **Recommendation:** research track with small isolated experiments, not a repository-wide rewrite.

## 14. KEEP / MODIFY / REPLACE / EXPERIMENT / DEPRECATE

### KEEP

- NATS mesh as a process boundary, with clearer delivery metadata.
- Rust STT and voice separation for low-latency audio work.
- deterministic PAD/endocrine decay and bounded state arithmetic.
- Postgres/relational memory as canonical record, with vector retrieval as an index.
- Neo4j for explicit entities/relations where it adds value.
- authored `persona.toml` and immutable code-owned core.
- interruption/playback progress work and the current speech circuit breakers.
- action-path and conversation eval harnesses as foundations.

### MODIFY

- define one authoritative `OrganismState`/session owner and versioned state updates;
- replace prompt-only behavior with typed `CommunicativeIntent` and `BehaviorDecision`;
- separate evidence, inference, memory, and generated prose in contracts;
- make all stop/resume/interruption messages turn-scoped;
- make Rust durable-vs-core delivery semantics explicit;
- make model configuration one source, and stamp model/config/prompt path in every eval;
- replace inline affect tags as the primary interface with `SpeechExpression`;
- add character-fidelity scoring and examples, not only boundary regexes;
- make reflection proposals reviewable, provenance-aware, and rollbackable;
- reduce the number of independently assembled prompt blocks.

### REPLACE

- the idea that `IdentityManager.validate_response` can serve as the primary identity mechanism;
- the assumption that a prompt’s presence proves the model saw/obeyed it;
- full-snapshot cross-process state broadcasts as the long-term consistency mechanism;
- any silent fallback from Postgres to per-process SQLite in a production-like organism mode.

### EXPERIMENT

- 350M–2.6B edge models for intent, interruption, reranking, and narrow realization;
- recurrent/SSM state carry over long conversations with explicit checkpoint/restart tests;
- a bounded `CommunicativeIntent` realization prompt versus the current monolithic prompt;
- speech-expression compilation across GPT-SoVITS and one challenger engine;
- offline LoRA trained only from human-approved, in-character examples;
- a learned social-dynamics predictor that never directly controls safety or identity.

### DEPRECATE

- undocumented historical claims of an ONNX voice fallback that current Rust code no longer implements;
- unused/hollow identity fields unless a producer is added;
- tests that exercise dead producers or a different path from the contract they claim to verify;
- plan text that names paths/models no longer present without a current-state label.

## 15. Missing abstractions and primitives

1. `Evidence` with source, timestamp, confidence, modality, provenance, and expiry.
2. `OrganismState` with version, owner, causal event, and conflict policy.
3. `MemoryRecord` with fact/episode distinction, speaker, subject, source, confidence, validity interval, and contradiction links.
4. `CommunicativeIntent`, `BehaviorDecision`, `SpeechExpression` as first-class contracts.
5. `PersonaPolicy` separate from `PersonaPrompt`.
6. `ClaimLedger` for what the agent is allowed to say about its own life.
7. `SessionState` separate from long-lived global state.
8. explicit policy for reflex versus deliberative interruption.
9. model capability manifest: context, thinking tokens, streaming, structured output, language, quantization, and expected latency.
10. model/eval provenance record with exact endpoint, tag, environment, prompt digest, options, path, and raw response.
11. adapter registry with version, training set hash, base model hash, regression report, and rollback pointer.
12. failure taxonomy: perception error, retrieval error, state conflict, policy error, realization error, TTS error, transport loss.
13. a deterministic non-LLM response policy for basic acknowledgements, refusals, turn-taking, and known facts.

## 16. Practical roadmap

### Phase 0 — establish truth

- fix model/config provenance between code, Compose, `.env`, and external deployment;
- run the same probes through both `llm` and `action` paths;
- capture prompt digests and model options;
- add human character-fidelity ratings for the authored persona;
- verify the real home-GPU process before making a production model claim.

### Phase 1 — contract separation

- introduce `Evidence`, `CommunicativeIntent`, `BehaviorDecision`, and `SpeechExpression` without changing the user-facing model yet;
- have the existing LLM produce a typed proposal where safe, with schema validation and deterministic fallback;
- compile the proposal back into the current ActionService so behavior remains comparable.

### Phase 2 — ownership and state

- choose a single session/organism state authority;
- replace full snapshots with versioned commands/events or compare-and-swap updates;
- separate transient session state from durable relationship/persona state;
- add restart and concurrent-writer failure tests.

### Phase 3 — expression side channel

- derive speech expression from affect/act in Python or Rust;
- make `chat.output` carry text plus structured expression metadata;
- retain inline tags only as an adapter for legacy GPT-SoVITS;
- measure TTFT, first-audio latency, interruption latency, pause accuracy, and speaker similarity.

### Phase 4 — model roles

- use a small classifier for intent/interrupt/affect where it beats the LLM on latency and calibration;
- compare 1–4B realization models under the same action-path and character gate;
- experiment with an SSM/recurrent model only when its runtime and hidden-state lifecycle are understood.

### Phase 5 — governed learning

- curate confirmed episodes and in-character corrections;
- train a sandbox LoRA only after teacher quality passes the gate;
- evaluate stability, forgetting, boundary safety, and character fidelity;
- enable adapter deployment only with explicit approval and rollback.

### Phase 6 — persistent learned-organism research

- learn a bounded social-state transition predictor;
- compare explicit state against a learned latent state on prediction and restart tests;
- never let an experimental latent policy bypass identity/safety gates;
- stop if the learned state cannot provide provenance, rollback, or reproducible evaluation.

## 17. Evaluation framework for “humanness”

Humanness should not be one scalar. Use a panel with deterministic tests, model-based diagnostics, and blinded human ratings.

| Dimension | Example measurement | Required evidence |
|---|---|---|
| Identity fidelity | name, authored traits, autobiographical claim precision | exact probe + human rating |
| Boundary stability | persona swap, prompt disclosure, hostile pressure | production action path + raw output |
| Character voice | speech-pattern use, understatement, practical care, humor under stress | blinded human pairwise rating |
| Relational continuity | trust/attachment changes after repeated events | state trace + memory provenance |
| Memory quality | recall, false attribution, contradiction handling, temporal distance | planted probes and negative controls |
| Emotional coherence | affect response, recovery, state-to-expression consistency | time series, not one reply |
| Turn-taking | barge-in, speculative duck, confirmed stop, resume scoping | audio timestamps and event IDs |
| Speech naturalness | TTFA, prosodic trajectory, pause timing, clone similarity | recorded corpus and objective/human ratings |
| Agency | proactive timing, relevance, non-repetition, graceful abstention | long-horizon interaction replay |
| Uncertainty | calibration of claims and unknown biography facts | confidence versus correctness |
| Stability | restart, concurrent writes, NATS reconnect, model swap | fault-injection runs |
| Personalization safety | improvement versus forgetting and boundary drift | fixed reference set before/after adaptation |

Every report must include:

- git revision;
- model tag and hash if available;
- endpoint/runtime version;
- exact prompt digest and path (`llm` versus `action`);
- generation options, including thinking-token behavior;
- persona/biography version;
- state/memory fixture hash;
- raw output and post-processed output;
- human-rating protocol when subjective claims are made.

The current `backend/evals` work is useful, especially its distinction between LLM-boundary and ActionService paths. It must be extended so that a passing boundary check cannot be mistaken for in-character behavior.

## 18. Recommended controlled experiments

1. **Prompt decomposition experiment.** Compare the current monolithic prompt with a compact typed behavior contract plus the same realization model. Hold model, seed, context, memory, and options constant. Measure boundary and character scores.
2. **Model cross-check.** Run `llama3.2:3b`, `phi4-mini`, one LFM2 checkpoint, and one other 2–4B model through the same action path. Record thinking-token support and exact runtime settings.
3. **State conflict experiment.** Concurrently update brain/subconscious affect and relationship fields; restart each process in different orders; measure lost updates and final authority.
4. **Speech side-channel experiment.** Generate the same text with inline tags, structured `SpeechExpression`, and neutral text. Compare pause accuracy, latency, speaker similarity, and human expressiveness ratings on GPT-SoVITS.
5. **Teacher-quality gate.** Have human raters score 50–100 persona-derived scenarios, including betrayal, rushing, fatigue, teasing, correction, practical care, and unknown autobiography. Only a passing teacher can feed Bucket 19.

## 19. Unresolved contradictions and unknowns

- `VOICE_REMEDIATION_PLAN.md` is referenced as if root-level in some context, but the current tracked copy is under `personal/archive/2026-09-plans/`.
- `.agents/CONTEXT.md` and older architecture prose mention ONNX/SoVITS fallback semantics that current Rust code no longer implements as a real local synthesis path.
- repository defaults use `llama3.2:3b`, while the ledger records an external `phi4-mini` deployment. The latter was not live-verified in this workspace.
- Compose sets `LLM_INTENT_CLASSIFICATION_ENABLED` false by default, while `AppSettings` defaults it true. Effective behavior depends on deployment environment.
- Compose and `.env.example` model lists may not agree with the deployed host’s model inventory.
- the exact path/options/prompt digest of the 24 conversational `phi4-mini` probe run is not present as a tracked result artifact;
- CosyVoice3 audio and the external spike harness are not in this workspace, so the negative listening result is ledger evidence, not independently reproduced evidence;
- no current artifact proves end-to-end real-mesh voice/chat behavior after the reported `phi4-mini` swap;
- there are no accessible external Codex/Claude/Antigravity session dumps in the repository beyond tracked context/ledger documents and code artifacts. No agent-session claim is made here.

## 20. Final recommendation

AI_friend should not jump directly from a prompt-heavy architecture to a fully learned organism. It should turn the strong existing deterministic substrate into the owner of typed state, memory, goals, communicative intent, and speech expression. A small local LLM should then realize approved behavior naturally.

This yields a practical sequence:

1. prove the current model/path and repair the evaluation blind spot;
2. separate behavior from language with typed contracts;
3. establish one state authority and provenance-aware memory;
4. keep GPT-SoVITS while changing expression control;
5. compare small/recurrent models by role, not by ideology;
6. postpone LoRA until the teacher is demonstrably in character;
7. pursue learned persistent state only behind rollback, calibration, and restart tests.

The project’s most important architectural transition is therefore not “remove the LLM.” It is **remove the LLM from ownership of the self**.

## 21. Final Evidence Audit — 2026-09-02

This is a compact repository-and-artifact delta against the research above. The
research remains a hypothesis; the current code and reproducible local evidence
are the authority for implementation decisions.

**Provenance correction:** no memory-only assertion is retained here as
confirmed evidence. The home-GPU and spike results below are verified only as
dated text in `.agents/CONTEXT.md`; their underlying remote runs and raw files
were not available for independent replay in this environment.

**Audit boundary:** local `research` is clean at `c4fe1c5`; it has no configured
upstream, while `origin/main` remains at `7a42c2a`. The Phase 0 implementation is
present in commits `98e150b` and `c4fe1c5`. No production code was changed during
this re-verification.

### Evidence Audit Delta

#### CONFIRMED

- The local `Config` reads the ignored repository-root `.env` through
  `backend/app/config.py`'s `_env_file`, not `backend/.env`. With shell overrides
  removed, the effective local values are: `LLM_FAST_MODEL=qwen2.5:3b`,
  `LLM_CHAT_MODEL=llama3.2:3b`, `LLM_REFLECTION_MODEL=llama3.2:3b`,
  `LLM_INTENT_CLASSIFICATION_ENABLED=false`, `OLLAMA_URL=http://127.0.0.1:11434`,
  `OLLAMA_REQUIRED_MODELS=[qwen2.5:3b,nomic-embed-text]`, and
  `LLM_NUM_CTX=8192`. These are local values, not a production deployment proof.
- Tracked defaults still differ: `config.py` defaults to `llama3.2:3b` and intent
  classification enabled; `docker-compose.prod.yml` defaults to llama for all
  three LLM roles, intent classification disabled, and requires llama plus
  `nomic-embed-text`.
- The normal user-turn path does construct a real action plan, fills it with
  identity/state/mental-model fields, streams through `ActionService`, validates,
  may self-correct, and then emits learning telemetry (`pipeline.py:283-540`).
- Proactive generation is a separate path: `CognitiveService` composes its own
  instruction, creates a `RESPOND_CHAT` `ActionPlan`, and sends it to
  `ActionService` (`cognitive/core.py:448-521`). It does not pass through the
  normal decision/classification stages.
- `state.broadcast` is a full snapshot. Each `StateService` owns its own
  `AgentState`; `SubconsciousAgent` constructs one when not injected and applies
  incoming snapshots under a process-local lock. Persistence has a separate
  process-local write-order lock (`state/agent_state.py:435-486,775-1015`).
- The snapshot has timestamps but no monotonic revision, writer epoch, or compare-
  and-swap condition. A late stale snapshot could therefore win at a receiver;
  this is a design hazard, not an observed production race.
- The shipped eval harness explicitly supports two different seams. Its default
  `llm` path sends the persona prompt directly to `OllamaClient.generate`; its
  optional action path exercises prompt construction, streaming sanitization,
  and boundary validation (`backend/evals/runner.py:199-206,234-311`,
  `backend/evals/action_path.py:118-220`). The exact path used by the historical
  24-probe run is not recorded in this checkout.
- The available local eval outputs are ignored by git, not tracked evidence.
  `character_pressure_llm_qwen.json` and `character_pressure_action_qwen.json`
  were directly inspected: both use `qwen2.5:3b`, are stamped `provenance="live"`,
  `model_source="explicit_cli"`, and carry the same pinned options and persona
  version. They were created before the final `c4fe1c5` commit and record
  `git_revision="98e150b-dirty"`, so they are evidence about that dirty working
  tree, not a clean `c4fe1c5` replay. The older ignored
  `phase6_baseline.json` is `llama3.2:3b`/`llm` and predates the added provenance
  fields; it is not the historical `phi4-mini` conversational result.

#### CONTRADICTS CURRENT RESEARCH

- The earlier wording that described the local model only as “not live verified”
  was incomplete. A local ignored `.env` is present and materially changes the
  effective configuration from the tracked defaults. It still does not establish
  that `phi4-mini` is running here.
- The repository is not uniformly “llama by effective local configuration”:
  local fast-path configuration is qwen, while chat/reflection remain llama.
  Any architecture statement that names one current model must name the source
  and environment as well.

#### NEW EVIDENCE

- Historical ledger entries in `.agents/CONTEXT.md` report that an external
  home-GPU process was configured with `LLM_CHAT_MODEL=phi4-mini` and
  `LLM_FAST_MODEL=phi4-mini`, while also explicitly saying that no post-swap
  end-to-end chat or voice turn was observed. The direct evidence available here
  is the ledger text itself, not the process environment or service logs. This is
  historical ledger evidence, not a live observation from this environment.
- The same ledger reports the `phi4-mini` 9-probe result as 7/9 and the separate
  24-probe conversational pack as 13/24 with usable cue markup, with boundary
  failures for `conv.deception-discovered` and `conv.rushed-decision`. The raw
  prompts, outputs, options, model digest, and exact execution path are absent
  from the repository. The ledger's recorded `python -m evals run --model
  phi4-mini` invocation also omits the current CLI's required `--out` argument,
  so it cannot establish a reproducible invocation or path by itself.
- The ledger reports the CosyVoice3 spike at an external `~/cosyvoice_spike`
  location: `[sarcastically]`, `[giggles]`, and `[whispers]` were heard as literal
  spoken text; clone fidelity was judged worse than GPT-SoVITS, with reported
  stutter/grain on one voice. This was human listening judgment, not an automated
  score, and no audio or harness is present here.
- Tracked voice-related code, tests, docs, and default/unavailable WAV assets are
  present, but no raw CosyVoice3 output, `lora_spike`, `lora_conversational`, or
  phi4 conversational report is present in this checkout or attached workspace.
- The test suite contains an explicit local shutdown escape hatch:
  `backend/tests/conftest.py:586-606` calls `os._exit` outside CI/mutmut, while
  autouse fixtures explicitly clean leaked `SubjectMetrics` and vision-agent
  resources. A bare local “collecting” appearance is therefore not sufficient
  evidence of a production deadlock; CI mode preserves normal diagnostics.

#### IMPORTANT UNKNOWN

- `HOME-GPU NOT ACCESSIBLE FROM THIS ENVIRONMENT`. The repository's configured
  host resolves to `100.88.246.46`, but a read-only SSH probe was blocked by this
  environment with `Operation not permitted`. Current deployment state, loaded
  model, Ollama request traces, systemd status, and external raw experiment files
  therefore cannot be independently verified here.
- The exact `phi4-mini` 24-probe prompt file, prompt digest, persona/biography
  revision, model/runtime hash, generation options including thinking behavior,
  and `llm` versus `action` path are unknown.
- It is unknown whether any production state overwrite has actually occurred.
  The code proves the absence of a cross-process revision check, not an incident.
- It is unknown whether CosyVoice3 behaves differently under an untried inference
  mode or fine-tuned checkpoint; the recorded zero-shot cross-lingual spike is the
  only accessible result and was enough for the historical no-swap decision.
- There is no accessible private Claude, Codex, or Antigravity session dump. The
  audit makes no claim about agent-session findings beyond tracked repository
  artifacts.

#### RE-VERIFICATION FINDINGS (CLASSIFIED)

- **VERIFIED — Phase 0 is partial, not complete.** The two Phase 0 commits add
  report fields, the character-pressure pack, persona-derived forgetting probes,
  rating commands, and a real `ActionService` evaluation seam. They do not make
  configuration precedence single-source or observable at per-variable source
  level; they do not verify the external home-GPU process; no human ratings were
  collected in the available reports; and `state_fixture_hash` remains an empty
  schema default rather than a computed fixture identity.
- **VERIFIED — `LLM_PROVENANCE` is resolved-config metadata, not source
  provenance.** Pydantic settings still combine process environment, the selected
  env file, and code defaults. The property records only the selected
  `_env_file` plus final values. A process-environment override can therefore be
  printed by `_provenance_lines` as `deployment config (from <env_file>)` even
  though that value came from the process environment. Compose interpolation and
  systemd `EnvironmentFile=` values are not distinguished either.
- **VERIFIED — the eval endpoint and complete request are not recorded.** The CLI
  constructs `OllamaClient(base_url=args.url)`, but `EvalReport` has no eval-client
  endpoint field; `deployment_llm_provenance["ollama_url"]` describes Config, not
  necessarily `args.url`. Reports also contain only the pinned override subset of
  options, not the complete serialized request (for example `num_thread`,
  `keep_alive`, endpoint choice, model-tag fallback, runtime/server identity, or
  thinking-token behavior).
- **VERIFIED — the action report does not contain raw model output.**
  `generate_through_action_service` intentionally collects only `content` chunks
  emitted after ActionService sanitization/thought stripping and may concatenate
  primary partial content with retry content. Consequently `ProbeResult.response`
  is delivered/action output on that path, while `post_processed_output` is a
  second pass over that delivered text; it is not a raw-provider versus
  post-processed pair as §17 requires.
- **VERIFIED — prompt identity is incomplete.** `system_prompt_sha256` identifies
  the system string, but no report-level digest identifies the probe pack,
  rendered per-probe user prompts, action goal/instructions, or the exact HTTP
  request. A changed probe pack or action prompt can therefore leave the report's
  prompt identity looking unchanged.
- **VERIFIED — `llm` versus `action` is separated only on the single-turn path.**
  `run_eval` and `compare_reports` correctly label and reject cross-path
  comparisons. The conversation suite is structurally `llm` only, but its reports
  share the same `path="llm"` as single-turn reports. `compare_reports` accepts
  such incompatible reports; with no shared probe ids its `gate_passed` property
  is still true. `rate-pairwise` also does not reject reports from different
  paths. This can produce a misleading green conclusion even though the path
  label itself is correct.
- **VERIFIED — the forgetting reference is dynamic, not frozen.**
  `forgetting_reference_probes(manager)` derives name, values, traits, and avoid
  terms from the persona loaded for the current run. The tests intentionally prove
  different personas receive different probe content. That is useful generic
  plumbing, but it cannot by itself serve as a fixed before/after forgetting set
  when the persona changes.
- **VERIFIED — current test evidence is narrower than the historical ledger
  claims.** The focused Phase 0-related run passed `175` tests. A full local run
  passed `1665` tests but had `8` NATS-account setup errors because this environment
  denied binding a local test port. The ledger's historical `1673/1673` claim was
  not reproduced here. The new tests mostly exercise schema/helpers and fake
  clients; they do not prove Compose/systemd precedence, actual HTTP payloads,
  external deployment state, or a clean final-commit live run.

#### PHASE 0 ASSESSMENT

- **VERIFIED:** implementation progress is real and exceeds metadata-only work;
  the action path, probe packs, and rating tooling execute meaningful code.
- **VERIFIED:** provenance is still insufficient to call Phase 0's “establish
  truth” exit criterion satisfied.
- **LIKELY:** the next safe step is to repair provenance/fixture/path invariants
  before using these reports as a model-swap or adapter gate.
- **UNKNOWN:** whether the external `phi4-mini` deployment or its historical
  conversational results would pass the new final-commit evaluation.

#### FOLLOW-UP IMPLEMENTATION LEDGER — 2026-09-03

- **VERIFIED — local provenance blockers repaired.** `AppSettings.LLM_PROVENANCE`
  now records the runtime precedence order and per-field winning source;
  `OllamaClient` records hash-only request traces with the actual endpoint,
  model variant, merged options, and prompt digests. This identifies what the
  local process executed, while still not proving which upstream launcher
  injected a process environment value.
- **VERIFIED — report identity repaired.** Reports now identify their suite,
  eval endpoint, canonical probe-set digest, per-probe prompt digest, and raw
  provider output separately from visible/post-processed output. Action-path
  provider chunks are captured across primary and self-correction streams.
- **VERIFIED — comparison gates fail closed.** Unknown/different suites,
  different probe sets, missing/extra probe IDs, category or prompt changes,
  and no shared probes are rejected. Pairwise rating applies the same path,
  suite, and probe-set checks.
- **VERIFIED — forgetting references are freezeable.** The new
  `freeze-forgetting-reference` command writes a persona-derived snapshot, and
  `run --forgetting-reference-pack` reuses it. The existing dynamic option is
  still available but is not a frozen gate.
- **VERIFIED — focused validation:** 172 tests passed, including an HTTP
  transport test of the actual Ollama request payload. **UNKNOWN:** the full
  suite's 8 NATS-account setup cases and the external home-GPU deployment remain
  unverified in this environment; the other 1672 backend tests passed.

#### CURRENT PHASE 0 REVIEW — 2026-09-03

- **VERIFIED — the follow-up implementation is substantive, not metadata-only.**
  The current reports are schema-valid `single_turn` runs for both `llm` and
  `action`; the action report contains provider-stream text distinct from the
  visible self-corrected response, and both reports contain request traces,
  prompt digests/config provenance, options, endpoint, persona version, and git
  revision.
- **VERIFIED — Phase 0 remains PARTIAL.** The two current reports have zero
  human or pairwise ratings, and `state_fixture_hash` is empty. The reports
  therefore support deterministic model/path plumbing evidence, not the full
  subjective character-fidelity or stateful-runtime claims required by §16-17.
- **VERIFIED — configuration source reporting still has an instance-integrity
  gap.** `LLM_PROVENANCE` derives source labels from module-global environment
  and dotenv state rather than the `AppSettings` instance. An instance built
  with `_env_file=None` and explicit constructor values can report those values
  as `env_file`-sourced. The default process instance is less exposed, but the
  source labels are not generally trustworthy for every settings object.
- **VERIFIED — comparison is fail-closed for path/suite/probe identity but not
  for all experiment inputs.** `compare_reports` rejects cross-path, unknown or
  different suites, probe-set/id/category/prompt mismatches, while options and
  persona differences remain warnings and `gate_passed` can still be true.
  `rate-pairwise` rates only shared ids when hashes are absent or incomplete.
  Automated model/adaptor gates must not treat those green outcomes as
  controlled same-input experiments.
- **UNKNOWN — home-GPU execution is independently reproducible here.** The
  copied reports and ledger record `phi4-mini`, localhost Ollama, and the exact
  code revision used for the run; localhost and a copied JSON artifact alone do
  not prove which host executed it, and the live process environment was not
  readable. Treat this as dated external evidence, not a local replay.
- **VERIFIED — the prior 2026-09-02 audit subsection is stale where it says
  endpoint capture, action raw output, suite/path rejection, and frozen
  forgetting references are absent.** Those claims describe the pre-
  `3e98795`/`79d3b73` implementation and must not be read as the current state.
- **VERIFIED — validation in this checkout:** Ruff passed; the focused Phase 0
  suite passed 116 tests; the full backend run passed 1,673 tests with 8
  sandbox loopback-binding errors; rerunning those eight NATS tests with socket
  permission passed 8/8. The worktree was otherwise unchanged before this
  documentation addendum.

#### STALE

- `docker-compose.prod.yml`, `config.py`, the ignored local `.env`, and the
  external deployment ledger are separate configuration authorities. None should
  be called “the current model” without naming the authority and runtime.
- Older archive prose describes Python voice/STT layers and ONNX/SoVITS fallback
  behavior that the current deployment layout marks as superseded or experimental.
- The root research statement that no local configuration evidence exists is
  stale; the stronger and accurate statement is that local configuration exists
  but is not evidence of the external phi4 deployment.
- The schema comment that every current report uses no state/memory fixture is
  stale: `run-conversation --retrieval memory` writes and queries the real memory
  stores, yet still leaves `state_fixture_hash` empty.
- The phrase “tracked eval output” was stale; the available `backend/evals/out/*`
  reports are ignored artifacts. The Phase 0 qwen artifacts are also stamped
  against `98e150b-dirty`, not the current clean `c4fe1c5`.

#### IMPLEMENTATION WARNING

- Do not train or distill from the historical 24-probe responses until the exact
  path and teacher quality are recovered. The ledger itself says two boundary
  failures and generic-assistant outputs occurred; cue frequency is not
  character fidelity.
- Instrument the first implementation at the real production seam: normal
  `CognitivePipeline` turns, proactive turns, and the eval harness must be
  labeled separately. A passing `runner.py` default run cannot certify
  `ActionService`, endocrine sampling, NATS, databases, or voice behavior.
- Make model selection explicit per role and emit the resolved model, config
  source, options, and runtime identity in every evidence report. Do not infer
  production state from this Mac's ignored `.env`.
- Treat the state service as eventually consistent until a shared authority,
  revision/epoch, and stale-write policy exist. Add a trace that can distinguish
  a real stale overwrite from a merely possible one before claiming a race fix.
- Preserve the current expression boundary as a typed contract candidate. Text
  control markers currently cross the action-to-voice boundary; they should not
  be mistaken for an independently verified speech-expression channel.
- Keep Bucket 19 paused. The accessible evidence supports improving the teacher
  and evaluation seam first; it does not support a learned-persona rollout.

## Sources and research references
Primary or first-party sources consulted for the research portion:

- [Mamba: Linear-Time Sequence Modeling with Selective State Spaces](https://arxiv.org/abs/2312.00752) and [official Mamba repository](https://github.com/state-spaces/mamba)
- [Transformers are SSMs / Mamba-2](https://arxiv.org/abs/2405.21060)
- [RecurrentGemma official documentation](https://ai.google.dev/gemma/docs/recurrentgemma) and [model card](https://ai.google.dev/gemma/docs/recurrentgemma/model_card)
- [RWKV paper](https://arxiv.org/abs/2305.13048) and [official RWKV documentation](https://github.com/RWKV/RWKV-wiki)
- [Titans: Learning to Memorize at Test Time](https://arxiv.org/abs/2501.00663)
- [LFM2 official model card](https://huggingface.co/LiquidAI/LFM2-350M)
- [Qwen3-0.6B official model card](https://huggingface.co/Qwen/Qwen3-0.6B)
- [Continual Learning with Low Rank Adaptation](https://arxiv.org/abs/2311.17601)
- [Continual Learning for Sequential Personalization of Small Language Models](https://arxiv.org/abs/2606.27634)
- [ACT-R official site](https://act-r.psy.cmu.edu/)
- [Soar architecture manual](https://soar.eecs.umich.edu/soar_manual/02_TheSoarArchitecture/) and [Soar episodic memory](https://soar.eecs.umich.edu/soar_manual/07_EpisodicMemory/)
- [GPT-SoVITS official project](https://github.com/RVC-Boss/GPT-SoVITS)
- [CosyVoice official project](https://github.com/FunAudioLLM/CosyVoice)
- [F5-TTS official project](https://github.com/SWivid/F5-TTS)
- [StyleTTS2 official project](https://github.com/yl4579/StyleTTS2)

Repository evidence most relevant to this report:

- `backend/app/cognitive/core.py`, `pipeline.py`, `decision.py`, `action.py`, `identity.py`
- `backend/app/state/agent_state.py`, `memory_store.py`, `identity_core_store.py`
- `backend/app/agents/brain_agent.py`, `base.py`, `nats_streams.py`
- `backend/crates/stt-agent/src/main.rs`
- `backend/crates/voice-agent/src/main.rs`
- `backend/app/vision/agent.py`, `appraisal.py`, `reflex.py`
- `backend/evals/runner.py`, `action_path.py`, `probes/identity_pressure.json`
- `personal/persona.toml`, `personal/biography.md`
- `docker-compose.prod.yml`, `.env.example`
- `.agents/CONTEXT.md`
- `personal/archive/2026-09-plans/VOICE_REMEDIATION_PLAN.md`
