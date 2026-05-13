# AI Friend Backend: Sovereign Mesh Core 🧠🔊

The decentralized, high-performance core of the AI Friend platform. This service orchestrates a mesh of specialized micro-agents through a **NATS JetStream** event bus.

## 🏗️ Architecture: Sovereign Mesh v3.0

The backend has evolved from a monolith into a **distributed agent mesh**. Each capability is a dedicated agent running as an independent process or container.

### Core Agents

- **Signaling Server (`main.py`)**: Manages WebRTC/WebSocket handshakes and state synchronization.
- **Brain Agent**: The reasoning engine (Ollama/Gemini) that processes context and calls tools.
- **STT Agent**: Real-time voice-to-text using Faster-Whisper with Silero VAD.
- **Voice Agent**: Expressive text-to-speech synthesis (GPT-SoVITS).
- **Vision Agent**: Synchronizes 1 FPS screen/camera situational awareness.
- **Transport Agent**: Low-latency WebRTC ↔ NATS audio bridge.

## 🚀 Key Features

- **⚡ NATS JetStream Integration**: Microsecond-latency internal communication with reliable message persistence.
- **🏎️ Audio Optimization**: High-fidelity resampling using `soxr` for sub-300ms vocal response loops.
- **🔒 Enterprise Quality**: 100% compliant with `ruff` and `flake8` standards.
- **📦 Tiered Builds**: Optimized Docker images (`slim` for logic, `full` for AI weights).

## ⚙️ Direct Deployment (Local Development)

### Prerequisites

- Python 3.13+
- NATS Server (with JetStream enabled: `nats-server -js`)
- Ollama (running locally)

### Installation

1. **Navigate to backend**: `cd backend`
2. **Create venv**: `python -m venv .venv`
3. **Activate**: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux)
4. **Install Base**: `pip install -r requirements-base.txt`
5. **Install AI (Optional)**: `pip install -r requirements-ai.txt` (Required for STT/Voice agents)

### Launching the Mesh

You can start individual agents or use the master orchestrator:

```bash
# Start the signaling hub (FastAPI) and core logic
python main.py

# Or start agents individually
python -m app.agents.brain_agent
python -m app.stt.agent
python -m app.voice.agent
```

## 🧪 Testing & Verification

We use `pytest` for integration testing against the NATS mesh:

```bash
# Run tests
pytest tests/test_mesh.py
```

## 📂 Project Structure

- `app/agents/`: Specialized micro-agent implementations.
- `app/knowledge/`: GraphRAG and Vector storage logic (Neo4j/Postgres).
- `app/llm/`: Local LLM clients (Ollama).
- `app/tts/`: Local voice synthesis clients (GPT-SoVITS).
- `scripts/`: Infrastructure setup and utility scripts.
- `tools/`: Dynamic tool registry for the Brain agent.

---
**Standardized on Sovereign Mesh v3.0 Pattern.**
