'use client';

import { useEffect } from 'react';
import AssistantCircle from '../../components/AssistantCircle';
import { useBackendState } from '../../hooks/useBackendState';
import { useVoiceInteraction } from '../../hooks/useVoiceInteraction';

export default function AssistantPage() {
    const state = useBackendState();
    const { isConnected, isConnecting, isRecording, startRecording } = useVoiceInteraction();

    // Automatically start recording once we arrive at this page and socket is connected.
    // The user has already given explicit interaction via the "Start" button on the previous page.
    useEffect(() => {
        if (isConnected && !isRecording) {
            startRecording();
        }
    }, [isConnected, isRecording, startRecording]);

    return (
        <main className="flex min-h-screen flex-col items-center justify-center bg-black overflow-hidden relative">
            <div className={`absolute top-4 left-4 flex items-center gap-2 transition-opacity duration-500 ${isConnected || isConnecting ? 'opacity-100' : 'opacity-50'}`}>
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' :
                        isConnecting ? 'bg-amber-500' :
                            'bg-red-500'
                    } animate-pulse`} />
                <span className="text-xs text-white/40 font-mono tracking-widest uppercase">
                    {isConnected ? 'Stream Active' : isConnecting ? 'Initializing...' : 'Disconnected'}
                </span>
            </div>

            <div className="relative flex items-center justify-center w-full h-full">
                <AssistantCircle state={state} />
            </div>

            {/* Mobile/Web Info */}
            <div className="absolute bottom-8 text-white/20 text-[10px] uppercase tracking-[0.2em] font-light">
                Secure Browser Audio Stream
            </div>
        </main>
    );
}
