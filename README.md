# AI Assistant - Human-like Voice Companion 🎙️✨

AI Assistant is a sophisticated, real-time voice-interactive AI assistant designed to feel like a natural companion rather than a robotic utility. It features **near-instantaneous responses**, **expressive vocal cues**, and **cross-platform support** for both desktop and mobile.

## 🌟 Key Features

- **⚡ Near-Instant Response**: Full streaming pipeline (Gemini tokens -> Sentence buffering -> ElevenLabs voice chunks) ensures negligible latency.
- **🎭 Human-like Soul**: Powered by a dynamic persona engine that "thinks" internally before speaking, using emotional context and vocal tags like `[laughs]`, `[sighs]`, and `[whispers]`.
- **📱 Mobile & Web Ready**: Decoupled from local hardware; audio is captured and played directly in the browser via Web Audio API and WebSockets.
- **☁️ Cloud Persistence**: Syncs personality, memory, and history with Supabase (PostgreSQL) for a persistent "soul" across sessions.
- **🐳 Production Ready**: Fully containerized with Docker and hardened with security best practices (CORS, HSTS).

## 🏗️ Architecture

### 1. Backend (Python/FastAPI)
The core logic engine:
- **Intelligence**: Google Gemini 2.5 Pro with internal emotional monologue.
- **Voice**: ElevenLabs v3 for ultra-realistic speech synthesis.
- **STT**: Faster Whisper for low-latency speech transcription.
- **Store**: Supabase (via asyncpg) for low-latency session and context management.

### 2. Frontend (Next.js/React)
A sleek, reactive interface:
- **Audio Engine**: Real-time 16bit PCM capture (16kHz) and playback (24kHz) via WebSockets.
- **Visualizer**: A dynamic "Assistant Circle" that pulses and morphs based on AI heartbeats (Idle, Thinking, Speaking).
- **Resilience**: Adaptive reconnect logic with exponential backoff for stable mobile usage.

## 🏁 Getting Started

### The Quick Way (Docker)
Ensure you have Docker and Docker Compose installed:
1. Populate your `.env` files in `backend/` and `frontend/`.
2. Run:
```bash
docker-compose up --build
```
Access the assistant at `http://localhost:3000`.

### The Manual Way
See the detailed setup guides in each subdirectory:
- [Backend Setup](./backend/README.md)
- [Frontend Setup](./frontend/README.md)

## 📄 Documentation
- [Deployment Guide](./DEPLOYMENT.md) - How to go live.
- [API Specification](./API_SPEC.md) - WebSocket & REST reference.

## 📄 License
MIT License. Feel free to build, remix, and share.

