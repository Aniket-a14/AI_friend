# 🧮 Mathematical Formulations & Algorithms

This document compiles the core mathematical formulations, system equations, and procedural algorithms driving **AI Friend CVS-3.0**. It serves as a rigorous drop-in asset for the **Mathematical Methodology** and **Algorithmic Architecture** sections of your academic paper.

---

## 1. System 1 & System 2 Cognitive Appraisal

The Cognitive Vocal System (CVS) implements a dual-process appraisal model based on **Lazarus' Cognitive-Mediational Theory (1991)**, the **OCC Model (Ortony, Clore, & Collins, 1988)**, and the **EMA computational architecture (Gratch & Marsella, 2004)**. On every sensory or conversational event, the system calculates a 6-variable appraisal vector.

### 1.1 Primary Appraisal (Lazarus)
Primary appraisal evaluates the immediate significance of an event for the agent's well-being and active goals*   **Relevance ($R \in [0, 1]$):** Quantifies the attention weight of the event. User-initiated dialogue events are treated as high relevance, while autonomous internal ticks are low relevance:

```math
R = \begin{cases} 
  1.0 & \text{if event is } \texttt{USER\_MESSAGE} \\
  0.1 & \text{if event is } \texttt{SYSTEM\_TICK} \\
  0.5 & \text{otherwise}
\end{cases}
```

*   **Novelty ($N \in [0, 1]$):** Measures semantic distance from recent dialogue history. Calculated as the Jaccard distance against a rolling queue of the $M = 20$ most recent conversational turns:

```math
N = 1 - \max_{h \in \mathcal{H}} \frac{|\mathcal{W}_{\text{event}} \cap \mathcal{W}_h|}{|\mathcal{W}_{\text{event}} \cup \mathcal{W}_h|}
```

    where $\mathcal{W}_{\text{event}}$ is the set of lowercase keywords in the active utterance, and $\mathcal{W}_h$ is the keyword set of historical turn $h$.
*   **Goal Congruence ($G \in [-1, 1]$):** Represents how much the event advances or hinders the agent's core social goal. It maps directly from emotional bias $E_b$ (extracted via acoustic pitch/sentiment trackers):

```math
G = \text{clamp}(E_b, -1.0, 1.0)
```

### 1.2 Secondary Appraisal (Lazarus/OCC/EMA)
Secondary appraisal evaluates the agent's coping potential, social norms, and relational impact.

*   **Agency ($A \in [0, 1]$):** Attributes causal responsibility. For user messages, the agent holds high coping agency since it can generate a verbal response; for system ticks, agency is lower:

```math
A = \begin{cases} 
  0.8 & \text{if event is } \texttt{USER\_MESSAGE} \\
  0.3 & \text{otherwise}
\end{cases}
```

*   **Norm Alignment ($NA \in [0, 1]$):** Represents social praiseworthiness and boundary respect. Evaluated by matching user input keywords against a set of $B$ configured identity boundaries (e.g., toxic, personal boundaries). Every keyword violation decreases norm alignment:

```math
NA = \max\left(0.0, 1.0 - 0.2 \cdot \sum_{b \in B} \mathbb{I}(\text{Violation}(b))\right)
```

    where $\mathbb{I}(\cdot)$ is the indicator function.

*   **Relationship Impact ($RI \in [-1, 1]$):** extension that projects the social valence of the interaction. Modulated by existing relational trust $T$:

```math
RI = \begin{cases} 
  E_b \cdot 0.25 & \text{if } T < 0.3 \text{ (Low trust dampens positive impact)} \\
  E_b \cdot 0.50 & \text{otherwise}
\end{cases}
```

### 1.3 System 2 Deliberative Reappraisal (LLM Hot-Path Drift)
For deep semantic reasoning, CVS-3.0 runs an asynchronous deliberative reappraisal cycle. It queries the fast LLM to grade three dimensions on $[-1.0, 1.0]$: goal congruence ($G_{\text{delib}}$), norm alignment ($NA_{\text{delib}}$), and expectedness ($E_{\text{delib}}$). These values act as coordinates pulling the active PAD emotional state via a drift coefficient $\eta = 0.2$:

```math
\vec{T}_{\text{PAD}} = \begin{bmatrix} G_{\text{delib}} \\ -E_{\text{delib}} \\ NA_{\text{delib}} \end{bmatrix}
```

```math
\vec{PAD}(t) = \vec{PAD}(t-1) + \eta \cdot (\vec{T}_{\text{PAD}} - \vec{PAD}(t-1))
```

---

## 2. Continuous Internal State & Endocrine Dynamics

CVS-3.0 maintains cognitive continuity through a multi-dimensional state vector updating on every appraisal trigger and evolving continuously during idle ticks.

### 2.1 PAD Affective Space Updates (Gebhard's ALMA Mood-Pull)
Internal emotional states are modeled using Mehrabian & Russell's (1974) **3D PAD (Valence-Arousal-Dominance) space**. Continuous updates are governed by Gebhard's (2005) ALMA mood-pull equations, using custom psychological drift rates:

*   **Valence ($V \in [-1.0, 1.0]$):** Governed by goal congruence and relationship impact, with drift rate $\alpha = 0.3$:

```math
V(t) = (1 - \alpha) \cdot V(t-1) + \alpha \cdot (0.6 \cdot G + 0.4 \cdot RI)
```

*   **Arousal ($Ar \in [0, 1]$):** Governed by event novelty and attention relevance, with drift rate $\beta = 0.5$:

```math
Ar(t) = (1 - \beta) \cdot Ar(t-1) + \beta \cdot (0.6 \cdot N + 0.4 \cdot R)
```

*   **Dominance ($D \in [0, 1]$):** Governed by causal agency and norm boundaries, with drift rate $\gamma = 0.2$:

```math
D(t) = (1 - \gamma) \cdot D(t-1) + \gamma \cdot (0.6 \cdot A + 0.4 \cdot NA)
```

### 2.2 Relational Trust & Attachment Dynamics
To model secure human-robot bonds, we implement a multi-dimensional trust space based on **Marsh's Formal Trust Model (1994)** and secure attachment styles based on **Bowlby's Attachment Theory**:

*   **Dimensional Trust:** Trust is decomposed into three components updating with rate $\delta = 0.1$:
    *   **Trust Benevolence ($T_b$):** Sensitivity to emotional relationship impact:

```math
T_b(t) = \text{clamp}(T_b(t-1) + \delta \cdot RI, 0.0, 1.0)
```

    *   **Trust Competence ($T_c$):** Sensitivity to conversational helpfulness and goal congruence:

```math
T_c(t) = \text{clamp}(T_c(t-1) + \delta \cdot (0.6 \cdot G + 0.4 \cdot R), 0.0, 1.0)
```

    *   **Trust Integrity ($T_i$):** Sensitivity to boundary adherence:

```math
T_i(t) = \text{clamp}(T_i(t-1) + \delta \cdot NA, 0.0, 1.0)
```

    *   **Scalar Combined Trust ($T$):** The average of the three components:

```math
T(t) = \frac{T_b(t) + T_c(t) + T_i(t)}{3.0}
```

*   **Bowlby Secure Attachment ($At \in [0, 1]$):** Attachment builds slowly over time based on interaction frequency and trust, with growth rate $\epsilon = 0.03$:

```math
At(t) = \text{clamp}\left(At(t-1) + \epsilon \cdot T(t) \cdot \min\left(1.0, \frac{\text{Interactions}}{100}\right), 0.0, 1.0\right)
```

### 2.3 Endocrine Homeostasis & Hormonal Coupling
Three continuous hormones modulate the LLM's generation hyperparameters (temperature, top_p, penalty) to model physical cognitive constraints:

*   **Fatigue Cycle ($F \in [0, 1]$):** Metabolic wear-and-tear accumulated during active turns and recovered during idle intervals. Governed by a circadian multiplier $\mu_{\text{circadian}}$ (set to $1.8$ at night $22:00\text{--}06:00$, otherwise $1.0$):

```math
F(t) = \begin{cases} 
  \text{clamp}\left(F(t-1) + \frac{0.15 \cdot \Delta t \cdot \mu_{\text{circadian}}}{3600}, 0.0, 1.0\right) & \text{if active interaction} \\
  \text{clamp}\left(F(t-1) - \frac{0.20 \cdot \Delta t}{\mu_{\text{circadian}} \cdot 3600}, 0.0, 1.0\right) & \text{if idle/resting} 
\end{cases}
```

    where $\Delta t$ is the elapsed time in seconds.

*   **Cortisol Coupling ($C \in [0, 1]$):** Represents stress levels. Spikes under negative valence ($V < 0$) and metabolic fatigue ($F$):

```math
C(t) = \text{clamp}\left(0.5 - \frac{V(t)}{2.0} + 0.3 \cdot F(t), 0.0, 1.0\right)
```

    *Hyperparameter mapping:* High cortisol reduces LLM generation temperature to enforce strict, defensive responses; low cortisol increases temperature to support warm, creative responses.

*   **Dopamine Coupling ($D_{\text{dopamine}} \in [0, 1]$):** Represents reward tracking. Mapped from positive valence ($V > 0$) combined with fatigue-modulated arousal $Ar_{\text{actual}}$:

```math
Ar_{\text{actual}}(t) = \text{clamp}(Ar(t) + 0.2 \cdot F(t), 0.0, 1.0) \quad \text{(fatigue induces restlessness)}
```

```math
D_{\text{dopamine}}(t) = \text{clamp}(\max(0.0, V(t)) \cdot Ar_{\text{actual}}(t), 0.0, 1.0)
```

    *Hyperparameter mapping:* High dopamine increases LLM `top_p` to enable playful and exploratory phrasing.

### 2.4 Idle State Decay (ALMA Decay)
During prolonged silence, internal mood converges back to the neutral baseline through exponential decay with decay coefficient $\lambda_{\text{decay}} = 0.05 \text{ hr}^{-1}$:

```math
V(t) = V(0) \cdot e^{-\lambda_{\text{decay}} \cdot \Delta t}
```

where $\Delta t$ is the silence duration in hours. Dominance remains stable as it behaves as a personality trait, while relational trust experiences a very slow drift ($0.01 \text{ hr}^{-1}$) back to the baseline of $0.5$.

---

## 3. Multi-Attribute Utility Theory (MAUT) Decision Layer

The decision layer selects the optimal conversational goal (**ENGAGE**, **COMFORT**, **INFORM**, **TEASE**, **PROTECT**) by executing Multi-Attribute Utility Theory (MAUT; Keeney & Raiffa, 1976).

### 3.1 Core MAUT Goal Scoring
For each goal candidate $g \in \mathcal{G}$, we compute a multi-attribute utility score $U(g)$ representing a weighted linear combination of four cognitive dimensions:

```math
U(g) = w_G \cdot S_G(g) + w_E \cdot S_E(g) + w_I \cdot S_I(g) + w_C \cdot S_C(g)
```

where the weights are configured to maintain system integrity:

```math
w_G = 0.3, \quad w_E = 0.3, \quad w_I = 0.2, \quad w_C = 0.2 \quad \left(\sum w_i = 1.0\right)
```

The scores $S$ for each attribute are defined dynamically based on the current state:

| Goal ($g$) | Goal Congruence ($S_G$) | Emotion Fit ($S_E$) | Identity Fit ($S_I$) | Context Relevance ($S_C$) |
| :--- | :--- | :--- | :--- | :--- |
| **ENGAGE** | $\max(0, G + 0.5)$ | $0.5 + 0.3 \cdot V + 0.2 \cdot Ar$ | $NA$ | $R$ |
| **COMFORT** | $\max(0, -G + 0.5)$ | $\max(0, -V + 0.5) \cdot (1.2 - 0.4 \cdot Ar)$ | $NA$ | $0.8 \cdot R$ |
| **INFORM** | $\max(0, 0.5 \cdot G + 0.3)$ | $0.4 + 0.2 \cdot Ar$ | $NA$ | $R \cdot N$ |
| **TEASE** | $\max(0, 0.3 \cdot G)$ | $\max(0, 0.3 \cdot V + 0.2 \cdot Ar)$ | $NA \cdot T$ | $0.3 \cdot (1 - R)$ |
| **PROTECT** | $0.2$ | $0.2 + 0.1 \cdot Ar$ | $\max(0, 1.0 - NA)$ | $0.5 \cdot R$ |

### 3.2 Intent Persistence with Context Gating
To prevent erratic goal switching during rapid dialogue turns, we implement temporal smoothing with a persistence rate $\rho = 0.15$ coupled with a hard context gating threshold $\theta_{\text{shift}} = 0.3$ (using Novelty $N$ as the shift proxy):

```math
U_{\text{final}}(g, t) = \begin{cases} 
  (1 - \rho) \cdot U_{\text{final}}(g, t-1) + \rho \cdot U(g, t) & \text{if } N < \theta_{\text{shift}} \\
  U(g, t) \quad \text{(Hard Reset)} & \text{if } N \ge \theta_{\text{shift}}
\end{cases}
```

The selected goal is the argmax of the final utility vector:

```math
g^*(t) = \arg\max_{g \in \mathcal{G}} U_{\text{final}}(g, t)
```

---

## 4. Sub-Symbolic ACT-R Graph Memory Activation

To retrieve highly relevant episodic memory chunks from the Neo4j graph, we govern retrieval using the **ACT-R cognitive architecture's sub-symbolic activation theory (Anderson et al., 2004)**.

### 4.1 Base Activation Equation
The total activation $A_i$ of a memory chunk $i$ at retrieval is formulated as:

```math
A_i = \ln \left( \sum_{j=1}^{n} t_j^{-d} \right) + \sum_{k} W_k \cdot S_{ki} + C_{\text{emo}} \cdot \left(1 - \left\| \vec{PAD}_{\text{agent}} - \vec{PAD}_{\text{memory}} \right\|_2\right) + \epsilon
```

*   **Temporal Logarithmic Decay:** $\ln \left( \sum_{j=1}^{n} t_j^{-d} \right)$ represents the power-law decay of availability. $t_j$ is the time elapsed (in seconds) since the $j$-th retrieval of the memory, and $d = 0.5$ is the standard ACT-R decay constant.
*   **Associative Attentional Weighting:** $\sum_{k} W_k S_{ki}$ calculates retrieval cue association, where $W_k$ represents context attention weights and $S_{ki}$ is graph proximity (hop depth factor) of context keys.
*   **Emotional Congruency:** Mapped as the Euclidean distance between the active 3D PAD vector of the agent and the PAD vector stored at encoding:

```math
\left\| \vec{PAD}_{\text{agent}} - \vec{PAD}_{\text{memory}} \right\|_2 = \sqrt{(V_{\text{agent}} - V_i)^2 + (Ar_{\text{agent}} - Ar_i)^2 + (D_{\text{agent}} - D_i)^2}
```

    where $C_{\text{emo}} = 0.15$ acts as the affective scale modifier.
*   **Cognitive Noise:** $\epsilon$ is a stochastic noise variable drawn from a normal distribution $\epsilon \sim \mathcal{N}(0, 0.02^2)$.

### 4.2 Gating and Retrieval Probability
A memory chunk is eligible for injection into the prompt context if its activation exceeds the retrieval threshold:

```math
A_i > \theta_{\text{gating}} = -1.5
```

The retrieval probability $P(i)$ follows the logistic Boltzmann distribution:

```math
P(i) = \frac{1}{1 + \exp\left(-\frac{A_i - \theta_{\text{gating}}}{s}\right)}
```

where $s = 0.05$ represents the stochastically scaled cognitive noise. Memory retrieval recall remains robust even under massive clutters, as evaluated dynamically:

![Memory Search Recall@K Curves](../plots/cognitive_rag_recall.png)

---

## 5. Acoustic Turn-Taking & Barge-in Gating

CVS-3.0 manages low-latency, natural voice turn-taking through a dual-loop System 1 DSP hardware hook and System 2 semantic conflict resolver.

### 5.1 System 1 DSP Audio energy detection
A continuous audio frame stream is processed inside a microsecond-level loop. We compute the Root-Mean-Square (RMS) energy of the incoming audio frame of size $N$:

```math
\text{RMS} = \sqrt{\frac{1}{N} \sum_{k=1}^N x[k]^2}
```

If $\text{RMS} > \text{Threshold}_{\text{silence}}$, a System 1 interruption is triggered. The active Text-to-Speech (TTS) engine immediately halts physical audio playback, capturing the exact epoch $t_{\text{stop}}$.

### 5.2 System 2 Speculative Conflict Resolution
To distinguish a genuine user turn from background room acoustics or conversational agreements (e.g. "I agree" or "Hmm"), a speculative System 2 background segmenter evaluates the early verbal transcript.
If a semantic command or pivot word (e.g., "stop", "wait", "hold", "listen", "sunno") is matched at the beginning of the utterance, the interruption is **Confirmed**. If the early transcript indicates a conversational filler or buried query that does not represent a turn pivot, playback is **Unmuted gracefully** with a crossfade.

### 5.3 Interruption Coherence Index ($ICI$)
The efficiency of turn-taking and physical stopping response speed is evaluated via the Interruption Coherence Index:

```math
ICI = \gamma \cdot \left(1 - P_{\text{false\_trigger}}\right) \cdot \exp\left(-\frac{\left|t_{\text{stop}} - t_{\text{interject}}\right|}{\tau_{\text{overlap}}}\right)
```

*   $\gamma \in [0, 1]$: Cosine similarity between user interjection embeddings and active agent goal intents.
*   $`P_{\text{false\_trigger}}`$: Probability of false-triggering due to background acoustics.
*   $t_{\text{stop}} - t_{\text{interject}}$: Turn response gap (in milliseconds) between when the user physically started speaking and when the TTS stopped.
*   $\tau_{\text{overlap}} = 200.0\text{ ms}$: Human turn-taking overlap baseline constant.

### 5.4 Acoustic prosody crossfading (OLA Crossfade)
To prevent phase discontinuities or popping noises when shifting voice styles dynamically, we apply a **10 ms linear Overlap-Add (OLA) crossfade** between the previous synthesis buffer $x_{\text{prev}}$ and the newly modified prosody buffer $x_{\text{curr}}$:

```math
y[i] = \left(1 - \frac{i}{\text{fade\_len}}\right) \cdot x_{\text{prev}}[i] + \frac{i}{\text{fade\_len}} \cdot x_{\text{curr}}[i], \quad 0 \le i < \text{fade\_len}
```

where $`\text{fade\_len} = \lfloor 0.010 \cdot \text{SampleRate} \rfloor`$ represents the blending window limit.

---

## 6. Algorithmic Implementations

### 6.1 Neurosymbolic ACT-R Memory Retrieval

The primary memory retrieval routine combines structural Graph search with cognitive ACT-R sub-symbolic gating:

```python
def retrieve_episodic_memory(context_query, active_pad_vector, neo4j_driver):
    """
    Algorithm 1: ACT-R Graph Memory Search with Endocrine-Affective Congruency Gating
    """
    # Step 1: dense vector extraction of context cues
    dense_vector = generate_dense_embeddings(context_query)
    
    # Step 2: execute graph multi-hop search in Neo4j (structural search)
    retrieved_chunks = neo4j_driver.query_hops(dense_vector, max_depth=3)
    
    max_activation = -float('inf')
    best_chunk = None
    
    for chunk in retrieved_chunks:
        # Calculate sub-symbolic temporal logarithmic decay
        elapsed_sec = time.time() - chunk.creation_time
        base_decay = math.log(elapsed_sec ** -0.5)  # d = 0.5 ACT-R constant
        
        # Calculate associative graph attentional weight
        attn_weight = chunk.attentional_cue_strength * chunk.hop_depth_factor
        
        # Calculate PAD emotional congruence Euclidean distance
        emo_dist = math.sqrt(
            (active_pad_vector[0] - chunk.pad_valence) ** 2 +
            (active_pad_vector[1] - chunk.pad_arousal) ** 2 +
            (active_pad_vector[2] - chunk.pad_dominance) ** 2
        )
        emo_congruency = 0.15 * (1.0 - emo_dist)
        
        # Inject stochastic cognitive noise
        epsilon = random.normalvariate(0, 0.02)
        
        # Compute total activation
        total_activation = base_decay + attn_weight + emo_congruency + epsilon
        
        # Gating threshold check
        if total_activation > -1.50 and total_activation > max_activation:
            max_activation = total_activation
            best_chunk = chunk
            
    return best_chunk
```

### 6.2 Speculative Turn-Taking Gating

The dual-loop System 1/System 2 barge-in algorithm ensures that speech playback halts instantaneously upon sound energy detection, but speculative validation restores playback if the sound is identified as noise:

```python
async def barge_in_gating_loop(audio_stream, active_tts_process):
    """
    Algorithm 2: Dual-Loop System 1 / System 2 Speculative Turn Interruption
    """
    async for frame in audio_stream:
        # System 1: Fast-Loop DSP Audio Hook (microsecond thresholding)
        rms = calculate_rms(frame)
        if rms > SYSTEM1_SILENCE_THRESHOLD:
            # Immediate physical audio halt
            active_tts_process.mute_playback()
            t_stop = time.time()
            
            # Spawn speculative System 2 Segmenter in background
            is_valid_interruption = await system2_speculative_scan(frame)
            
            if is_valid_interruption:
                # True interruption: flush active dialogue pipelines and route user turn
                publish_nats_event("chat.interrupted", {"t_stop": t_stop})
                break
            else:
                # False trigger: restore TTS playback gracefully with 10ms OLA crossfade
                active_tts_process.unmute_playback_crossfade(fade_ms=10)
```

The absolute inference error distributions of the Theory of Mind (ToM) affect modeling under intensive stressor sequences show high convergence precision across domains:

![Theory of Mind Absolute Inference Errors Boxplots](../plots/cognitive_tom_errors.png)
