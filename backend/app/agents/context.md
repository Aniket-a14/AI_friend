# Agentic Context: Phase 4 Dynamic Continuous Prosody Mapping & DSP Playback

This document provides the formal mathematical specification, operational design, and data-flow pathways for the **Phase 4 Dynamic Continuous Prosody Mapping**, **Overlap-Add (OLA) Crossfade Processing**, and **Dynamic Emotional Parameters** within the Cognitive Voice System (CVS).

---

## 🧠 1. Dynamic Emotional & Physiological Parameters

The system models the agent's internal state as a high-dimensional vector combining **dimensional affect** (PAD), **relational factors**, and **metabolic/spatial proprioceptive indicators**:

| Parameter | Symbol | Range | Tracking Mechanism / Description |
| :--- | :--- | :--- | :--- |
| **Valence** | $V$ | $[-1.0, 1.0]$ | Pleasure/Mood dimension. Updated via goal congruence appraisal. |
| **Arousal** | $Ar$ | $[0.0, 1.0]$ | Energy/Excitement. Drives speech rate and pitch dynamics. |
| **Dominance** | $D$ | $[0.0, 1.0]$ | Sense of agency/control. Directly modulates vocal volume. |
| **Trust** | $T$ | $[0.0, 1.0]$ | Long-term relational warmth. Composed of Benevolence, Competence, and Integrity. |
| **Attachment** | $At$ | $[0.0, 1.0]$ | Long-term relational bond intensity. |
| **Fatigue** | $F$ | $[0.0, 1.0]$ | Metabolic fatigue. Accumulates during active turns, decays during idle cycles. |
| **User Distance** | $d$ | $[0.0, \infty)$ | Spatial distance in meters. Inferred via OpenCV Haar Cascade face detection width ($d = \frac{0.15}{S}$). |

---

## 🎙️ 2. Dynamic Continuous Prosody Mapping Equations

The Voice Agent utilizes a dynamic linear-algebraic mapper to translate internal emotional-physiological states into synthesis parameters for the GPT-SoVITS runtime (`speed_factor`, `pitch`, `volume`, `pause_bias`).

These equations are computed native in Rust (`backend/crates/contracts/src/lib.rs`):

### 2.1 Inputs & Modifiers

1. **Fatigue Adjustments**:
   * Speaking Rate slowdown:

```math
\text{fatigue-slow} = 0.25 \cdot F
```

   * Pitch dropdown:

```math
\text{fatigue-pitch-drop} = 0.10 \cdot F
```

2. **Distance Spatial Adaptation**:
   * Close-range threshold ($d < 0.6\text{m}$, whisper configuration):

```math
\text{dist-vol-mod} = -0.15, \quad \text{dist-pitch-mod} = -0.05
```

   * Far-range threshold ($d > 1.5\text{m}$, projection configuration):

```math
\text{dist-vol-mod} = 0.20, \quad \text{dist-pitch-mod} = 0.10
```

   * Intermediate baseline:

```math
\text{dist-vol-mod} = 0.00, \quad \text{dist-pitch-mod} = 0.00
```

### 2.2 Core Synthesis Parameters

1. **Speaking Rate ($R$)**:
   Modulated by arousal energy and valence, slowed down by metabolic fatigue, clamped to safety bounds:

```math
R = 1.0 + 0.20 \cdot Ar - 0.10 \cdot V - \text{fatigue-slow}
```

```math
\text{SpeedFactor} = \text{clamp}(R, 0.6, 1.8)
```

2. **Vocal Pitch ($P$)**:
   Jointly modulated by valence and arousal, tempered by dominance, and adjusted for fatigue and distance:

```math
P = 1.0 + 0.05 \cdot V + 0.15 \cdot Ar - 0.10 \cdot D - \text{fatigue-pitch-drop} + \text{dist-pitch-mod}
```

```math
\text{Pitch} = \text{clamp}(P, 0.5, 2.0)
```

3. **Vocal Volume ($V_{ol}$)**:
   Modulated by interpersonal dominance (assertiveness) and adjusted for distance propagation:

```math
V_{ol} = 0.4 + 0.6 \cdot D + \text{dist-vol-mod}
```

```math
\text{Volume} = \text{clamp}(V_{ol}, 0.1, 1.0)
```

4. **Pause Bias ($B_{\text{pause}}$)**:
   Determines the baseline silent duration between speech segments. Higher arousal suppresses silence:

```math
B_{\text{pause}} = 1.0 - Ar
```

All parameters are rounded to exactly **two decimal places** ($0.01$ precision) prior to serialized delivery to the SoVITS inference pipeline.

---

## 🔊 3. Chunk-Boundary PCM Reassembly (OLA Crossfade Removed)

**Corrected 2026-09-01** — this section previously described a 10ms linear Overlap-Add crossfade applied at every prosody shift between consecutive chunks. That mechanism was removed entirely (Bucket 2, `VOICE_REMEDIATION_PLAN.md`): it blended the last 15ms of the *already-published, already-playing* previous chunk into the head of the next, which is not overlap-add — true OLA blends two buffers analyzed together **before** either is sent downstream. Because the "previous" side here had already gone out over `audio.stream` and reached the listener, those 15ms were heard twice, at a phase discontinuity — reported live as a hazy, not-crystal-clear artifact, and it fired on almost any prosody inequality between chunks arriving tens of milliseconds apart (which, at the time, was most chunk boundaries — see §8's chunking notes below). A clean butt-join was judged strictly better than replaying already-heard audio, so the crossfade was deleted rather than corrected in place; correctly implementing true OLA would need holding back every chunk's tail until the next chunk arrives, adding a full chunk of latency to an already latency-critical path.

What remains at this seam (`OlaCrossfadeFilter` in `voice-agent/src/main.rs`, name kept only for continuity) is exactly the part of the old type that was never about prosody:

### 3.1 Odd-Byte PCM Buffering

16-bit PCM samples must never be split across two chunk boundaries. If a chunk's byte length is odd, the trailing byte is held and prepended to the next chunk before framing:

```math
\text{framed} = \begin{cases} [\text{pending\_byte}] \Vert \text{bytes} & \text{if a byte is pending from the previous chunk} \\ \text{bytes} & \text{otherwise} \end{cases}
```

If $|\text{framed}|$ is odd, its last byte becomes the new `pending_byte` and is excluded from this chunk's decoded samples. No blending, fading, or lookahead is involved — every complete pair of bytes in `framed` passes through as a plain 16-bit sample, unmodified.

### 3.2 Float-Domain PCM Round-Trip (shared with the reverb filter, §4)

This pattern is no longer specific to a crossfade — it is the general float-domain processing round-trip the reverb filter (§4) actually performs on every chunk.

1. **Quantization Recovery**: High-performance calculations are carried out in 32-bit floating point space to prevent precision loss.
2. **Clipping Protection**: The modified floats are clipped to prevent digital overflow distortion:

```math
y_{\text{clipped}}[i] = \text{clamp}(y[i], -32768.0, 32767.0)
```

3. **Re-quantization**: Samples are re-quantized to signed 16-bit PCM (`int16`) bytes prior to NATS JetStream publication:

```math
y_{\text{pcm}}[i] = \lfloor y_{\text{clipped}}[i] \rceil
```

---

## 🌌 4. Spatial Proprioception & Reverb DSP

When the physical distance $d$ increases, high-frequency elements decay, and atmospheric reflections introduce reverberation. The Voice Agent implements a real-time **Reverb Comb Filter** within its processing pipeline (`backend/crates/voice-agent/src/main.rs`).

### 4.1 Wet/Dry Linear Interpolation

Acoustic reverb gain ($\text{wet-gain}$) is scaled dynamically as a function of distance:

```math
\text{wet-gain} = \begin{cases}
0.0 & \text{if } d \le 2.5\text{m} \\
\frac{d - 2.5}{3.5 - 2.5} & \text{if } 2.5\text{m} < d < 3.5\text{m} \\
1.0 & \text{if } d \ge 3.5\text{m}
\end{cases}
```

### 4.2 Delay & Echo Network (not feedback — corrected 2026-09-01)

**This section previously named the delay line's update as feedback** (delay buffer accumulating $x[n] + 0.5 \cdot w[n]$, i.e. the buffer's own delayed output folded back into itself). That is a real bug that shipped: because the buffer is read from and written to every sample, that update is exactly $y[n] = x[n] + \text{gain} \cdot y[n-D]$ — true feedback, whose steady-state gain is $\frac{1}{1-\text{gain}}$ ($2.0\times$ at gain $=0.5$), unbounded for a sustained tone. It was what drove the downstream `clamp` into a hard clipper on normalized TTS output, reported live as harsh/distorted audio (Bucket 2, `VOICE_REMEDIATION_PLAN.md`). The fix stores only the **input** in the delay line, making this a simple bounded echo, $y[n] = x[n] + \text{gain} \cdot x[n-D]$ (gain $1+\text{gain}$, $1.5\times$ at gain $=0.5$ — bounded, cannot run away), plus a headroom scale so the wet path itself cannot clip regardless of input content:

For input samples $x[n]$, delay buffer size $M = \lfloor 0.050 \cdot \text{SampleRate} \rfloor$ (1600 samples at 32kHz), gain $g = 0.5$, and headroom $h = \frac{1}{1+|g|}$:

1. Retrieve the delayed sample, **then** overwrite the buffer with the current input only (not the delayed sample or any feedback term):

```math
w[n] = d_{\text{buffer}}[n \pmod M], \qquad d_{\text{buffer}}[n \pmod M] \leftarrow x[n]
```

2. Compute the headroom-scaled echo:

```math
\text{echoed}[n] = (x[n] + g \cdot w[n]) \cdot h
```

3. Blend dry and wet signals:

```math
y[n] = (1.0 - \text{wet-gain}) \cdot x[n] + \text{wet-gain} \cdot \text{echoed}[n]
```

The delay line and playback index are reset at utterance boundaries (`event.done`), not per-chunk — resetting per-chunk would drop the previous chunk's echo tail at every boundary — and, since 2026-09-01, a fix also clears a stray buffered odd PCM byte on reset, so it cannot splice one utterance's trailing byte onto the next, unrelated utterance's first byte.

This ensures that the agent's spatial projection matches the visual distance of the user, achieving true sensory-motor loop integration.

---

## 🧠 5. Phase 5: Theory of Mind (ToM) Modeling Layer

To prevent generic and repetitive responses, the system implements a **Theory of Mind (ToM) Modeling Layer** that maintains separate, lightweight representations of the user's inferred emotional state, implied goals, and known concept vocabulary.

### 5.1 The User Mental Model (`UserMentalModel`)

The user's perspective is decoupled from the agent's internal state and represented as:
- **Inferred Valence ($V_{\text{user}}$)**: $[-1.0, 1.0]$. The user's pleasure/mood, drifted dynamically by SenseVoice acoustic appraisal signals and extracted by LLM classification.
- **Inferred Arousal ($Ar_{\text{user}}$)**: $[0.0, 1.0]$. The user's emotional intensity/arousal, extracted via System 2 classification.
- **Implied Goals**: Inferred short-term desires of the user (e.g., `"seek_reassurance"`, `"express_frustration"`, `"learn_concept"`, `"chat_socially"`).
- **Known Concepts**: A case-insensitive history of terms and concepts the user has active knowledge of.

### 5.2 Zero-Overhead Vocabulary Tracking

To enforce knowledge boundaries without introducing dynamic LLM inference costs, raw user transcripts undergo pre-decision word indexing:
- **Length Constraint**: Matches alphabetical words $w$ where $4 \le |w| \le 15$ characters.
- **Stop-Word Filtering**: Prunes common high-frequency English particles and pronouns (e.g. `them`, `their`, `there`, `with`, `from`, `your`).
- **Deduplication**: Appends newly discovered concepts uniquely to `known_concepts`, preserving chronological order.

### 5.3 System 2 Latency-Optimized Schema Merge

To respect the sub-800ms System 2 latency budget, ToM parameter extraction is merged directly into the pre-existing intent/goal classification LLM query. The combined schema eliminates extra REST/FCP network overhead:

```json
{
  "intent": "CHAT",
  "goal": "ENGAGE",
  "inferred_valence": 0.25,
  "inferred_arousal": 0.60,
  "implied_goals": ["learn_concept"]
}
```

### 5.4 Dynamic Dialogue Empathy Prompts

During dialogue generation (`RESPOND_CHAT`), the `ActionService` retrieves the active `user_mental_model`. The **10 most recent** entries of `known_concepts` are slice-extracted and formatted alongside the user's emotional parameters into the LLM dynamic user prompt:

```text
Your Inferred Perspective of the User (Theory of Mind):
- User Inferred Valence: 0.25 (Scale: -1.0 to 1.0)
- User Inferred Arousal: 0.60 (Scale: 0.0 to 1.0)
- User Implied Goals: learn_concept
- User Known Concepts (Respect this knowledge boundary): python, programming
```

This enforces strict cognitive boundaries, forcing the assistant to explain new topics using only vocabulary matching the user's inferred familiarity, and directly prevents repetitive or overly generic responses.

### 5.5 Multi-User Relational Context & Gated Memory Routing

To support social scaling in shared environments (such as a multi-user household or workspace):
- **Dynamic Turn Attribution**: The `BrainAgent` extracts the active speaker's ID (`user_id`, e.g., `"Raj"`, `"Priya"`) from incoming interaction packets, logging conversation turns with explicit user roles in the database instead of a static `"user"` string.
- **Gated Memory Queries**: Vector searches and graph spreading activation queries use the dynamic `user_id` context to restrict semantic activation mapping. Relational memory retrieval is gated such that private user contexts (e.g., Raj's childhood memories of Kolkata sweet rasgullas or Priya's memory of Bangalore filter coffee) do not leak across users.
- **Biographical Milestone Scale**: Benchmarked using a 20-milestone structure (6 Shared, 7 Raj-specific, 7 Priya-specific) and 60 corresponding recall questions (3 per milestone) to stress-test relational separation under high-density semantic interference.
- **Attributed Dialogue Consolidation**: Reflective consolidation compiles offline conversation logs using speaker-prefixed lines (e.g., `Raj: content`, `Priya: content`), allowing the system to form clean episodic nodes mapped to the correct user in the Neo4j graph.

---

## 🧠 6. Phase 6: Dual-Tier Edge Architecture & Live iMac M3 Benchmarking (N=100)

To support natural social HRI (Human-Robot Interaction) under strict local compute constraints, AI Friend establishes a **Dual-Tier Edge Model** that partition tasks based on cognitive latency budgets:

### 6.1 Fast-Loop Turn-Taking Tier (`llama3.2:1b`)
* **Role**: Real-time dialogue turn-taking, speculative micro-appraisals, and rapid barge-in interrupt arbitration.
* **Priority**: Temporal responsiveness (Time-to-First-Token target < 250ms).
* **Hardware Profile**: Loaded completely in local VRAM via Apple Metal GPU acceleration, running synchronously inside the event bus loop.

### 6.2 Deep-Loop Reflective Tier (`llama3.2:3b`)
* **Role**: Multi-dimensional Theory of Mind (ToM) inference, paralinguistic tag and filler synthesis (injecting `[laughs]`, `[sighs]` tags dynamically linked to PAD affect states), and subconscious offline memory maturation.
* **Deployment Config**: Configured dynamically in `.env` as the primary chat and reflection core:
  ```ini
  LLM_FAST_MODEL=llama3.2:1b
  LLM_CHAT_MODEL=llama3.2:3b
  LLM_REFLECTION_MODEL=llama3.2:3b
  OLLAMA_REQUIRED_MODELS=llama3.2:1b,llama3.2:3b,nomic-embed-text
  ```

#### 6.3 Empirical GPU Benchmarking Results (Hermes 3 8B on Cloud GPU)
Empirical performance profiling of the cognitive core running under GPU acceleration with the champion `hermes3:8b` model (`scripts/results/hermes3_benchmark_results.json`):

| Metric | Mean | Min | Max | Target |
| :--- | :---: | :---: | :---: | :---: |
| **Time-to-First-Token (TTFT)** | **88.0 ms** | 60.6 ms | 121.7 ms | < 250 ms (Achieved) |
| **Generation Throughput** | **44.4 tok/s** | 43.6 tok/s | 45.2 tok/s | > 30 tok/s (Achieved) |
| **End-to-End Turn Latency** | **5,211.8 ms** | 1,062.3 ms | 9,599.1 ms | — |

* **Empirical Inference Efficiency**: **88.0 ms TTFT / 44.4 tokens/sec** verified on GPU (`scripts/results/hermes3_benchmark_results.json`, `scripts/results/extended_benchmarks.json`).
* **Lightweight Footprint**: **1,266 MB RAM / 0.99 W** for the full 8-agent mesh + Postgres/Neo4j/Qdrant/NATS/Redis stack (`scripts/results/human_realism_results.json`).

---

## 🏆 7. SOTA Comparative Benchmarking Matrix & Academic Mappings

To establish rigorous scientific boundaries, AI Friend is actively compared against the latest state-of-the-art conversational humanoid robots, mechanical humanoids, and advanced software cognitive architectures:

| Performance Axis | SOTA Humanoid: Figure 02 (In-House AI) [1] | SOTA Humanoid: Tesla Optimus Gen 2 [2] | Compact Humanoid: Unitree G1 [3] | SOTA Expressive: Ameca Gen 3 [4] | Kyoto Android: ERICA [5] | SOTA Graph Memory: AriGraph/HippoRAG [6] | SOTA Embodied: ACT-R/E [7] | **Ours: AI Friend (Physical)** | **Ours: AI Friend (Accelerated)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Speech Barge-in Stop** | Cloud VLM Delay (~300ms) | N/A (Secondary audio) | Cloud VAD (~400ms) | Tritium Stream Buffer (~250ms) | 200.0 ms | N/A | N/A | **~104 ms**¹ | *(mode retired)*⁶ |
| **Cognitive Gating Latency** | Cloud VLM reasoning | Onboard task planning | Cloud LLM reasoning | Cloud LLM reasoning | 100.0 ms | N/A | 50.0 ms | **5.44 ms**² | *(mode retired)*⁶ |
| **Speech-to-Speech TTFT** | ~350 ms | Cloud speech delays | ~500 ms | ~400 ms | 200.0 ms | N/A | N/A | **61.9 ms**³ (Hermes 3) | *(mode retired)*⁶ |
| **Memory Scaling Complexity** | N/A | N/A | N/A | N/A | N/A | $O(\log M_{\text{total}})$ | Linear search | $O(\log N)$ (ACT-R + Qdrant) | *(mode retired)*⁶ |
| **Memory Recall (Recall@5)** | N/A | N/A | N/A | N/A | N/A | ~92.0% | ~85.0% | **87.5%**⁴ | *(mode retired)*⁶ |
| **Theory of Mind MAE** | N/A | N/A | N/A | N/A | N/A | N/A | 0.280 MAE | **0.032 (valence) / 0.041 (arousal)**⁴ | *(mode retired)*⁶ |
| **Autonomic Somatic State** | Static Response | Static Response | Static Response | Static Response | Static Response | N/A | N/A | **Dynamic** (PAD + tonic/phasic cortisol and dopamine — see `algorithms_equations.md` §2.3) | *(mode retired)*⁶ |
| **System Idle Memory** | High (Onboard OS) | High (Optimus FSD) | High (ROS2 Mesh) | High (Tritium Stack) | High Cloud | N/A | N/A | **1,266 MB**⁵ (8-agent mesh + DB stack) | *(mode retired)*⁶ |
| **Active Edge Power** | High (Onboard GPU) | High (Tesla FSD Core) | Moderate | High (Onboard NUC) | High Cloud | N/A | N/A | **0.99 W**⁵ | *(mode retired)*⁶ |
| **Structural Novelties** | End-to-End VLM | Vision-Motor NN | Local VLM Plan | Gaze-to-Speech Tritium | Attentive VAP Frame | Associative Graph | Symbolic Decays | **Live Localized Mind Mesh** | *(mode retired)*⁶ |

> Provenance/caveats for the "Physical" column (¹composed estimate, not a live stopwatch trial; ²composed from 7 measured components, excludes LLM generation; ³measured empirical streaming TTFT on Tesla T4 GPU for Hermes 3 8B; ⁴independently recomputed from raw per-sample arrays and matches exactly; ⁵full 8-agent mesh + DB stack; ⁶accelerated mode is intentionally disabled in `hard_benchmark.py`) mirror `README.md` §8 and `scripts/results/benchmark_results_summary.md` — keep these three in sync.

### 📚 Reference Mapping

> [!NOTE]
> **Provenance.** [1]–[4] are vendor product materials, **not** peer-reviewed
> publications. [5]–[7] are real, verified publications whose titles were
> previously paraphrased into non-existent variants and have since been corrected
> against the published record. See the canonical, annotated list in the root
> `README.md` (§8) — maintained there to avoid duplicate drift. The *comparative
> performance figures* attributed to these sources remain unverified.

---

## 🔊 8. Hybrid Brain Architecture (Native Speech Features & Dynamic Prosody)

In AI Friend, the system incorporates three specialized messaging topics on the solid-state NATS bus to bridge System 1 raw voice sensors directly with System 2 symbolic reasoning:

### 8.1 user.voice.properties
Emitted by the **STT Agent** (`backend/crates/stt-agent`) during raw PCM ingest:
- **Pitch ($F_0$)**: Extracted via real-time autocorrelation ($F_0 = \frac{\text{SampleRate}}{\text{lag}}$).
- **Energy (RMS)**: Continuous Root-Mean-Square calculation of audio frame amplitude normalized to $[-1.0, 1.0]$.
- **Tempo (WPM)**: Speed estimation via Zero-Crossing Rate (ZCR).

### 8.2 agent.voice.modulation
Emitted by the **Surfacing Agent** (`backend/app/agents/surfacing_agent.py`) upon receiving a `state.update` event:
- Employs the **APRA v2** Continuous Frame-wise Prosody Engine to generate a 3.0-second trajectory consisting of 60 frames spaced at 50ms intervals.
- Translates active Pleasure-Arousal-Dominance (PAD) and metabolic fatigue parameters into continuous Speaking Rate ($R$), Pitch ($P$), and Volume ($V_{ol}$) trajectories, enriched with organic human features such as a 6Hz micro-vibratory ripple (pitch vibrato) and start/end breathing/volumetric envelopes.
- Employs a type-safe `List[ProsodyFrame]` payload to feed the downstream synthesis parameter pipeline (**corrected 2026-09-01**: no OLA DSP stage exists anymore, see §3). Each *sentence-level* synthesis call now samples one point on this trajectory, chosen from the utterance's real elapsed time — a meaningful improvement over the flattening this design used to suffer when chunking cut every ~3 words (Bucket 5, `VOICE_REMEDIATION_PLAN.md`, prior to which the trajectory's 60 frames were being sampled at 3-word granularity regardless of the continuous curve underneath). Chunking is now clause-aligned (§10.2 below), so consecutive synthesis calls span a genuine portion of the trajectory instead of a near-constant slice of it.

### 8.3 audio.playback.visemes
Emitted by the **Voice Agent** (`backend/crates/voice-agent`) dynamically during audio output:
- Maps active playback energy levels into viseme target amplitudes (`target_level` $\in [0.0, 1.0]$) and standard viseme phonetic identifiers (`AA`, `O`, `AH`, `sil`) to enable sample-accurate robotic lip-sync expressions.

---

## 🧠 9. Dialogue Truncation on User Interruption (Embodied Feedback Loop)

To prevent cognitive dissonance and enable realistic social interaction, the system supports real-time dialogue history truncation when a user interrupts the agent.

### 9.1 Character-Count Speech Rate Fallback Model
If progress telemetry (`audio.playback.progress`) is absent (e.g. running offline, in lightweight development environments, or during benchmark runs without active voice client loops), the system falls back to a **Time-based Speech Rate Fallback Model**.

The character offset ($C$) at the moment of interruption ($t_{\text{stop}}$) is estimated based on elapsed time since speech onset ($t_{\text{start}}$) and average speaking rate ($\text{speech-rate}$ = 15 characters per second):

```math
C = \lfloor \text{speech-rate} \cdot (t_{\text{stop}} - t_{\text{start}}) \rfloor
```

The logged assistant message is truncated to at most $C$ characters while respecting word boundaries (i.e., cut at the last full word that keeps length $\le C$) to match the user's auditory experience of the interruption.

---

## 🧠 10. Single-Engine Synthesis & Quality-Prioritized Look-Ahead

AI Friend's voice agent renders every utterance through one self-hosted GPT-SoVITS
endpoint — the cloned voice's identity lives permanently in its loaded weights
(`CUSTOM_GPT_PATH`/`CUSTOM_SOVITS_PATH`), so there is nothing to select between
at synthesis time.

**History**: an earlier iteration ("Scenario B", May 31 2026) embedded the `ort`
library (ONNX Runtime) directly in the Rust binary as a `LocalTtsEngine`, with
dynamic execution-provider selection (TensorRT/CUDA/CoreML/CPU) and a
custom→base model fallback under `models/custom/`/`models/base/`. It was
removed 2026-07: on failure it fell back to a *different, uncloned* voice,
which is strictly worse than silence under a no-fallback requirement. See the
ledger entry for the removal and what replaced it.

### 10.1 Emotion-Selected Reference Clips & Same-Engine Resilience
- **Delivery register, not identity**: `select_emotion_bucket` maps the turn's
  PAD affect (valence/arousal) onto one of five registers — calm, warm,
  concerned, excited, neutral — each an optional GPT-SoVITS reference clip
  (`REF_AUDIO_PATH_*`/`REF_TEXT_*`). An unconfigured register falls back to
  neutral silently. This changes *how* a line is delivered per turn; the
  cloned voice's identity never changes, since that is baked into the
  server's weights, not the reference clip.
- **No fallback, same-engine recovery only**: a circuit breaker with bounded
  retry wraps every synthesis call, and a background readiness probe proves
  the engine renders real audio (not just answers HTTP) independently of live
  traffic, so an outage is caught even during silence. A confirmed failure
  plays a same-voice fallback vocalization instead of dropping the turn or
  switching voices.

### 10.2 Quality-Latency Balanced Pacing
To prevent fragmented or robotic speech (which occurs when chunk sizes are too small), the system implements a quality-prioritized look-ahead configuration:
- **Speech Segmentation**: The `brain_agent` buffers words and flushes on whichever of three conditions fires first: a clause boundary (comma/colon/semicolon at or past the **7-word** target, or sentence-ending punctuation, scored by `HybridSegmenter.score_split_point`), a hard 12-word cap, or a **300ms formation-buffer timer** once at least 3 words are buffered — the timer is a latency safety net for a stalled model, not the primary segmentation signal. **Corrected 2026-09-01**: this timer used to be misnamed `formation_buffer_ms` while actually holding 0.030 compared against a seconds-based clock — an effective 30ms, so in practice it almost always won the race against the clause segmenter and flushed every 3 words regardless of where a real clause boundary was (`VOICE_REMEDIATION_PLAN.md` Bucket 5). Raised to a real 300ms clause-formation window.
- **Speculative Filler Timing**: If the LLM has not emitted the first token within **1200ms** of generation actually starting (`Config.VOICE_FILLER_THRESHOLD`, corrected 2026-09-01 from a smaller value per direct product-owner direction — 400ms was found to be baseline pipeline overhead, not a noticeable delay, so it fired on effectively every turn), a filler word (one of `hmm`, `let's see`, `well`, `ah`, `right` — see `FILLERS` in `conversational_runtime.py`) is dispatched, additionally suppressed if a previous turn's audio is still backed up in playback or a filler already fired too recently. This is unrelated to chunk size; both the clause segmenter and the filler timer were independently mistuned, not causally linked the way this section previously implied.
