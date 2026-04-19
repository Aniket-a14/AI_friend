'use client';

import { useEffect, useState, useRef } from 'react';
import AssistantCircle from '../components/AssistantCircle';
import { useWebRTCVoice } from '../hooks/useWebRTCVoice';
import { motion, AnimatePresence } from 'framer-motion';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function Home() {
    const { isConnected, isConnecting, state, startRecording } = useWebRTCVoice();
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
            {/* Atmospheric Layers */}
            <div className="atmosphere" />
            <div className="noise-overlay" />

            {/* Status Bar */}
            <div className={`absolute top-6 left-6 flex items-center gap-3 z-50 transition-opacity duration-500 ${isConnected || isConnecting ? 'opacity-100' : 'opacity-30'}`}>
                <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-cyan-500 shadow-[0_0_10px_rgba(0,245,255,0.5)]' :
                    isConnecting ? 'bg-amber-500' :
                        'bg-red-500'
                    } animate-pulse`} />
                <span className="text-[9px] text-white/50 font-mono tracking-[0.3em] uppercase">
                    {isConnected ? 'Neural Bridge Active' : isConnecting ? 'Initializing Link...' : 'Signal Lost'}
                </span>
            </div>

            {/* Vision Controls */}
            <div className="absolute top-6 right-6 flex gap-3 z-50">
                <button
                    onClick={() => toggleVision('screen')}
                    className={`glass-pill ${visionSource === 'screen' ? 'active-pill' : ''}`}
                >
                    Observer 1
                </button>
                <button
                    onClick={() => toggleVision('camera')}
                    className={`glass-pill ${visionSource === 'camera' ? 'active-pill' : ''}`}
                >
                    Observer 2
                </button>
            </div>

            {/* Webcam Preview (Holographic) */}
            <AnimatePresence>
                {visionSource === 'camera' && (
                    <motion.div
                        initial={{ opacity: 0, x: 50, filter: 'blur(20px)' }}
                        animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, x: 20, filter: 'blur(10px)' }}
                        className="absolute bottom-12 right-12 w-64 h-40 rounded-3xl border border-white/5 overflow-hidden bg-white/5 backdrop-blur-2xl z-40 shadow-2xl"
                    >
                        <video
                            ref={videoRef}
                            autoPlay
                            playsInline
                            muted
                            className="w-full h-full object-cover grayscale opacity-40 hover:opacity-60 transition-opacity duration-700"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent pointer-events-none" />
                        <div className="absolute bottom-3 left-4 text-[7px] text-white/30 uppercase tracking-[0.4em]">Visual Stream :: Cam</div>

                        {/* Scanning Line Effect */}
                        <motion.div
                            animate={{ top: ['0%', '100%', '0%'] }}
                            transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                            className="absolute left-0 w-full h-px bg-cyan-500/20 shadow-[0_0_15px_rgba(0,245,255,0.3)] pointer-events-none"
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Main Interaction Circle */}
            <div className="relative flex items-center justify-center w-full h-full z-10">
                <AssistantCircle state={state} />
            </div>

            {/* Subtitles / Feedback */}
            <div className="absolute bottom-20 text-center max-w-lg px-8 z-20">
                <motion.p
                    animate={state === 'listening' ? { opacity: [0.4, 0.8, 0.4] } : { opacity: 0.6 }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="text-white/40 text-[11px] font-light tracking-[0.2em] leading-relaxed uppercase"
                >
                    {state === 'speaking' ? "Sourcing Neural Response..." :
                        state === 'thinking' ? "Processing Context..." :
                            state === 'listening' ? "Awaiting Vocal Signature..." : "Synching Data..."}
                </motion.p>
            </div>

            {/* System Info */}
            <div className="absolute bottom-8 text-white/5 text-[7px] uppercase tracking-[0.6em] font-light">
                Sovereign Intelligence Mesh :: v3.0.42
            </div>
        </main>
    );
}
