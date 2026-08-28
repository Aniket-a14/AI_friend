# Installation & Prerequisites

AI Friend runs as a self-hosted, local-first multi-agent mesh. It is designed to run entirely on your own workstation or home server with zero mandatory cloud dependencies.

---

## System Requirements

| Specification | Minimum Tier (CPU Baseline) | Recommended Tier (Apple Silicon / GPU) |
| :--- | :--- | :--- |
| **Operating System** | macOS 13+ (Apple Silicon), Linux (Ubuntu 22.04+), Windows (WSL2) | macOS 14+ (M1/M2/M3), Linux with NVIDIA GPU (CUDA 12+) |
| **RAM / Unified Memory** | 16 GB Unified Memory / Host RAM | 16 GB - 32 GB Unified Memory or 12GB+ Dedicated VRAM |
| **Processor** | 8-core modern x86_64 CPU (AVX2 / AVX-512) | Apple Silicon M-Series or 8-core CPU + NVIDIA RTX 3060/4060+ |
| **Storage** | 25 GB free disk space (models + databases) | 50 GB fast NVMe SSD storage |
| **Network** | Loopback only (zero external internet required after setup) | Loopback only |

---

## Prerequisites

Before starting the stack, ensure the following prerequisites are installed:

1. **Docker & Docker Compose**:
   - [Install Docker Desktop for macOS / Windows](https://www.docker.com/products/docker-desktop/) or `docker-ce` + `docker-compose-plugin` on Linux.
   - Ensure Docker is allocated at least **8GB RAM** (12GB recommended on macOS Docker settings).

2. **Ollama (Host-Native LLM Engine)**:
   - [Download & Install Ollama](https://ollama.com).
   - Start Ollama host-natively:
     ```bash
     ollama serve
     ```
   - Pull the default conversational model:
     ```bash
     ollama pull llama3.2:3b
     ```

3. **Python 3.11+ & Rust (Optional for source development)**:
   - Python virtual environment for running CLI scripts and tests.
   - Rust toolchain (`rustup`) if modifying the `stt-agent` or `voice-agent` native binaries.

---

## One-Command Quick Boot

Clone the repository and launch the stack using the bundled orchestration launcher:

```bash
# 1. Clone the repository
git clone https://github.com/Aniket-a14/AI_friend.git
cd AI_friend

# 2. Configure environment defaults
cp .env.example .env

# 3. Launch the full mesh
./start.sh
```

---

## Launch Modes

The `./start.sh` launcher supports tailored operational profiles depending on your hardware:

```bash
./start.sh              # Default: launches full multimodal mesh (Voice, Brain, STT, LiveKit)
./start.sh light        # Cognitive-only: runs Brain + Memory without real-time STT/TTS
./start.sh heavy        # Cognitive + local Whisper STT, with pre-synthesized voice
./start.sh full         # Full stack with live GPT-SoVITS voice cloning
./start.sh full --vision # Full stack + Moondream visual appraisal (Linux host only)
```

### Profile Comparison

* **`light` Mode**: Ideal for lower-spec laptops or remote headless servers. Memory footprint is $< 4 \text{ GB}$.
* **`heavy` Mode**: Perfect for text-first interactions with natural speech transcription.
* **`full` Mode**: The complete embodied companion experience with real-time cloned voice synthesis.
* **`full --vision` Mode**: Adds continuous Moondream VLM screen and camera appraisal.

---

## Preflight Verification

Once launched, verify that all containerized agents are healthy:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.prod.yml ps
```

Expected healthy services:
* `nats`: Signal bus message broker (Port 4222)
* `postgres`: Core identity & episodic vector memory (Port 5432)
* `neo4j`: Relational knowledge graph (Port 7687 / 7474)
* `redis`: Ephemeral state cache & turn locks (Port 6379)
* `qdrant`: Semantic vector index (Port 6333)
* `local_voice`: GPT-SoVITS voice synthesis server (Port 9880)
* `local_sfu`: LiveKit WebRTC media server (Port 7880)
* `brain_agent`, `voice_agent`, `stt_agent`, `transport_agent`, `subconscious_agent`: Core workers

---

Next: [Quickstart Guide](/docs/getting-started/quickstart) to author your friend's persona.
