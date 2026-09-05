# 🧮 Mathematical Formulations & Algorithmic Specifications

This document compiles the core mathematical formulations, system equations, and procedural algorithms driving the cognitive and sensory layers of **AI Friend (Cognitive Vocal System)**. It serves as a rigorous, publication-ready asset for the **Mathematical Methodology** and **Algorithmic Architecture** sections of academic publications.

---

## 1. System 1 & System 2 Cognitive Appraisal

The Cognitive Vocal System (CVS) implements a dual-process appraisal model rooted in **Lazarus' Cognitive-Mediational Theory (1991)**, the **OCC Model (Ortony, Clore, & Collins, 1988)**, and the **EMA computational architecture (Gratch & Marsella, 2004)**. For every conversational, internal, or sensory event, the system computes a 6-variable appraisal vector.

### 1.1 Primary Appraisal (Lazarus)

Primary appraisal evaluates the immediate significance of an event for the agent's active goals and well-being:

*   **Relevance ($R \in [0, 1]$):** Quantifies the attention weight of the incoming event. User-initiated dialogue events are treated as high relevance, while autonomous internal ticks are low relevance:

```math
R = \begin{cases}
  1.0 & \text{if event is } \texttt{USER-MESSAGE} \\
  0.1 & \text{if event is } \texttt{SYSTEM-TICK} \\
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

where $\mathcal{W}$ denotes the set of lowercase keywords extracted from the active utterance (event) or a historical turn $h$.

*   **Goal Congruence ($G \in [-1, 1]$):** Represents how much the event advances or hinders the agent's core social goal. It maps directly from the emotional bias $E_b$ (extracted via acoustic pitch/sentiment trackers):

```math
G = \text{clamp}(E_b, -1.0, 1.0)
```

### 1.2 Secondary Appraisal (Lazarus/OCC/EMA)

Secondary appraisal evaluates the agent's coping potential, social norms, and relational impact.

*   **Agency ($A \in [0, 1]$):** Attributes causal responsibility. For user messages, the agent holds high coping agency since it can generate a verbal response; for system ticks, agency is lower:

```math
A = \begin{cases}
  0.8 & \text{if event is } \texttt{USER-MESSAGE} \\
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

For deep semantic reasoning, AI Friend runs an asynchronous deliberative reappraisal cycle. It queries the fast LLM to grade three dimensions on $[-1.0, 1.0]$: goal congruence ($gc$), norm alignment ($na$), and expectedness ($exp$). These values act as coordinates pulling the active 3D PAD emotional state via a drift coefficient $\eta = 0.2$:

```math
\vec{T}_{\text{PAD}} = \begin{bmatrix} gc \\ -exp \\ na \end{bmatrix}
```

```math
\vec{PAD}(t) = \vec{PAD}(t-1) + \eta \cdot (\vec{T}_{\text{PAD}} - \vec{PAD}(t-1))
```

The resulting coordinates are clamped to ensure psychological boundaries: Valence $V \in [-1.0, 1.0]$, Arousal $Ar \in [0.0, 1.0]$, and Dominance $D \in [0.0, 1.0]$.

---

## 2. Continuous Internal State & Endocrine Dynamics

AI Friend maintains cognitive continuity through a multi-dimensional state vector updating on every appraisal trigger and evolving continuously during idle ticks.

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

*   **Fatigue Cycle ($F \in [0, 1]$):** Metabolic wear-and-tear accumulated during active turns and recovered during idle intervals. Governed by a circadian multiplier (set to $1.8$ at night 22:00–06:00, otherwise $1.0$):

```math
F(t) = \begin{cases}
  \text{clamp}\left(F(t-1) + \frac{0.15 \cdot \Delta t \cdot \mu_{\text{circadian}}}{3600}, 0.0, 1.0\right) & \text{if active interaction} \\
  \text{clamp}\left(F(t-1) - \frac{0.20 \cdot \Delta t}{\mu_{\text{circadian}} \cdot 3600}, 0.0, 1.0\right) & \text{if idle/resting}
\end{cases}
```

where $\Delta t$ is the elapsed time in seconds.

*   **Cortisol Coupling ($C \in [0, 1]$):** Represents stress levels. **Corrected 2026-09-01** — this used to be documented as a single tonic term; the shipped implementation (`backend/app/state/agent_state.py`) is tonic **plus a decaying phasic burst**, and the two are deliberately not equivalent. Tonic cortisol is a pure function of current affect and forgets the instant valence recovers:

```math
C_{\text{tonic}}(t) = \text{clamp}\left(0.5 - \frac{V(t)}{2.0} + 0.3 \cdot F(t), 0.0, 1.0\right)
```

A `release_cortisol(amount)` call (fired on an acute stressor) adds a phasic burst on top, stored **relative to the tonic floor** at release time and decaying exponentially toward zero with half-life $\tau_C$ — CONSTITUTIONAL, a persona temperament dial, not a deployment setting, defaulting to 4500s (75 minutes, the midpoint of measured human cortisol plasma half-life; raised from an earlier 600s default that was 6-9x faster than that reference point — Bucket 11, voice remediation Phase 3):

```math
C_{\text{phasic}}(t) = C_{\text{peak}} \cdot 2^{-\frac{t - t_{\text{release}}}{\tau_C}}, \qquad C(t) = \text{clamp}(C_{\text{tonic}}(t) + C_{\text{phasic}}(t), 0.0, 1.0)
```

*Hyperparameter mapping:* High cortisol reduces LLM generation temperature to enforce strict, defensive responses; low cortisol increases temperature to support warm, creative responses.

*   **Dopamine Coupling ($D \in [0, 1]$):** Represents reward tracking. **Corrected 2026-09-01**, same reason as cortisol above — tonic tracks current affect only, mapped from positive valence ($V > 0$) combined with fatigue-modulated actual arousal:

```math
Ar_{\text{actual}}(t) = \text{clamp}(Ar(t) + 0.2 \cdot F(t), 0.0, 1.0)
```

```math
D_{\text{tonic}}(t) = \text{clamp}(\max(0.0, V(t)) \cdot Ar_{\text{actual}}(t), 0.0, 1.0)
```

A `release_dopamine(amount)` call (fired on a reward event) adds a phasic burst, stored relative to the tonic floor and decaying with half-life $\tau_D = 90\text{s}$ (markedly shorter than cortisol's — a fright lingers, a reward mostly does not):

```math
D_{\text{phasic}}(t) = D_{\text{peak}} \cdot 2^{-\frac{t - t_{\text{release}}}{\tau_D}}, \qquad D(t) = \text{clamp}(D_{\text{tonic}}(t) + D_{\text{phasic}}(t), 0.0, 1.0)
```

*Hyperparameter mapping:* High dopamine increases LLM `top_p` to enable playful and exploratory phrasing.

**Why this split matters, not just how it works:** $C_{\text{tonic}}$ and $D_{\text{tonic}}$ are both pure functions of valence and are therefore perfectly anti-correlated by construction — one rises exactly as the other falls. Only the phasic channels let the agent register being stressed and rewarded *at the same time*, a combination the tonic-only model above could never represent. Phasic bursts are deliberately **not persisted** across a restart — a deliberate session-reset rule, not a claim that the burst is always negligible by then: dopamine's 90s half-life makes a stale value genuinely meaningless within minutes, but cortisol's half-life is now 4500s (75 minutes, corrected from an earlier 600s — see above), so a burst can still be materially non-zero across a restart that happens to land within that window. The reset is accepted anyway, as a deliberate choice to let stress state start clean on restart, even though the discarded value may still have been meaningful.

### 2.4 Idle State Decay (ALMA Decay)

During prolonged silence, internal mood converges back to the neutral baseline through exponential decay with decay coefficient $\lambda = 0.05$ per hour:

```math
V(t) = V(0) \cdot e^{-\lambda_{\text{decay}} \cdot \Delta t}
```

where $\Delta t$ is the silence duration in hours. Dominance remains stable as it behaves as a personality trait, while relational trust experiences a very slow drift ($0.01 \text{ hr}^{-1}$) back to the baseline of $0.5$.

---

## 3. Behavior Tree Routing & Action Planning

To structure execution flow and cognitive priorities, AI Friend adopts a modular **Behavior Tree (BT)** framework. This separates high-level intention selection from low-level mechanical action execution.

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

To prevent erratic goal switching during rapid dialogue turns, we implement temporal smoothing with a persistence rate $\rho = 0.15$ coupled with a hard context gating threshold $\theta = 0.3$ (using Novelty $N$ as the shift proxy):

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

*   **Effective Similarity:** Blends vector cosine similarity with hormone levels (cortisol stress dampening) and emotional valence:

```math
\text{Similarity}_{\text{eff}} = \text{Similarity} \cdot (1.0 + 0.1 \cdot V_{\text{memory}} \cdot Ar_{\text{memory}} - 0.2 \cdot Ar_{\text{agent}} \cdot C_{\text{cortisol}})
```

### 5.2 Attentional Spreading & Direct Cue Boost

AI Friend extends standard ACT-R with dynamic, real-time associative spreading activation. **Corrected 2026-09-01** — this section previously listed a fixed example cue vocabulary (*Kolkata*, *Bangalore*, *Priya*, *Rasgulla*, ...) and a flat +0.6 propagation constant. Neither matches the shipped implementation (`backend/app/state/memory_store.py`): cues are the agent's own **learned mental lexicon** (`lexicon_store.py`), built from its actual conversation history, not a hardcoded example list — production personas are authored per-deployment with no shared vocabulary, so a fixed example set would not even apply across two installs. The generic-English seed in `lexicon_seed.py` runs once at DB seeding only, never on this hot path.

*   **Direct Cue Boost:** If a cue from the agent's learned lexicon matches a term in the query text, matching memories receive an instantaneous boost of `DIRECT_CUE_BOOST = 5.0` per matched cue (deliberately large relative to ACT-R's own activation scale, so a literal cue match dominates the ranking):

```math
Score_i \leftarrow Score_i + 5.0 \cdot n_{\text{matched cues}}
```

*   **Spreading Activation:** Not a flat additive constant to directly-connected nodes. Candidates are boosted by a **HippoRAG-inspired, degree-scaled Personalized PageRank (PPR)** pass: cue-matched memories' entities seed a 3-iteration power-method PPR over the candidate entity graph (teleport factor `PPR_DAMPING`), and each non-directly-boosted candidate receives a boost proportional to its seeded entities' PPR mass, discounted by node degree (a high-degree "hub" entity contributes less per mention than a rare, specific one):

```math
Score_j \leftarrow Score_j + \sum_{e \in \text{entities}(j)} \frac{1.2 \cdot \text{PPR}(e)}{1 + \ln(\max(1, \deg(e)))}
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

AI Friend manages low-latency, natural voice turn-taking through a dual-loop System 1 DSP hardware hook and System 2 semantic conflict resolver.

### 6.1 System 1 DSP Audio Energy Detection

A continuous audio frame stream is processed inside a microsecond-level loop. We compute the Root-Mean-Square (RMS) energy of the incoming audio frame of size $N$:

```math
\text{RMS} = \sqrt{\frac{1}{N} \sum_{k=1}^N x[k]^2}
```

If RMS exceeds the noise floor by a fixed factor (`speech_factor = 3.0`, adaptive per session), a candidate speech onset is flagged. **Corrected 2026-09-01** — RMS crossing this threshold does not itself halt playback; there is no hardware-level, microsecond-latency stop path. What actually happens: `Endpointer` (Rust, `stt-agent`) is a real-time pre-filter that gates when Whisper transcription runs, not a playback switch. Only a *confirmed* stop — one that has passed through Whisper transcription and §6.2's semantic resolver below — triggers a halt, and the halt itself is a track-rotation flush in `transport_agent` (unpublish the current LiveKit audio track, publish a fresh one) rather than an instantaneous DSP mute; `rtc.AudioSource.capture_frame()` exposes no way to drain audio already handed to the client's native playout buffer, so recreating the published track is what routes around that gap. This mechanism (`transport_agent._on_audio_stop` / `_flush_downstream_audio`) predates this document's most recent revision (shipped 2026-08-23) and is now additionally gated correctly: earlier, a non-speculative `chat.input` published this stop unconditionally on every turn, bypassing §6.2's resolver entirely; it is now routed through the resolver first (fixed 2026-09-01, see `.agents/CONTEXT.md`), so an utterance the resolver would reject no longer cuts playback before the resolver ever runs. End-to-end wall-clock latency for this full path (RMS flag → transcription → resolver → track rotation → client-observed silence) has **not been measured** against live infrastructure; do not treat this section's presence as a latency claim.

### 6.2 System 2 Speculative Conflict Resolution

To distinguish a genuine user turn from background room acoustics or conversational agreements (e.g., "I agree" or "Hmm"), a speculative System 2 background segmenter evaluates the early verbal transcript.

A candidate interruption is matched against conversational keywords (e.g. *stop*, *wait*, *hold*, *listen*, *sunno*, *ruko*, *quiet*).
1.  **Connector Rejection:** If a conversational connector (e.g., *i agree*, *i think*, *i actually*, *but*, *though*, *to*, *be*) immediately follows the keyword, the stop is rejected.
2.  **Pivot Alignment:** The keyword must act as a turn pivot, occurring at the start (`idx == 0`) or following call signs (`hey`, `friend`). Buried keywords are rejected.
3.  **Conciseness Confirmation:** The interruption is confirmed if the length of the early transcript is short ($\le 4$ words) or the keyword is the absolute starting word.

If these filters fail, an `audio.resume` signal is published and playback continues uninterrupted. **Corrected 2026-09-01**: earlier text described this as a graceful crossfade-based unmute — no crossfade is involved on the rejection path, and §6.4 below explains why the crossfade mechanism this once referred to no longer exists at all.

### 6.3 Interruption Coherence Index ($ICI$)

The efficiency of turn-taking and physical stopping response speed is evaluated via the Interruption Coherence Index:

```math
\text{ICI} = \gamma \cdot \left(1 - P_{\text{false-trigger}}\right) \cdot \exp\left(-\frac{\left|t_{\text{stop}} - t_{\text{interject}}\right|}{\tau_{\text{overlap}}}\right)
```

*   $\gamma \in [0, 1]$: Cosine similarity between user interjection embeddings and active agent goal intents.
*   $P$: Probability of false-triggering due to background acoustics.
*   $t$ (stop − interject): Turn response gap (in milliseconds) between when the user physically started speaking and when the TTS stopped.
*   $\tau = 200.0$ ms: Human turn-taking overlap baseline constant.

*Status note (2026-09-01):* $ICI$ as defined here is aspirational — nothing in the codebase currently computes it at runtime, and $\tau$ is not wired to any live measurement. This is not a wrong claim, just an unbuilt one; it is named here so a future implementer has the target formula rather than needing to re-derive it.

### 6.4 Acoustic Chunk Boundaries (Crossfade Removed)

**Corrected 2026-09-01** — this section previously described a 10ms linear Overlap-Add (OLA) crossfade blended between consecutive prosody-shifted synthesis buffers. That mechanism was removed (Bucket 2, see `.agents/CONTEXT.md`'s 2026-09-01 entries), not merely retuned: audit showed it was blending the last 15ms of the *already-published, already-playing* previous chunk into the head of the next, which is not overlap-add (true OLA overlaps two buffers analyzed together **before** either is sent downstream) — it made the listener hear those 15ms twice, at a phase discontinuity, reported live as a "hazy"/muddy artifact. Correctly implementing true OLA would need holding back every chunk's tail until the next chunk arrives, adding one full chunk of latency to an already latency-critical path (see §8/Bucket 8's dual-loop discussion) for a benefit only relevant at chunk boundaries where prosody shifts sharply between clauses — chunking is now clause-aligned (§10.2, Bucket 5), which already reduces how often that boundary occurs. The engineering call was that a clean butt-join is strictly better than replaying already-heard audio, so the crossfade was deleted rather than reimplemented. What remains at this seam (`PcmSampleFramer` in `backend/crates/voice-agent/src/main.rs`) is exactly the part that was never about prosody: buffering a single dangling odd byte across chunk boundaries so a 16-bit PCM sample is never split across two network chunks.

---

## 7. Voice Prosody & Acoustic Parameter Mapping (APRA v2)

To express continuous cognitive and endocrine states paralinguistically, AI Friend upgrades the voice modulation to a dynamic continuous frame-wise trajectory model (**APRA v2**). Instead of static sentence-level values, the internal Pleasure-Arousal-Dominance (PAD) affect values, fatigue metrics, and physical distance variables are mapped into continuous, time-varying functions representing acoustic prosody trajectory parameters (pacing speech rate, vocal pitch, and volume) across 50ms interval frames:

### 7.1 Speech Rate (Pacing) Trajectory Modulation

The continuous speech pacing rate factor ($R(t) \in [0.60, 1.80]$) is modulated by emotional arousal (positive scaling), valence (negative scaling), metabolic fatigue, and a dynamic pacing breathing curve factor $B(t)$ simulating natural breathing pauses near endpoints:

```math
R(t) = \text{clamp}(1.0 + 0.20 \cdot Ar - 0.10 \cdot V - 0.25 \cdot F + B(t), 0.60, 1.80)
```

where the dynamic breathing dampening $B(t)$ is defined as:

```math
B(t) = \begin{cases}
-0.15 \cdot \left(1.0 - \frac{t}{200}\right), & \text{if } t < 200 \text{ ms} \\
0.0, & \text{if } 200 \le t \le 2700 \text{ ms} \\
-0.15 \cdot \left(\frac{t - 2700}{300}\right), & \text{if } t > 2700 \text{ ms}
\end{cases}
```

### 7.2 Vocal Pitch (F0) Trajectory Modulation

The continuous fundamental frequency scale trajectory ($P(t) \in [0.50, 2.00]$) is pulled dynamically by valence and arousal (positive pitch shifts), dominance (defensive low-frequency pitch drops), metabolic fatigue, physical distance, and an organic 6Hz sinusoidal human vocal cord vibrato ripple $\nu(t)$:

```math
P(t) = \text{clamp}(1.0 + 0.05 \cdot V + 0.15 \cdot Ar - 0.10 \cdot D - 0.10 \cdot F + \text{dist-pitch-mod} + \nu(t), 0.50, 2.00)
```

where the vocal vibrato ripple $\nu(t)$ is modeled at 6Hz as:

```math
\nu(t) = 0.02 \cdot \sin\left(2\pi \cdot 6.0 \cdot \frac{t}{1000}\right)
```

and the distance modifier is defined as:
*   $\text{dist-pitch-mod} = \text{clamp}(0.05 \cdot (\text{distance} - 1.0), -0.10, 0.10)$

### 7.3 Vocal Volume Trajectory Modulation

Vocal intensity trajectory ($V(t) \in [0.10, 1.00]$) is mapped from dominance adjusted by distance compensation and a smooth volumetric envelope $E(t)$ at the utterance boundaries:

```math
V(t) = \text{clamp}\left((0.40 + 0.60 \cdot D + \text{dist-vol-mod}) \cdot E(t), 0.10, 1.00\right)
```

where $\text{dist-vol-mod} = \text{clamp}(0.15 \cdot (\text{distance} - 1.0), -0.20, 0.30)$, and the boundary volumetric envelope $E(t)$ is defined as:

```math
E(t) = \begin{cases}
\frac{t}{150}, & \text{if } t < 150 \text{ ms} \\
1.0, & \text{if } 150 \le t \le 2850 \text{ ms} \\
\frac{3000 - t}{150}, & \text{if } t > 2850 \text{ ms}
\end{cases}
```

---

## 8. Solid State Reflection & Memory Consolidation Pipeline

To achieve continuous learning without real-time latency, AI Friend offloads episodic and semantic synthesis to a decoupled background consolidation thread.

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

**Corrected 2026-09-01** — the pseudocode below previously modeled an immediate, microsecond-level physical mute triggered directly off RMS energy, with a crossfaded unmute on a false trigger. Neither exists: RMS crossing the noise floor (`Endpointer`, `speech_factor = 3.0`) gates *transcription*, not playback, and the actual halt/resume path runs through real STT + the semantic resolver (§9.3) before anything happens to the audio track — see §6.1's correction for the full reasoning. The crossfade referenced on the false-trigger path was removed entirely (§6.4). This version reflects the actual multi-stage pipeline, in its real message-passing shape rather than as a single tight loop with a hardware hook:

```python
async def barge_in_gating_loop(audio_stream, endpointer, transcriber, resolver, mesh):
    """
    Algorithm 2: Dual-Loop System 1 / System 2 Speculative Turn Interruption

    System 1 (Endpointer, Rust) is an RMS-relative-to-noise-floor pre-filter
    that decides when enough speech has accumulated to hand off to Whisper --
    it never touches playback directly. Only a transcript that survives
    System 2's semantic resolver (is_speculative_stop_confirmed, §9.3)
    produces a confirmed stop; transport_agent then rotates the published
    LiveKit track to flush audio already handed to the client's native
    playout buffer, since capture_frame() exposes no way to drain it directly.
    """
    async for frame in audio_stream:
        # System 1: adaptive-noise-floor pre-filter, not a playback switch.
        if not endpointer.is_speech(frame):
            continue

        # Endpointing accumulates frames until Whisper has enough audio for
        # a final transcript -- real transcription latency, not microseconds.
        transcript = await transcriber.transcribe_when_endpointed(frame)
        if transcript is None:
            continue

        if resolver.is_speculative_stop_confirmed(transcript.text, transcript.keywords):
            # Confirmed: publish audio.stop, transport_agent flushes via
            # track rotation (see _flush_downstream_audio).
            await mesh.publish("audio.stop", {"turn_id": transcript.turn_id})
            break
        else:
            # Rejected: playback was never touched, so there is nothing to
            # restore -- just tell the mesh the ducking is over.
            await mesh.publish("audio.resume", {"turn_id": transcript.turn_id})
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

### 9.5 Multi-Attribute Utility Theory (MAUT) Decision Engine & Intent Persistence

The decision system scores each social goal dynamically and applies temporal intent persistence with a context gating threshold to prevent goal-switching:

```python
def _score_goals_maut(self, appraisal: Dict[str, float], state: Dict[str, Any]) -> str:
    """
    Algorithm 5: Multi-Attribute Utility Theory (MAUT) Goal Scoring and Intent Persistence
    """
    V = state.get("mood", 0.0)
    Ar = state.get("energy", 0.5)
    T = state.get("trust", 0.5)
    R = appraisal.get("relevance", 0.5)
    G = appraisal.get("goal_congruence", 0.0)
    N = appraisal.get("novelty", 0.3)
    NA = appraisal.get("norm_alignment", 1.0)

    scores = {}

    # ENGAGE: Best for neutral/positive states, high energy, novel topics
    scores["ENGAGE"] = (
        self.w_goal * max(0, G + 0.5)
        + self.w_emotion * (0.5 + V * 0.3 + Ar * 0.2)
        + self.w_identity * NA
        + self.w_context * R
    )

    # COMFORT: Best when user seems distressed — favored at low arousal (calm tone)
    scores["COMFORT"] = (
        self.w_goal * max(0, -G + 0.5)
        + self.w_emotion * max(0, -V + 0.5) * (1.2 - Ar * 0.4)
        + self.w_identity * NA
        + self.w_context * R * 0.8
    )

    # INFORM: Best for high relevance, novel content — arousal-neutral
    scores["INFORM"] = (
        self.w_goal * max(0, G * 0.5 + 0.3)
        + self.w_emotion * (0.4 + Ar * 0.2)
        + self.w_identity * NA
        + self.w_context * R * N
    )

    # TEASE: Only when trust is high, mood positive, and energy high
    scores["TEASE"] = (
        self.w_goal * max(0, G * 0.3)
        + self.w_emotion * max(0, V * 0.3 + Ar * 0.2)
        + self.w_identity * NA * T
        + self.w_context * (1 - R) * 0.3
    )

    # PROTECT: When norm alignment is low — arousal-neutral (boundary enforcement)
    scores["PROTECT"] = (
        self.w_goal * 0.2
        + self.w_emotion * (0.2 + Ar * 0.1)
        + self.w_identity * max(0, 1.0 - NA)
        + self.w_context * R * 0.5
    )

    # Apply temporal smoothing for goal stability
    new_goal = max(scores, key=scores.get)
    context_shift = N

    if self._previous_goal is not None and context_shift < self.shift_threshold:
        rho = self.persistence_rate
        for g in GOALS:
            prev_score = self._goal_scores.get(g, 0.0)
            scores[g] = (1 - rho) * prev_score + rho * scores[g]
        new_goal = max(scores, key=scores.get)

    self._previous_goal = new_goal
    self._goal_scores = scores
    return new_goal
```

### 9.6 Adaptive Emotion Regulation and Reappraisal Engine (Gross-Bosse Model)

This engine evaluates the outcome of each conversation turn and adapts appraisal weights in the background:

```python
async def evaluate_outcome(
    self,
    actual_text_valence: float,
    acoustic_delta: float = 0.0,
    behavioral_signal: float = 0.5,
):
    """
    Algorithm 6: Adaptive Reappraisal Weight Adaptation and Emotional Regulation
    """
    if not self.enabled:
        return

    if self._expected_valence is None or self._pre_response_state is None:
        return

    # Multi-signal outcome computation
    actual_outcome = (
        0.5 * actual_text_valence + 0.3 * acoustic_delta + 0.2 * behavioral_signal
    )

    # Prediction error
    delta = self._expected_valence - actual_outcome

    # Only adapt on significant mismatches
    if abs(delta) < 0.1:
        self._reset_turn_state()
        return

    # Confidence weighting based on intensity of actual valence
    confidence = min(1.0, abs(actual_text_valence) + 0.3)
    effective_lr = self.learning_rate * confidence

    # Update valence-related appraisal weights
    self.appraisal_weights["w1_g_to_v"] = self._clamp(
        self.appraisal_weights["w1_g_to_v"] - effective_lr * delta
    )
    self.appraisal_weights["w2_ri_to_v"] = self._clamp(
        self.appraisal_weights["w2_ri_to_v"] - effective_lr * delta * 0.5
    )

    self._reset_turn_state()
```

### 9.7 Continuous PAD-to-Prosody Speech Synthesis Coordinator

Coordinates speech synthesis parameter ranges dynamically mapped from continuous affective and metabolic fatigue states:

```python
def map_affect_to_prosody(self, state_snap: Dict[str, Any]) -> Dict[str, float]:
    """
    Algorithm 7: Continuous PAD-to-Prosody Speech Pacing, Intensity, and Pause Mapping
    """
    V = state_snap.get("valence", state_snap.get("mood", 0.0))
    Ar = state_snap.get("arousal", state_snap.get("energy", 0.5))
    F = state_snap.get("fatigue", 0.0)

    # Continuous speech pacing rate modulation
    speaking_rate = max(0.6, min(1.8, 1.0 + (0.20 * Ar) - (0.10 * V) - (0.25 * F)))
    confidence = 0.9

    # Emotional intensity scaling
    intensity = abs(V) * Ar

    # Speaking pause bias modulation
    pause_bias = max(0.0, min(1.0, 1.0 - Ar))

    return {
        "speaking_rate": round(speaking_rate, 3),
        "intensity": round(intensity, 3),
        "pause_bias": round(pause_bias, 3),
        "confidence": confidence,
    }
```

### 9.8 Goldman-Eisler Semantic Speech Chunking Segmenter

Uses punctuation cues, linguistic juncture markers, and target size boundaries to divide generated speech streams into natural, expressive chunks:

```python
def score_split_point(self, word: str, chunk_len: int) -> float:
    """
    Algorithm 8: Goldman-Eisler Semantic Speech Segmentation Engine
    """
    score = 0.0

    # Punctuation is the strongest speech boundary cue
    if word:
        if "." in word or "?" in word or "!" in word:
            score += 0.8
        elif "," in word or ":" in word or ";" in word:
            score += 0.4

    # Length-based chunk pressure
    if chunk_len >= self.target_size:
        score += 0.3

    # Hard boundary limit override
    if chunk_len > 12:
        score = 1.0

    return score
```
