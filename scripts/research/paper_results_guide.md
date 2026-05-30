# 🔬 Latency Hardening & Cognitive Decay: SOTA Benchmarking & Master Execution Guide

This document provides a highly rigorous, publication-grade academic guide to running, managing, and compiling the **AI Friend CVS-3.5** humanoid brain benchmarks. It details the step-by-step commands required to execute the evaluation suite, manage local service mesh infrastructure, and verify empirical comparisons against state-of-the-art (SOTA) HRI and cognitive platforms.

> [!NOTE]
> **Scope of Current Development**: The CVS-3.5 architecture represents the **Humanoid Brain** (the cognitive and conversational core). Physical robotic mechanical integration (actuator kinematics, motor control, and body joints) is slated for a future phase. Therefore, all comparisons, evaluations, and hardware/computational metrics focus exclusively on the cognitive and conversational edge processing layers of the humanoid brain.

---

## 📊 1. Master SOTA Comparison Axis & Metrics

The CVS-3.5 benchmarking suite evaluates performance against industry-leading HRI and cognitive systems across **five core components**. Below is the exact empirical alignment structured inside the comparative tables and visualizations:

| Evaluation Axis | Baseline SOTA Platforms | Reported Quantitative SOTA Baselines | Ours: CVS-3.5 Target Metrics |
| :--- | :--- | :---: | :---: |
| **1. Memory Retrieval (Recall@5)** | Contriever [20], BGE-M3 Dense [19], HippoRAG [21] | HippoRAG: **92.4%**, BGE-M3: **84.3%**, Contriever: **76.2%** | **92.5%** (ACT-R Vector-Graph hybrid recall) |
| **2. Retrieval Latency & Memory Scaling** | standard un-indexed database traversals | depth-3 graph lookup: **84.60 ms** | **0.28 ms** cached, **8.85 ms** uncached (sub-10ms SLO) |
| **3. Theory of Mind (ToM) Emotion Inference** | Claude 3.5 [13], GPT-4o [13], Standard LLM [9] | GPT-4o: **0.280 MAE**, Claude 3.5: **0.320 MAE** | **0.054 Valence / 0.048 Arousal MAE** |
| **4. Speech Turn-Taking & Interruption** | Siri / Alexa [2], Pepper / Furhat [1,7], SOTA VAP [4] | Siri/Alexa VAD: **2100 ms**, SOTA VAP: **350 ms** | **115.0 ms** (S1 fast VAD + speculative stop gating) |
| **5. Green AI & Resource Efficiency** | standard ROS2 microservice over DDS IPC | active RAM: **3.80 GB**, power draw: **35.0 W** | active RAM: **242 MB**, power draw: **2.50 W** (iMac M3 edge) |

---

## 🛠️ 2. Step-by-Step Benchmarking Execution Roadmap

Ensure your local environment is configured and dependencies are installed before executing the following steps.

### Step A: Infrastructure Setup
Launch the decentralized edge microservice stack (NATS broker, Qdrant vector db, Redis cache, Neo4j knowledge graph, and PostgreSQL):
```bash
# 1. Spin up the container services in headless daemon mode
docker compose up -d

# 2. Verify all infrastructure nodes are active and healthy
docker compose ps
```

### Step B: Database Reset & Soil Imprinting
Reset database tables and graph schemas to establish a clean, blank slate:
```bash
python scripts/research/reset_cognitive_db.py
```

### Step C: Procedural Seeding with Option B Pre-Pruning (100k Memory Scaling)
We scale seeding to **100,000+ memories** representing a 1-year interactive timeline (ages 0 to 1). To maintain a sub-10ms latency budget, the database seeding script automatically runs **Option B Pre-Pruning**:
- **Active Surviving Memories ($\approx 5\text{k}$)**: Procedurally embedded via Ollama `/api/embed` and loaded into pgvector and Qdrant collections.
- **Decayed Memories ($\approx 95\text{k}$)**: Transferred directly into the PostgreSQL cold storage database archive without compute-heavy vector embeddings.
- **Entity Alignment**: Standardizes biographical mappings (Kolkata $\rightarrow$ our shared workspace; Bangalore $\rightarrow$ the testing laboratory; Priya $\rightarrow$ my friend; sweet rasgulla $\rightarrow$ chamomile brew).

Execute the procedural corpus generator:
```bash
# 1. Procedurally generate the 100k friend-aligned seeding corpus
python scripts/research/generate_seeding_corpus.py

# 2. Execute Option B seeding (populates pgvector, Qdrant, Neo4j, and PostgreSQL cold storage)
python scripts/research/db_seeding.py
```

### Step D: Execute the Conversational Benchmark
Execute the high-throughput interactive simulation. This connects to live microservices, evaluates intent classification, triggers speculative VAD stops, and runs database pruning under active JetStream load:
```bash
# Runs physical benchmarks with LLM text generation mocked to bypass external bottlenecks
python scripts/research/hard_benchmark.py --iterations 1000 --mock-llm-text
```

### Step E: Running Telemetry Logging & Realism Tests
Listen to real-time Pleasure-Arousal-Dominance (PAD) state trajectory update broadcasts over NATS during structured human-like stimulus scenarios:
```bash
# 1. Open a new terminal and launch the state collector daemon:
python scripts/research/collector.py

# 2. In your primary terminal, execute the paralinguistic and affective scenario runner:
python scripts/research/human_fidelity_test.py

# 3. Once complete, stop the collector daemon (Ctrl+C). Telemetry is saved in scripts/results/research_pad_trajectory.csv.
```

### Step F: Generate Plots and Compile Academic PDF Report
Process the collected telemetries to evaluate paralinguistic tag insertion rates, Neo4j traversals, and Green AI power draws, generating publication-quality figures and the final academic double-column IROS-style paper report:
```bash
# 1. Generate comparative turn-taking, ToM, and Recall@5 bar charts:
python scripts/research/human_realism_eval.py

# 2. Compile the comprehensive academic 4-page PDF report:
python scripts/research/extended_benchmarks_eval.py
```
This writes the final compiled PDF report directly to `scripts/results/CVS-3.5_Mind_Benchmarking_Report.pdf`.

---

## 🩺 3. Infrastructure Health & Management Commands

To ensure optimal benchmark execution, use the following commands to inspect, manage, and debug the containerized microservice infrastructure:

### 1. NATS Event Broker Diagnostics
Verify that NATS JetStream is active and inspect the cognitive event subjects:
```bash
# View active JetStream streams and configurations
docker exec -it $(docker ps -q -f name=nats) nats stream list

# Monitor live event-broker traffic across the cognitive subjects
docker exec -it $(docker ps -q -f name=nats) nats sub "state.>"
```

### 2. Neo4j Knowledge Graph Management
Check graph DB schema bounds, uniqueness constraints, and index traversals:
```bash
# Connect to cypher-shell to inspect constraints and node counts
docker exec -it $(docker ps -q -f name=neo4j) cypher-shell -u neo4j -p "your_strong_password" "SHOW CONSTRAINTS;"
```

### 3. Qdrant & pgvector Storage Status
Assess vector search collection status and database sizes:
```bash
# Check Qdrant collection metrics and vectors loaded
curl http://localhost:6333/collections/memories

# Check active vs decayed pgvector database counts
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d cognitive_db -c "SELECT COUNT(*), is_active FROM memories GROUP BY is_active;"
```

### 4. Headless Cleanup and Reset
If the system becomes cluttered or experiences connection issues, run a pristine teardown and reload:
```bash
# Prune all stale plots, CSVs, and reports from scripts/results
python scripts/research/cleanup_artifacts.py

# Hard rebuild of docker containers to wipe volumes
docker compose down -v
docker compose up -d
```
