# Agentic Context: Phase 4 Dynamic Continuous Prosody Mapping & DSP Playback

This document provides the formal mathematical specification, operational design, and data-flow pathways for the **Phase 4 Dynamic Continuous Prosody Mapping**, **Overlap-Add (OLA) Crossfade Processing**, and **Dynamic Emotional Parameters** within the Cognitive Voice System (CVS).

---

## 🧠 1. Dynamic Emotional & Physiological Parameters

The system models the agent's internal state as a high-dimensional vector combining **dimensional affect** (PAD), **relational factors**, and **metabolic/spatial proprioceptive indicators**:

| Parameter | Symbol | Range | Tracking Mechanism / Description |
| :--- | :--- | :--- | :--- |
| **Valence** | $`V`$ | $`[-1.0, 1.0]`$ | Pleasure/Mood dimension. Updated via goal congruence appraisal. |
| **Arousal** | $`Ar`$ | $`[0.0, 1.0]`$ | Energy/Excitement. Drives speech rate and pitch dynamics. |
| **Dominance** | $`D`$ | $`[0.0, 1.0]`$ | Sense of agency/control. Directly modulates vocal volume. |
| **Trust** | $`T`$ | $`[0.0, 1.0]`$ | Long-term relational warmth. Composed of Benevolence, Competence, and Integrity. |
| **Attachment** | $`At`$ | $`[0.0, 1.0]`$ | Long-term relational bond intensity. |
| **Fatigue** | $`F`$ | $`[0.0, 1.0]`$ | Metabolic fatigue. Accumulates during active turns, decays during idle cycles. |
| **User Distance** | $`d`$ | $`[0.0, \infty)`$ | Spatial distance in meters. Inferred via OpenCV Haar Cascade face detection width ($`d = \frac{0.15}{S}`$). |

---

## 🎙️ 2. Dynamic Continuous Prosody Mapping Equations

The Voice Agent utilizes a dynamic linear-algebraic mapper to translate internal emotional-physiological states into synthesis parameters for the GPT-SoVITS runtime (`speed_factor`, `pitch`, `volume`, `pause_bias`).

These equations are computed native in Rust (`backend/crates/contracts/src/lib.rs`):

### 2.1 Inputs & Modifiers

1. **Fatigue Adjustments**:
   * Speaking Rate slowdown: 

```math
\text{fatigue\_slow} = 0.25 \cdot F
```

   * Pitch dropdown: 

```math
\text{fatigue\_pitch\_drop} = 0.10 \cdot F
```

2. **Distance Spatial Adaptation**:
   * Close-range threshold ($`d < 0.6\text{m}`$, whisper configuration):

```math
\text{dist\_vol\_mod} = -0.15, \quad \text{dist\_pitch\_mod} = -0.05
```

   * Far-range threshold ($`d > 1.5\text{m}`$, projection configuration):

```math
\text{dist\_vol\_mod} = 0.20, \quad \text{dist\_pitch\_mod} = 0.10
```

   * Intermediate baseline:

```math
\text{dist\_vol\_mod} = 0.00, \quad \text{dist\_pitch\_mod} = 0.00
```

### 2.2 Core Synthesis Parameters

1. **Speaking Rate ($`R`$)**:
   Modulated by arousal energy and valence, slowed down by metabolic fatigue, clamped to safety bounds:

```math
R = 1.0 + 0.20 \cdot Ar - 0.10 \cdot V - \text{fatigue\_slow}
```

```math
\text{SpeedFactor} = \text{clamp}(R, 0.6, 1.8)
```

2. **Vocal Pitch ($`P`$)**:
   Jointly modulated by valence and arousal, tempered by dominance, and adjusted for fatigue and distance:

```math
P = 1.0 + 0.05 \cdot V + 0.15 \cdot Ar - 0.10 \cdot D - \text{fatigue\_pitch\_drop} + \text{dist\_pitch\_mod}
```

```math
\text{Pitch} = \text{clamp}(P, 0.5, 2.0)
```

3. **Vocal Volume ($`V_{ol}`$)**:
   Modulated by interpersonal dominance (assertiveness) and adjusted for distance propagation:

```math
V_{ol} = 0.4 + 0.6 \cdot D + \text{dist\_vol\_mod}
```

```math
\text{Volume} = \text{clamp}(V_{ol}, 0.1, 1.0)
```

4. **Pause Bias ($`B_{\text{pause}}`$)**:
   Determines the baseline silent duration between speech segments. Higher arousal suppresses silence:

```math
B_{\text{pause}} = 1.0 - Ar
```

All parameters are rounded to exactly **two decimal places** ($`0.01`$ precision) prior to serialized delivery to the SoVITS inference pipeline.

---

## 🔊 3. Overlap-Add (OLA) Crossfade Processing

To ensure seamless audio transitions, eliminate acoustic pops, and guarantee signal continuity during sudden state transitions or speculative interruptions, the playback engine applies a sample-accurate **Linear Overlap-Add (OLA) Crossfade**.

### 3.1 Linear Fade Window Formulation

When a prosody shift is detected between consecutive audio segments, the engine computes a **10ms linear crossfade window** based on the configured sample rate (typically 32kHz):

```math
\text{fade\_len} = \lfloor 0.010 \cdot \text{SampleRate} \rfloor
```

For $`32,000\text{Hz}`$, the crossfade window contains exactly $`320`$ samples.

### 3.2 Signal Modulation

For each sample index $`i`$ in the crossfade window ($`0 \le i < \text{fade\_len}`$), the blend factor $`t`$ is computed as:

```math
t = \frac{i}{\text{fade\_len}}
```

The output blends the previous prosody segment buffer $`x_{\text{prev}}[i]`$ with the incoming segment $`x_{\text{curr}}[i]`$:

```math
y[i] = (1 - t) \cdot x_{\text{prev}}[i] + t \cdot x_{\text{curr}}[i], \quad 0 \le i < \text{fade\_len}
```

For $`i \ge \text{fade\_len}`$, the signal passes through unmodified:

```math
y[i] = x_{\text{curr}}[i]
```

### 3.3 Dynamic Signal Reconstruction

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

When the physical distance $`d`$ increases, high-frequency elements decay, and atmospheric reflections introduce reverberation. The Voice Agent implements a real-time **Reverb Comb Filter** within its processing pipeline (`backend/crates/voice-agent/src/main.rs`).

### 4.1 Wet/Dry Linear Interpolation

Acoustic reverb gain ($`\text{wet\_gain}`$) is scaled dynamically as a function of distance:

```math
\text{wet\_gain} = \begin{cases} 
0.0 & \text{if } d \le 2.5\text{m} \\
\frac{d - 2.5}{3.5 - 2.5} & \text{if } 2.5\text{m} < d < 3.5\text{m} \\
1.0 & \text{if } d \ge 3.5\text{m}
\end{cases}
```

### 4.2 Delay & Feedback Network

The DSP reverb comb filter uses a **50ms circular delay line** with a $`0.5`$ feedback gain factor. For input samples $`x[n]`$ and delay buffer size $`M = \lfloor 0.050 \cdot \text{SampleRate} \rfloor`$ (1600 samples at 32kHz):

1. Retrieve delayed sample:

```math
w[n] = d_{\text{buffer}}[n \pmod M]
```

2. Update delay buffer:

```math
d_{\text{buffer}}[n \pmod M] = x[n] + 0.5 \cdot w[n]
```

3. Blend dry and wet signals:

```math
y[n] = (1.0 - \text{wet\_gain}) \cdot x[n] + \text{wet\_gain} \cdot d_{\text{buffer}}[n \pmod M]
```

This ensures that the agent's spatial projection matches the visual distance of the user, achieving true sensory-motor loop integration.

---

## 🧠 5. Phase 5: Theory of Mind (ToM) Modeling Layer

To prevent generic and repetitive responses, the system implements a **Theory of Mind (ToM) Modeling Layer** that maintains separate, lightweight representations of the user's inferred emotional state, implied goals, and known concept vocabulary.

### 5.1 The User Mental Model (`UserMentalModel`)

The user's perspective is decoupled from the agent's internal state and represented as:
- **Inferred Valence ($`V_{\text{user}}`$)**: $`[-1.0, 1.0]`$. The user's pleasure/mood, drifted dynamically by SenseVoice acoustic appraisal signals and extracted by LLM classification.
- **Inferred Arousal ($`Ar_{\text{user}}`$)**: $`[0.0, 1.0]`$. The user's emotional intensity/arousal, extracted via System 2 classification.
- **Implied Goals**: Inferred short-term desires of the user (e.g., `"seek_reassurance"`, `"express_frustration"`, `"learn_concept"`, `"chat_socially"`).
- **Known Concepts**: A case-insensitive history of terms and concepts the user has active knowledge of.

### 5.2 Zero-Overhead Vocabulary Tracking

To enforce knowledge boundaries without introducing dynamic LLM inference costs, raw user transcripts undergo pre-decision word indexing:
- **Length Constraint**: Matches alphabetical words $`w`$ where $`4 \le |w| \le 15`$ characters.
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

---

## 🧠 6. Phase 6: Dual-Tier Edge Architecture & Live iMac M3 Benchmarking (N=100)

To support natural social HRI (Human-Robot Interaction) under strict local compute constraints, CVS-3.0 establishes a **Dual-Tier Edge Model** that partition tasks based on cognitive latency budgets:

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

### 6.3 Live iMac M3 Empirical Benchmarking Results ($`N=100`$)
Empirical performance profiling of the containerized cognitive mesh running locally on the Apple iMac (M3 Host Node) under Apple Metal GPU acceleration with the active `llama3.2:3b` model yielded high performance metrics:

| Metric | Mean | p50 | p95 | p99 | Jitter |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **End-to-End Thought Latency** | **1646.95 ms** | 1147.14 ms | 5169.28 ms | 13423.38 ms | 2156.00 ms |
| **Time-to-First-Token (TTFT)** | **703.36 ms** | 230.02 ms | 4111.32 ms | 12512.93 ms | 2157.01 ms |

* **Local Inference Efficiency**: Achieving a **2.6x reduction in TTFT** (703.36 ms vs. 1850.0 ms) compared to cloud humanoid baseline architectures.
* **Lightweight Footprint**: The mesh operates fully in light-mode (with real-time voice and vision containers isolated via compose profiles), dropping the entire system memory footprint to only **1,079.58 MB** and maintaining average CPU utilization below **8.19%**.
