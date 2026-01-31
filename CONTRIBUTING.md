# Contributing to AI Friend

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to AI Friend. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Getting Started

Please refer to the [README.md](README.md) for instructions on how to set up the project locally.

## 🗺️ Codebase Walkthrough

Understanding where things live will help you move faster.

### 🧠 Backend (`/backend`)
The brain of the operation, built with **FastAPI**.
*   **`main.py`**: The entry point. Handles WebSocket connections (`/ws/audio`), state management loop (`AIBackend.run`), and CORS.
*   **`app/state_manager.py`**: Manages the AI's heartbeat (IDLE, IGNORING, LISTENING, THINKING, SPEAKING).
*   **`app/llm.py`**: The interface to **Google Gemini 2.5 Pro**. Handles the "Inner Monologue" mechanism (`<emotion_thought>`) and memory management.
*   **`app/audio.py`**: Handles raw PCM audio streams. Contains `AudioStream` (input buffer) and `AudioPlayer` (local playback).
*   **`app/wake_word.py`**: **Porcupine** integration for Wake Word detection.
*   **`app/vad.py`**: Voice Activity Detection to know when the user stops speaking.

### 🎨 Frontend (`/frontend`)
The face of the operation, built with **Next.js 14** (App Router).
*   **`app/page.tsx`**: The main dashboard.
*   **`components/AssistantCircle.jsx`**: The core visualizer. It subscribes to the WebSocket state and morphs the UI (pulsing when listening, spinning when thinking).
*   **`components/StartButton.jsx`**: Simple UI trigger to start the session manually.


## Development Workflow

1.  **Fork the repository** and clone it locally.
2.  **Create a branch** for your edits.
    *   Use a descriptive name, e.g., `feature/new-voice-command` or `fix/websocket-connection`.
3.  **Setup Environment**:
    *   **Backend**:
        ```bash
        cd backend
        python -m venv .venv
        source .venv/bin/activate  # Windows: .venv\Scripts\activate
        pip install -r requirements.txt
        ```
    *   **Frontend**:
        ```bash
        cd frontend
        npm install
        ```
4.  **Make your changes**.
    *   Ensure you follow the coding standards.
    *   Use **Conventional Commits** for your messages (e.g., `feat: add voice`, `fix: webrtc crash`).
5.  **Test your changes**:
    *   **Backend**: `flake8 .` and `pytest`
    *   **Frontend**: `npm run lint` and `npm run build`
6.  **Push to your fork** and submit a **Pull Request**.

## Pull Request Process

1.  Ensure your code builds and runs locally without errors.
2.  Update the `README.md` with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.
3.  The PR title should be descriptive.
4.  Provide a description of the changes and link to any relevant issues.

## Coding Standards

### Python (Backend)
*   Follow PEP 8 style guidelines.
*   Use type hints where possible.
*   Keep functions small and focused.

### TypeScript/React (Frontend)
*   Use functional components and Hooks.
*   Use strict type checking.
*   Follow the existing directory structure (e.g., `components/`, `app/`).
*   Use Tailwind CSS for styling.

## Reporting Issues

If you find a bug or have a feature request, please open an issue on GitHub. include as much detail as possible, such as:

*   Steps to reproduce the issue.
*   Expected behavior.
*   Actual behavior.
*   Screenshots or logs (if applicable).

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
