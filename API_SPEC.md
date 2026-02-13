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

### 2. WebSocket Endpoint

#### `WS /ws`
The high-speed binary interface for real-time audio and vision.

**Inbound (Client -> Server):**
- **Type**: Binary (Int16Array)
- **Format**: Raw PCM, 16-bit, 48kHz (default)
- **Logic**: Streamed directly to `audio.inbound` on NATS.

**Outbound (Server -> Client):**
- **Type**: Binary / JSON
- **Content**: Dispatched from `audio.stream` and `chat.output`.

---

## 🌊 Internal Messaging (NATS JetStream)

The "Sovereign Mesh" communicates via a decentralized event bus.

### Subject Dictionary

| Subject | Publisher | Subscriber | Payload Schema |
| :--- | :--- | :--- | :--- |
| `audio.inbound` | Signaling | STT Agent | `{"audio": "base64", "sample_rate": int}` |
| `chat.input` | STT Agent | Brain Agent | `{"text": "string"}` |
| `chat.output` | Brain Agent | Voice Agent | `{"chunk": "string", "done": bool}` |
| `audio.stream` | Voice Agent | Signaling | `{"audio": "base64", "done": bool}` |
| `audio.stop` | STT Agent | Voice Agent | `{"interrupt": true}` |
| `vision.frames` | Signaling | Brain Agent | `{"image": "base64", "source": "string"}` |
| `state.update` | BaseAgent | UI / Logs | `{"agent": "string", "state": "string"}` |

### Detailed Schemas

#### `chat.output` (Incremental)
Sent by the Brain Agent during LLM streaming.
```json
{
  "chunk": "The",
  "done": false
}
```

#### `chat.output` (Final)
Sent when the response is complete.
```json
{
  "chunk": "",
  "done": true,
  "full_response": "The full text of the AI response."
}
```

#### `audio.stream` (Audio Buffer)
Sent by the Voice Agent.
```json
{
  "audio": "UklGR...",
  "format": "wav",
  "sample_rate": 22050,
  "done": false
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
