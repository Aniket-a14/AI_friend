# 🧪 Research Paper Methodology: Tier-5 Sovereign Mesh

> **Guide for testing, observing, and validating Architecture, Mathematics, and Mesh Dynamics.**

This document outlines the experimental framework for validating the Tier-5 Sovereign Mesh architecture, focusing on the mathematical models and signal dynamics that power the cognitive core, independent of vocal synthesis.

---

## 1. Architectural Validation (The Sovereign Mesh)

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

Validating the deterministic nature of the psychological and memory models.

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

- **Target**: sub-500ms for total cognitive turnaround on local hardware.

### B. State Hydration Performance
Measure the time taken to hydrate the agent's full state (Prisma + Neo4j) during a heartbeat. The O(1) L1 Cache provides sub-microsecond `surface_actr_memories` resolution.

### C. Telemetry Profiling
Monitor signal bounds using the lock-free asynchronous telemetry worker. Previous synchronous logging induced 661 µs overhead; the current Tier-5 baseline is strictly `< 0.5 µs` per pulse.

---

## 4. Viewing & Observability (The Invisible Mesh)

To collect results for your paper, you must observe the signal flow.

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

### A. Mesh Architecture Visualization
Use the **React Flow** dashboard (`/admin/mesh`) to visualize the decoupling of agents.

### B. Emotional Trajectory Plotting
Generate PAD charts using `scripts/visualization/visualize_affect.py` to demonstrate deterministic emotional evolution over time.

### C. Memory Activation Heatmaps
Plot the "Activation Score" of recalled memories over a 60-minute session to show contextual relevance dynamics.

---

## 6. System Parameter Map (Benchmarking Targets)

To ensure reproducibility, your paper should cite the following system constants. All values are configurable in `backend/app/config.py` or `.env`.

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
These parameters modulate LLM generation parameters (Temperature, Top-P) in real-time to simulate biological constraints:
- **Cortisol (Stress)**: `0.5 - (Valence / 2.0)` — Affects LLM Temperature (Rigidity).
- **Dopamine (Reward)**: `max(0.0, Valence) * Arousal` — Affects LLM Top-P (Creativity).

---

## 7. Benchmarking Workflow (Step-by-Step)

To produce valid research data, follow this standardized benchmarking pipeline.

### Step 1: Baseline Establishment
Run the system with the default parameters listed in Section 6.
- **Automated Validation**: For isolated system-level verification, run the 16-metric automated suite via `pytest backend/tests/test_performance.py`.
- **Log Source**: Ensure `DEBUG=True` in `.env` to capture high-fidelity signal timing.
- **State Capture**: Initialize a clean Neo4j and PostgreSQL state.

### Step 2: Automated Input Injection
Do not use manual chat input for benchmarks; it introduces human latency variability.
- **Tool**: Create a "Researcher Agent" (using the NATS CLI or a Python script) that publishes standardized message bursts to `chat.input`.
- **Command**: `nats pub chat.input '{"text": "Standardized Test Input", "metadata": {"start_time": %TIMESTAMP%}}'`

### Step 3: Real-Time Signal Monitoring
Use the NATS CLI to capture the "Turnaround Mesh" timing.
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
1.  **Preparation**: Ensure the backend is fully initialized (`NATS`, `Neo4j`, `BrainAgent` all online).
2.  **Instrumentation**: Open two terminals and start the telemetry scripts:
    ```bash
    python scripts/research/monitor.py   # Latency Profiling
    python scripts/research/collector.py # State Trajectory Logging
    ```
3.  **Simulation**: In a third terminal, trigger the benchmark:
    ```bash
    python scripts/research/injector.py  # Standardized Pulse Injection
    ```
4.  **Finalization**: Once the session ends, stop the collector and generate plots:
    ```bash
    python scripts/research/visualizer.py
    python scripts/diagnostics/human_readable_benchmarks.py  # Generate decade profiles
    ```

### When to Benchmark
- **After Mesh Optimization**: Run the `monitor.py` after changing NATS streaming settings or agent hardware allocation to verify latency gains.
- **After Formula Tuning**: Run `collector.py` + `visualizer.py` after modifying `PSYCH_ALPHA` or `ACTR_DECAY_RATE` in `.env` to visualize the new cognitive behavior curve.
- **Database Scaling**: Run benchmarks as your Neo4j/Prisma data grows to measure "Hydration Latency" performance impact.
- **Publication Prep**: Use the visualizer to generate final, high-resolution figures for your research paper figures.

---

## 🧭 Recommended Research Focus
Focus on **"Mathematical Determinism in Agentic Cognition"**: How structured psychological math (PAD) and cognitive theory (ACT-R) can be implemented in a decoupled mesh to create a "Sovereign Intelligence" that is observable and reproducible.
