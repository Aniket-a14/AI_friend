# AI Assistant Frontend

The modern, reactive web interface for the AI Assistant, built with **Next.js 14** and **Tailwind CSS**. This frontend serves as the visual counterpart to the Python backend, providing users with real-time feedback on the AI's current status and activity.

## ✨ Features

- **Dynamic State Visualization**: The core of the UI is the `AssistantCircle` component, which morphs and animates to reflect the AI's state:
    - **Idle**: A gentle, breathing pulse.
    - **Listening**: An active, flickering glow indicating audio capture.
    - **Thinking**: A spinning animation representing processing.
    - **Speaking**: A rhythmic pulse synchronized with audio output.
- **Minimalist Design**: A clean, dark-themed interface that focuses attention on the interaction.
- **Real-Time Synchronization**: Polls or connects to the backend to stay perfectly in sync with the voice assistant's lifecycle.
- **Responsive**: Fully responsive layout that works seamlessly on desktop and mobile devices.

## 🚀 Getting Started

### Prerequisites

- Node.js 18.17 or later.

### Installation

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```

2.  Install dependencies:
    ```bash
    npm install
    # or
    yarn install
    ```

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## 📂 Project Structure

- **`app/`**: The App Router directory containing pages and layouts.
    - `page.js`: The landing page with the start button.
    - `assistant/page.jsx`: The main assistant interface featuring the visualizer.
    - `layout.js`: Global layout and font configurations.
- **`components/`**: Reusable UI components.
    - `AssistantCircle.jsx`: The main visual component that handles state animations.
    - `StartButton.jsx`: A styled button to initiate the session.
- **`hooks/`**: Custom React hooks.
    - `useBackendState.js`: Manages the connection to the backend and state synchronization.

## 🎨 Styling

The project uses **Tailwind CSS** for styling.
- **Animations**: Custom keyframe animations (like `breathe`, `flicker`, `pulse-slow`) are defined in `tailwind.config.js` or global CSS to create organic, fluid movements.
- **Glassmorphism**: Usage of backdrops, blurs, and translucent colors to create a modern, high-tech feel.

## 🔧 Configuration

The frontend is configured to communicate with the backend (defaulting to `localhost:8000`). Ensure your backend is running and accessible. You can modify the API endpoints in the `hooks/useBackendState.js` or `components/StartButton.jsx` files if your backend runs on a different port or host.
