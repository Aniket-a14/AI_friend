# NATS Topics & Contracts

The inter-agent communication mesh is defined by strictly typed Pydantic models in `backend/app/contracts.py` over NATS JetStream topics. Using these contracts at publish/subscribe boundaries eliminates key-rename and type-mismatch bugs at runtime.

---

## Core Subject Routing Table

| Subject Name | Topics Enum | Publisher Agent | Subscriber Agents | Payload Contract Class |
| :--- | :--- | :--- | :--- | :--- |
| `audio.inbound` | `AUDIO_INBOUND` | `transport_agent` | `stt-agent` (Rust) | Raw binary PCM (16kHz mono) |
| `audio.stop` | `AUDIO_STOP` | `stt-agent` (Rust) | `voice-agent` (Rust) | `AudioStop` |
| `audio.perception` | `AUDIO_PERCEPTION` | `stt-agent` (Rust) | `brain_agent` | `AudioPerception` |
| `chat.input` | `CHAT_INPUT` | `main.py` / `talk.py` | `brain_agent` | `ChatInput` |
| `chat.output` | `CHAT_OUTPUT` | `brain_agent` | `voice-agent`, `main.py` | `ChatOutput` |
| `audio.playback` | `AUDIO_STREAM` | `voice-agent` (Rust) | `transport_agent` | Raw binary PCM (32kHz) |
| `audio.playback.visemes` | `AUDIO_PLAYBACK_VISEMES` | `voice-agent` (Rust) | `transport_agent` | `AudioPlaybackVisemes` |
| `audio.playback.progress` | `AUDIO_PLAYBACK_PROGRESS` | `voice-agent` (Rust) | `brain_agent` | `AudioPlaybackProgress` |
| `vision.description` | `VISION_DESCRIPTION` | `vision_agent` | `brain_agent` | `VisionDescription` |
| `state.presence` | `SESSION_PRESENCE` | `transport_agent` | `subconscious_agent` | `SessionPresence` |
| `state.subconscious` | `STATE_SUBCONSCIOUS` | `subconscious_agent` | `brain_agent` | `StateSubconscious` |
| `memory.surfaced` | `MEMORY_SURFACED` | `subconscious_agent` | `brain_agent` | `MemorySurfaced` |

---

## Authenticated Schema Definitions (`backend/app/contracts.py`)

### `ChatInput`
```python
class ChatInput(BaseModel):
    model_config = {"extra": "allow"}
    text: str
    utterance_id: str | None = None
    turn_id: str | None = None
    modality: str = "text"  # "text" | "voice" | "mock"
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### `ChatOutput`
```python
class ChatOutput(BaseModel):
    model_config = {"extra": "allow"}
    content: str
    turn_id: str
    done: bool = False
    proactive: bool = False
    affect: ChatOutputAffect | None = None
```

### `AudioPlaybackVisemes`
```python
class AudioPlaybackVisemes(BaseModel):
    model_config = {"extra": "allow"}
    target_level: float
    viseme_id: int
    turn_id: str
    timestamp: float
```

### `SessionPresence`
```python
class SessionPresence(BaseModel):
    model_config = {"extra": "allow"}
    client_id: str
    status: str  # "connected" | "disconnected" | "speaking"
    timestamp: float
```
