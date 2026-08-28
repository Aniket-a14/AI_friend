# WebSocket Signaling & Streaming Protocol

Real-time bidirectional text streaming and session signaling are exposed over FastAPI WebSockets (`backend/app/api/chat.py`).

---

## 1. Web Chat Bridge Endpoint

* **URL**: `ws://localhost:8000/api/chat/ws`
* **Authentication**: Session auth (`require_session_auth` and LAN check `require_lan_client`).

### Client $\to$ Server (Message Inbound)
Send clean UTF-8 text strings directly:
```text
"Hey, how was your day?"
```
The server assigns a unique `turn_id` (UUIDv4) and publishes a typed `ChatInput` model onto the NATS JetStream `chat.input` topic.

---

### Server $\to$ Client (Streaming Token Dispatch)
The server streams structured JSON objects matching `ChatOutput`:

```json
{
  "content": "Pretty good! Just finished reviewing some memory nodes.",
  "turn_id": "4a72d96c-824f-4d92-965a-0294719bb810",
  "done": false,
  "proactive": false,
  "affect": {
    "valence": 0.35,
    "arousal": 0.40,
    "dominance": 0.60,
    "cortisol": 0.15,
    "dopamine": 0.70
  }
}
```

When the LLM finishes generating words for the active turn, the final packet arrives with `"done": true`.

---

## 2. LiveKit WebRTC Audio Channel (Voice & Visemes)

For real-time low-latency voice streaming and instant interruption, audio does not travel over plain WebSockets. Instead, it connects to the local LiveKit SFU:

* **SFU Port**: `7880` (`http://localhost:7880`)
* **Room Name**: Configured per session (default: `ai-friend-room`)
* **Inbound Audio Track**: 16kHz Mono PCM from user microphone $\to$ `stt-agent` (Rust)
* **Outbound Audio Track**: 32kHz Stereo PCM from `voice-agent` (Rust) $\to$ browser speaker
* **Data Channel**: LiveKit Lossy Data Channel streaming real-time viseme phonetic amplitude packets (`audio.playback.visemes`) at 60 FPS for synchronized avatar lip sync.
