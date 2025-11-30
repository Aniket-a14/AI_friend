# AI Friend Backend

A real-time, voice-interactive AI assistant backend designed to be a conversational companion. It features wake-word detection, real-time speech-to-text, an expressive personality powered by Gemini, and natural-sounding text-to-speech.

## Features

- **Wake Word Detection**: Activates upon hearing a custom wake word (e.g., "Hello love") using [Porcupine](https://picovoice.ai/platform/porcupine/).
- **Real-Time Speech-to-Text**: Uses local [Whisper](https://github.com/openai/whisper) (via `faster-whisper`) for low-latency, accurate transcription with Voice Activity Detection (VAD).
- **Intelligent Conversation**: Powered by Google's **Gemini 2.5 Pro** LLM for natural, context-aware, and personality-driven responses.
- **Expressive Text-to-Speech**: Utilizes [ElevenLabs](https://elevenlabs.io/) TTS (Model: `eleven_v3`) for high-quality, emotionally resonant voice output.
- **Memory**: Maintains short-term conversation history for context retention.
- **Event-Driven Architecture**: Built with Python `asyncio` for efficient, non-blocking handling of audio streams and API calls.

## Prerequisites

- Python 3.10+
- [PVRecorder](https://pypi.org/project/pvrecorder/) compatible microphone.
- [ElevenLabs](https://elevenlabs.io/) Account & API Key.
- [Google AI Studio](https://aistudio.google.com/) API Key (Gemini).
- [Picovoice Console](https://console.picovoice.ai/) Access Key (Porcupine).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Setup Environment Variables:**
    Create a `.env` file in the root directory (copy from `.env.example` if available) and add your API keys:

    ```env
    PORCUPINE_ACCESS_KEY=your_porcupine_key
    GEMINI_API_KEY=your_gemini_key
    ELEVENLABS_API_KEY=your_elevenlabs_key
    ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id
    ```

5.  **Wake Word File:**
    Place your Porcupine wake word file (`.ppn`) in the `wake_up_file/` directory and ensure the path in `app/wake_word.py` matches.

6.  **Personality:**
    Define the AI's personality in `app/personality.json`.

## Usage

Run the main application:

```bash
python main.py
```

- The system will start in `IDLE` mode.
- Say the wake word to activate the session.
- Speak naturally. The AI will listen, transcribe, think, and respond.
- To end the session, say "Bye", "Stop", or wait for the silence timeout.

## Project Structure

```
├── app/
│   ├── audio.py                # Audio input/output handling
│   ├── config.py               # Configuration & env vars
│   ├── llm.py                  # Gemini LLM integration
│   ├── personality.json        # AI Personality definition (Ignored by Git)
│   ├── state_manager.py        # State machine (IDLE, ACTIVE, SPEAKING)
│   ├── tts.py                  # ElevenLabs TTS integration
│   ├── vad.py                  # Voice Activity Detection
│   ├── wake_word.py            # Porcupine wake word detection
│   └── whisper_stt_service.py  # Local Whisper STT service
├── wake_up_file/               # Porcupine .ppn files (Ignored by Git)
├── main.py                     # Main entry point & orchestration
├── requirements.txt            # Python dependencies
├── .env                        # API Keys (Ignored by Git)
└── .gitignore                  # Git ignore rules
```

## License

[MIT License](LICENSE)
