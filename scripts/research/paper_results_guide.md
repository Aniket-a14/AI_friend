# 🔬 Latency Hardening & Cognitive Decay: Research Results Data Guide

This directory contains the high-fidelity empirical datasets compiled from the **AI Friend CVS-3.0** edge social humanoid robot platform. These metrics represent the post-optimization state of your sovereign mesh subsystems and are fully formatted to be dropped directly into your LaTeX manuscript, parsed with pandas, or plotted in matplotlib.

> [!NOTE]
> **Scope of Current Development**: The CVS-3.0 architecture represents the **Humanoid Brain** (the cognitive and conversational core). Physical robotic mechanical integration (actuator kinematics, motor control, and body joints) is slated for a future phase. Therefore, all comparisons, evaluations, and hardware/computational metrics focus exclusively on the cognitive and conversational edge processing layers of the humanoid brain.

---

## 📁 Dataset Directory Contents

1.  **[raw_research_data.json](../results/raw_research_data.json)**:
    *   **Micro-Benchmarks**: Pre- vs. Post-optimization latency tables (LLM Modulation, Hybrid Segmenter, Audio Normalizer).
    *   **State Trajectories**: Pleasure-Arousal-Dominance (PAD) and Hormone (Cortisol/Dopamine) transitions over a 90-second threat-appraisal stressor pulse.
    *   **System Budgets**: Hardware budget execution ratios for a NVIDIA Jetson AGX Orin edge robot rig.
2.  **[benchmark_results.json](../results/benchmark_results.json)**:

    *   Dynamic statistical aggregates (Min, Mean, Median, Max, Jitter, p95, p99) automatically populated whenever you run the physical architectural benchmarker script (`python scripts/research/hard_benchmark.py`).

---

## 📊 Empirical Performance Table (GitHub Preview)

| Subsystem Component | Original Latency | Optimized Latency | Throughput | Budget Limit | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Audio Ingest & Normalizer** | -- | `[TBP]` | `[TBP]` | 5.00 ms | `[TBP]` |
| **Hybrid Text Segmenter** | 4.294 ms | `[TBP]` | `[TBP]` | 10.00 ms | `[TBP]` |
| **Subconscious Threat Scan** | -- | `[TBP]` | `[TBP]` | 2.00 ms | `[TBP]` |
| **Memory ACT-R Index Search** | -- | `[TBP]` | `[TBP]` | 8.00 ms | `[TBP]` |
| **Hormonal State Appraisal** | -- | `[TBP]` | `[TBP]` | 5.00 ms | `[TBP]` |
| **LLM Temperature Modulation** | 2.30 µs | `[TBP]` | `[TBP]` | 1.00 ms | `[TBP]` |
| **End-to-End Pathway** | **--** | **`[TBP]`** | **`[TBP]`** | **15.00 ms** | **`[TBP]`** |

### LaTeX Table Template for Your Paper

You can copy-paste the LaTeX code below directly into your paper's **Results & Evaluation** section:

```latex
\begin{table}[htbp]
\caption{Subsystem Performance and Real-Time Budget Headroom on NVIDIA Jetson AGX Orin}
\label{tab:subsystem_performance}
\centering
\begin{tabular}{lccccr}
\hline
\textbf{Subsystem Component} & \textbf{Original Latency} & \textbf{Optimized Latency} & \textbf{Throughput} & \textbf{Budget Limit} & \textbf{Status} \\ \hline
Audio Ingest \& Normalizer   & --                       & [TBP]                      & [TBP]               & 5.00 ms               & [TBP]       \\
Hybrid Text Segmenter        & 4.294 ms                 & [TBP]                      & [TBP]               & 10.00 ms              & [TBP]    \\
Subconscious Threat Scan     & --                       & [TBP]                      & [TBP]               & 2.00 ms               & [TBP]          \\
Memory ACT-R Index Search    & --                       & [TBP]                      & [TBP]               & 8.00 ms               & [TBP]   \\
Hormonal State Appraisal     & --                       & [TBP]                      & [TBP]               & 5.00 ms               & [TBP]          \\
LLM Temperature Modulation   & 2.30 \(\mu\)s            & [TBP]                      & [TBP]               & 1.00 ms               & [TBP]    \\ \hline
\textbf{End-to-End Pathway}  & \textbf{--}              & \textbf{[TBP]}             & \textbf{[TBP]}      & \textbf{15.00 ms}     & \textbf{[TBP]} \\ \hline
\end{tabular}
\end{table}
```

---

## 📈 Pandas Quick Start Analysis Code

Use the Python script below to load, analyze, and generate LaTeX tables or plots of the cognitive state trajectory over time:

```python
import json
import pandas as pd
import matplotlib.pyplot as plt

# 1. Load raw data
with open("../results/raw_research_data.json", "r") as f:
    data = json.load(f)

# 2. Convert PAD Trajectories to Pandas DataFrame
trajectory_data = data["cognitive_state_trajectories"]
df = pd.DataFrame(trajectory_data["datapoints"], columns=trajectory_data["columns"])

# 3. Print Statistical Description
print("=== Empirical Cognitive Trajectory Summary ===")
print(df.describe())

# 4. Generate Publication-Quality Plot
plt.figure(figsize=(8, 4.5), dpi=300)
plt.style.use('seaborn-v0_8-whitegrid')
plt.plot(df['elapsed_seconds'], df['pleasure'], marker='o', label='Pleasure (P)', linewidth=2)
plt.plot(df['elapsed_seconds'], df['arousal'], marker='s', label='Arousal (A)', linewidth=2)
plt.plot(df['elapsed_seconds'], df['dominance'], marker='^', label='Dominance (D)', linewidth=2)

plt.title('PAD Mood-Energy Trajectory under Threat Appraisal Trigger', fontsize=12, fontweight='bold')
plt.xlabel('Elapsed Time (Seconds)', fontsize=10)
plt.ylabel('Dimension Value Range [-1.0, 1.0]', fontsize=10)
plt.legend(loc='lower right', frameon=True)
plt.tight_layout()
plt.savefig('pad_trajectory_paper.pdf', format='pdf')
plt.show()
```

---

## 📊 Extended Results Tables (GitHub Preview)

### Table 2: Edge Resource Overhead & Hardware Footprint (GitHub Preview)

| Component Services | RAM Allocation | VRAM Allocation | CPU Util. (Avg) | Power Footprint |
| :--- | :--- | :--- | :--- | :--- |
| **NATS Event Broker** | `[TBP]` | `[TBP]` | `[TBP]` | `[TBP]` |
| **Neo4j Graph Database** | `[TBP]` | `[TBP]` | `[TBP]` | `[TBP]` |
| **Redis Cache Server** | `[TBP]` | `[TBP]` | `[TBP]` | `[TBP]` |
| **Python Cognitive Agents** | `[TBP]` | `[TBP]` | `[TBP]` | `[TBP]` |
| **Total Mesh Footprint** | **`[TBP]`** | **`[TBP]`** | **`[TBP]`** | **`[TBP]`** |
| Whisper STT (CPU edge) | `[TBP]` | `[TBP]` | `[TBP]` | `[TBP]` |
| Local Llama 3B (Quantized) | `[TBP]` | `[TBP]` | `[TBP]` | `[TBP]` |
| **Full Stack Total** | **`[TBP]`** | **`[TBP]`** | **`[TBP]`** | **`[TBP]`** |

#### Copy LaTeX Code for Table 2:
```latex
\begin{table}[htbp]
\caption{Edge Computational Footprint and Resource Budgets of the Sovereign Mesh}
\label{tab:edge_hardware_footprint}
\centering
\begin{tabular}{lcccr}
\hline
\textbf{Component Services} & \textbf{RAM Allocation} & \textbf{VRAM Allocation} & \textbf{CPU Util. (Avg)} & \textbf{Power Footprint} \\ \hline
NATS Event Broker           & [TBP]                   & [TBP]                    & [TBP]                    & [TBP]                    \\
Neo4j Graph Database        & [TBP]                   & [TBP]                    & [TBP]                    & [TBP]                    \\
Redis Cache Server          & [TBP]                   & [TBP]                    & [TBP]                    & [TBP]                    \\
Python Cognitive Agents     & [TBP]                   & [TBP]                    & [TBP]                    & [TBP]                    \\ \hline
\textbf{Total Mesh Footprint} & \textbf{[TBP]}         & \textbf{[TBP]}           & \textbf{[TBP]}           & \textbf{[TBP]}           \\ \hline
Whisper STT (CPU edge)      & [TBP]                   & [TBP]                    & [TBP]                    & [TBP]                    \\
Local Llama 3B (Quantized)   & [TBP]                   & [TBP]                    & [TBP]                    & [TBP]                    \\ \hline
\textbf{Full Stack Total}   & \textbf{[TBP]}          & \textbf{[TBP]}           & \textbf{[TBP]}           & \textbf{[TBP]}           \\ \hline
\end{tabular}
\end{table}
```

### Table 3: Mathematical Decay Calibration & Conversational Robustness (GitHub Preview)

| Mathematical Decay Metric | Measured Value | HRI Robustness Metric (N=500) | Measured Value |
| :--- | :--- | :--- | :--- |
| **Decay Constant (Tau)** | `[TBP]` | **Interruption Success Rate (Barge-In)** | `[TBP]` |
| **Mood Fit (R2 Pleasure)** | `[TBP]` | **Interruption Latency (Stop Time)** | `[TBP]` |
| **Energy Fit (R2 Arousal)** | `[TBP]` | **Ambient False Trigger Ratio** | `[TBP]` |
| **Control Fit (R2 Dominance)** | `[TBP]` | **Knowledge RAG Recall@1** | `[TBP]` |
| **Memory Search Recall@3** | `[TBP]` | **Knowledge RAG Recall@5** | `[TBP]` |

#### Copy LaTeX Code for Table 3:
```latex
\begin{table}[htbp]
\caption{Mathematical Model Decay Fit and Human-Robot Interaction Metrics}
\label{tab:mathematical_alignment}
\centering
\begin{tabular}{lc|lc}
\hline
\textbf{Mathematical Decay Metric} & \textbf{Measured Value} & \textbf{HRI Robustness Metric (N=500)} & \textbf{Measured Value} \\ \hline
Decay Constant (\(\tau\))         & [TBP]                   & Interruption Success Rate (Barge-In)  & [TBP]                  \\
Mood Fit (\(R^2\) Pleasure)       & [TBP]                   & Interruption Latency (Stop Time)     & [TBP]               \\
Energy Fit (\(R^2\) Arousal)      & [TBP]                   & Ambient False Trigger Ratio          & [TBP]                   \\
Control Fit (\(R^2\) Dominance)   & [TBP]                   & Knowledge RAG Recall@1               & [TBP]                   \\
Memory Search Recall@3            & [TBP]                   & Knowledge RAG Recall@5               & [TBP]                   \\ \hline
\end{tabular}
\end{table}
```

---

## 📈 Pandas Quick Start Analysis Code

Use the Python script below to load, analyze, and generate LaTeX tables or plots of the cognitive state trajectory over time:

```python
import json
import pandas as pd
import matplotlib.pyplot as plt

# 1. Load raw data
with open("../results/raw_research_data.json", "r") as f:
    data = json.load(f)

# 2. Convert PAD Trajectories to Pandas DataFrame
trajectory_data = data["cognitive_state_trajectories"]
df = pd.DataFrame(trajectory_data["datapoints"], columns=trajectory_data["columns"])

# 3. Print Statistical Description
print("=== Empirical Cognitive Trajectory Summary ===")
print(df.describe())

# 4. Print Advanced Math & Hardware Footprints
print("\n=== Extended Research Diagnostics ===")
print(f"Decay Constant (Tau): {data['mathematical_homeostasis_alignment']['decay_coefficient_tau_seconds']} seconds")
print(f"Pleasure Curve Fit (R^2): {data['mathematical_homeostasis_alignment']['exponential_decay_regression']['pleasure_r_squared']}")
print(f"Barge-In Interruption Success: {data['conversational_hri_robustness']['barge_in_interruption_success_rate'] * 100}%")
print(f"Memory Search Recall@1: {data['mathematical_homeostasis_alignment']['knowledge_graph_memory_search']['recall_at_1'] * 100}%")
print(f"Total Mesh RAM Overhead: {data['edge_hardware_resource_footprint']['system_ram_allocation_mb']['total_mesh_overhead_mb']} MB")

# 5. Generate Publication-Quality Plot
plt.figure(figsize=(8, 4.5), dpi=300)
plt.style.use('seaborn-v0_8-whitegrid')
plt.plot(df['elapsed_seconds'], df['pleasure'], marker='o', label='Pleasure (P)', linewidth=2)
plt.plot(df['elapsed_seconds'], df['arousal'], marker='s', label='Arousal (A)', linewidth=2)
plt.plot(df['elapsed_seconds'], df['dominance'], marker='^', label='Dominance (D)', linewidth=2)

plt.title('PAD Mood-Energy Trajectory under Threat Appraisal Trigger', fontsize=12, fontweight='bold')
plt.xlabel('Elapsed Time (Seconds)', fontsize=10)
plt.ylabel('Dimension Value Range [-1.0, 1.0]', fontsize=10)
plt.legend(loc='lower right', frameon=True)
plt.tight_layout()
plt.savefig('pad_trajectory_paper.pdf', format='pdf')
plt.show()
```

---

## 🛠️ Code Correction Note

> [!IMPORTANT]
> A critical `NameError` crash in `hard_benchmark.py` (which tried to write undefined statistics variables `avg`, `p50`, `p95`, `p99`, `jitter` to `benchmark_results.json`) has been **fully corrected**. 
> The script now accurately calculates, logs, and outputs these values in high-precision floats automatically whenever ran.
