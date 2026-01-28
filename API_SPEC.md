# API Specification 📖🔌

This document details the technical interfaces for the Pankudi AI assistant.

## 📡 WebSocket Audio Protocol
**Endpoint**: `/ws/audio`  
**Protocol**: Binary (16-bit PCM)

The WebSocket provides bi-directional, real-time audio streaming.

### 1. Client -> Server (User Voice)
- **Format**: Raw 16-bit PCM chunks.
- **Sample Rate**: 16,000 Hz (Mono).
- **Chunk Size**: Recommended 512-1024 samples per message.

### 2. Server -> Client (AI Voice)
- **Format**: Raw 16-bit PCM chunks.
- **Sample Rate**: 24,000 Hz (Mono).
- **Logic**: Streamed as a series of binary messages.

## 🚥 REST Endpoints

### Get Current Status
**GET** `/status`

Returns the current lifecycle state of the AI.

**Response**:
```json
{
  "state": "IDLE" | "LISTENING" | "THINKING" | "SPEAKING",
  "reasoning": "Optional hidden monologue snippet"
}
```

## 🔄 Lifecycle States

| State | Source | Description |
|-------|--------|-------------|
| `IDLE` | Backend | Waiting for wake word or initial connection. |
| `LISTENING` | Backend | Actively transcribing user speech via Whisper. |
| `THINKING` | Backend | LLM is generating tokens. |
| `SPEAKING` | Backend | ElevenLabs audio is being streamed to client. |

## 🛠️ Communication Flow

1. **Connection**: Frontend opens WebSocket to `/ws/audio`.
2. **Streaming**: Frontend continuously streams microphone data.
3. **Detection**: Backend VAD detects speech -> switches to `LISTENING`.
4. **Processing**: Backend finishes STT -> LLM starts streaming -> switches to `THINKING`.
5. **Output**: LLM sentence ready -> TTS starts streaming -> switches to `SPEAKING`.
6. **Reset**: Audio finishes -> switches back to `IDLE` (or auto-resumes listening).
