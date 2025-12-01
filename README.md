# AI Assistant

A sophisticated, voice-enabled AI assistant application that combines a modern Next.js frontend with a powerful Python backend. This project demonstrates a seamless integration of real-time voice processing, advanced Large Language Models (LLMs), and reactive user interfaces.

## 🚀 Overview

The AI Assistant is designed to provide a natural, conversational experience. It listens for a wake word, transcribes user speech in real-time, processes the intent using Google's Gemini LLM, and responds with an expressive voice powered by ElevenLabs. The frontend provides immediate visual feedback, mirroring the AI's internal state (Listening, Thinking, Speaking) to create an engaging user interaction.

## 🏗️ Architecture

The project is divided into two main components:

### 1. Backend (Python)
The brain of the operation, handling all logic and processing:
- **Wake Word Detection**: Uses **Porcupine** for low-latency, offline wake word detection.
- **Speech-to-Text (STT)**: Implements **Faster Whisper** for accurate, local real-time transcription.
- **Intelligence**: Integrated with **Google Gemini 2.5 Pro** to generate context-aware and personality-driven responses.
- **Text-to-Speech (TTS)**: Utilizes **ElevenLabs** for high-quality, lifelike voice synthesis.
- **State Management**: A robust state machine manages transitions between `IDLE`, `LISTENING`, `THINKING`, and `SPEAKING` states.

### 2. Frontend (Next.js)
The visual face of the assistant:
- **Reactive UI**: Built with **React** and **Next.js 14** (App Router).
- **State Visualization**: A dynamic "Assistant Circle" component that changes color, animation, and size based on the backend's real-time state.
- **Modern Styling**: Styled with **Tailwind CSS** for a sleek, dark-themed aesthetic with smooth animations.

## 🔄 How It Works

1.  **Activation**: The backend listens for the specific wake word.
2.  **Listening**: Once activated, the system records user audio and transcribes it using Whisper. The frontend displays a "Listening" animation.
3.  **Thinking**: The transcribed text is sent to the Gemini LLM. The frontend shows a "Thinking" state.
4.  **Speaking**: The LLM's response is converted to audio via ElevenLabs and played back. The frontend pulses in the "Speaking" state.
5.  **Loop**: The system returns to a listening or idle state, ready for the next interaction.

## 🛠️ Tech Stack

- **Frontend**: Next.js, React, Tailwind CSS, Framer Motion (animations).
- **Backend**: Python, FastAPI (optional for API), Porcupine (Wake Word), Faster Whisper (STT), Google Gemini (LLM), ElevenLabs (TTS).
- **Communication**: HTTP/WebSocket (for state synchronization).

## 🏁 Getting Started

### Prerequisites

- **Node.js** (v20+ recommended)
- **Python** (v3.10+)
- API Keys for **Gemini**, **ElevenLabs**, and **Picovoice (Porcupine)**.

### Installation

1.  **Backend Setup**:
    Navigate to the `backend` directory and follow the detailed instructions in `backend/README.md` to set up the virtual environment and install dependencies.

2.  **Frontend Setup**:
    Navigate to the `frontend` directory:
    ```bash
    cd frontend
    npm install
    ```

### Running the Application

1.  **Start the Backend**:
    Follow the usage instructions in `backend/README.md`.

2.  **Start the Frontend**:
    ```bash
    cd frontend
    npm run dev
    ```
3.  **Access the UI**:
    Open [http://localhost:3000](http://localhost:3000) in your browser.

## 📄 License

This project is open-source and available under the MIT License.
