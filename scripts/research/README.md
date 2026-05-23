# 🧪 CVS-3.0 Cognitive & Physical Benchmarking Suite

This directory contains the standardized, modular evaluation suite designed to validate the math, cognitive dynamics, and physical performance of the **CVS-3.0 Affective Cognitive Architecture** for academic publication.

---

## 📈 Dual-Layer Evaluation Framework

To prevent performance profiling overhead from introducing latency into live conversational pathways, the benchmarking suite is structured into two decoupled, synergistic layers:

```
                  ┌──────────────────────────────────────────────┐
                  │          CVS-3.0 BENCHMARKING SUITE          │
                  └──────────────────────┬───────────────────────┘
                                         │
                  ┌──────────────────────┴──────────────────────┐
                  ▼                                             ▼
     [L1: Continuous Telemetry]                    [L2: High-Res Evaluations]
     - hard_benchmark.py (1000 iters)              - human_realism_eval.py
     - Live NATS JetStream Pulses                  - extended_benchmarks_eval.py
     - pgvector & Neo4j Active Pruning             - Autonomic Physiological Curves
     - Latency, ToM, & Recall Averages             - CPU, RAM, & Power Footprints
```

---

## 📊 Comprehensive Metrics Mapped

### 1. Active Memory Bounding & Latency Scaling
*   **Active Memory Size ($M_{\text{active}}$):** Measures the bounded search space size. Active forgetting uses an ACT-R decay model ($\theta_{\text{prune}} = -2.5$) to transactionally delete decayed distractors, capping active memory while standard databases grow linearly ($M_{\text{total}}$).
*   **Retrieval Speedup ($O(\log M_{\text{active}})$):** Quantifies lookup latency differences between unpruned search spaces and pruned bounded spaces, achieving an asymptotic $\sim30\%$ speedup over long conversational sessions.

### 2. Autonomic Physiological Entrainment
*   **Coupled Heart Rate (HR):** Spikes under conversational threat and stress, driven by dynamic endocrine coupling:
    $$\text{HR (BPM)} = 70 + 40 \times \text{Cortisol} + 10 \times \text{Arousal} + \epsilon_{\text{noise}}$$
*   **Respiration Rate (RR):** Models breathing rate dynamics under stress:
    $$\text{RR (Breaths/Min)} = 12 + 10 \times \text{Arousal} + 4 \times \text{Cortisol} + \epsilon_{\text{noise}}$$
*   **Heart Rate Variability (HRV - RMSSD):** Models autonomic regulation decline under stress and fatigue:
    $$\text{HRV (ms)} = 65 - 35 \times \text{Cortisol} - 15 \times \text{Fatigue} + \epsilon_{\text{noise}}$$

### 3. Cognitive & Endocrine (Hormonal) States
*   **Cortisol & Dopamine:** Internal stress and reward appraisals mapped to Pleasure-Arousal-Dominance (PAD) dynamics.
*   **Theory of Mind (ToM) MAE:** Mean Absolute Error of our real-time user emotional state inferences against a dual-oracle sentiment appraisal model (Target MAE $< 0.05$).

### 4. Behavioral & Paralinguistic Realism
*   **Emotional Tag Precision:** Dynamic insertion accuracy of paralinguistic tag metadata (e.g., `[sighs]`, `[clears throat]`, `[voice cracks]`) matching conversational stress.
*   **Vocal Filler Rate:** Mimics human verbal hesitation under cognitive load (e.g., raising filler rate from $0.08$ to $0.42$ words/turn during stress).

### 5. Physical System Performance
*   **Hardware Footprint:** RAM consumption (MB), CPU usage (%), and power draw (Watts) profiling for all active agent nodes.
*   **E2E Turnaround Pathways:** Time-to-First-Token (TTFT), JetStream E2E turnaround, and Sub-LLM local compute overheads (Target E2E $< 15.0\text{ ms}$).

---

## 🛠️ Step-by-Step Benchmarking Workflow

This is a comprehensive, end-to-end execution guide for AI agents and human developers to run the entire evaluation suite.

### Step 1: Environment & Dependency Verification
Ensure your Python environment is active and equipped with the necessary scientific and report-generation libraries:
```bash
# 1. Create and activate a clean python virtual environment (if not already active)
python -m venv .venv
.venv\Scripts\activate      # On Windows
source .venv/bin/activate    # On macOS/Linux

# 2. Install the benchmarking suite's required python packages
pip install matplotlib numpy pandas reportlab nats-py python-dotenv scipy asyncpg neo4j vaderSentiment
```

### Step 2: Infrastructure Activation
Ensure the local service mesh and databases are fully active:
```bash
# 1. Spin up the NATS JetStream messaging mesh, PostgreSQL, pgvector, and Neo4j
docker compose up -d

# 2. Verify all containers are running and healthy
docker compose ps
```

### Step 3: Complete Pristine Cleanup
Before executing fresh benchmarks, purge any old simulation reports, temporary CSV files, or plots left over from previous runs:
```bash
python scripts/research/cleanup_artifacts.py
```

### Step 4: Database Reset & Soil Imprinting
Reset the backend pgvector tables and Neo4j graph nodes to establish a blank slate with clean schemas:
```bash
python scripts/research/reset_cognitive_db.py
```

### Step 5: Procedural Seeding Corpus Generation (The 19-Year Baseline)
Compile Aniket's 19-year life timeline (Ages 0 to 19) procedurally. This generates exactly **100,000 everyday conversations** backdated over 19 years and **10,000 milestones** structured across four developmental epochs (infancy, middle school, high school, and Bangalore college research with Priya):
```bash
python scripts/research/generate_seeding_corpus.py
```
This writes the full baseline dataset to `scripts/research/flooded_seeding_corpus.json`.

### Step 6: Verify with Dry Run (5 Iterations)
Before embarking on the full benchmark, execute a quick 5-iteration dry run to verify NATS JetStream connectivity, PostgreSQL pgvector connection, and Neo4j graph nodes are working perfectly:
```bash
# Execute dry run verification
python scripts/research/hard_benchmark.py --iterations 5
```

### Step 7: Post-Verification Database Reset & Re-seeding
Once the dry run successfully completes, wipe the database and regenerate the seeding corpus to ensure a fresh, pristine baseline:
```bash
python scripts/research/reset_cognitive_db.py
python scripts/research/generate_seeding_corpus.py
```

### Step 8: Run the Full 110,000-Memory Physical Stress Test (1000 Iterations)
Execute the rigorous physical benchmark at full scale. This connects to live microservices, loads all 110,000 memories (100,000 chitchats and 10,000 milestones) from `flooded_seeding_corpus.json` into pgvector, seeds Neo4j with Aniket's relational trust circle, and runs exactly **1,000 conversational turn interactions between Aniket and a close friend, compressed entirely within a single day (his 20th birthday)** under live JetStream load while executing active database pruning:
```bash
# Run the full physical benchmark flooding 100,000 distractors
python scripts/research/hard_benchmark.py --iterations 1000 --distractors 100000
```

### Step 9: Running Subsequent Tests Instantly (Bypassing Seeding)
To execute additional evaluation runs without wiping and re-seeding the 110,000-memory database, use the `--skip-seed` (or `-s`) flag:
```bash
# Run subsequent conversational trials instantly
python scripts/research/hard_benchmark.py --iterations 1000 --skip-seed
```


### Step 10: Real-time Telemetry Logging & Interactive Testing (Passive Daemon Mode)
To observe real-time physiological response changes and generate the publication affective trajectories, run the passive event listener alongside manual or automated interactive testing:
```bash
# 1. Open a new terminal and launch the state collector daemon:
python scripts/research/collector.py

# 2. In your primary terminal, execute the automated human realism stimuli scenario runner:
python scripts/research/human_fidelity_test.py

# 3. Once complete, stop the collector daemon (Ctrl+C). The telemetry is saved in scripts/results/research_pad_trajectory.csv.

# 4. Generate the publication-grade 3-panel affective arc tracking chart:
python scripts/research/visualizer.py

# 5. Generate the sample Pleasure-Arousal-Dominance (PAD) trajectory curves:
python scripts/visualization/visualize_affect.py
```

### Step 11: Compile Realism & Autonomic Curves
Process the benchmark's collected endocrine outputs to evaluate physiological entrainment, generating RMSSD HRV models and heart rate plots:
```bash
python scripts/research/human_realism_eval.py
```

### Step 12: Calculate Cognitive Metrics
Measure core user intent classification gate accuracy and Theory of Mind Mean Absolute Error (MAE) statistics:
```bash
python scripts/research/cognitive_metrics_eval.py
```

### Step 13: System Profiling & Report PDF Compilation
Measure graph search traversals, database size scaling, memory constraints, and compile the final academic PDF publication report embedding all generated figures:
```bash
python scripts/research/extended_benchmarks_eval.py
```


---

## 📂 Output Artifacts Directory Structure

All generated telemetry logs, high-resolution plots, and LaTeX-grade academic reports are compiled exclusively in the relative **`scripts/results/`** directory. No host directories or absolute paths are touched:

*   **Raw Telemetry Dataset:**
    *   `scripts/results/benchmark_results.json` (continuous latency, recall, and ToM measurements)
    *   `scripts/results/human_realism_results.json` (autonomic heart rate, endocrine, and realism data)
    *   `scripts/results/extended_benchmarks.json` (graph query speeds and systems usage telemetry)
    *   `scripts/results/cognitive_metrics_results.json` (intent classification rates and ToM statistics)
    *   `scripts/results/research_pad_trajectory.csv` (real-time high-fidelity chronological tracking CSV)

*   **Publication-Grade Figures:**
    *   `scripts/results/hard_benchmark_progression.png` (4-panel visualizer showing search space stabilization, $O(\log M_{\text{active}})$ speedups, and intent convergence)
    *   `scripts/results/human_realism_physiological.png` (coupled heart rate, breathing rate, and RMSSD HRV trajectories)
    *   `scripts/results/human_realism_comparisons.png` (appraisal valence vs. baseline physiological comparisons)
    *   `scripts/results/extended_benchmarks_comparisons.png` (graph database search latencies vs. memory usage)
    *   `scripts/results/extended_benchmarks_radar.png` (radar diagram comparing multi-axis performance limits)
    *   `scripts/results/cognitive_confusion_matrix.png` (confusion matrix plotting classification accuracy)
    *   `scripts/results/cognitive_rag_recall.png` (recall performance curve comparing standard vs. ACT-R RAG memory)
    *   `scripts/results/cognitive_tom_errors.png` (Theory of Mind emotional modeling error rates)
    *   `scripts/results/research_trajectory_plot.png` (3-panel real-time endocrine, affect, and ToM plot)
    *   `scripts/results/affective_trajectory_sample.png` (sample Pleasure-Arousal-Dominance (PAD) curve tracking)

*   **LaTeX-Grade Compilation Report:**
    *   `scripts/results/CVS-3.0_Mind_Benchmarking_Report.pdf` (fully compiled, multi-page, double-column academic evaluation paper with embedded visual telemetry)
