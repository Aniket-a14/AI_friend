# 🧪 Research Methodology Guide

> **Guide for testing, observing, and validating the architecture, mathematics, and mesh dynamics.**

This document outlines an experimental framework for validating this project's architecture, focusing on the mathematical models and signal dynamics that power the cognitive core, independent of vocal synthesis.

---

## 1. Architectural Validation (The Mesh)

The primary research goal is validating the efficacy of a decentralized, event-driven cognitive architecture.

### A. Mesh Resilience & Throughput
- **Goal**: Measure the overhead of NATS JetStream compared to a monolithic architecture.
- **Methodology**: Simulate high-frequency event bursts across `chat.input`, `state.update`, and `memory.surfaced` subjects.
- **Key Metric**: Event propagation jitter and message delivery reliability under high cognitive load.

### B. Agent Decoupling Efficiency
- **Goal**: Demonstrate how individual agents (Brain, Subconscious, Surfacing) operate asynchronously without blocking the main cognitive loop.
- **Metric**: CPU/Memory utilization per agent during complex reasoning tasks.

---

## 2. Mathematical Validation (The Cognitive Core)

Validating the deterministic nature of the psychological and memory models. These formulas are real and match `backend/app/state/agent_state.py` / `backend/app/config.py` at time of writing — verify against current code before citing in a paper, since defaults can drift.

### A. Affective Drift (PAD Model)
Validate the **Pleasure, Arousal, Dominance** trajectories.
- **Metric**: Correlation between input sentiment and PAD coordinate shifts.
- **Validation**: Demonstrate that emotional drift follows the expected logarithmic decay curve back to a neutral baseline during idle periods (Mesh Heartbeat).

### B. Memory Activation (ACT-R Scoring)
Validate the episodic recall mechanism.
- **Metric**: Recall precision based on the **Base-Level Activation** formula:

```math
A_i = \ln \left( \sum_{j=1}^n t_j^{-d} \right)
```

- **Validation**: Show how time-based decay ($d$) and frequency of access ($n$) accurately simulate human-like forgetting and retrieval.

---

## 3. Benchmarking Cognitive Latency

Since voice is excluded, the focus shifts to **Decision Latency**.

### A. Signal Turnaround Time
Measure the delta between `chat.input` and the final `chat.output` event.

```math
L_{cognitive} = T_{perception} + T_{memory\_surfacing} + T_{llm\_generation}
```

Any target latency figure cited here should carry a provenance label (measured vs. estimated) matching the discipline `CLAUDE.md` and `.agents/CONTEXT.md` already apply to every other number in this repo — see `backend/tools/measure/out/` for what's actually been measured against real infrastructure so far.

### B. State Hydration Performance
Measure the time taken to hydrate the agent's full state (Postgres + Neo4j) during a heartbeat.

### C. Telemetry Profiling
If profiling logging overhead specifically, compare a synchronous vs. asynchronous telemetry path and report the actual measured delta rather than assuming one.

---

## 4. Viewing & Observability

To collect results for your paper, you must observe the signal flow. There is
**no dashboard UI** for this — an `/admin/mesh` React Flow visualization
panel has been discussed but does not exist anywhere in the codebase (no
`react-flow` dependency, no admin route in `frontend/` or `website/`); don't
reference it as a current feature.

### A. Graph Knowledge (Neo4j Browser)
Visualize the agent's beliefs and episodic memory connections.
- Query: `MATCH (n) RETURN n LIMIT 50` to see the current cognitive state.

### B. Signal Bus (NATS)
Monitor real-time inter-agent communication using the NATS CLI.
```bash
nats sub ">"
```

---

## 5. Visualization for Publication

### A. Mesh Latency Observation
`scripts/research/monitor.py` and `scripts/research/injector.py` are real,
existing scripts: the injector sends standardized inputs to the mesh over
NATS to measure cognitive turnaround without human timing variability; the
monitor subscribes to the input/output/perceptual subjects and computes
turnaround/jitter from what it observes. Run them in separate terminals
against a live mesh.

### B. Emotional Trajectory Plotting
`scripts/research/collector.py` logs the agent's live PAD state to CSV by
subscribing to NATS broadcasts. `scripts/visualization/visualize_affect.py`
plots a PAD trajectory chart from that kind of data (its own current
implementation renders a synthetic sample trajectory for illustration —
check its source before assuming it plots your real collected CSV without
modification).

### C. Memory Activation Heatmaps
`scripts/research/visualizer.py` renders results out of `scripts/results/`
into plots (headless matplotlib) for publication figures.

`scripts/diagnostics/human_readable_benchmarks.py` also exists and can generate a readable summary of a benchmark run.

**One thing worth knowing about all five research scripts above:** at time
of writing they still carry the same "AI Friend / Sovereign Mesh / Tier-4/5"
branding this pass removed from the docs — e.g. `monitor.py`'s own print
output says "Sovereign Mesh Research Monitor (Tier-4/5) online...". That
cleanup wasn't done in this pass (scope was the nine `docs/*.md` files, not
`scripts/`) — flagged here rather than silently left, since a paper's
methodology section quoting this guide shouldn't be surprised by it.

---

## 6. System Parameter Map (Benchmarking Targets)

To ensure reproducibility, your paper should cite the following system constants. All values are configurable in `backend/app/config.py` or `.env`. Verified present at these defaults in `backend/app/config.py` as of this writing.

### A. Architectural & Sensory Parameters
| Parameter | Default | Research Significance |
| :--- | :--- | :--- |
| `INTENT_THRESHOLD` | `0.75` | Required confidence for cognitive execution. |
| `MIN_PERCEPTION_CONF` | `0.55` | Filter for sensory emotional cues. |
| `SYSTEM_TICK_INTERVAL`| `60s` | Frequency of idle state evolution. |
| `SURFACING_COOLDOWN` | `30s` | Temporal buffer for proactive memory recall. |
| `NATS_SETUP_RETRIES` | `30` | Infrastructure resilience: retry limit for JetStream. |
| `NATS_SETUP_DELAY` | `1.5s` | Infrastructure resilience: delay between setup retries. |

### B. Mathematical Coefficients (Cognitive Core)
| Coefficient | Default | Model Utility |
| :--- | :--- | :--- |
| `PSYCH_ALPHA` | `0.3` | **Valence Drift**: Rate of mood change. |
| `PSYCH_BETA` | `0.5` | **Arousal Response**: Sensitivity to novelty. |
| `PSYCH_GAMMA` | `0.2` | **Dominance Stability**: Trait-like persistence. |
| `PSYCH_DELTA` | `0.1` | **Trust Change Rate**: Marsh Trust Model sensitivity. |
| `PSYCH_EPSILON` | `0.03` | **Attachment Growth**: Bowlby Attachment coefficient. |
| `PSYCH_LAMBDA_DECAY` | `0.05` | **ALMA Decay**: Return to neutral baseline. |
| `ACTR_DECAY_RATE` | `0.5` | **Forgetting Rate** ($d$) in ACT-R. |
| `ACTR_SPREAD_WEIGHT`| `1.0` | **Spreading Activation**: Semantic linkage strength. |
| `MAUT_W_GOAL` | `0.35` | Decision weight: Goal Alignment. |
| `MAUT_W_EMOTION` | `0.25` | Decision weight: Affective Fit. |
| `MAUT_W_IDENTITY` | `0.20` | Decision weight: Identity Constraint. |
| `MAUT_W_CONTEXT` | `0.20` | Decision weight: Local Contextual Relevance. |

### C. Physiological (Endocrine) Formulas
These parameters modulate LLM generation parameters (temperature, top_p) in real-time — this is a real, shipped mechanism (`action.py::_compute_endocrine_options`), not aspirational:
- **Cortisol (Stress)**: tonic component `0.5 - (Valence / 2.0)`, plus a decaying phasic burst from `release_cortisol()` — affects LLM temperature (narrows it).
- **Dopamine (Reward)**: tonic component `max(0.0, Valence) * Arousal`, plus a decaying phasic burst from `release_dopamine()` — affects LLM top_p (widens it).

See `CLAUDE.md`'s "Endocrine layer" section for why the tonic/phasic split matters: the tonic terms are perfectly anti-correlated by construction, so only the phasic channels let the agent be stressed and rewarded at once.

---

## 7. Benchmarking Workflow (Step-by-Step)

To produce valid research data, follow this standardized benchmarking pipeline — using the real, shipped tooling.

### Step 1: Baseline Establishment
Run the system with the default parameters listed in Section 6.
- **Automated Validation**: `cd backend && ../.venv/bin/python -m pytest tests/test_performance.py` runs the isolated system-level performance suite.
- **Behavioral baseline**: `python -m evals run --model <tag> --out evals/out/baseline.json` — see `CLAUDE.md`'s "Behavioral eval harness" section. This probes the LLM boundary specifically, with deterministic scoring and provenance tracking built in.
- **Log Source**: Ensure `DEBUG=True` in `.env` to capture high-fidelity signal timing.
- **State Capture**: Initialize a clean Neo4j and PostgreSQL state.

### Step 2: Automated Input Injection
Do not use manual chat input for benchmarks; it introduces human latency variability.
- **Tool**: `scripts/talk.py` publishes real `chat.input` over the mesh and can be scripted/piped for repeatable input, or use the NATS CLI directly:
- **Command**: `nats pub chat.input '{"text": "Standardized Test Input", "metadata": {"start_time": %TIMESTAMP%}}'`

### Step 3: Real-Time Signal Monitoring
Use the NATS CLI to capture end-to-end timing.
```bash
# Monitor perception, brain, and mesh update latency simultaneously
nats sub "audio.perception" & nats sub "chat.output" & nats sub "state.update"
```

### Step 4: Parameter Stress Testing (A/B Isolation)
Isolate a single variable (e.g., `PSYCH_ALPHA`) and modify it in `.env`.
- **Test Case**: Change `PSYCH_ALPHA` from `0.3` to `0.9` (Fast Drift) and re-run the same Input Injection from Step 2.
- **Objective**: Measure how the "Emotional Velocity" changes in the `state_logs` table.

### Step 5: Data Extraction & Export
Extract the resulting trajectories from the persistent stores.
- **Relational**: Query `state_logs` in PostgreSQL to export PAD coordinates over time to CSV.
- **Graph**: Export the Neo4j relationship weights (Trust/Attachment) to visualize relationship growth curves.

### Step 6: Mathematical Verification
Apply the results to the formulas in Section 2.
- Compare the actual observed drift against the theoretical ALMA exponential decay curve ($I_0 \cdot e^{-\lambda t}$).
- Calculate the **Mean Squared Error (MSE)** between the system's output and the cognitive model's predictions.

---

## 8. Execution: How & When to Benchmark

### How to Run
1.  **Preparation**: Ensure the backend is fully initialized (`NATS`, `Neo4j`, `BrainAgent` all online) — `./start.sh` handles this.
2.  **Instrumentation**: Open two terminals and start the real, existing telemetry scripts:
    ```bash
    python scripts/research/monitor.py   # Latency profiling
    python scripts/research/collector.py # State trajectory logging (writes CSV)
    ```
3.  **Simulation**: In a third terminal, trigger the benchmark:
    ```bash
    python scripts/research/injector.py  # Standardized input injection
    ```
4.  **Finalization**: Once the session ends, stop the collector and generate plots:
    ```bash
    python scripts/research/visualizer.py
    python scripts/diagnostics/human_readable_benchmarks.py  # readable summary
    ```
5.  **Real measurement harness**: `cd backend && python -m tools.measure <n>` runs one of the registered `m11`-`m17` measurements against real infrastructure, writing a provenance-tagged report to `backend/tools/measure/out/` — a separate, more rigorous path than the scripts above, worth using when a number needs to carry provenance for a claim in this repo specifically.
6.  **Behavioral harness**: `python -m evals run` / `run-conversation` (see Section 7, Step 1, and `backend/evals/README.md`) for anything about model/persona *behavior* rather than latency.

### When to Benchmark
- **After Mesh Optimization**: Re-run `monitor.py`, or the relevant `tools.measure` scenario, after changing NATS streaming settings or agent hardware allocation to verify latency gains.
- **After Formula Tuning**: Re-run `collector.py` + `visualizer.py`, or `evals`, after modifying `PSYCH_ALPHA` or `ACTR_DECAY_RATE` in `.env` to visualize or check for a behavioral change, not just a config diff.
- **Database Scaling**: Run benchmarks as your Neo4j/Postgres data grows to measure hydration-latency impact.
- **Publication Prep**: Every number that goes into a paper should carry the same provenance label (`measured` vs. `estimated` vs. `unmeasured`) this repo's own docs use — see `CLAUDE.md`'s integrity constraints.

---

## 🧭 Recommended Research Focus
Focus on **"Mathematical determinism in agentic cognition"**: how structured psychological math (PAD) and cognitive theory (ACT-R) can be implemented in a decoupled mesh to create behavior that is observable and reproducible, not a black box.
