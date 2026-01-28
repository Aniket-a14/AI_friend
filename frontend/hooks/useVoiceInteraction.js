'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://localhost:8000/ws/audio';

export function useVoiceInteraction() {
    const [isConnected, setIsConnected] = useState(false);
    const [isRecording, setIsRecording] = useState(false);
    const wsRef = useRef(null);
    const audioContextRef = useRef(null);
    const playbackAudioContextRef = useRef(null);
    const nextStartTimeRef = useRef(0);
    const processorRef = useRef(null);
    const isPlayingRef = useRef(false);

    // handleNextChunk scheduling for seamless playback
    const playChunk = useCallback(async (chunk) => {
        if (!playbackAudioContextRef.current) {
            playbackAudioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            nextStartTimeRef.current = playbackAudioContextRef.current.currentTime;
        }

        const ctx = playbackAudioContextRef.current;

        // If we haven't played anything for a while, reset the timeline to "now"
        if (ctx.currentTime > nextStartTimeRef.current) {
            nextStartTimeRef.current = ctx.currentTime;
        }

        const bufferSize = chunk.byteLength / 2;
        const buffer = ctx.createBuffer(1, bufferSize, 24000);
        const channelData = buffer.getChannelData(0);
        const int16Array = new Int16Array(chunk);

        for (let i = 0; i < bufferSize; i++) {
            channelData[i] = int16Array[i] / 32768.0;
        }

        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);

        // Schedule accurately
        const startTime = nextStartTimeRef.current;
        source.start(startTime);

        // Advance the clock for the next chunk
        nextStartTimeRef.current += buffer.duration;
    }, []);

    // Initialize Audio Context for Input (16kHz Mono)
    const startRecording = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const source = audioContextRef.current.createMediaStreamSource(stream);

            processorRef.current = audioContextRef.current.createScriptProcessor(4096, 1, 1);

            processorRef.current.onaudioprocess = (e) => {
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
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

    // WebSocket Setup
    useEffect(() => {
        let socket;
        let reconnectTimeout;
        let reconnectAttempts = 0;
        const MAX_RECONNECT_ATTEMPTS = 5;

        const connect = () => {
            socket = new WebSocket(WS_URL);
            socket.binaryType = 'arraybuffer';
            wsRef.current = socket;

            socket.onopen = () => {
                console.log("WebSocket Connected to AI Backend");
                setIsConnected(true);
                reconnectAttempts = 0;
            };

            socket.onmessage = (event) => {
                if (event.data instanceof ArrayBuffer) {
                    playChunk(event.data);
                }
            };

            socket.onclose = (event) => {
                setIsConnected(false);
                console.log("WebSocket closed", event.code, event.reason);

                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                    reconnectTimeout = setTimeout(() => {
                        reconnectAttempts++;
                        connect();
                    }, delay);
                }
            };

            socket.onerror = (error) => {
                console.error("WebSocket error:", error);
            };
        };

        connect();

        return () => {
            wsRef.current?.close();
            stopRecording();
            if (playbackAudioContextRef.current) {
                playbackAudioContextRef.current.close();
            }
        };
    }, [playChunk, stopRecording]);

    return { isConnected, isRecording, startRecording, stopRecording };
}

return { isConnected, isRecording, startRecording, stopRecording };

