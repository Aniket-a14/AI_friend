'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://localhost:8000/ws/audio';

export function useVoiceInteraction() {
    const [isConnected, setIsConnected] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const wsRef = useRef(null);
    const audioContextRef = useRef(null);
    const processorRef = useRef(null);
    const playbackQueueRef = useRef([]);
    const isPlayingRef = useRef(false);

    // Initialize Audio Context for Input (16kHz Mono)
    const startRecording = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const source = audioContextRef.current.createMediaStreamSource(stream);

            // We use ScriptProcessor for simplicity in this MVP, 
            // though AudioWorklet is better for production.
            processorRef.current = audioContextRef.current.createScriptProcessor(4096, 1, 1);

            processorRef.current.onaudioprocess = (e) => {
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    // Convert Float32 to Int16
                    const pcmData = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                    }
                    wsRef.current.send(pcmData.buffer);
                }
            };

            source.connect(processorRef.current);
            processorRef.current.connect(audioContextRef.current.destination);
            setIsRecording(true);
            console.log('Recording started at 16kHz');
        } catch (err) {
            console.error('Error starting audio capture:', err);
        }
    }, []);

    const stopRecording = useCallback(() => {
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
        setIsRecording(false);
        console.log('Recording stopped');
    }, []);

    // Handle Playback of 24kHz PCM from Backend
    const playNextInQueue = useCallback(async () => {
        if (playbackQueueRef.current.length === 0 || isPlayingRef.current) return;

        isPlayingRef.current = true;
        const chunk = playbackQueueRef.current.shift();

        // Create a temporary AudioContext for playback if needed
        const playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        const buffer = playCtx.createBuffer(1, chunk.length / 2, 24000);
        const channelData = buffer.getChannelData(0);

        // Convert Int16 to Float32
        const int16Array = new Int16Array(chunk);
        for (let i = 0; i < int16Array.length; i++) {
            channelData[i] = int16Array[i] / 32768.0;
        }

        const source = playCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(playCtx.destination);
        source.onended = () => {
            isPlayingRef.current = false;
            playNextInQueue();
            playCtx.close();
        };
        source.start();
    }, []);

    // WebSocket Setup
    useEffect(() => {
        let socket;
        let reconnectTimeout;
        let reconnectAttempts = 0;
        const MAX_RECONNECT_ATTEMPTS = 5;

        const connect = () => {
            socket = new WebSocket(WS_URL); // Using WS_URL constant
            socket.binaryType = 'arraybuffer'; // Ensure binaryType is set
            wsRef.current = socket;

            socket.onopen = () => {
                console.log("WebSocket Connected to AI Backend"); // Clarified log
                setIsConnected(true);
                reconnectAttempts = 0;
            };

            socket.onmessage = (event) => { // Adjusted to original playback logic
                if (event.data instanceof ArrayBuffer) {
                    playbackQueueRef.current.push(event.data);
                    playNextInQueue();
                }
            };

            socket.onclose = (event) => {
                setIsConnected(false);
                console.log("WebSocket closed", event.code, event.reason); // Detailed log

                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000); // Exponential backoff
                    console.log(`Attempting reconnect in ${delay}ms... (Attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`); // Detailed log
                    reconnectTimeout = setTimeout(() => {
                        reconnectAttempts++;
                        connect();
                    }, delay);
                } else {
                    console.error("WebSocket: Max reconnect attempts reached. Connection failed."); // Error log
                }
            };

            socket.onerror = (error) => {
                console.error("WebSocket error:", error); // Detailed error log
                // An error typically precedes a close event, so no need to trigger reconnect here.
            };
        };

        connect();

        return () => {
            wsRef.current?.close();
            stopRecording();
        };
    }, [playNextInQueue, stopRecording]);

    return { isConnected, isRecording, startRecording, stopRecording };
}
