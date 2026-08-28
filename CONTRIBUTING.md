# 🤝 Contributing to AI Friend

Thank you for contributing. This project is a local-first, state-driven AI
friend platform built on a mesh of specialized agents. We value precision,
architectural integrity, and honesty about what actually works — see
`CLAUDE.md` and `.agents/CONTEXT.md` (the engineering ledger) before making
architecture or behavior changes; where any doc disagrees with the ledger,
the ledger is right.

---

## 🏗️ 1. Understanding the mesh

Before writing a single line of code, you must understand that AI Friend is a
**decentralized system of autonomous agents** synchronized via a central
nervous system (**NATS JetStream**), not a monolith with internal function
calls.

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
3.  **Latency awareness**: A cognitive turn can legitimately run long (`LLM_STREAM_MAX_SECONDS`, 120s) — `BaseAgent.subscribe` only acks after the callback returns, so a long-running consumer needs to be reasoned about against JetStream's AckWait, not against a fixed latency budget. See `CLAUDE.md`'s "Ack model matters here" note before touching long-running consumers. No end-to-end latency number is currently measured against real infrastructure — see `.agents/CONTEXT.md` for what's actually been proven.

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
| **Change AI Personality** | `backend/app/personality.json` / `history.json` (seeds), `backend/app/persona/profile.py` (numeric tiers) and `app/cognitive/identity.py` (narrative) |
| **Add a new Voice/Tone** | `backend/crates/voice-agent/` (Rust; prosody is derived from the affect vector in `crates/contracts`) |
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
The Vision Agent must run on the host on Windows and macOS — Docker Desktop's
Linux VM has no route to the host display or webcam (see the Vision Agent row
in `README.md`'s agent table for why). Run it natively instead:
```bash
pip install -r backend/requirements-ai.txt   # mss + opencv-python
NATS_URL=nats://127.0.0.1:4222 python -m app.vision.agent
```
On Linux, the containerized path works: uncomment the `devices`/X11 entries
for `vision_agent` in `docker-compose.prod.yml` and run
`docker compose --profile vision up vision_agent`.

---

## 🧪 5. Verification: How to Check?

The virtualenv lives at the **repo root** (`.venv`), but pytest must run from
`backend/` — see `CLAUDE.md`'s Commands section for the full explanation and
the Windows-path equivalents.

### 1. Linting & Type Safety (Mandatory)
```bash
cd backend
../.venv/bin/python -m ruff check .
../.venv/bin/python -m mypy app
```
`mypy`/`radon`/`bandit` currently run in CI as report-only jobs against a
committed baseline (`backend/tools/quality/baseline/`) — see `CLAUDE.md` and
the roadmap's Phase 7 for the ongoing triage; don't fix an unrelated finding
opportunistically while touching a file for something else, note it instead.

### 2. Regression Tests
```bash
cd backend
../.venv/bin/python -m pytest -q --junit-xml=<scratch>/res.xml   # full suite
../.venv/bin/python -m pytest -k "decision or subconscious"       # targeted
```
Pytest's terminal summary is unreliable in this repo — parse the JUnit XML
for the real pass/fail count rather than trusting the dots; see `CLAUDE.md`
for why and how to recover a swallowed traceback.

### 3. Mesh Health Probe
Verify containers for your chosen mode are actually healthy:
```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps
```

---

## 📜 6. Mesh Communication Contracts (NATS)

All inter-agent talk is strictly typed. **Never** send raw dictionaries. Every
subject has a Pydantic model in `backend/app/contracts.py`, validated at the
publish and subscribe boundary rather than trusted implicitly.

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

1.  **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
2.  **Context Ledger**: If you change agent behavior, you **MUST** update `.agents/CONTEXT.md` with a summary of the change — what changed, why, how it was verified, and an explicit "NOT done" section. Existing entries show the expected style.
3.  **No Dead Code**: Remove unused variables and commented-out blocks (unless documenting a design decision).
4.  **Mutation-test new tests**: deliberately break the code a new test covers and confirm the test actually fails — a test that passes either way is asserting nothing.

Thank you for contributing.
