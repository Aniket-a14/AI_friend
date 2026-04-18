# 🐳 Sovereign Mesh: Docker Verification Guide (CVS-1.0)

This guide provides the technical procedures for verifying that the **AI Friend Sovereign Mesh** and **CVS-1.0 runtime** are correctly orchestrated, healthy, and communicating with sub-280ms performance.

---

## 1. The Orchestration Pulse
The first step is ensuring all **12 services** (5 Agents + 7 Infra) are running and healthy.

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
**Expected Output**: You should see 12 containers with a status of `Up` or `Healthy`.

### 🛡️ Solid State Hardening Audit
Verify that the mesh is working in "Solid State" (no hardcoded credentials):
```bash
# Check if Neo4j rejected the default password (Expected: Log should NOT show Auth Failure)
docker logs brain_graph | grep "unauthorized"
```

---

## 2. Infrastructure Readiness Check
Before the agents can think, the backbone must be ready.

### A. NATS JetStream (Central Nervous System)
Check if NATS is routing all 9 core subjects:
```bash
# Check if JetStream is active on all subjects
docker exec -it nats_mesh nats stream info AI_MESSAGES
```
*Expect: Subjects list including `system.*`, `memory.*`, `identity.*`, and `knowledge.*`.*

### B. Persistence Seeding (Prisma 7.7.0)
Ensure the AI's "Deep Self" has been successfully hydrated:
```bash
# Check if AgentConfig exists with ID 1
docker exec -it postgres_db psql -U ai_friend -d ai_friend_db -c "SELECT personality FROM agent_configs WHERE id = 1 LIMIT 1;"
```

### C. Ollama & SoVITS
Ensure local inference engines are responsive:
```bash
# Check Ollama
docker exec -it local_brain ollama list

# Check SoVITS API
curl http://localhost:9871/
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
