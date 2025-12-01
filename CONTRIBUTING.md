# Contributing to Pankudi AI

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to Pankudi AI. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Getting Started

Please refer to the [README.md](README.md) for instructions on how to set up the project locally.

## Project Structure

The project is divided into two main components:

*   **`backend/`**: Python-based backend using FastAPI (optional), Porcupine, Faster Whisper, Google Gemini, and ElevenLabs.
*   **`frontend/`**: Next.js 14 application using React and Tailwind CSS.

## Development Workflow

1.  **Fork the repository** and clone it locally.
2.  **Create a branch** for your edits.
    *   Use a descriptive name, e.g., `feature/new-voice-command` or `fix/websocket-connection`.
3.  **Make your changes**.
    *   Ensure you follow the coding standards (see below).
    *   Test your changes thoroughly.
4.  **Commit your changes**.
    *   Write clear and concise commit messages.
5.  **Push to your fork** and submit a **Pull Request**.

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
