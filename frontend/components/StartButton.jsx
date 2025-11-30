'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function StartButton() {
    const router = useRouter();
    const [isStarting, setIsStarting] = useState(false);

    const handleStart = async () => {
        setIsStarting(true);
        try {
            const res = await fetch('http://localhost:8000/start-session', {
                method: 'POST',
            });

            if (res.ok) {
                // Optional: wait a bit for animation
                setTimeout(() => {
                    router.push('/assistant');
                }, 500);
            } else {
                console.error('Failed to start session');
                setIsStarting(false);
            }
        } catch (error) {
            console.error('Error starting session:', error);
            setIsStarting(false);
        }
    };

    return (
        <button
            onClick={handleStart}
            disabled={isStarting}
            className={`
        relative px-8 py-4 
        border-2 border-white rounded-full 
        bg-transparent text-white text-xl font-light tracking-wider
        transition-all duration-500 ease-in-out
        hover:shadow-[0_0_20px_rgba(255,255,255,0.5)] hover:scale-105
        active:scale-95
        disabled:opacity-0 disabled:cursor-default
        ${isStarting ? 'opacity-0 scale-90' : 'opacity-100 scale-100'}
      `}
        >
            Start Assistant
        </button>
    );
}
