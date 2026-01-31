# AI Friend Backend 🧠🔊

The high-performance core of the AI Friend assistant. Built with FastAPI and optimized for real-time streaming voice interaction.

## 🚀 Performance Features

- **Streaming Pipeline**: Implements sentence-based pipelining. As soon as a sentence is "thought," it's converted to voice while the rest of the response is still generating.
- **Dynamic Soul Engine**: Instructs the LLM to use hidden reasoning (`<emotion_thought>`) to align vocal tone with user sentiment.
- **Production Hardened**: Includes security middleware, CORS origin filtering, and graceful resource cleanup.
- **Cloud Persistence**: Dynamic context loading from Supabase for agent personality and history.

## 🛠️ Technical Stack
- **FastAPI**: Main API and WebSocket server.
- **Gemini 2.5 Pro**: Advanced LLM for reasoning and personality.
- **ElevenLabs v3**: Industry-leading text-to-speech with expressive tags.
- **Faster Whisper**: Local STT engine for lightning-fast transcription.
- **asyncpg**: High-concurrency PostgreSQL driver for Supabase integration.

## ⚙️ Environment Configuration

Create a `.env` file with the following:
```env
# API Keys
PORCUPINE_ACCESS_KEY=your_key
GEMINI_API_KEY=your_key
ELEVENLABS_API_KEY=your_key
ELEVENLABS_VOICE_ID=your_id

# Database
DATABASE_URL=your_supabase_connection_string

# Identity
AI_NAME=AI Friend (or whatever you want!)

# Production Settings
DEBUG=False
ALLOWED_ORIGINS=http://your-domain.com,http://localhost:3000
```

## 🐳 Docker Deployment
```bash
docker build -t ai-friend-backend .
docker run -p 8000:8000 --env-file .env ai-friend-backend
```

## 📂 Internal Modules
- `app/llm.py`: Streaming persona management and emotional monologue.
- `app/conversation_history_store.py`: Persistent session logging via Supabase.
- `app/whisper_stt_service.py`: Real-time audio transcription with VAD.
- `app/tts.py`: ElevenLabs streaming voice integration.
