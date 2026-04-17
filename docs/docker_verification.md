# 🐳 Sovereign Mesh: Docker Verification Guide

This guide provides the technical procedures for verifying that the **AI Friend Sovereign Mesh** is correctly orchestrated, healthy, and communicating with sub-300ms performance.

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
Check if NATS is accepting connections and monitoring is active:
```bash
# Check monitoring endpoint
curl http://localhost:8222/varz
```
*Look for `"jetstream": { ... }` in the JSON response.*

### B. Ollama (The Brain's Processor)
Ensure models are loaded and accessible:
```bash
docker exec -it local_brain ollama list
```
*Expected: `qwen2.5:7b` and `llama3.2:1b` should be in the list.*

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

# Tail STT Agent
docker logs -f stt_agent
```

---

## 4. Signal Mesh Monitoring (Deep-Dive)
To go beyond "Is it running?" and see "Is it talking?", use the NATS CLI inside the mesh.

### Watch Conversation Signals
```bash
# Watch transcription inputs arriving from the mic
docker exec -it nats_mesh nats sub "chat.input"

# Watch the brain's reasoning output
docker exec -it nats_mesh nats sub "chat.output"
```

### Watch Audio Stream Buffers
```bash
# Watch generated PCM chunks flowing to the speaker
docker exec -it nats_mesh nats sub "audio.stream"
```

---

## 5. The Docker Smoke-Test (Benchmark)
Run the latency benchmark script *inside* the Docker context to measure genuine production performance.

```bash
docker exec -it brain_agent python scripts/bench_latency.py
```
**Success Criteria**:
- `✅ BENCHMARK COMPLETE` message.
- `Total Latency: <300ms`.

---

## 🌍 Networking Note
If agents are failing to connect, verify your `.env` variables:
- `NATS_URL` should be `nats://nats_mesh:4222` within the docker network.
- `OLLAMA_URL` should be `http://local_brain:11434` or `http://host.docker.internal:11434` depending on your setup.

---

**Designed for Visibility. Built for Stability.**
