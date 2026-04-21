# AI Friend Frontend 🎨🎙️

A modern, high-performance web interface for the AI Friend assistant. Built with **Next.js 14** and optimized for real-time voice streaming.

## 🌟 Voice UX Features

- **Bi-Directional Streaming**: Uses Web Audio API to capture 16kHz mono audio and play back high-quality 24kHz streams directly over WebSockets.
- **Smart Visualizer**: The `AssistantCircle` morphs its animation pattern based on direct state signals from the backend:
  - **Listening**: Flickering energy glow.
  - **Thinking**: Orbiting data particles.
  - **Speaking**: Pulsing audio-reactive heartbeats.
- **Auto-Healing Connection**: Integrated exponential backoff system that automatically restores WebSocket connections during network drops.
- **Mobile First**: Fully responsive layout designed for a "Phone-as-a-Microphone" experience.

## 🛠️ Tech Stack

- **Next.js 14**: App Router for fast, optimized delivery.
- **Tailwind CSS**: Glassmorphic UI with custom animations.
- **Framer Motion**: Smooth, organic transitions for the assistant's "soul."
- **Web Audio API**: Low-level audio processing without external plugins.

## ⚙️ Environment Configuration

Create a `frontend/.env` file:

```env
NEXT_PUBLIC_WS_URL=ws://your-backend:8000/ws/audio
```

## 🐳 Docker Deployment

```bash
docker build -t ai-friend-frontend .
docker run -p 3000:3000 --env-file .env ai-friend-frontend
```

## 📂 Project Structure

- `app/assistant/page.jsx`: Main interaction hub.
- `hooks/useVoiceInteraction.js`: The "Ear & Mouth" of the app; handles WebSocket streaming.
- `components/AssistantCircle.jsx`: The visual representation of the AI's life-state.
