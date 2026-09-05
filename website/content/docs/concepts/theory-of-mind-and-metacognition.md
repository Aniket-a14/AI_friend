# Theory of Mind & Metacognition

Two separate mechanisms let the agent track what *you* know (as opposed to what *it* knows), and be honest about what it doesn't know itself.

---

## User Mental Model

A lightweight, serializable `UserMentalModel` runs alongside the agent's own state, tracking:

- **Known concepts** — a running, deduplicated vocabulary of significant words you've actually said, extracted without any LLM call (a zero-overhead regex tracker, capped at 200 entries with sliding-window eviction so a long session's memory doesn't grow unbounded).
- **Implied goals** — what you appear to be trying to do right now.
- **User beliefs** — what you've stated or implied you believe about specific concepts, tracked separately from what's actually true.

When a stated belief conflicts with ground truth the agent actually holds, that's a **belief discrepancy** — not silently corrected, not ignored, but surfaced as its own signal the agent can act on (challenge gently, ask a clarifying question, or let it pass depending on context and relationship).

**Honesty note:** the concept-tracking and belief-discrepancy detection above are exactly what the code does — deterministic, no LLM involved. The *inferred emotional state* (valence/arousal) that also lives on the same user model comes from the LLM-backed appraisal engine elsewhere in the pipeline, not from this tracker. The Playground's Theory-of-Mind demo runs the real concept-tracking and discrepancy logic live; any emotional-state numbers shown alongside it are scripted scenario data, not computed from your input.

## Metacognition: Calibrated Confidence, Not Stated Confidence

A model's own stated confidence ("I'm pretty sure...") is not trusted directly — it's a feature that gets calibrated against what actually happened. A per-domain calibration tracker maintains a running Brier score from observed (predicted, actual) outcome pairs, and discounts raw confidence by it:

$$\text{calibrated} = \text{raw} \times \left(1 - 0.5 \cdot \min(1, \text{Brier})\right)$$

The calibrated value then maps deterministically to one of five directives:

| Calibrated confidence | Directive |
| :--- | :--- |
| ≥ 0.75 | **PROCEED** |
| ≥ 0.50 | **HEDGE** |
| ≥ 0.30 | **ASK_CLARIFICATION** |
| < 0.30 | **VERIFY** |
| (known limitation matched) | **ABSTAIN**, confidence forced to 0 |

A known-limitation match always wins regardless of confidence — if the query touches something the agent has been explicitly told it can't reliably do, it abstains rather than guessing convincingly. This is the mechanism behind principled "I don't know" — not a canned refusal string, but a directive computed the same way every time from the same inputs, live in the Playground's Metacognitive Abstention demo.

## Related: Governed Learning and Planning

Two further mechanisms round out metacognition beyond confidence: a **learning review queue** that treats every proposed personality or belief update as a reviewable, rollback-able proposal rather than a silent write (proposals touching the agent's immutable safety core are rejected before a human ever sees them), and a **deterministic plan verifier** that checks multi-step plans against typed pre/post-conditions before execution, plus a sandboxed episodic simulator for prospective "what-if" rollouts that cannot leak into real state (strict write quarantine). None of this is exposed as a playground demo yet — it's backend-only governance machinery, documented here for completeness rather than shown.
