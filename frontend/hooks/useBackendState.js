'use client';

import { useState, useEffect } from 'react';

const BACKEND_URL = 'http://localhost:8000';

export function useBackendState() {
  const [state, setState] = useState('idle'); // idle | listening | thinking | speaking

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/status`);
        if (res.ok) {
          const data = await res.json();
          // Assuming backend returns { state: "idle" | "listening" | ... }
          if (data.state) {
            setState(data.state);
          }
        }
      } catch (error) {
        console.error('Failed to fetch backend state:', error);
        // Optional: set to 'idle' or error state on failure
      }
    }, 500); // Poll every 500ms

    return () => clearInterval(interval);
  }, []);

  return state;
}
