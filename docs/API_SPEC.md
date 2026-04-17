# 🔌 API & Messaging Specification

This document provides a technical exhaustive breakdown of the external and internal interfaces of the AI Friend Sovereign Mesh.

---

## 🌎 External Interfaces (Signaling Server)

The Signaling Server (FastAPI) acts as the gateway to the mesh.

### 1. REST Endpoints

#### `GET /status`
Health check and versioning info.
- **Response**:
  ```json
  {
    "status": "healthy",
    "version": "3.0.0",
    "uptime": 1234.5
  }
  ```

#### `GET /token`
Generates a LiveKit access token for WebRTC sessions.
- **Parameters**: `identity` (string)
- **Response**:
  ```json
  {
    "token": "ey..."
  }
  ```

---

## 🌊 Internal Messaging (NATS JetStream)

The "Sovereign Mesh" communicates via a decentralized event bus.

### Subject Dictionary

| `audio.inbound` | Signaling | STT Agent | `{"audio": "base64", "sample_rate": int, "latency_metadata": {}}` |
| `chat.input` | STT Agent | Brain Agent | `{"text": "string", "latency_metadata": {}}` |
| `chat.output` | Brain Agent | Voice Agent | `{"content": "string", "done": bool, "state": {}, "latency_metadata": {}}` |
| `audio.stream` | Voice Agent | Signaling | `{"audio": "base64", "format": "pcm", "done": bool, "latency_metadata": {}}` |
| `audio.stop` | STT Agent | Voice Agent | `{"interrupt": true}` |
| `vision.frames` | Signaling | Brain Agent | `{"image": "base64", "source": "string"}` |
| `state.update` | BaseAgent | UI / Logs | `{"agent": "string", "state": "string"}` |

### Detailed Schemas

#### `chat.output` (Incremental / Sentence-Stream)
Sent by the Brain Agent during sentence-level streaming.
```json
{
  "content": "The quick brown fox.",
  "done": false,
  "state": {
    "emotion": "joy",
    "energy": 0.8
  },
  "latency_metadata": {
    "start_time": 1713330000.0,
    "hops": ["brain_agent"]
  }
}
```

#### `chat.output` (Final)
Sent when the entire cognitive process is complete.
```json
{
  "content": "",
  "done": true,
  "full_response": "The entire response text.",
  "state": {...},
  "latency_metadata": {...}
}
```

#### `audio.stream` (PCM Audio Buffer)
Sent by the Voice Agent. Format is raw 16-bit PCM.
```json
{
  "audio": "UklGR...",
  "format": "pcm",
  "sample_rate": 22050,
  "done": false,
  "latency_metadata": {...}
}
```

---

## ⚙️ Agent State Machine

All agents broadcast their internal state to `state.update`.

| State | Source | Trigger |
| :--- | :--- | :--- |
| `idle` | All | Default state when not processing. |
| `listening` | STT | Audio energy detected above threshold. |
| `thinking` | Brain | Received `chat.input`, running LLM inference. |
| `speaking` | Voice | Generating audio buffers. |
| `error` | All | Exception caught during processing. |
