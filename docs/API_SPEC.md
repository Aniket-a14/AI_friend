# 🔌 API & Messaging Specification (v5.0.0 / CVS-3.0 Rust Native Edition)

This document provides a technical exhaustive breakdown of the external and internal interfaces of the AI Friend **Cognitive Voice System**.

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
    "version": "CVS-3.0",
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

#### `POST /start-session`

Alias for token generation used by legacy or simplified clients.

- **Parameters**: `participant` (string, optional)
- **Response**:

  ```json
  {
    "token": "ey...",
    "url": "http://localhost:7880",
    "status": "session_started"
  }
  ```

#### `GET /health`

Minimal health endpoint for Docker and uptime monitors.

- **Response**:

  ```json
  {
    "status": "healthy",
    "nats": true
  }
  ```

#### `POST /vision/toggle`

Broadcasts a vision source switch to the mesh.

- **Parameters**: `source` must be `screen` or `camera`.
- **Mesh Side Effect**: publishes `vision.control`.

---

## 🌊 Internal Messaging (NATS JetStream)

The "Sovereign Mesh" communicates via a decentralized event bus. In the CVS-3.0 Rust Native Edition, all payloads are strictly validated using Pydantic models and serialized to binary via `orjson` to achieve sub-millisecond, 80,000 OPS network throughput.

### Subject Dictionary

| Subject | Source | Sink | Payload Schema |
| :--- | :--- | :--- | :--- |
| `audio.inbound` | Transport Agent | STT Agent | Raw PCM bytes with metadata headers: `sample_rate`, `channels` |
| `chat.input` | STT Agent | Brain Agent | `{"text": "string", "metadata": {}}` |
| `chat.output` | Brain Agent | Voice Agent | `{"content": "string", "done": bool, "emotion": str, "emotional_intensity": float, "speaking_rate": float}` |
| `audio.perception` | STT Agent | Brain Agent | `{"text": "string", "metadata": {...}, "speculative_intent": {...}}` |
| `audio.stop` | STT/Brain | Voice Agent | `{"interrupt": true, "speculative": bool, "keywords": []}` |
| `audio.resume` | Brain Agent | Voice Agent | `{"reason": "conflict_rejected", "perception_text": "string"}` |
| `audio.stream` | Voice Agent | Signaling | Raw 32kHz PCM bytes with NATS headers |
| `voice.segmentation_feedback` | Voice Agent | Brain Agent | `{"segment_id": str, "latency": float, "drift": float, "override_triggered": bool}` |
| `vision.frames` | Signaling | Vision Agent | `{"image": "base64", "source": "string"}` |
| `vision.control` | Signaling | Vision Agent | `{"command": "string", "source": "string"}` |
| `vision.description` | Vision Agent | Brain Agent | `{"description": "string", "objects": [], "latency_ms": int}` |
| `state.update` | BaseAgent | UI / Logs | `{"agent": "string", "state": "string"}` |

### Detailed Schemas

#### `chat.output` (CVS-3.0 Cognitive Segment)

Sent by the BrainAgent during cognitive streaming. Mapped to the `ChatOutput` Pydantic contract.

```json
{
  "content": "I'm listening, go on.",
  "done": false,
  "emotion": "attentive",
  "emotional_intensity": 0.75,
  "speaking_rate": 1.1,
  "confidence": 0.98,
  "latency_metadata": {
    "start_time": 1713330000.0,
    "hops": [
      {
        "agent": "brain_agent",
        "subject": "chat.output",
        "timestamp": 1713330000.1
      }
    ],
    "source": "stt_agent"
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
  "emotion": "neutral",
  "latency_metadata": {...}
}
```

#### `audio.perception` (Fast Acoustic Perception)

Published by STT after SenseVoice processes a low-latency chunk. This event is not the final transcript. It is a fast perception packet used for emotion bias, acoustic events, and speculative interruption.

```json
{
  "text": "wait",
  "intent": "SPECULATIVE_STOP",
  "keywords": ["wait"],
  "confidence": 0.9,
  "speculative_intent": {
    "name": "SPECULATIVE_STOP",
    "keywords": ["wait"],
    "confidence": 0.9,
    "text": "wait",
    "timestamp": 1713330000.0,
    "utterance_id": "a7f7..."
  },
  "metadata": {
    "text": "wait",
    "emotion": "NEUTRAL",
    "emotional_bias": 0.0,
    "events": [],
    "latency_tier": "fast"
  },
  "timestamp": 1713330000.0
}
```

#### `audio.stop` (Speculative And Final Stop)

The same subject is used for reversible speculative pauses and final confirmed stops.

```json
{
  "interrupt": true,
  "speculative": true,
  "intent": "SPECULATIVE_STOP",
  "keywords": ["stop"],
  "confidence": 0.9,
  "perception_text": "stop",
  "utterance_id": "a7f7..."
}
```

If Whisper confirms the user intended to interrupt, BrainAgent publishes:

```json
{
  "interrupt": true,
  "speculative": false,
  "reason": "confirmed_command",
  "command_text": "stop right now",
  "keywords": ["stop"]
}
```

#### `audio.resume` (False Positive Recovery)

If Whisper contradicts the early perception hypothesis, BrainAgent publishes:

```json
{
  "reason": "conflict_rejected",
  "perception_text": "stop"
}
```

#### `audio.inbound` (Rust Native PCM)

Sent by the transport layer to the Rust STT Agent as raw signed 16-bit PCM bytes. JSON/base64 audio payloads are rejected on this subject to enforce the LAN-only security boundary.

NATS metadata:

```json
{
  "sample_rate": 48000,
  "channels": 1,
  "source": "livekit"
}
```

#### `audio.stream` (CVS-3.0 Raw 32kHz PCM)

Sent by the VoiceAgent directly from the Signal Runtime. In the optimized path this is raw binary PCM, not JSON.

NATS headers:

```json
{
  "X-Payload-Format": "binary/raw-pcm",
  "X-Latency-Meta": "{\"start_time\":1713330000.0,\"hops\":[...]}"
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
| `speculative_pause` | Voice | Fast perception requested a reversible pause. |
| `error` | All | Exception caught; failsafe triggered. |

---

## 🧾 Expression Contract

Text content may contain timing markers:

- `<pause=300ms>`
- `<hesitate>`

Text content should not contain `<emotion ...>` wrappers. The runtime strips legacy emotion wrappers before TTS, but new integrations should carry affect as structured metadata (`emotion`, `emotional_intensity`, `speaking_rate`) rather than as spoken control text.
