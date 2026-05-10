# 📄 CVS Psychological Layer — Equation Sheet (V2.1)

> This document defines the mathematical model behind CVS-1.0's cognitive-emotional system.
> Every equation is annotated with its **source** — whether it's an established formula from
> a published model or an engineering adaptation we designed for this system.
>
> **Related**: See [analysis_results.md](./analysis_results.md) for the gap analysis that motivated this design.

## 2026-04-20 Implementation Status Note

This equation sheet is still the target-state design for future work.

Recent runtime changes improved reliability and throughput behavior, but did not replace this
planned psychological layer:

- Live-only subscriptions, surfacing sweep guards, and bootstrap hardening improved operational stability.
- CI startup reliability for NATS/JetStream was hardened.
- Optional runtime controls were added to reduce background LLM pressure.

Still pending from this equation sheet:

- Full appraisal pass (`R, N, G, A, NA, RI`) as a first-class step in the cognitive loop.
- Explicit PAD + relational state propagation as a structured affect side-channel to voice prosody.
- Narrative episodic memory structure and retrieval beyond flat vector surfacing.

---

## 🎯 System Principle

```
Signal → Appraisal → State → Intent → Expression → Reappraisal → Memory
         ↑                                                         │
         └─────────────────────────────────────────────────────────┘
```

This system is a **closed-loop cognitive model**, not a linear pipeline.
Every response outcome feeds back into the next appraisal cycle.

> **Source**: The closed-loop structure follows **EMA** (Marsella & Gratch, 2009) — where coping
> outcomes re-trigger appraisal, creating continuous emotion dynamics rather than one-shot labeling.

---

## 🧠 1. Appraisal System — Core Cognitive Engine

### Model Basis

The appraisal system follows the **OCC model** (Ortony, Clore & Collins, 1988) for emotion
categorization, combined with **Lazarus's** (1991) primary/secondary appraisal distinction,
as implemented computationally in **EMA** (Gratch & Marsella, 2004) and **FAtiMA** (Dias & Paiva).

> **Key insight from EMA**: Appraisal is not a separate module — it is derived from the agent's
> beliefs, desires, and intentions (BDI). Emotion is a *byproduct* of the agent interpreting
> its environment, not a lookup table.

### 1.1 Primary Appraisal

Evaluates the event's raw significance. Variables adapted from OCC/Lazarus:

| Variable | Definition | OCC/Lazarus Equivalent | Our Implementation |
|----------|-----------|----------------------|-------------------|
| **R** | Relevance | Goal relevance (Lazarus) | `cosine_similarity(event_embedding, goal_embeddings)` |
| **N** | Novelty | Unexpectedness (OCC intensity variable) | `1 − max(cosine_similarity(event, past_events))` |
| **G** | Goal Congruence | Desirability (OCC) | `alignment(event_valence, goal_direction)` |

> **Source**: OCC defines desirability as "the degree to which an event is congruent with
> an agent's goals." Novelty/unexpectedness is one of OCC's global intensity variables.
> R (relevance) is from Lazarus's primary appraisal.
>
> **Our adaptation**: We compute R and N using embedding cosine similarity, which is not
> in OCC — OCC uses symbolic goal matching.

### 1.2 Secondary Appraisal

Evaluates the event against identity, agency, and relationship:

| Variable | Definition | Lazarus/OCC Equivalent | Our Implementation |
|----------|-----------|----------------------|-------------------|
| **A** | Agency | Coping potential (Lazarus) / Controllability (EMA) | `controllability_estimate(event)` |
| **NA** | Norm Alignment | Praiseworthiness (OCC) | `alignment(event, identity_core_values)` |
| **RI** | Relationship Impact | Not in OCC — our extension | `predicted_trust_delta(event, relationship_state)` |

> **Source**: Agency maps to Lazarus's secondary appraisal ("Can I do anything about this?")
> and EMA's controllability variable. NA maps to OCC's praiseworthiness against standards.
>
> **Our extension**: RI (Relationship Impact) is not in the original models. We added it because
> CVS is a relational agent — the effect on the user-agent bond matters for every event.

### 1.3 Appraisal Vector

```
Appraisal = [R, N, G, A, NA, RI]
```

> **Note**: EMA does not output a vector — it computes appraisal variables individually and maps
> them to OCC emotion types. We flatten them into a vector for the state update equations below.
> This is our engineering simplification.

---

## ❤️ 2. Emotional State Model — PAD + Relational Framework

### Model Basis

The dimensional emotion model is **PAD** (Pleasure-Arousal-Dominance), established by
**Mehrabian & Russell (1974)**. The same space is used by **ALMA** (Gebhard, 2005) for its
medium-term mood layer, where emotions are points in PAD space and moods drift via pull/push
mechanisms.

### 2.1 State Variables

**Affective dimensions** (PAD — Mehrabian & Russell, 1974):

| Dimension | Symbol | Range | Source |
|-----------|--------|-------|--------|
| Pleasure / Valence | **V** | [−1, 1] | PAD model (Mehrabian & Russell) |
| Arousal | **Ar** | [0, 1] | PAD model |
| Dominance | **D** | [0, 1] | PAD model |

**Relational dimensions** (our extension for persistent agent-user bond):

| Dimension | Symbol | Range | Source |
|-----------|--------|-------|--------|
| Trust | **T** | [0, 1] | Adapted from Marsh (1994) computational trust |
| Attachment | **At** | [0, 1] | Inspired by Bowlby attachment theory — our formulation |

### 2.2 State Update — Emotion Decay (ALMA)

ALMA establishes that emotion intensity follows **exponential decay**:

```
I(t) = I₀ · exp(−λ · t)
```

> **Source**: Gebhard (2005), ALMA — "the intensity of an active emotion follows an exponential
> decay function." λ is a personality-dependent decay parameter.
>
> **Status**: ✅ Established formula.

### 2.3 State Update — Mood Pull (ALMA-inspired)

In ALMA, active emotions "pull" the current mood toward the emotion's PAD coordinates.
We adapt this for our appraisal-driven updates:

**Affective updates:**

```
V_new  = (1 − α) · V_old  +  α · (w₁·G + w₂·RI)

Ar_new = (1 − β) · Ar_old +  β · (w₃·N + w₄·R)

D_new  = (1 − γ) · D_old  +  γ · (w₅·A + w₆·NA)
```

> **Source**: The EMA (exponential moving average) blending structure is standard signal
> processing. ALMA uses a similar pull mechanism for mood updates in PAD space.
>
> **Our adaptation**: ALMA pulls mood toward discrete OCC emotion coordinates. We instead
> pull mood toward appraisal output values (G, RI, N, R, A, NA). The *mapping* of which
> appraisal feeds which PAD dimension is our design choice:
>
> - Goal Congruence (G) + Relationship Impact (RI) → Valence — because "did things go well?" drives feeling
> - Novelty (N) + Relevance (R) → Arousal — because surprising/important events energize
> - Agency (A) + Norm Alignment (NA) → Dominance — because control and values → sense of agency
>
> **Status**: ⚠️ Structure is established (EMA/ALMA). Specific mapping is our engineering design.

**Relational updates:**

```
T_new  = clamp(T_old + δ · RI, 0, 1)

At_new = clamp(At_old + ε · T · InteractionFrequency, 0, 1)
```

> **Source for Trust**: Marsh (1994) defines trust as `T(y,α) = U(α) · I(α) · dT(y)` where
> trust is situation-dependent, accumulates from history, and ranges [−1, +1]. Our simplified
> version uses RI (Relationship Impact) as the per-interaction trust delta, which approximates
> Marsh's outcome-based update but drops the utility/importance decomposition.
>
> **Source for Attachment**: Bowlby's attachment theory says bonds form through repeated positive
> interactions over time, requiring established trust first. The multiplicative form `T × Frequency`
> is **our engineering translation** of this principle — no published formula exists.
>
> **Status**: ⚠️ Trust update is a simplification of Marsh. Attachment equation is our design.

### 2.4 Coefficients

| Symbol | Range | Purpose | Basis |
|--------|-------|---------|-------|
| α | 0.2 – 0.4 | Slow valence drift | ALMA's personality-dependent rates |
| β | 0.3 – 0.6 | Faster arousal response | Arousal changes faster than valence in PAD literature |
| γ | 0.1 – 0.3 | Very stable dominance | Dominance is trait-like (Mehrabian) |
| δ | 0.05 – 0.15 | Trust changes slowly | Marsh: trust builds/decays gradually |
| ε | 0.01 – 0.05 | Attachment grows very slowly | Bowlby: attachment forms over months |

> **Status**: ⚠️ Ranges are our engineering estimates. Must be tuned experimentally.

---

## 🎯 3. Intent Selection — Decision Layer

### Model Basis

Uses **Multi-Attribute Utility Theory** (Keeney & Raiffa, 1976), which is standard in
AI planning and decision-making under uncertainty.

### 3.1 Utility Function

```
U(Intent) = w₁·GoalAlignment
           + w₂·EmotionalFit
           + w₃·IdentityAlignment
           + w₄·ContextRelevance
```

### 3.2 Intent Persistence

#### Motivation

The base selection rule is **stateless** — it recomputes intent every turn.  
Human behavior, however, is **goal-continuous**, where intentions persist and evolve over time.

Without persistence, the system may exhibit:

- abrupt tone shifts  
- inconsistent conversational direction  
- loss of perceived intentionality  

---

#### Persistence Model

We introduce a temporal smoothing layer over intent selection:

```
Intent_new = argmax(U(Intent))
Intent_t = (1 − ρ) · Intent_{t−1} + ρ · Intent_new
```

Where:

- `Intent_new = argmax(U(Intent))`
- `ρ ∈ [0.3, 0.7]` is the adaptation rate

---

#### Context Gating

To prevent stale or stuck intent:

```
If ContextShift > θ_shift:
    Intent_t = Intent_new
Else:
    apply persistence
```

Where:

- `ContextShift` represents semantic or emotional change in conversation

---

#### Behavioral Effect

This layer ensures:

- continuity in conversational goals  
- smoother emotional transitions  
- responses reflect ongoing intent rather than isolated decisions  

Without this layer, the system behaves as a **stateless responder**.  
With it, the system behaves as a **persistent, goal-driven agent**.

---

#### Status

⚠️ Engineering design

There is no direct published equation for conversational intent persistence.  
This is derived from control theory (temporal smoothing) and observed human behavior.

---

> **Source**: Standard utility maximization from decision theory.
>
> **Our adaptation**: The specific attributes (GoalAlignment, EmotionalFit, IdentityAlignment,
> ContextRelevance) are our design for CVS. Standard MAUT would work with any attributes.
>
> **Status**: ✅ Framework is established. Attribute choice is our design.

---

## ⏱️ 4. Timing & Pause Model — Speech Behavior

### Model Basis

Goldman-Eisler (1968) established empirically that silent pauses >250ms correlate with
cognitive planning load. There is **no published formula** — her contribution was the
empirical evidence, not a mathematical model.

### 4.1 Pause Duration

```
Pause = clamp(
    Base + k₁(1 − Confidence) + k₂·Load + k₃·Intensity,
    MinPause,
    MaxPause
)
```

> **Source**: Goldman-Eisler showed pauses increase with cognitive complexity. The linear
> additive form and the specific terms (Confidence, CognitiveLoad, EmotionalIntensity)
> are **our engineering model** — there is no published equation for this.
>
> **Empirical anchor**: Goldman-Eisler's threshold of 250ms for cognitive pauses informs
> our `Base` parameter.
>
> **Status**: ⚠️ Inspired by Goldman-Eisler's findings. The equation itself is our design.

### 4.2 Hesitation Trigger

```
If (Confidence < θ₁) AND (Novelty > θ₂)  →  Hesitation
```

> **Status**: ⚠️ Our design. The logic is intuitive (uncertain + surprised → hesitate)
> but not from a specific published model.

---

## 🎙️ 5. Voice Prosody Mapping

### Model Basis

Scherer's **Component Process Model** (CPM) predicts that emotional states produce systematic
variations in vocal parameters. However, Scherer emphasizes that acoustic profiles are
**configurations of multiple parameters**, not simple linear outputs.

### 5.1 Parameter Equations

| Parameter | Equation | Scherer's Prediction |
|-----------|---------|---------------------|
| **Pitch** | `BasePitch + tanh(k₁·V + k₂·Ar)` | High arousal → increased F0 mean and range ✅ |
| **Rate** | `BaseRate + tanh(k₃·Ar − k₄·Hesitation)` | High arousal → faster speech rate ✅ |
| **Volume** | `clamp(BaseVolume + k₅·D, min, max)` | High dominance → increased intensity ✅ |

> **Source**: The *directions* (arousal↑ → pitch↑, rate↑; dominance↑ → volume↑) are
> well-documented in Scherer (2003) and Bänziger & Scherer (2005).
>
> **Our simplification**: Scherer explicitly warns against simple linear mappings — real
> prosody is a multivariate configuration. Our linear equations are a **first-order
> approximation** that may need to be replaced with learned mappings if they don't sound right.
>
> **Status**: ⚠️ Directions are established. Linear form is our simplification.

### 5.2 Derived Behavior

```
PauseFrequency ∝ (1 − Confidence)
```

### 5.3 Affect Metadata Contract (Brain → Voice)

This is the NATS side-channel payload that accompanies every `chat.output` message:

```json
{
  "valence": 0.0,
  "arousal": 0.0,
  "dominance": 0.0,
  "trust": 0.5,
  "attachment": 0.1,
  "confidence": 0.0,
  "intensity": 0.0,
  "speaking_rate": 1.0,
  "pause_bias": 0.0
}
```

> **Status**: Our design — this is the data contract, not a formula.

---

## 🧠 6. Memory System — ACT-R Based Retrieval + Episodic Structure

### Model Basis

Memory retrieval scoring is adapted from **ACT-R** (Anderson & Lebiere, 1998), is one of the most widely used and empirically supported models in cognitive science. Episode structure is inspired by
**Tulving's** (1972) episodic memory theory and **Amory** (Zhou et al., 2026).

### 6.1 Episode Schema

```json
{
  "id": "uuid",
  "event": "User talked about exam stress",
  "context": "Late night study session",
  "emotion_vector": { "V": -0.3, "Ar": 0.7, "D": 0.4 },
  "cause": "episode_id / null",
  "outcome": "User felt reassured",
  "relationship_delta": 0.05,
  "timestamp": "2026-04-20T02:00:00Z"
}
```

> **Source**: Tulving (1972) defines episodic memory as containing *what happened*, *where*,
> and *when*. Amory (Zhou et al., 2026) adds causal linking and emotional context.
> Our schema is an engineering synthesis of both.
>
> **Status**: ✅ Conceptually grounded. Schema details are our design.

### 6.2 Base-Level Activation (ACT-R)

The ACT-R activation equation is **one of the most validated formulas in cognitive science**:

```
Aᵢ = Bᵢ + Σⱼ Wⱼ · Sⱼᵢ + ε
```

Where:

```
Bᵢ = ln( Σₖ tₖ⁻ᵈ )        ← Base-level activation (frequency + recency)

Σⱼ Wⱼ · Sⱼᵢ               ← Spreading activation (context relevance)

ε ~ Logistic(0, s)      ← Noise term (accounts for random retrieval fluctuations)
```

- **n**: Number of times the memory was accessed
- **tₖ**: Time elapsed since the k-th access
- **d**: Decay rate (typically 0.5)
- **Wⱼ**: Attentional weight of context element j
- **Sⱼᵢ**: Association strength between context j and memory i
- **s**: Scale parameter for noise

> **Source**: Anderson & Lebiere (1998), *The Atomic Components of Thought*.
> This is the standard ACT-R declarative memory equation, used in hundreds of published models.
>
> **Status**: ✅ Established formula. Directly usable.

### 6.3 Our Retrieval Score (ACT-R Adapted)

We extend ACT-R's activation with emotional and relational dimensions:

```
Score = Aᵢ + w₁·EmotionalAlignment + w₂·RelationshipRelevance
```

where

- Aᵢ is the ACT-R base-level + spreading activation
- EmotionalAlignment measures similarity between memory emotion and current state
- RelationshipRelevance captures impact on user-agent relationship

Retrieval Condition

```
Retrieve only if:
Score > θ_retrieval
```

Selection Rule

```
SelectedMemory = argmax(Score)
```

This deterministic selection ensures stability and consistency in memory recall. A probabilistic alternative (softmax sampling) can be introduced later if needed.

Optional Multi-Memory Retrieval

```
Top-k memories where:
Score > θ_retrieval
AND Score ≥ max(Score) − ε
```

This allows retrieval of closely competing memories for richer contextual reasoning.

Where `Aᵢ` is the ACT-R base+spreading activation above.

> **Source**: ACT-R provides Aᵢ. The emotional and relational extensions are from the
> analysis requirements (Theme 3) — not from ACT-R.
>
> **Status**: ⚠️ ACT-R core is established. Extensions are our design.

### 6.4 Emotional Coupling

```
EmotionalAlignment = exp(−|Memory.V − Current.V|)

Score += w · EmotionalAlignment
```

If alignment > (1 − ε), boost the score.

> **Source**: Our design. The idea that congruent mood facilitates recall is from
> mood-congruent memory research (Bower, 1981), but the specific formula is ours.

### 6.5 Episode Link Strength

Episodes are connected in a temporal-causal graph:

```
Link(i, j) = w₁·TemporalProximity + w₂·EmotionalSimilarity + w₃·CausalRelation
```

> **Source**: Amory (Zhou et al., 2026) uses agentic reasoning to build narrative links.
> Our linear scoring is a simplification of their approach.
>
> **Status**: ⚠️ Inspired by Amory. The linear form is our simplification.

---

## 🧠 7. Memory Consolidation — Long-Term Learning

### Model Basis

During offline periods, memory systems consolidate recent episodes. This is inspired by
**sleep consolidation research** and **ALMA's** layered affect model (short-term emotions
→ medium-term moods → long-term personality).

### 7.1 Importance Function

```
Importance = EmotionalIntensity × Frequency × Recency
```

> **Status**: ⚠️ Our design. ACT-R uses `Bᵢ = ln(Σ tₖ⁻ᵈ)` for importance via
> frequency/recency — our version adds emotional intensity as a multiplier, which is
> not in ACT-R but is supported by emotional memory research (McGaugh, 2004).

### 7.2 Consolidation

Consolidation is **not a formula** — it's an LLM summarization call:

```
ConsolidatedMemory = LLM_summarize(
    episodes = recent_episodes,
    weights  = importance_scores,
    prompt   = "Summarize the emotional and relational patterns across these episodes"
)
```

> **Correction from V2.0**: The previous version used `Σ(Episode_i × Importance_i) / Σ(Importance_i)`
> which is mathematically invalid — you cannot multiply a structured episode by a scalar.
> The actual implementation is an importance-weighted LLM summarization.
>
> **Status**: Engineering design.

---

## 🔁 8. Reappraisal Loop — Feedback System

### Model Basis

Follows **Gross's Process Model of Emotion Regulation** (1998, 2015). Computationally
formalized by **Bosse, Pontier & Treur (2010)** using differential equations:

```
dE/dt = f(S, A, E)
```

Where E = emotional response,
 S = stimulus,
  A = appraisal state.
   Reappraisal acts by
    modifying A (the appraisal),
     which in turn changes E.

### 8.1 Outcome Evaluation

```
Δ = ExpectedOutcome − ActualOutcome
```

ActualOutcome is not raw user emotion, but the change in user state caused by the agent's response.

We define:

```
ActualOutcome =
  w₁ · Δ_emotion_text
 + w₂ · Δ_emotion_acoustic
 + w₃ · BehavioralSignal
```

where

- Δ_emotion_text = sentiment shift between user responses (before vs after agent reply)
- Δ_emotion_acoustic = tone shift from SenseVoice (before vs after)
- BehavioralSignal = engagement-based proxy (e.g., response length, openness, continuation)

Additionally:

```
Δ_emotion = Emotion_after − Emotion_before
```

To handle noise:

```
Δ_effective = confidence · Δ_emotion
```

Outcome must be evaluated over a temporal window (1–2 turns), not instantly.

> **Correction**: SenseVoice output alone is not a valid proxy for outcome.
> It reflects user tone, not whether the agent’s response was successful.
> Outcome must be computed as state change over time, combining acoustic, textual, and behavioral signals.

> **Our implementation note**: ActualOutcome requires sentiment analysis of the user's
> next response. This is inherently noisy and delayed. We use the SenseVoice acoustic
> perception as a proxy — it gives us emotional tone without waiting for explicit feedback.

### 8.2 Appraisal Parameter Update (Reappraisal)

```
w₁ = clamp(w₁ − η · Δ_emotional, w_min, w_max)
w₂ = clamp(w₂ − η · Δ_relational, w_min, w_max)
D_new = (1 − γ) · D_old + γ · ControlAfterResponse
```

where:

- Δ_emotional is derived from emotional outcome signal
- Δ_relational reflects trust/relationship impact
- η = learning rate
- γ = dominance smoothing factor

> **Interpretation**:
> The system does not directly modify emotional state (PAD)
> Instead, it updates appraisal parameters (w₁, w₂)
> These parameters influence future appraisal → which influences emotion
>
> This maintains consistency with Gross/Bosse, where reappraisal changes interpretation, not raw feeling.
>
> **Known Risks**:
>
> - If η is too high → unstable behavior (overcorrection)
> - If outcome signals are noisy → incorrect adaptation
> - If behavioral signal is weak → system learns shallow patterns
>
> **To mitigate**:
>
> - Apply confidence weighting
> - Use temporal smoothing
> - Clamp parameter updates
>
> **Status**:
> ⚠️ Inspired by Gross (1998) and Bosse et al. (2010)
> ⚠️ Outcome modeling is an engineering extension (multi-signal, time-aware)
> ✅ Parameter-based reappraisal aligns with established computational models

---

## 📊 Validation Summary

| # | Component | Published Source | Our Equation Status |
|---|-----------|----------------|-------------------|
| 1 | Appraisal dimensions | OCC (1988), Lazarus (1991), EMA (2004) | ✅ Dimensions are established; embedding implementation is ours |
| 2 | PAD state space | Mehrabian & Russell (1974) | ✅ Established model |
| 2 | Emotion decay | ALMA — Gebhard (2005) | ✅ `I(t) = I₀·exp(−λt)` is published |
| 2 | Mood pull / state update | ALMA pull mechanism | ⚠️ Structure is established; appraisal→PAD mapping is ours |
| 2 | Trust update | Marsh (1994) | ⚠️ Simplified from Marsh's full model |
| 2 | Attachment update | Bowlby (theory only) | ⚠️ Our formulation — no published equation |
| 3 | Intent selection | MAUT — Keeney & Raiffa (1976) | ✅ Standard decision theory |
| 4 | Pause model | Goldman-Eisler (1968) | ⚠️ Her findings; our equation |
| 5 | Prosody mapping | Scherer CPM (2003) | ⚠️ Directions established; linear form is ours |
| 6 | Memory retrieval | ACT-R — Anderson & Lebiere (1998) | ✅ `Bᵢ = ln(Σtₖ⁻ᵈ)` is one of cognitive science's most validated formulas |
| 7 | Consolidation | Sleep research + McGaugh (2004) | ⚠️ Our design |
| 8 | Reappraisal | Gross (1998), Bosse et al. (2010) | ⚠️ Inspired by Bosse; our simplification |

---

## ⚠️ Implementation Notes

- Equations marked ✅ can be implemented with confidence
- Equations marked ⚠️ are engineering designs that need **experimental validation**
- The **ACT-R retrieval equation** (§6.2) should replace the current `memory_store.py` scoring — it's the most battle-tested formula in this sheet
- The **prosody linear mapping** (§5.1) is the most likely to need replacement with a learned model
- The **reappraisal direct correction** (§8.2) is the most likely to cause instability — consider Bosse's appraisal-parameter approach instead
- Start with ✅ formulas, add ⚠️ formulas incrementally with kill-switches

---

## 📚 References

1. Anderson, J.R. & Lebiere, C. (1998). *The Atomic Components of Thought*. Lawrence Erlbaum.
2. Bänziger, T. & Scherer, K.R. (2005). The role of intonation in emotional expressions. *Speech Communication*, 46(3-4).
3. Bosse, T., Pontier, M., & Treur, J. (2010). A computational model based on Gross' emotion regulation theory. *Cognitive Systems Research*, 11(3).
4. Bower, G.H. (1981). Mood and memory. *American Psychologist*, 36(2).
5. Gebhard, P. (2005). ALMA: A Layered Model of Affect. *Proceedings of AAMAS*.
6. Goldman-Eisler, F. (1968). *Psycholinguistics: Experiments in Spontaneous Speech*. Academic Press.
7. Gratch, J. & Marsella, S. (2004). A domain-independent framework for modeling emotion. *Cognitive Systems Research*, 5(4).
8. Gross, J.J. (1998). The emerging field of emotion regulation. *Review of General Psychology*, 2(3).
9. Keeney, R.L. & Raiffa, H. (1976). *Decisions with Multiple Objectives*. Wiley.
10. Lazarus, R.S. (1991). *Emotion and Adaptation*. Oxford University Press.
11. Marsh, S.P. (1994). *Formalising Trust as a Computational Concept*. PhD Thesis, University of Stirling.
12. Marsella, S. & Gratch, J. (2009). EMA: A process model of appraisal dynamics. *Cognitive Systems Research*, 10(1).
13. McGaugh, J.L. (2004). The amygdala modulates the consolidation of memories. *Annual Review of Neuroscience*, 27.
14. Mehrabian, A. & Russell, J.A. (1974). *An Approach to Environmental Psychology*. MIT Press.
15. Ortony, A., Clore, G.L., & Collins, A. (1988). *The Cognitive Structure of Emotions*. Cambridge University Press.
16. Scherer, K.R. (2003). Vocal communication of emotion. *Speech Communication*, 40(1-2).
17. Tulving, E. (1972). Episodic and semantic memory. In *Organization of Memory*. Academic Press.
18. Zhou, Y. et al. (2026). Amory: Building Coherent Narrative-Driven Agent Memory. *Proceedings of EACL*.

---

## 🚀 Expected Outcome

- Emotion becomes smooth and stable (ALMA decay + EMA blending)
- Memory feels contextual and human-like (ACT-R retrieval + episodic structure)
- Speech timing reflects cognition (Goldman-Eisler empirical basis)
- Responses feel intentional, not reactive (appraisal before generation)

---
