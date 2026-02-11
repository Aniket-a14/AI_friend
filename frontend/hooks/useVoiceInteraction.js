'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = 'ws://localhost:8000/ws/audio';

export function useVoiceInteraction() {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [interactionState, setInteractionState] = useState('idle'); // idle | listening | speaking

    const wsRef = useRef(null);
    const audioContextRef = useRef(null);
    const playbackAudioContextRef = useRef(null);
    const nextStartTimeRef = useRef(0);
    const processorRef = useRef(null);
    const playbackTimeoutRef = useRef(null);

    const stopRecording = useCallback(() => {
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }
        if (audioContextRef.current) {
            if (audioContextRef.current.state !== 'closed') {
                audioContextRef.current.close();
            }
            audioContextRef.current = null;
        }
        setInteractionState('idle');
        console.log('Recording stopped');
    }, []);

    const playChunk = useCallback(async (chunk) => {
        setInteractionState('speaking');

        if (playbackTimeoutRef.current) {
            clearTimeout(playbackTimeoutRef.current);
        }

        if (!playbackAudioContextRef.current) {
            playbackAudioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            nextStartTimeRef.current = playbackAudioContextRef.current.currentTime;
        }

        const ctx = playbackAudioContextRef.current;
        if (ctx.currentTime > nextStartTimeRef.current) {
            nextStartTimeRef.current = ctx.currentTime;
        }

        const bufferSize = Math.floor(chunk.byteLength / 2);
        if (bufferSize < 1) return;

        const buffer = ctx.createBuffer(1, bufferSize, 24000);
        const channelData = buffer.getChannelData(0);
        const int16Array = new Int16Array(chunk);

        for (let i = 0; i < bufferSize; i++) {
            channelData[i] = int16Array[i] / 32768.0;
        }

        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);

        const startTime = nextStartTimeRef.current;
        source.start(startTime);
        nextStartTimeRef.current += buffer.duration;

        // Set timeout to return to listening after the buffer finishes
        const delayMs = (nextStartTimeRef.current - ctx.currentTime) * 1000;
        playbackTimeoutRef.current = setTimeout(() => {
            setInteractionState('listening');
        }, delayMs + 100);
    }, []);

    const startRecording = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });

            // Load AudioWorklet
            await audioContextRef.current.audioWorklet.addModule('/audio-processor.js');

            const source = audioContextRef.current.createMediaStreamSource(stream);
            const workletNode = new AudioWorkletNode(audioContextRef.current, 'audio-processor');
            processorRef.current = workletNode;

            workletNode.port.onmessage = (event) => {
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(event.data);
                }
            };

            source.connect(workletNode);
            workletNode.connect(audioContextRef.current.destination);

            setInteractionState('listening');
            console.log('Recording started (AudioWorklet) at 16kHz');
        } catch (err) {
            console.error('Error starting audio capture:', err);
        }
    }, []);

    const isConnectingRef = useRef(false);

    useEffect(() => {
        let socket;
        let reconnectTimeout;
        let reconnectAttempts = 0;
        const MAX_RECONNECT_ATTEMPTS = 5;

        const connect = () => {
            if (isConnectingRef.current || (wsRef.current && wsRef.current.readyState === WebSocket.OPEN)) {
                return;
            }

            isConnectingRef.current = true;
            setIsConnecting(true);

            socket = new WebSocket(WS_URL);
            socket.binaryType = 'arraybuffer';
            wsRef.current = socket;

            socket.onopen = () => {
                console.log("WebSocket Connected");
                setIsConnected(true);
                setIsConnecting(false);
                isConnectingRef.current = false;
                reconnectAttempts = 0;
            };

            socket.onmessage = (event) => {
                if (event.data instanceof ArrayBuffer) {
                    playChunk(event.data);
                } else {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'stop') {
                            if (playbackAudioContextRef.current) {
                                playbackAudioContextRef.current.close().catch(() => { });
                                playbackAudioContextRef.current = null;
                            }
                            nextStartTimeRef.current = 0;
                            setInteractionState('listening');
                        }
                    } catch (e) { }
                }
            };

            socket.onclose = () => {
                setIsConnected(false);
                setIsConnecting(false);
                isConnectingRef.current = false;
                if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    reconnectTimeout = setTimeout(() => {
                        reconnectAttempts++;
                        connect();
                    }, 2000);
                }
            };

            socket.onerror = () => {
                setIsConnecting(false);
                isConnectingRef.current = false;
            };
        };

        connect();

        return () => {
            if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
                wsRef.current.close();
            }
            stopRecording();
            if (playbackAudioContextRef.current) {
                playbackAudioContextRef.current.close().catch(() => { });
            }
            if (playbackTimeoutRef.current) {
                clearTimeout(playbackTimeoutRef.current);
            }
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
            }
        };
    }, [playChunk, stopRecording]);

    return {
        isConnected,
        isConnecting,
        state: interactionState,
        startRecording,
        stopRecording
    };
}
