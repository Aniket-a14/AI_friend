'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function AssistantCircle({ state = 'idle' }) {
    // Variants for the main container
    const containerVariants = {
        idle: {
            scale: 1,
            backgroundColor: "rgba(88, 28, 135, 0.1)",
            borderColor: "rgba(139, 92, 246, 0.3)",
            boxShadow: "0 0 40px rgba(139, 92, 246, 0.2)",
            transition: { duration: 1.5, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }
        },
        listening: {
            scale: 1.1,
            backgroundColor: "rgba(88, 28, 135, 0.3)",
            borderColor: "rgba(139, 92, 246, 0.8)",
            boxShadow: "0 0 60px rgba(139, 92, 246, 0.5)",
            transition: { type: "spring", stiffness: 300, damping: 20 }
        },
        thinking: {
            scale: 0.95,
            backgroundColor: "rgba(15, 15, 15, 0.4)",
            borderColor: "rgba(255, 255, 255, 0.2)",
            boxShadow: "0 0 30px rgba(255, 255, 255, 0.1)",
        },
        speaking: {
            scale: [1, 1.15, 1],
            backgroundColor: "rgba(219, 39, 119, 0.2)",
            borderColor: "rgba(236, 72, 153, 0.6)",
            boxShadow: "0 0 80px rgba(236, 72, 153, 0.6)",
            transition: { duration: 0.5, repeat: Infinity, ease: "easeInOut" }
        }
    };

    return (
        <div className="relative flex items-center justify-center">
            {/* Background Glow */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={state}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 1.2 }}
                    className="absolute w-[120%] h-[120%] rounded-full bg-gradient-to-br from-purple-500/10 to-pink-500/10 blur-3xl"
                />
            </AnimatePresence>

            {/* Main Circle */}
            <motion.div
                variants={containerVariants}
                animate={state}
                className="relative w-64 h-64 rounded-full border-2 flex items-center justify-center z-10 overflow-hidden backdrop-blur-md"
            >
                {/* Inner Ambient Glow */}
                <motion.div 
                    animate={{ rotate: 360 }}
                    transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
                    className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/5 to-transparent w-full h-full"
                />

                {/* State Specific Content */}
                {state === 'thinking' && (
                    <motion.div 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 flex items-center justify-center"
                    >
                        {[0, 1, 2].map((i) => (
                            <motion.div
                                key={i}
                                className="absolute w-4 h-4 bg-white rounded-full shadow-[0_0_15px_white]"
                                animate={{
                                    rotate: 360,
                                    scale: [1, 1.2, 1],
                                }}
                                transition={{
                                    rotate: { duration: 3, repeat: Infinity, ease: "linear", delay: i * 1 },
                                    scale: { duration: 2, repeat: Infinity, ease: "easeInOut" }
                                }}
                                style={{
                                    transformOrigin: `center 80px`,
                                    top: 'calc(50% - 40px)'
                                }}
                            />
                        ))}
                    </motion.div>
                )}

                {/* Central Core */}
                <motion.div
                    animate={state === 'speaking' ? { scale: [1, 1.3, 1] } : { scale: 1 }}
                    transition={{ duration: 0.4, repeat: state === 'speaking' ? Infinity : 0 }}
                    className={`w-24 h-24 rounded-full blur-xl z-20 ${
                        state === 'speaking' ? 'bg-pink-400/40' : 
                        state === 'listening' ? 'bg-purple-400/40' : 
                        'bg-white/10'
                    }`}
                />
            </motion.div>

            {/* Speaking Ripples */}
            {state === 'speaking' && (
                [1, 2].map((i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0.5, scale: 1 }}
                        animate={{ opacity: 0, scale: 2 }}
                        transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.5 }}
                        className="absolute w-64 h-64 rounded-full border border-pink-500/30 z-0"
                    />
                ))
            )}
        </div>
    );
}
