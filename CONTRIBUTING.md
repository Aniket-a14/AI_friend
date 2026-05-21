# 🤝 Contributing to AI Friend (v6.0.0 / CVS-3.0 Rust Native Edition)

Thank you for contributing to the **Sovereign Mesh**. This project is a high-fidelity cognitive identity emulator designed for 100% local, ultra-low latency execution. We value precision, architectural integrity, and behavioral realism.

---

## 🏗️ 1. Understanding the Sovereign Mesh

Before writing a single line of code, you must understand that AI Friend is a **decentralized system of autonomous agents** synchronized via a central nervous system (**NATS JetStream**).

### The Cognitive Hierarchy
- **Tier 1 (Infrastructure)**: NATS, Neo4j, PostgreSQL, Redis. The "Bones".
- **Tier 2 (Sensory)**: Dual-path STT, Vision, Transport. The "Eyes and Ears".
- **Tier 3 (Cognitive)**: Appraisal, Decision, Learning. The "Mind".
- **Tier 4 (State)**: Emotion (PAD), Memory (ACT-R). The "Personality".
- **Tier 5 (Autonomy)**: Subconscious Engine (internal monologue) and Endocrine system (Cortisol/Dopamine modulation). The "Will".

---

## 🛠️ 2. Development Workflow: The "Solution Architect" Protocol

We follow a strict **Planning-First** philosophy. Non-trivial changes (anything affecting >2 agents or the cognitive core) require a plan.

### Step 1: Research & Planning
1.  **Identify the Boundary**: Determine which agents or services are affected.
2.  **Define the Contract**: If agents need to talk, define the Pydantic model in `backend/app/contracts.py`.
3.  **Latency Budget**: Every cognitive turn has a budget of **<150ms**. If your change adds latency, you must justify it.

### Step 2: Implementation Sequence
1.  **Contract Update**: Modify `contracts.py` and run `backend/scripts/bootstrap/setup_nats_streams.py`.
2.  **Logic Update**: Modify the core service in `app/cognitive/` or `app/vision/`.
3.  **Agent Wiring**: Update the agent in `app/agents/` to handle the new signals.
4.  **Verification**: Run targeted regression tests.

---

## 📂 3. The Project Map: Where to Edit?

| If you want to... | Edit these files/folders |
| :--- | :--- |
| **Change how AI "Sees"** | `backend/app/vision/` (Links, Appraisal, Agent) |
| **Change AI Personality** | `backend/persona/` (JSON seeds) and `app/cognitive/identity.py` |
| **Add a new Voice/Tone** | `backend/app/voice/prosody.py` |
| **Change Memory logic** | `backend/app/state/memory_store.py` (ACT-R) |
| **Add a new NATS Signal** | `backend/app/contracts.py` and `backend/app/nats_streams.py` |
| **Update the Dashboard** | `frontend/components/` and `frontend/app/` |
| **Change Mesh Startup** | `docker-compose.infra.yml` or `docker-compose.prod.yml` |

---

## ⚙️ 4. Running the Mesh for Development

### A. The "Nuclear" Clean Start
If you've modified NATS stream definitions or Database schemas, start fresh:
```powershell
# 1. Wipe everything (including volumes)
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml down -v

# 2. Start Infrastructure
docker compose -f docker-compose.infra.yml up -d

# 3. Hydrate Mesh & Database
cd backend
python scripts/bootstrap/setup_nats_streams.py
cd ../frontend
npx prisma db push
```

### B. Multimodal Development (Vision)
Because Windows screen capture cannot run inside Docker, use the **Host Bridge**:
1.  Ensure **Ollama** is running on your host with `moondream`.
2.  Run the launcher:
    ```powershell
    ./scripts/host/start-vision.ps1
    ```

---

## 🧪 5. Verification: How to Check?

### 1. Linting & Type Safety (Mandatory)
We use **Ruff** for high-speed linting. Your code **must** be clean before pushing.
```bash
cd backend
ruff check . --fix
mypy .
```

### 2. Cognitive Regression Tests
Check that your change didn't break the AI's "Mind" or performance budget:
```bash
# Run all cognitive tests
pytest backend/tests/test_decision.py backend/tests/test_subconscious.py -v

# Run state persistence tests
pytest backend/tests/test_regressions.py -k "state"

# Run the 16-metric isolated performance suite (Mandatory for latency-sensitive PRs)
pytest backend/tests/test_performance.py
```

### 3. Mesh Health Probe
Verify all 22 containers are actually talking to each other:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Health}}"
```

---

## 📜 6. Mesh Communication Contracts (NATS)

All inter-agent talk is strictly typed. **Never** send raw dictionaries. We utilize strict Pydantic models for validation and `orjson` binary serialization for ultra-fast 80,000 OPS network transport.

**To add a new subject:**
1.  Define the `Topic` in `app/contracts.py`.
2.  Define the strictly typed `Pydantic Model` for the payload.
3.  Add the subject to the stream list in `app/nats_streams.py` (using `>` wildcards).

**Example Code Pattern:**
```python
# GOOD: Using a contract with binary serialization
from app.contracts import Topics, MyNewContract

await self.publish(Topics.MY_NEW_SUBJECT, MyNewContract(field="value").model_dump_json().encode("utf-8"))

# BAD: Do not do this
await self.publish("my.raw.subject", {"raw": "data"})
```

---

## 🚀 7. Pull Request Rules

1.  **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `mesh:`, `docs:`.
2.  **Context Ledger**: If you change agent behavior, you **MUST** update `.agents/CONTEXT.md` with a summary of the change.
3.  **No Dead Code**: Remove unused variables and commented-out blocks (unless documenting a design decision).

---

**Designed for Perception. Built for Identity.**  
*The Sovereign Mesh is a living organism. Treat its architecture with respect.* 🦾✨
