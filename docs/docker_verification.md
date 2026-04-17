# 🐳 Sovereign Mesh: Docker Verification Guide (CVS-1.0)

This guide provides the technical procedures for verifying that the **AI Friend Sovereign Mesh** and **CVS-1.0 runtime** are correctly orchestrated, healthy, and communicating with sub-280ms performance.

---

## 1. The Orchestration Pulse
The first step is ensuring all containers are running and healthy.

```bash
docker compose ps
```
**Expected Output**: You should see ~10 containers (NATS, Postgres, Neo4j, Redis, LiveKit, Ollama, SoVITS, and all Agents) with a status of `Up` or `Healthy`.

---

## 2. Infrastructure Readiness Check
Before the agents can think, the backbone must be ready.

### A. NATS JetStream (Central Nervous System)
Check if NATS is accepting connections and Monitoring is active:
```bash
# Check monitoring endpoint
curl http://localhost:8222/varz

# Check if JetStream is active on audio subjects (CVS Requirement)
docker exec -it nats_mesh nats stream info audio
```

### B. Ollama (The Brain's Processor)
Ensure models are loaded and accessible:
```bash
docker exec -it local_brain ollama list
```
*Expected: `llama3.2:1b` and `llama3.2:3b` should be in the list.*

### C. Neo4j (Memory Graph)
Check if the Bolt port is active:
```bash
docker logs brain_graph | grep "Remote interface available at"
```

---

## 3. Agent Connectivity Verification
Each agent must successfully connect to the NATS bus to participate in the mesh.

### Tail Agent Logs
Watch for the "Connected to mesh" and "Subscribed to" log entries:
```bash
# Tail Brain Agent
docker logs -f brain_agent

# Tail Voice Agent (Check for NATS Sync)
docker logs -f voice_agent | grep "NATS Sync"
```

---

## 4. Signal Mesh Monitoring (Deep-Dive)

### Watch Conversation Signals
```bash
# Watch transcription inputs arriving from the mic
docker exec -it nats_mesh nats sub "chat.input"

# Watch the brain's reasoning output (CVS Metadata)
docker exec -it nats_mesh nats sub "chat.output"
```

### Watch Pulse Telemetry (CVS-1.0 Closed-Loop)
```bash
# Watch the BrainAgent adjusting to VoiceAgent feedback
docker exec -it nats_mesh nats sub "voice.segmentation_feedback"
```

---

## 5. The Docker Smoke-Test (Benchmark)
Run the latency benchmark script *inside* the Docker context to measure genuine production performance.

```bash
docker exec -it brain_agent python scripts/bench_latency_perceptual.py
```
**Success Criteria**:
- `✅ BENCHMARK COMPLETE`
- `Total Perceived Latency: <280ms`.
- `Jitter Recovery Rate: 100%`.

---

## 🍏 Apple Silicon (Mac) Note
If running on an M-series Mac via Docker Desktop:
1.  **Memory**: Go to **Settings > Resources** and ensure at least **12GB RAM** is allocated.
2.  **Metal**: Verify that "Use Rosetta" is disabled for maximum native ARM64 performance in STT/TTS containers.

---

**Designed for Perceptual Mastery.**
