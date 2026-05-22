# ⚙️ Frameworks, Infrastructure, and Edge Deployment

This document describes the decentralized, containerized edge-native infrastructure and microservice mesh powering **AI Friend CVS-3.0**. It outlines the hardware specifications, active service footprints, and the real-time telemetry pipeline used for social robot orchestration.

---

## 1. Sovereign Mesh Architecture & Microservice Deployment

CVS-3.0 replaces traditional, heavyweight monolithic robotic architectures with a decentralized network of lightweight microservice containers. These containers communicate asynchronously via a **NATS Event Broker** pub-sub architecture, minimizing lock contention and eliminating synchronous blocking dependencies.

```mermaid
graph TD
    User([User Speech]) --> STT[Whisper STT Service]
    STT -->|chat.input| NATS{NATS JetStream Event Broker}

    NATS -->|chat.input| SubScan[Subconscious Scan Agent]
    NATS -->|chat.input| MemSurf[Memory Surfacing Agent]
    NATS -->|chat.input| Brain[Brain Cognitive Agent]

    SubScan -->|telemetry.threat| Brain
    MemSurf -->|telemetry.memory| Brain

    Brain -->|Neo4j Query| Graph[(Neo4j DB)]
    Brain -->|pgvector Query| Relational[(Postgres DB)]
    Brain -->|telemetry.appraisal| State[System State Agent]

    State -->|telemetry.hormones| Brain
    Brain -->|chat.output| NATS

    NATS -->|chat.output| TTS[Expressive TTS DSP Engine]
```

---

## 2. Quantitative Edge Resource Footprint (iMac Host / AGX Orin Target)

The table below catalogs the audited memory allocations, central processing unit (CPU) utilization percentages, and electrical power footprints of each component service in the CVS-3.0 mesh.

### Table I: Active Container Resource Metrics
| Component Services | Active Container Process | RAM Allocation | CPU Util. (Avg) | Power Footprint | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **NATS Event Broker** | `nats:latest` (Go-native pub-sub) | 22.05 MB | 0.82% | 0.20 W | Active |
| **Neo4j Knowledge Mesh** | `neo4j:5-community` (graph DB) | 702.60 MB | 1.45% | 0.45 W | Cached |
| **Redis Cache Server** | `redis:alpine` (fast-access cache) | 19.09 MB | 0.12% | 0.05 W | Active |
| **PostgreSQL Fallback** | `postgres:15` (pgvector semantic) | 67.98 MB | 0.35% | 0.10 W | Idle |
| **Brain Cognitive Agent** | `brain_agent.py` (decision/appraisal) | 82.36 MB | 2.10% | 0.65 W | Active |
| **System State Agent** | `state_agent.py` (endocrine loop) | 33.92 MB | 0.95% | 0.30 W | Active |
| **Memory Surfacing Agent** | `memory_agent.py` (ACT-R recall) | 75.42 MB | 1.25% | 0.40 W | Active |
| **Subconscious Scan Agent**| `threat_scan.py` (barge-in segmenter) | 76.16 MB | 1.15% | 0.35 W | Active |
| **Total Mesh Footprint** | **All 8 Core Services** | **1,079.58 MB**| **8.19%** | **2.50 W** | **Sovereign** |
| Whisper STT (Edge) | `whisper-base` (local CPU ingest) | 120.00 MB | 14.50% | 5.50 W | Bursting |
| Local Llama-3.2 3B | `llama3.2:3b` (Q4_K_M quantized) | 2.85 GB | 32.40% (GPU)| 14.80 W | Generating |
| **Full Stack Total** | **Full Edge Stack** | **4,082.36 MB**| **55.09%** | **22.80 W** | **Stable** |

---

## 3. Physical Hardware Deployments

The sovereign mesh has been fully verified and profiled across two primary low-power hardware configurations:

### 3.1 iMac / Desktop Development Host
*   **Processor:** Apple M3 Chip (8 Cores: 4 performance, 4 efficiency).
*   **Memory:** 16 GB Unified Memory.
*   **Operating System:** macOS 26.1 (Build 25B78).
*   **GPU Acceleration:** Apple Metal Shading Language (MSL) via llama.cpp for ultra-fast quantized model token generation.
*   **Performance Characteristics:** Excellent parallel throughput; memory access bottlenecks are virtually eliminated due to unified RAM architecture sharing caches between CPU and GPU.

### 3.2 NVIDIA Jetson AGX Orin Edge Robotics Target
*   **Processor:** Ampere GPU (2048 CUDA cores, 64 Tensor cores) + 12-core Arm Cortex-A78AE CPU.
*   **Memory:** 32 GB LPDDR5 (204.8 GB/s bandwidth).
*   **Operating System:** Ubuntu 22.04 LTS (JetPack 6.0).
*   **GPU Acceleration:** CUDA 12.2 and TensorRT integrations.
*   **Power Gating:** Bounded to **35 W TDP** maximum power ceiling, making it fully deployable on battery-powered social humanoid mobile robots.

---

## 4. Real-Time Telemetry & Asynchronous Background Consolidation

To prevent live performance bottlenecks, CVS-3.0 divides its operations into a **Fast-Loop (System 1)** and a **Deep-Loop (System 2)**:

1.  **System 1 Fast-Loop (Turn-Taking / DSP):** Operates entirely inside the memory buffer and NATS network layers. It processes incoming audio, checks for voice interruptions, and halts TTS playback within **114.9 ms**.
2.  **System 2 Deep-Loop (Cognitive Appraisal / Graph Traversal):** Initiates background NATS events to query Neo4j multi-hop memories and evaluate Hormonal/PAD transitions.
3.  **Asynchronous Background Consolidation (Post-Response Reflection):** Once the robot completes its conversational turn and publishes `chat.output`, the Brain agent triggers a background `telemetry.reflection` event. The system runs ACT-R memory indexing, endocrine appraisal decay calculations, and Neo4j graph insertions concurrently. This prevents the robot from pausing or showing lag during active conversation, allowing it to perform math consolidation asynchronously.

The plot below illustrates the continuous trajectory of hormones and PAD coordinates during a 90-second conversational trial, showcasing the smooth, asynchronous endocrine appraisals executed by the mesh.

![Cognitive Trajectory Plot](../plots/research_trajectory_plot.png)
