'use client';

import React from 'react';

export default function AssistantCircle({ state }) {
    // Base circle classes
    const baseClasses = "relative flex items-center justify-center rounded-full transition-all duration-700 ease-in-out";

    // State-specific styles
    const stateStyles = {
        idle: "w-64 h-64 bg-gradient-to-br from-purple-900/40 to-pink-900/40 border border-purple-500/30 animate-breathe shadow-[0_0_30px_rgba(140,100,255,0.2)]",
        listening: "w-72 h-72 bg-purple-600/20 border border-purple-400/60 animate-flicker shadow-[0_0_50px_rgba(160,120,255,0.5)]",
        thinking: "w-64 h-64 bg-transparent border border-white/10 shadow-[0_0_20px_rgba(255,255,255,0.1)]",
        speaking: "w-80 h-80 bg-gradient-to-r from-pink-500/30 to-purple-600/30 border border-pink-400/50 animate-pulse-slow shadow-[0_0_60px_rgba(255,100,150,0.6)]",
    };

    // Thinking dots animation
    const ThinkingDots = () => (
        <div className="absolute inset-0 animate-spin [animation-duration:3s]">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-[0_0_10px_white]"></div>
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-4 h-4 bg-purple-400 rounded-full shadow-[0_0_10px_purple]"></div>
            <div className="absolute top-1/2 left-0 -translate-x-1/2 -translate-y-1/2 w-4 h-4 bg-pink-400 rounded-full shadow-[0_0_10px_pink]"></div>
        </div>
    );

    return (
        <div className={`${baseClasses} ${stateStyles[state] || stateStyles.idle}`}>
            {/* Inner core for all states */}
            <div className="absolute w-full h-full rounded-full bg-white/5 blur-xl"></div>

            {/* Specific content for thinking state */}
            {state === 'thinking' && <ThinkingDots />}

            {/* Optional: Inner glow for speaking */}
            {state === 'speaking' && (
                <div className="absolute w-1/2 h-1/2 bg-white/20 rounded-full blur-2xl animate-pulse"></div>
            )}
        </div>
    );
}
