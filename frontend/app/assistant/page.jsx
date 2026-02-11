'use client';

import { useEffect, useState, useRef } from 'react';
import AssistantCircle from '../../components/AssistantCircle';
import { useVoiceInteraction } from '../../hooks/useVoiceInteraction';
import { motion, AnimatePresence } from 'framer-motion';

const BACKEND_URL = 'http://localhost:8000';

export default function AssistantPage() {
    const { isConnected, isConnecting, state, startRecording } = useVoiceInteraction();
    const [visionSource, setVisionSource] = useState('screen'); // screen | camera
    const videoRef = useRef(null);

    // Automatically start recording once we arrive at this page and socket is connected.
    useEffect(() => {
        if (isConnected && state === 'idle') {
            startRecording();
        }
    }, [isConnected, state, startRecording]);

    // Handle Backend Vision Toggle
    const toggleVision = async (source) => {
        try {
            const res = await fetch(`${BACKEND_URL}/vision/toggle?source=${source}`, {
                method: 'POST'
            });
            if (res.ok) {
                setVisionSource(source);
                if (source === 'camera') {
                    startWebcamPreview();
                } else {
                    stopWebcamPreview();
                }
            }
        } catch (err) {
            console.error("Failed to toggle vision:", err);
        }
    };

    const startWebcamPreview = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) {
            console.error("Camera preview failed:", err);
        }
    };

    const stopWebcamPreview = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            const tracks = videoRef.current.srcObject.getTracks();
            tracks.forEach(t => t.stop());
            videoRef.current.srcObject = null;
        }
    };

    return (
        <main className="flex min-h-screen flex-col items-center justify-center bg-black overflow-hidden relative font-sans">
            {/* Status Bar */}
            <div className={`absolute top-4 left-4 flex items-center gap-2 transition-opacity duration-500 ${isConnected || isConnecting ? 'opacity-100' : 'opacity-50'}`}>
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' :
                    isConnecting ? 'bg-amber-500' :
                        'bg-red-500'
                    } animate-pulse`} />
                <span className="text-[10px] text-white/40 font-mono tracking-widest uppercase">
                    {isConnected ? 'Stream Active' : isConnecting ? 'Initializing...' : 'Disconnected'}
                </span>
            </div>

            {/* Vision Controls */}
            <div className="absolute top-4 right-4 flex gap-2 z-50">
                <button
                    onClick={() => toggleVision('screen')}
                    className={`px-3 py-1 text-[10px] uppercase tracking-tighter rounded-full border transition-all ${visionSource === 'screen' ? 'bg-white text-black border-white' : 'bg-transparent text-white/40 border-white/10 hover:border-white/30'}`}
                >
                    Desktop
                </button>
                <button
                    onClick={() => toggleVision('camera')}
                    className={`px-3 py-1 text-[10px] uppercase tracking-tighter rounded-full border transition-all ${visionSource === 'camera' ? 'bg-white text-black border-white' : 'bg-transparent text-white/40 border-white/10 hover:border-white/30'}`}
                >
                    Webcam
                </button>
            </div>

            {/* Webcam Preview (Small/Floating) */}
            <AnimatePresence>
                {visionSource === 'camera' && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className="absolute bottom-20 right-8 w-48 h-32 rounded-2xl border border-white/10 overflow-hidden bg-black/50 backdrop-blur-md z-40"
                    >
                        <video
                            ref={videoRef}
                            autoPlay
                            playsInline
                            muted
                            className="w-full h-full object-cover grayscale opacity-60"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent pointer-events-none" />
                        <div className="absolute bottom-2 left-3 text-[8px] text-white/40 uppercase tracking-widest">Live Feed</div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Main Interaction Circle */}
            <div className="relative flex items-center justify-center w-full h-full">
                <AssistantCircle state={state} />
            </div>

            {/* Subtitles / Feedback Placeholder */}
            <div className="absolute bottom-24 text-center max-w-lg px-8">
                <motion.p
                    animate={state === 'listening' ? { opacity: [0.3, 0.6, 0.3] } : { opacity: 0.8 }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="text-white/60 text-sm font-light tracking-wide leading-relaxed italic"
                >
                    {state === 'speaking' ? "Assistant is speaking..." :
                        state === 'thinking' ? "Assistant is thinking..." :
                            state === 'listening' ? "Listening for your voice..." : "Connecting..."}
                </motion.p>
            </div>

            {/* Mobile/Web Info */}
            <div className="absolute bottom-8 text-white/10 text-[8px] uppercase tracking-[0.3em] font-light">
                Multimodal Neural Interface v2.5
            </div>
        </main>
    );
}
