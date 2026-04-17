# 🔌 API & Messaging Specification (CVS-1.0)

This document provides a technical exhaustive breakdown of the external and internal interfaces of the AI Friend **Cognitive Voice System (CVS-1.0)**.

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
    "version": "CVS-1.0",
    "uptime": 1234.5,
    "runtime": "Perceptual Mastery"
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

The "Sovereign Mesh" communicates via a decentralized event bus. CVS-1.0 utilizes high-speed pulse telemetry for real-time behavior adjustment.

### Subject Dictionary

| Subject | Source | Sink | Payload Schema |
| :--- | :--- | :--- | :--- |
| `audio.inbound` | Signaling | STT Agent | `{"audio": "base64", "sample_rate": 16000}` |
| `chat.input` | STT Agent | Brain Agent | `{"text": "string", "metadata": {}}` |
| `chat.output` | Brain Agent | Voice Agent | `{"content": "string", "done": bool, "metadata": {"emotion": str, "intensity": float, "speaking_rate": float}}` |
| `audio.stream` | Voice Agent | Signaling | `{"audio": "base64", "format": "raw", "sample_rate": 32000, "done": bool}` |
| `voice.segmentation_feedback` | Voice Agent | Brain Agent | `{"segment_id": str, "latency": float, "drift": float, "override_triggered": bool}` |
| `audio.stop` | STT Agent | Voice Agent | `{"interrupt": true}` |
| `vision.frames` | Signaling | Brain Agent | `{"image": "base64", "source": "string"}` |
| `state.update` | BaseAgent | UI / Logs | `{"agent": "string", "state": "string"}` |

### Detailed Schemas

#### `chat.output` (CVS-1.0 Cognitive Segment)
Sent by the BrainAgent during cognitive streaming.
```json
{
  "content": "I'm listening, go on.",
  "done": false,
  "metadata": {
    "emotion": "attentive",
    "intensity": 0.75,
    "speaking_rate": 1.1,
    "confidence": 0.98
  },
  "latency_metadata": {
    "start_time": 1713330000.0,
    "hops": ["brain_agent"]
  }
}
```

#### `chat.output` (Final Response)
Sent when the entire cognitive process is complete for history persistence.
```json
{
  "content": "",
  "done": true,
  "full_response": "The entire response text.",
  "metadata": {...},
  "latency_metadata": {...}
}
```

#### `audio.stream` (CVS-1.0 Raw 32kHz PCM)
Sent by the VoiceAgent directly from the Signal Runtime.
```json
{
  "audio": "UklGR...",
  "format": "raw",
  "sample_rate": 32000,
  "bit_depth": 16,
  "channels": 1,
  "done": false,
  "latency_metadata": {...}
}
```

#### `voice.segmentation_feedback` (Closed-Loop Pulse)
Real-time telemetry used by the BrainAgent to adjust semantic chunking.
```json
{
  "segment_id": "chunk_94a2",
  "processing_latency_ms": 42.5,
  "temporal_drift": 0.002,
  "queue_depth": 1,
  "override_triggered": false
}
```

---

## ⚙️ Agent State Machine (Temporal Mode)

All agents broadcast their internal state to `state.update`.

| State | Source | Trigger |
| :--- | :--- | :--- |
| `idle` | All | Default state when not processing. |
| `listening` | STT | Audio energy detected above threshold. |
| `thinking` | Brain | Received `chat.input`, running semantic segmentation. |
| `buffering` | Voice | Filling jitter buffer to safe watermark. |
| `speaking` | Voice | Emitting PCM signals; active Atomic State. |
| `error` | All | Exception caught; failsafe triggered. |
