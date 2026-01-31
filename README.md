# AI Friend v2.1.2 - Human-like Voice Companion 🎙️✨

AI Friend is a sophisticated, real-time voice-interactive AI assistant designed to feel like a natural companion rather than a robotic utility. It features **near-instantaneous responses**, **expressive vocal cues**, and a **human-like "soul"** with local roots in Jalandhar, Punjab.

[![CI](https://github.com/Aniket-a14/Ai_friend/actions/workflows/ci.yml/badge.svg)](https://github.com/Aniket-a14/Ai_friend/actions/workflows/ci.yml)
[![Container Security](https://github.com/Aniket-a14/Ai_friend/actions/workflows/trivy-analysis.yml/badge.svg)](https://github.com/Aniket-a14/Ai_friend/actions/workflows/trivy-analysis.yml)
[![Link Checker](https://github.com/Aniket-a14/Ai_friend/actions/workflows/links.yml/badge.svg)](https://github.com/Aniket-a14/Ai_friend/actions/workflows/links.yml)
[![Release](https://github.com/Aniket-a14/Ai_friend/actions/workflows/release.yml/badge.svg)](https://github.com/Aniket-a14/Ai_friend/actions/workflows/release.yml)

## 🌟 Key Features (The Humanized Era)

- **⚡ Memory v2 (Imperfect Memory)**: Features Short-term, Blurry, and Core memory layers for human-like recall.
- **⏰ Biological Clock**: Awareness of time passage, absences, and simulated day/night energy cycles.
- **🌱 Human Growth Engine**: Learns and evolves her personality based on past conversations.
- **🎭 Expressive Voice**: Uses emotional context and vocal tags like `[laughs]`, `[sighs]`, and `[whispers]` via ElevenLabs v3.
- **☁️ Persistent Soul**: Syncs personality and growth with Supabase (PostgreSQL) for a continuous friendship.

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

## ⚙️ Production Workflows

This project uses advanced GitHub Actions for production readiness:

- **🛡️ Security**: Weekly container vulnerability scans (Trivy) and code security analysis (CodeQL).
- **📦 Release Automation**: Automated Docker builds and GHCR publishing on every `v*` tag.
- **🧹 Maintenance**: Dependabot for dependency updates and Stale Bot for issue management.
- **✅ Quality Assurance**: Automated linting (ESLint/Flake8) and documentation link checking.

## 📄 Documentation
- [Deployment Guide](./DEPLOYMENT.md) - How to go live.
- [API Specification](./API_SPEC.md) - WebSocket & REST reference.

## 📄 License
MIT License. Feel free to build, remix, and share.

