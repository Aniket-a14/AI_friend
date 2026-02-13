'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function AssistantCircle({ state = 'idle' }) {
    // Variants for the core atmosphere
    const auraVariants = {
        idle: {
            scale: 1,
            opacity: 0.4,
            transition: { duration: 3, repeat: Infinity, repeatType: "reverse" }
        },
        listening: {
            scale: 1.25,
            opacity: 0.8,
            transition: { type: "spring", stiffness: 200, damping: 15 }
        },
        thinking: {
            scale: 0.9,
            opacity: 0.3,
            transition: { duration: 2, repeat: Infinity, repeatType: "reverse" }
        },
        speaking: {
            scale: [1, 1.3, 1],
            opacity: 1,
            transition: { duration: 0.6, repeat: Infinity }
        }
    };

    return (
        <div className="relative flex items-center justify-center w-full h-full">
            {/* SVG Filters for Spectral Look */}
            <svg className="absolute w-0 h-0">
                <defs>
                    <filter id="spectral-blur">
                        <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="blur" />
                        <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="spectral" />
                    </filter>
                </defs>
            </svg>

            {/* Inbound Resonance (Speaking) */}
            <AnimatePresence>
                {state === 'speaking' && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.5 }}
                        animate={{ opacity: 1, scale: 1.5 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 1, repeat: Infinity }}
                        className="absolute w-[400px] h-[400px] rounded-full border border-pink-500/10 blur-sm"
                    />
                )}
            </AnimatePresence>

            {/* Core Neural Atmosphere */}
            <motion.div
                variants={auraVariants}
                animate={state}
                style={{ filter: 'url(#spectral-blur)' }}
                className={`relative w-72 h-72 rounded-full transition-colors duration-1000 ${state === 'speaking' ? 'bg-pink-500/20' :
                        state === 'listening' ? 'bg-cyan-500/20' :
                            state === 'thinking' ? 'bg-indigo-500/10' : 'bg-white/5'
                    }`}
            >
                {/* Central Singularity */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <motion.div
                        animate={state === 'speaking' ? { scale: [1, 1.4, 1] } : { scale: 1 }}
                        className={`w-36 h-36 rounded-full blur-2xl ${state === 'speaking' ? 'bg-pink-400/40' :
                                state === 'listening' ? 'bg-cyan-400/40' :
                                    'bg-white/10'
                            }`}
                    />
                </div>

                {/* Orbital Paths (Listening/Thinking) */}
                <AnimatePresence>
                    {(state === 'listening' || state === 'thinking') && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0"
                        >
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    className={`absolute left-1/2 top-1/2 w-2 h-2 rounded-full blur-[1px] ${state === 'listening' ? 'bg-cyan-400' : 'bg-white'
                                        }`}
                                    animate={{
                                        rotate: 360,
                                        x: 100 * Math.cos(i * 120 * (Math.PI / 180)),
                                        y: 100 * Math.sin(i * 120 * (Math.PI / 180)),
                                    }}
                                    transition={{
                                        rotate: { duration: 4, repeat: Infinity, ease: "linear", delay: i * 0.5 },
                                    }}
                                />
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            {/* Interaction States */}
            <div className="absolute flex items-center justify-center font-mono text-[8px] tracking-[0.4em] uppercase text-white/20 select-none">
                <AnimatePresence mode="wait">
                    <motion.span
                        key={state}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                    >
                        {state}
                    </motion.span>
                </AnimatePresence>
            </div>
        </div>
    );
}
