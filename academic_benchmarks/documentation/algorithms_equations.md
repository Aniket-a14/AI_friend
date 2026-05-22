# 🧮 Mathematical Formulations & Algorithmic Specifications

This document compiles the core mathematical formulations, system equations, and procedural algorithms driving the cognitive and sensory layers of **AI Friend CVS-3.0 (Cognitive Vocal System)**. It serves as a rigorous, publication-ready asset for the **Mathematical Methodology** and **Algorithmic Architecture** sections of academic publications.

---

## 1. System 1 & System 2 Cognitive Appraisal

The Cognitive Vocal System (CVS) implements a dual-process appraisal model rooted in **Lazarus' Cognitive-Mediational Theory (1991)**, the **OCC Model (Ortony, Clore, & Collins, 1988)**, and the **EMA computational architecture (Gratch & Marsella, 2004)**. For every conversational, internal, or sensory event, the system computes a 6-variable appraisal vector.

### 1.1 Primary Appraisal (Lazarus)

Primary appraisal evaluates the immediate significance of an event for the agent's active goals and well-being:

*   **Relevance ($R \in [0, 1]$):** Quantifies the attention weight of the incoming event. User-initiated dialogue events are treated as high relevance, while autonomous internal ticks are low relevance:

```math
R = \begin{cases}
  1.0 & \text{if event is } \texttt{USER\_MESSAGE} \\
  0.1 & \text{if event is } \texttt{SYSTEM\_TICK} \\
  0.5 & \text{otherwise}
\end{cases}
```

*   **Novelty ($N \in [0, 1]$):** Measures semantic distance from recent dialogue history. Calculated as the Jaccard distance against a rolling queue of the $M = 20$ most recent conversational turns:

```math
N = \begin{cases}
  0.8 & \text{if } \mathcal{H} = \emptyset \\
  1 - \max_{h \in \mathcal{H}} \frac{|\mathcal{W}_{\text{event}} \cap \mathcal{W}_h|}{|\mathcal{W}_{\text{event}} \cup \mathcal{W}_h|} & \text{otherwise}
\end{cases}
```

where $\mathcal{W}_{\text{event}}$ is the set of lowercase keywords in the active utterance, and $\mathcal{W}_h$ is the keyword set of historical turn $h$.

*   **Goal Congruence ($G \in [-1, 1]$):** Represents how much the event advances or hinders the agent's core social goal. It maps directly from the emotional bias $E_b$ (extracted via acoustic pitch/sentiment trackers):

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

*   **Norm Alignment ($NA \in [0, 1]$):** Represents social praiseworthiness and boundary respect. Evaluated by matching user input keywords against a configured set of identity boundaries, excluding standard skip words (e.g., *not*, *no*, *don't*, *never*, *without*, *isn't*). Every keyword violation decreases norm alignment:

```math
NA = \max(0.0, 1.0 - 0.2 \cdot \text{violations})
```

*   **Relationship Impact ($RI \in [-1, 1]$):** Projects the social valence of the interaction, modulated by the existing relational trust $T$:

```math
RI = \begin{cases}
  E_b \cdot 0.25 & \text{if } T < 0.3 \text{ (Low trust dampens positive impact)} \\
  E_b \cdot 0.50 & \text{otherwise}
\end{cases}
```

### 1.3 System 2 Deliberative Reappraisal & Semantic Mood Drift

For deep semantic reasoning, CVS-3.0 runs an asynchronous deliberative reappraisal cycle. It queries the fast LLM to grade three dimensions on $[-1.0, 1.0]$: goal congruence ($gc$), norm alignment ($na$), and expectedness ($exp$). These values act as coordinates pulling the active 3D PAD emotional state via a drift coefficient $\eta = 0.2$:

```math
\vec{T}_{\text{PAD}} = \begin{bmatrix} gc \\ -exp \\ na \end{bmatrix}
```

```math
\vec{PAD}(t) = \vec{PAD}(t-1) + \eta \cdot (\vec{T}_{\text{PAD}} - \vec{PAD}(t-1))
```

The resulting coordinates are clamped to ensure psychological boundaries: Valence $V \in [-1.0, 1.0]$, Arousal $Ar \in [0.0, 1.0]$, and Dominance $D \in [0.0, 1.0]$.

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

To model secure human-agent bonds, we implement a multi-dimensional trust space based on **Marsh's Formal Trust Model (1994)** and secure attachment styles based on **Bowlby's Attachment Theory**:

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
Ar_{\text{actual}}(t) = \text{clamp}(Ar(t) + 0.2 \cdot F(t), 0.0, 1.0)
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

## 3. Behavior Tree Routing & Action Planning

To structure execution flow and cognitive priorities, CVS-3.0 adopts a modular **Behavior Tree (BT)** framework. This separates high-level intention selection from low-level mechanical action execution.

```
                  [RootSelector] (Selector)
                 /             |          \
      [SystemTasks]     [MemoryCommands]   [SocialReasoning] (Sequences)
       /         \         /        \          /         \
 [IsSysTick] [PlanRefl] [IsRem] [PlanStore] [IsChat] [PlanSocial] (Leafs)
```

The BT blackboard serves as the shared state medium, containing the active event, current state snapshot, and generated execution plans:

```math
\mathcal{B} = \{ \text{event}: \text{Event}, \, \text{state}: \text{Snapshot}, \, \text{plan}: \text{ActionPlan} \}
```

### 3.1 Node Status & Composite Execution

Nodes return a status $s \in \{ \text{SUCCESS}, \, \text{FAILURE}, \, \text{RUNNING} \}$ on every tick.

*   **Selector Nodes ($\lor$):** Fallback routers that tick their children sequentially. If any child succeeds or is running, the Selector propagates that status immediately. It returns `FAILURE` if and only if all children fail:

```math
\text{Selector}(b) = \begin{cases}
  s_i & \text{if } \exists i \text{ s.t. } \text{tick}(C_i, b) = s_i \in \{\text{SUCCESS}, \text{RUNNING}\} \\
  \text{FAILURE} & \text{otherwise}
\end{cases}
```

*   **Sequence Nodes ($\land$):** Reactive pipelines that tick children sequentially. If any child fails or is running, the Sequence propagates that status immediately. It returns `SUCCESS` if and only if all children succeed:

```math
\text{Sequence}(b) = \begin{cases}
  s_i & \text{if } \exists i \text{ s.t. } \text{tick}(C_i, b) = s_i \in \{\text{FAILURE}, \text{RUNNING}\} \\
  \text{SUCCESS} & \text{otherwise}
\end{cases}
```

### 3.2 Leaf Nodes (Actions & Conditions)

*   **Action Nodes:** Execute a computational callback `func(blackboard)`. Returns `SUCCESS` if execution returns a truthy value, otherwise returns `FAILURE`.
*   **Condition Nodes:** Perform non-blocking state evaluations `func(blackboard)`. Returns `SUCCESS` if the boolean statement evaluates to `True`, otherwise `FAILURE`.

---

## 4. Multi-Attribute Utility Theory (MAUT) Decision Layer

The decision layer selects the optimal conversational goal (**ENGAGE**, **COMFORT**, **INFORM**, **TEASE**, **PROTECT**) by executing Multi-Attribute Utility Theory (MAUT; Keeney & Raiffa, 1976).

### 4.1 Core MAUT Goal Scoring

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

### 4.2 Intent Persistence with Context Gating

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

## 5. Sub-Symbolic ACT-R Graph Memory Activation

To retrieve highly relevant episodic memory chunks from the Neo4j graph and vector database, we govern retrieval using the **ACT-R cognitive architecture's sub-symbolic activation theory (Anderson et al., 2004)**.

### 5.1 Base Activation and Temporal Decay

The total activation $Score_i$ of a memory chunk $i$ at retrieval is formulated as a combination of sub-symbolic strength, effective semantic similarity, and emotional distance:

```math
Score_i = A_i + W_{\text{spread}} \cdot \text{Similarity}_{\text{eff}} - 0.5 \cdot \text{dist-emo}
```

*   **Sub-Symbolic Base Activation ($A_i$):** Represents the power-law decay of availability. $t$ is the time elapsed (in hours) since memory creation, $n$ is the recall count, and $d = 0.5$ is the standard ACT-R decay constant:

```math
A_i = \ln(n) - d \cdot \ln(t + 1.0) + 1.5 \cdot \text{Importance}_i + 0.15 \cdot (1.0 - \text{dist-emo})
```

*   **Emotional Distance ($\text{dist-emo}$):** Mapped as the Euclidean distance between the active emotional parameters of the agent and those stored at encoding:

```math
\text{dist-emo} = \sqrt{(V_{\text{memory}} - V_{\text{agent}})^2 + (Ar_{\text{memory}} - Ar_{\text{agent}})^2}
```

*   **Effective Similarity ($\text{Similarity}_{\text{eff}}$):** Blends vector cosine similarity with hormone levels (cortisol stress dampening) and emotional valence:

```math
\text{Similarity}_{\text{eff}} = \text{Similarity} \cdot (1.0 + 0.1 \cdot V_{\text{memory}} \cdot Ar_{\text{memory}} - 0.2 \cdot Ar_{\text{agent}} \cdot C_{\text{cortisol}})
```

### 5.2 Attentional Spreading & Direct Cue Boost

CVS-3.0 extends standard ACT-R with dynamic, real-time associative spreading activation:

*   **Direct Cue Boost:** If direct cues match key terms in the query text (e.g. *Kolkata*, *Bangalore*, *Priya*, *Rasgulla*, *Cognitive Architectures*, *Affective*), matching memories receive an instantaneous boost:

```math
Score_i \leftarrow Score_i + 1.2
```

*   **Spreading Activation:** Memories receiving a direct cue boost propagate activation $+0.6$ to related candidate nodes in the pool sharing common entities or matching cross-epoch age attributes in content:

```math
Score_j \leftarrow Score_j + 0.6 \quad \forall j \text{ connected to } i
```

### 5.3 Gating and Retrieval Probability

A memory chunk is eligible for injection into the prompt context if its activation exceeds the retrieval threshold:

```math
Score_i > \theta_{\text{recall}} = -1.5
```

The retrieval probability $P(i)$ follows the logistic Boltzmann distribution:

```math
P(i) = \frac{1}{1 + \exp\left(-\frac{Score_i - \theta_{\text{recall}}}{s}\right)}
```

where $s = 0.05$ represents the stochastically scaled cognitive noise.

---

## 6. Acoustic Turn-Taking & Speculative Barge-in Gating

CVS-3.0 manages low-latency, natural voice turn-taking through a dual-loop System 1 DSP hardware hook and System 2 semantic conflict resolver.

### 6.1 System 1 DSP Audio Energy Detection

A continuous audio frame stream is processed inside a microsecond-level loop. We compute the Root-Mean-Square (RMS) energy of the incoming audio frame of size $N$:

```math
\text{RMS} = \sqrt{\frac{1}{N} \sum_{k=1}^N x[k]^2}
```

If $\text{RMS} > \text{Threshold}_{\text{silence}}$, a System 1 interruption is triggered. The active Text-to-Speech (TTS) engine immediately halts physical audio playback, capturing the exact epoch $t_{\text{stop}}$.

### 6.2 System 2 Speculative Conflict Resolution

To distinguish a genuine user turn from background room acoustics or conversational agreements (e.g., "I agree" or "Hmm"), a speculative System 2 background segmenter evaluates the early verbal transcript.

A candidate interruption is matched against conversational keywords (e.g. *stop*, *wait*, *hold*, *listen*, *sunno*, *ruko*, *quiet*).
1.  **Connector Rejection:** If a conversational connector (e.g., *i agree*, *i think*, *i actually*, *but*, *though*, *to*, *be*) immediately follows the keyword, the stop is rejected.
2.  **Pivot Alignment:** The keyword must act as a turn pivot, occurring at the start (`idx == 0`) or following call signs (`hey`, `friend`). Buried keywords are rejected.
3.  **Conciseness Confirmation:** The interruption is confirmed if the length of the early transcript is short ($\le 4$ words) or the keyword is the absolute starting word.

If these filters fail, playback is unmuted gracefully with a crossfade.

### 6.3 Interruption Coherence Index ($ICI$)

The efficiency of turn-taking and physical stopping response speed is evaluated via the Interruption Coherence Index:

```math
\text{ICI} = \gamma \cdot \left(1 - P_{\text{false-trigger}}\right) \cdot \exp\left(-\frac{\left|t_{\text{stop}} - t_{\text{interject}}\right|}{\tau_{\text{overlap}}}\right)
```

*   $\gamma \in [0, 1]$: Cosine similarity between user interjection embeddings and active agent goal intents.
*   $P_{\text{false-trigger}}$: Probability of false-triggering due to background acoustics.
*   $t_{\text{stop}} - t_{\text{interject}}$: Turn response gap (in milliseconds) between when the user physically started speaking and when the TTS stopped.
*   $\tau_{\text{overlap}} = 200.0\text{ ms}$: Human turn-taking overlap baseline constant.

### 6.4 Acoustic Prosody Crossfading (OLA Crossfade)

To prevent phase discontinuities or popping noises when shifting voice styles dynamically, we apply a **10 ms linear Overlap-Add (OLA) crossfade** between the previous synthesis buffer $x_{\text{prev}}$ and the newly modified prosody buffer $x_{\text{curr}}$:

```math
y[i] = \left(1 - \frac{i}{\text{fade-len}}\right) \cdot x_{\text{prev}}[i] + \frac{i}{\text{fade-len}} \cdot x_{\text{curr}}[i], \quad 0 \le i < \text{fade-len}
```

where $\text{fade-len} = \lfloor 0.010 \cdot \text{SampleRate} \rfloor$ represents the blending window limit.

---

## 7. Voice Prosody & Acoustic Parameter Mapping

To express continuous cognitive and endocrine states paralinguistically, CVS-3.0 maps the internal PAD affect values, fatigue metrics, and physical distance variables directly into acoustic synthesis parameters (pacing speech rate, vocal pitch, and physical volume) using bounded non-linear activation functions:

### 7.1 Speech Rate (Pacing) Modulation

The speech pacing rate factor ($R_{\text{pace}} \in [0.5, 2.0]$) is modulated by emotional arousal (positive scaling), valence (negative scaling for slow, sad vocalization), and fatigue-driven pace-dampening:

```math
R_{\text{pace}} = 1.0 + \tanh(0.20 \cdot Ar - 0.10 \cdot V - 0.15 \cdot F)
```

### 7.2 Vocal Pitch (F0) Modulation

The fundamental frequency scale factor ($P_{\text{vocal}} \in [0.5, 2.0]$) is pulled dynamically by valence and arousal (positive pitch shifts), dominance (defensive low-frequency pitch drops), metabolic fatigue, and volumetric distance:

```math
P_{\text{vocal}} = 1.0 + \tanh(0.05 \cdot V + 0.15 \cdot Ar - 0.10 \cdot D - 0.05 \cdot F + \text{dist-pitch-mod})
```

where:
*   $\text{dist-pitch-mod} = \text{clamp}(0.05 \cdot (\text{distance} - 1.0), -0.10, 0.10)$

### 7.3 Vocal Volume Modulation

Vocal intensity ($V_{\text{vocal}} \in [0.1, 1.5]$) maps from dominance (confident louder speech) adjusted by inverse-square physical distance compensation:

```math
V_{\text{vocal}} = 0.40 + 0.60 \cdot D + \text{dist-vol-mod}
```

where $\text{dist-vol-mod} = \text{clamp}(0.15 \cdot (\text{distance} - 1.0), -0.20, 0.30)$.

---

## 8. Solid State Reflection & Memory Consolidation Pipeline

To achieve continuous learning without real-time latency, CVS-3.0 offloads episodic and semantic synthesis to a decoupled background consolidation thread.

```
       [Raw Dialog Events]
                |
     (Reflection Interval Gate)
                |
                v
      [Reflection Service]
     /          |         \
[Fact Resolution] [Persona Evolution] [Episodic Consolidation]
 (Neo4j Graph)     (Identity Core)        (pg_vector)
```

### 8.1 Background Gating & Control

Reflection is gated by standard system parameters. A minimum interval is enforced to prevent execution overlap:

```math
\Delta t_{\text{reflection}} \ge \text{REFLECTION-MIN-INTERVAL-SECONDS}
```

### 8.2 Fact Extraction & Graph Resolution

During consolidation, the LLM processes dialogue summaries to extract semantic triplets:

```math
\mathcal{T} = \{ (s, r, o) \mid s \in \text{Entities}, \, r \in \text{Relations}, \, o \in \text{Entities} \}
```

*   **Confidence Gating:** Triplets are discarded if extraction confidence falls below the reliability threshold:

```math
\text{Confidence}(T_k) < \theta_{\text{confidence}} = 0.8
```

*   **Graph Deduplication:** Triplet elements are sanitized. The system queries Neo4j to verify relationship uniqueness. If the triplet is a duplicate, the insertion is bypassed:

```math
(s \xrightarrow{r} o) \in \mathcal{G}_{\text{graph}} \implies \text{Bypass Insertion}
```

### 8.3 Persona Evolution

The agent's active social role and core personality traits are evaluated for potential growth based on recent interactions. Modifications are executed if the confidence of the proposed identity trajectory meets the gating criteria:

```math
\text{Confidence}(\text{Evolution}) \ge 0.8 \implies \text{evolve-persona}()
```

### 8.4 Episodic Memory Consolidation

Dialogue sequences are synthesized into a single narrative summary representing the agent's memory of the interaction.

*   **Composite Affective Compression:** The emotional attributes ($V, Ar, D$) of individual dialogue turns are compressed into composite coordinates:

```math
\bar{V} = \frac{1}{K}\sum_{k=1}^K V_k, \quad \bar{Ar} = \frac{1}{K}\sum_{k=1}^K Ar_k, \quad \bar{D} = \frac{1}{K}\sum_{k=1}^K D_k
```

*   **Vector Persistence:** The narrative text is embedded and persisted into `pg_vector` with a consolidated importance score of $0.6$ and associated with the computed composite PAD coordinates.

### 8.5 ACT-R Decay & Pruning

Over time, stored memories experience passive decay and structural pruning.

*   **Activation Decay Evaluation:** On decay intervals, the sub-symbolic base activation is re-evaluated using decay constant $d = 0.5$:

```math
A_i = \ln(n) - d \cdot \ln(t + 1.0)
```

where $t$ is the hours since creation, and $n$ is the historical recall frequency.

*   **Pruning Gating:** Memories are permanently pruned if their base activation drops below the decay threshold:

```math
A_i < \theta_{\text{prune}} = -3.5 \implies \text{Delete Memory } i
```

*   **Importance Score Decay:** Surviving memories have their importance score decayed by a factor of $0.8$ to represent natural cognitive decay:

```math
\text{Importance}_i(t) = \max(0.01, \text{Importance}_i(t-1) \cdot 0.8)
```

---

## 9. Algorithmic Implementations

### 9.1 ACT-R Memory Retrieval Engine

The memory retrieval routine combines semantic graph queries with sub-symbolic cognitive gating and neuromodulatory factors:

```python
def retrieve_episodic_memory(context_query, active_pad_vector, neo4j_driver):
    """
    Algorithm 1: ACT-R Graph Memory Search with Endocrine-Affective Congruency Gating
    """
    # Step 1: Generate vector embeddings for the query
    dense_vector = generate_dense_embeddings(context_query)

    # Step 2: Execute structural graph search in Neo4j
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

### 9.2 Speculative Turn-Taking Gating Loop

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

### 9.3 Hardened Speculative Barge-in Conflict Resolver

Distinguishes between genuine agent commands and conversational agreement or noise in early transcripts:

```python
def is_speculative_stop_confirmed(backbone_text: str, perception_keywords: list[str] = None) -> bool:
    """
    Algorithm 3: System 2 Speculative Interruption Gating and Conflict Resolver
    """
    if not backbone_text:
        return False

    if perception_keywords is None:
        perception_keywords = ["stop", "wait", "hold", "listen", "sunno", "ruko", "quiet"]

    clean_text = backbone_text.lower().strip()
    words = [w.strip("!.,?;:") for w in clean_text.split()]

    conversational_connectors = [
        "i agree", "i think", "i actually", "i just", "i am",
        "but", "though", "it is", "raining", "singing", "working",
        "playing", "for", "to", "be"
    ]
    call_signs = ["hey", "friend", "listen"]

    for kw in perception_keywords:
        kw = kw.lower()
        if kw in words:
            idx = words.index(kw)

            # Lookahead check for conversational connectors following keyword
            if idx + 1 < len(words):
                next_words = " ".join(words[idx + 1 : idx + 3])
                if any(conn in next_words for conn in conversational_connectors):
                    continue

            # Check if keyword acts as a conversational pivot
            is_pivot = (idx == 0) or all(words[w] in call_signs for w in range(idx))

            if not is_pivot:
                continue

            # Confirm concisely structured stop commands or starting pivots
            if len(words) <= 4 or idx == 0:
                return True

    return False
```

### 9.4 Decoupled Background Learning and Consolidation

Processes recent events to extract facts, update the persona, and consolidate memories:

```python
async def _consolidate(self, episodes: list[dict]):
    """
    Algorithm 4: Background Solid State Fact Resolution, Persona Evolution & Memory Consolidation
    """
    self.is_reflecting = True
    try:
        # Build composite transcript block
        summary_text = "\n---\n".join([
            f"Context: {e.get('context','')}\nUser: {e.get('content','')}\nAI: {e.get('response','')}"
            for e in episodes
        ])

        # Step 1: Extract and Gate Facts
        fact_res = await self.llm.generate(fact_prompt, model=Config.LLM_REFLECTION_MODEL)
        facts = extract_json_list(fact_res)
        for f in facts:
            if f.get("confidence", 0.0) >= 0.8:
                subject = f.get("subject")
                object_val = f.get("object")
                relation = GraphDB.safe_relation(f.get("relation"))

                # Check for existing duplication in GraphDB
                exists = await self.graph.execute_query(
                    "MATCH (s)-[r]->(t) WHERE s.name=$s AND t.name=$t RETURN r",
                    {"s": subject, "t": object_val}
                )
                if not exists:
                    await self.graph.create_triplet(subject, relation, object_val, properties={"confidence": f.get("confidence")})

        # Step 2: Persona Evolution Gate
        identity_res = await self.llm.generate(identity_prompt, model=Config.LLM_REFLECTION_MODEL)
        suggestions = extract_json_dict(identity_res)
        if suggestions.get("confidence", 0.0) >= 0.8:
            await self.identity.evolve_persona(suggestions)

        # Step 3: Episodic Memory Consolidation
        avg_valence = sum(e.get("V", 0.0) for e in episodes) / len(episodes)
        avg_arousal = sum(e.get("Ar", 0.5) for e in episodes) / len(episodes)

        consolidation_res = await self.llm.generate(consolidation_prompt, model=Config.LLM_REFLECTION_MODEL)
        consolidated_summary = clean_think_tags(consolidation_res)

        if consolidated_summary and self.vector:
            await self.vector.add_memory(
                content=consolidated_summary,
                raw_content=summary_text,
                wing="personal",
                importance=0.6,
                emotion=avg_arousal,
                valence=avg_valence,
                source="subconscious_consolidation"
            )
    finally:
        self.is_reflecting = False
        self.reflection_done.set()
```
