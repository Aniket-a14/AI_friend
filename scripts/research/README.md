# 🧪 Tier-5 Sovereign Mesh Research Scripts

This folder contains the standardized tools required to validate the architecture and mathematics of the Sovereign Mesh for your research paper.

## 📦 Script Overview

1.  **`injector.py`**: Automated Stress Tester. Sends standardized message pulses to the mesh to measure response dynamics without human variability.
2.  **`monitor.py`**: Mesh Latency Monitor. Subscribes to the NATS bus to calculate end-to-end cognitive turnaround (Turnaround Time).
3.  **`collector.py`**: State Trajectory Logger. Polls the agent's internal state from Neo4j and logs PAD/Trust values to `research_pad_trajectory.csv` at 1Hz.
4.  **`visualizer.py`**: Plot Generator. Reads the CSV logs and produces publication-quality trajectory charts.

## 🚀 Execution Workflow

### 1. Start the Mesh
Ensure NATS, Neo4j, and the Backend (Brain, Subconscious, Surfacing agents) are running.

### 2. Start the Monitor & Collector
Open two terminal windows and run:
```bash
python scripts/research/monitor.py
# and
python scripts/research/collector.py
```

### 3. Run the Benchmark
In a third window, run the injector to send standardized pulses:
```bash
python scripts/research/injector.py
```

### 4. Wait for Evolution
Allow the system to run for several minutes after the injector finishes to capture the **ALMA Decay** (the mathematical return to neutral baseline).

### 5. Generate Results
Stop the collector (Ctrl+C) and run the visualizer:
```bash
python scripts/research/visualizer.py
```

---
**Note**: Ensure `pandas` and `matplotlib` are installed in your environment.
