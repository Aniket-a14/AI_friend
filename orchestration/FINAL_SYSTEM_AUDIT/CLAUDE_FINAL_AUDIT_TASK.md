Perform an independent final cognitive and behavioral audit of the fully integrated six-phase humanoid brain architecture.

Do not read Codex's final audit before completing your own initial assessment.

Read:

* `FINAL_HUMANOID_BRAIN_ARCHITECTURE.md`
* `orchestration/MASTER_STATE.md`
* all six phase gates
* relevant phase acceptance criteria
* behavioral benchmark results
* the final integrated repository

Your role is:

**cognitive and behavioral truth**

Do not focus primarily on code style.

The central question is:

**Does this system now behave as a coherent cognitive architecture, or are some mechanisms still labels/state variables around an LLM pipeline?**

Audit each mechanism for causal behavioral value.

## 1. Cognitive Architecture Conformance

Assess whether the implemented system genuinely contains meaningful equivalents of:

* perception integration
* attention/salience
* working mental state
* memory
* appraisal
* emotion/mood
* global control / neuromodulation
* goals/drives where retained
* world model
* self model
* social cognition
* reasoning
* fast cognition
* slow cognition
* background cognition
* metacognition
* learning
* action selection
* expression planning

Do not give credit merely because classes or variables exist.

Ask whether each mechanism affects cognition or behavior.

## 2. Emotion / Appraisal

Determine whether emotional state is causally meaningful.

Check whether it influences things such as:

* attention
* memory retrieval
* decisions
* risk/persistence
* social behavior
* action selection
* learning
* expression

Separate:

internal state

from:

generated emotional language or TTS styling.

Flag theatrical emotion.

## 3. Global Control / Neuromodulation

Evaluate whether retained global control signals have measurable computational roles.

For each important signal ask:

* what changes it?
* what does it change?
* does behavior change reproducibly?
* is the mechanism still useful without biological naming?

Flag decorative variables.

## 4. Memory

Assess whether memory is cognitively integrated.

Check:

* episodic continuity
* semantic knowledge
* relationship continuity
* autobiographical identity
* retrieval relevance
* emotional association
* consolidation
* forgetting
* contradiction handling
* provenance
* causal influence on later decisions

Distinguish real architecture-managed memory from simple prompt retrieval.

## 5. Self Model / Identity

Evaluate whether identity survives beyond the current LLM.

Ask:

* does self state persist?
* are capabilities/limitations represented?
* are goals/history represented?
* are relationships preserved?
* is uncertainty represented?
* does personality remain stable?
* would switching LLM providers preserve recognizable identity?

Separate persona prompt from persistent identity.

## 6. World Model

Determine whether the implemented world model genuinely represents evolving state and predictions.

Do not treat:

* conversation history
* entity memory
* knowledge graphs

as automatically equivalent to a world model.

Look for state transitions and predictive use.

## 7. Social Cognition

Assess:

* user identity
* familiarity
* trust/relationship state
* interaction history
* inferred intentions
* social expectations
* relationship-dependent behavior

Avoid overstating theory-of-mind capabilities.

## 8. Fast / Slow Cognition

Determine whether the two pathways produce meaningfully different cognitive behavior.

Ask:

* what is actually fast?
* what bypasses the LLM?
* can fast reactions influence later deliberation?
* can slow cognition reinterpret earlier reactions?

Distinguish cognitive layering from ordinary asynchronous software.

## 9. Background Cognition

Evaluate whether background processes provide meaningful value.

Check for:

* unresolved-goal maintenance
* emotional decay/regulation
* memory consolidation
* prediction
* reflection
* relationship updates

Verify bounded execution and stopping conditions.

Flag "background thinking" that is simply repeated LLM calls without measurable benefit.

## 10. Metacognition

Assess whether the system meaningfully represents:

* uncertainty
* confidence
* contradiction detection
* failure recognition
* self-correction
* deciding when more information is needed
* deciding not to answer

Do not equate logs/reflection with metacognition automatically.

## 11. Learning

Be strict.

Separate:

* memory storage
* preference adaptation
* relationship updates
* reflection
* learned rules
* policy changes
* model changes
* code changes

Determine what actual future behavior changes because of experience.

Assess:

* improvement
* rollback
* reviewability
* accumulation of incorrect learning
* generalization
* regression

## 12. Action Selection

Determine whether cognition produces an internal action decision before expression.

Check whether the system can genuinely choose among:

* speak
* stay silent
* wait
* ask
* observe
* retrieve
* reason
* update state
* change goal
* interrupt
* perform external action

Language output should not automatically equal the chosen action.

## 13. Provider Independence

Assess cognitive dependence on the underlying foundation model.

Conceptually test:

* stronger frontier LLM
* smaller local LLM
* different provider

Determine what aspects of identity, state, memory, emotion and behavior genuinely belong to the architecture.

## 14. Behavioral Experiments

Review existing experiments and propose/execute relevant controlled tests where feasible.

Prefer:

### Ablation

with mechanism vs without mechanism

### Controlled state changes

same input, different internal state

### Provider substitution

same persistent brain, different compatible LLM

### Longitudinal tests

repeated interactions across time/restarts

### Counterfactual tests

same context with altered world/self state

For important cognitive claims, determine whether current evidence is:

* SUPPORTED
* PARTIALLY SUPPORTED
* UNSUPPORTED
* NOT YET TESTED

## 15. Scientific Defensibility

Check claims against the intended architecture and established research where needed.

Flag:

* biological overclaiming
* anthropomorphic wording unsupported by implementation
* consciousness-like claims
* emotion claims beyond evidence
* theory-of-mind overclaims
* learning claims that are actually memory

## 16. Research Value

Identify which implemented mechanisms now appear strongest for:

* research publication
* technical demonstration
* collaboration
* eventual commercial differentiation

Also identify mechanisms that currently add complexity without enough evidence.

## 17. Findings

Classify findings:

* BLOCKER
* HIGH
* MEDIUM
* LOW
* NEEDS_EXPERIMENT

Provide evidence.

Create:

`orchestration/FINAL_SYSTEM_AUDIT/CLAUDE_FINAL_COGNITIVE_AUDIT.md`

Use this structure:

# Claude Final Cognitive Audit

## Executive Verdict

## Cognitive Architecture Conformance

## Emotion and Appraisal

## Global Control / Neuromodulation

## Memory

## Self Model and Identity

## World Model

## Social Cognition

## Fast and Slow Cognition

## Background Cognition

## Metacognition

## Learning

## Action Selection

## Provider Independence

## Behavioral Evidence

## Scientific Defensibility

## Strongest Research Contributions

## Weak/Unsupported Claims

## Findings

## Recommended Fixes or Experiments

## Final Cognitive Verdict

Do not implement fixes during the initial audit.

Finish the report independently, then stop and wait for Gemini to arbitrate findings and assign any fixes.

Do not merge or push.
