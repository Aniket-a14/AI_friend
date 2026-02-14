import { useState, useEffect, useRef, useCallback } from 'react';
import { Room, RoomEvent, createLocalAudioTrack } from 'livekit-client';

const BACKEND_URL = 'http://localhost:8000';
const LIVEKIT_URL = 'ws://localhost:7880';

export function useWebRTCVoice() {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [interactionState, setInteractionState] = useState('idle'); // idle | listening | speaking

    const roomRef = useRef(null);
    const audioTrackRef = useRef(null);

    const startRecording = useCallback(async () => {
        setInteractionState('listening');
    }, []);

    const stopRecording = useCallback(() => {
        setInteractionState('idle');
    }, []);

    useEffect(() => {
        let mounted = true;

        const connectToRoom = async () => {
            if (isConnected || isConnecting) return;

            setIsConnecting(true);
            try {
                // 1. Get Token from Backend
                const res = await fetch(`${BACKEND_URL}/token`);
                if (!res.ok) throw new Error("Failed to fetch token");
                const { token, url } = await res.json();

                if (!mounted) return;

                // 2. Join Room
                const room = new Room();
                roomRef.current = room;

                room
                    .on(RoomEvent.Connected, () => {
                        if (mounted) {
                            console.log('Connected to LiveKit Room');
                            setIsConnected(true);
                            setIsConnecting(false);
                            setInteractionState('listening');
                        }
                    })
                    .on(RoomEvent.Disconnected, () => {
                        if (mounted) {
                            console.log('Disconnected from LiveKit Room');
                            setIsConnected(false);
                            setInteractionState('idle');
                        }
                    })
                    .on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
                        if (mounted && track.kind === 'audio') {
                            console.log('Subscribed to audio track', track.sid);
                            track.attach(); // Automatically play
                            setInteractionState('speaking');
                        }
                    })
                    .on(RoomEvent.TrackUnsubscribed, (track) => {
                        track.detach();
                    });

                await room.connect(url || LIVEKIT_URL, token);

                // 3. Publish Local Microphone
                if (mounted) {
                    try {
                        const localTrack = await createLocalAudioTrack({
                            echoCancellation: true,
                            noiseSuppression: true,
                        });
                        await room.localParticipant.publishTrack(localTrack);
                        console.log('Published local audio track');
                    } catch (micErr) {
                        console.warn('Microphone permission denied or error:', micErr);
                    }
                }

            } catch (err) {
                if (mounted) {
                    console.error('WebRTC Connection Error:', err);
                    setIsConnecting(false);
                }
            }
        };

        connectToRoom();

        return () => {
            mounted = false;
            if (roomRef.current) {
                roomRef.current.disconnect();
            }
        };
    }, []); // Empty dependency array ensures this runs only once on mount

    // Autoplay Policy Fix: Resume AudioContext on first user interaction
    useEffect(() => {
        const handleInteraction = async () => {
            if (roomRef.current) {
                try {
                    await roomRef.current.startAudio();
                    console.log('🔊 AudioContext resumed by user interaction');
                    // Remove listener once successful
                    window.removeEventListener('click', handleInteraction);
                    window.removeEventListener('keydown', handleInteraction);
                } catch (err) {
                    console.warn('Could not resume audio context:', err);
                }
            }
        };

        window.addEventListener('click', handleInteraction);
        window.addEventListener('keydown', handleInteraction);

        return () => {
            window.removeEventListener('click', handleInteraction);
            window.removeEventListener('keydown', handleInteraction);
        };
    }, []);

    return {
        isConnected,
        isConnecting,
        state: interactionState,
        startRecording,
        stopRecording
    };
}
