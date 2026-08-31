# Configuration Reference

AI Friend is configured via environment variables defined in `.env` (copied from `.env.example`).

---

## Core Operational Settings

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DEBUG` | `false` | Enables verbose debug logging and diagnostics. |
| `ENVIRONMENT` | `production` | Deployment mode (`development` / `production`). Production enforces secret presence. |
| `MOCK_LLM_TEXT` | `false` | Set to `true` for hermetic testing without running a live LLM model. |
| `LLM_PROVIDER` | `ollama` | LLM inference backend (`ollama` or `anthropic`). |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Endpoint for host-native Ollama server. |
| `OLLAMA_MODEL` | `llama3.2:3b` | Target conversational LLM model tag. |

---

## Database & Persistence Endpoints

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://ai_friend:ai_friend@127.0.0.1:5432/ai_friend` | Primary Postgres + pgvector connection string. |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Relational Knowledge Graph Bolt endpoint. |
| `NEO4J_USER` | `neo4j` | Neo4j database username. |
| `NEO4J_PASSWORD` | `your_secure_password` | Neo4j database password. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Ephemeral state cache and distributed turn lock broker. |
| `QDRANT_HOST` | `127.0.0.1` | Vector similarity engine host. |
| `QDRANT_PORT` | `6333` | Vector similarity engine HTTP port. |

---

## NATS JetStream Signal Mesh

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `NATS_URL` | `nats://127.0.0.1:4222` | Core message bus connection URI. |
| `NATS_USER` | `ai_friend` | NATS client authentication username. |
| `NATS_PASSWORD` | `nats_secret_password` | NATS client authentication password. |

---

## Voice & Audio Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `SOVITS_URL` | `http://127.0.0.1:9880` | Self-hosted GPT-SoVITS synthesis service. |
| `REF_AUDIO_PATH` | `output/sample_en_gold.wav` | Path to reference WAV clip for voice cloning. |
| `REF_TEXT` | `"Hello, I am ready to talk."` | Exact transcript of reference voice audio clip. |
| `REF_CALM_AUDIO_PATH` | (optional) | Audio reference for Calm emotional state. |
| `REF_WARM_AUDIO_PATH` | (optional) | Audio reference for Warm emotional state. |
| `REF_CONCERNED_AUDIO_PATH` | (optional) | Audio reference for Concerned emotional state. |
| `REF_EXCITED_AUDIO_PATH` | (optional) | Audio reference for Excited emotional state. |

---

## LiveKit WebRTC Gateway

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `LIVEKIT_URL` | `ws://127.0.0.1:7880` | Internal LiveKit SFU WebSocket endpoint. |
| `LIVEKIT_PUBLIC_URL` | `ws://127.0.0.1:7880` | Publicly reachable LiveKit SFU endpoint for browser clients. |
| `LIVEKIT_API_KEY` | `devkey` | API authentication key for JWT token issuance. |
| `LIVEKIT_API_SECRET` | `secret` | API authentication secret for JWT token issuance. |

---

## Cloud Fallback (Optional)

When running on resource-constrained hardware without local GPU/Ollama:

```ini
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

> [!NOTE]
> Enabling cloud fallback transmits conversation transcripts to a third party. Local inference is always the zero-leak default.
