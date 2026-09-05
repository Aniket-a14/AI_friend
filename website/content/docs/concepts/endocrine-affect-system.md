# Endocrine & Affect Simulation

Unlike standard chatbots that rely on static text prompts, AI Friend incorporates an **internal neurochemical simulation**. Internal affective states change how the LLM generates tokens in real time.

---

## The Tonic + Phasic Mathematical Model

The endocrine engine tracks two primary neurochemicals: **Cortisol** (stress/caution) and **Dopamine** (reward/enthusiasm). Each hormone is decomposed into two distinct mathematical channels:

$$\text{Hormone}(t) = \text{Tonic}(t) + \text{Phasic}(t)$$

### 1. Tonic Channel (Affective Baseline)
The tonic baseline reflects long-term emotional equilibrium and is derived continuously from the 3D PAD (Pleasure, Arousal, Dominance) space:

$$\text{Tonic}_{\text{Cortisol}} = \text{clamp}\left(0.5 - 0.5 \cdot \text{Valence} + 0.3 \cdot \text{Arousal}, 0.0, 1.0\right)$$
$$\text{Tonic}_{\text{Dopamine}} = \text{clamp}\left(0.5 + 0.5 \cdot \text{Valence} + 0.4 \cdot \text{Arousal}, 0.0, 1.0\right)$$

### 2. Phasic Channel (Decaying Event-Driven Bursts)
Phasic bursts are triggered by conversational events (e.g. insults, achievements, praise, long pauses) and decay exponentially according to their calibrated half-lives:

$$\text{Phasic}(t) = \text{Phasic}_0 \cdot e^{-\lambda t} \quad \text{where } \lambda = \frac{\ln(2)}{t_{1/2}}$$

* **Dopamine Half-Life ($t_{1/2}$)**: $90\text{ seconds}$ (Rapid reward spike and decay).
* **Cortisol Half-Life ($t_{1/2}$)**: $4500\text{ seconds}$ (Prolonged stress persistence, ~75 minutes).

Because phasic channels operate independently of anti-correlated tonic baselines, the agent can experience realistic complex emotions, such as being **simultaneously stressed and rewarded**.

### 3. A Third Channel: Adrenaline

A third hormone, **Adrenaline**, is phasic-only — it has no tonic baseline, only a decaying burst (half-life $120\text{ seconds}$), fired by startle/interruption events and lifting arousal directly:

$$\text{Arousal}_{\text{lift}} = 0.3 \cdot \text{Adrenaline}$$

Unlike cortisol and dopamine, adrenaline doesn't have a slow-moving mood-like component — it's purely a fast reflex signal, matching its role as an interruption/shock reaction rather than a sustained mood.

---

## Trust and Attachment (Marsh + Bowlby)

Alongside affect, every relationship tracks three independent trust components — **benevolence**, **competence**, and **integrity** (Marsh, 1994) — plus a separate **attachment** value (Bowlby). These update from the same per-turn appraisal that drives PAD:

$$\text{Trust}_{\text{benevolence}} \mathrel{+}= \delta \cdot RI \qquad \text{Trust}_{\text{competence}} \mathrel{+}= \delta \cdot (0.6G + 0.4R) \qquad \text{Trust}_{\text{integrity}} \mathrel{+}= \delta \cdot NA$$

where $RI$ is relationship impact, $G$ is goal congruence, $R$ is relevance, and $NA$ is norm alignment — all appraisal outputs, not hand-tuned dials. Attachment grows separately, scaled by both trust and how many interactions have happened so far:

$$\text{Attachment} \mathrel{+}= \epsilon \cdot \text{Trust} \cdot \min\left(1, \frac{\text{interaction\_count}}{100}\right)$$

This is why attachment is slow to build even with high trust: a friend who trusts you immediately (high benevolence/competence/integrity from the first conversation) still needs repeated interaction — the $\min(1, n/100)$ term — before attachment itself catches up. Trust can be earned in one exchange; attachment cannot. Both $\delta$ (trust change rate) and $\epsilon$ (attachment growth rate) are persona fields, seeded per-friend from how the description reads (see [Persona Constitution](/docs/concepts/persona-constitution)) — a guarded character and a quick-to-trust one respond to the same events at genuinely different rates.

Try this live: the [Trust & Attachment Visualizer](/playground) in the playground runs this exact formula against appraisal sliders you control.

---

## Dynamic LLM Sampling Modulation

Neurochemicals directly modulate LLM generation parameters during the cognitive action stream:

```mermaid
graph LR
    Cortisol[High Cortisol / Stress] -->|Lowers Temperature| Temp[Temperature: 0.35]
    Dopamine[High Dopamine / Reward] -->|Expands Top-P| TopP[Top-P: 0.95]
    Fatigue[High Fatigue / Exhaustion] -->|Contracts Max Tokens| Tokens[Max Tokens: 120]
```

| Parameter | Modulated By | Impact on Generated Speech |
| :--- | :--- | :--- |
| **Temperature** | $\text{Cortisol}$ | High cortisol lowers temperature ($0.7 \rightarrow 0.35$), making responses concise, cautious, and direct. |
| **Top-P** | $\text{Dopamine}$ | High dopamine increases top-p ($0.8 \rightarrow 0.95$), encouraging creative vocabulary, humor, and expressive metaphors. |
| **Max Tokens** | $\text{Fatigue}$ | Fatigue reduces token ceiling ($500 \rightarrow 120$), causing the agent to give shorter, less verbose answers when tired. |
| **Speaking Rate** | $\text{Arousal}$ | High arousal accelerates speech pacing and shortens pauses. |

---

## Authentic Emotional Friction

The agent does **not** artificially soften or placate when the user is rude or unreasonable. If an insult occurs:
1. Valence drops, and an immediate **phasic Cortisol burst** fires.
2. The agent's temperature drops, and deliberation selects an assertive or disengaged conversational stance.
3. The response reflects authentic human annoyance, maintaining identity integrity rather than sycophantic obedience.
