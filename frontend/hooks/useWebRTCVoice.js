import { useState, useEffect, useRef, useCallback } from 'react';
import { Room, RoomEvent, createLocalAudioTrack } from 'livekit-client';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const LIVEKIT_URL = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';
// Only needed when the backend is reached from a device other than the one
// running it (BACKEND_ACCESS_KEY on the backend); unset for same-machine use.
const BACKEND_ACCESS_KEY = process.env.NEXT_PUBLIC_BACKEND_ACCESS_KEY || '';

export function useWebRTCVoice() {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [interactionState, setInteractionState] = useState('idle'); // idle | listening | speaking
    // Phase 5.3: transport_agent bridges voice-agent's viseme stream onto
    // this room's data channel (topic "visemes") -- 0..1, how loud the
    // current audio chunk is. Not a mouth shape (AssistantCircle is an
    // abstract aura, not a face); the visual equivalent is pulsing the aura
    // with the sound rather than on a fixed animation loop.
    const [visemeLevel, setVisemeLevel] = useState(0);

    const roomRef = useRef(null);
    const audioTrackRef = useRef(null);
    const remoteAudioElementsRef = useRef(new Set());
    const isConnectedRef = useRef(false);
    const isConnectingRef = useRef(false);

    const startRecording = useCallback(async () => {
        setInteractionState('listening');
    }, []);

    const stopRecording = useCallback(() => {
        setInteractionState('idle');
    }, []);

    useEffect(() => {
        isConnectedRef.current = isConnected;
    }, [isConnected]);

    useEffect(() => {
        isConnectingRef.current = isConnecting;
    }, [isConnecting]);

    useEffect(() => {
        let mounted = true;
        const remoteAudioElements = remoteAudioElementsRef.current;

        const connectToRoom = async () => {
            if (isConnectedRef.current || isConnectingRef.current) return;

            setIsConnecting(true);
            try {
                // 1. Get Token from Backend
                // Query param, not a custom header: a custom header forces a CORS
                // preflight (OPTIONS) round-trip before every session start, and
                // the key is already exposed in the client bundle either way.
                const tokenUrl = BACKEND_ACCESS_KEY
                    ? `${BACKEND_URL}/token?key=${encodeURIComponent(BACKEND_ACCESS_KEY)}`
                    : `${BACKEND_URL}/token`;
                const res = await fetch(tokenUrl);
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
                            setVisemeLevel(0);
                        }
                    })
                    .on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
                        if (!mounted || topic !== 'visemes') return;
                        try {
                            const viseme = JSON.parse(new TextDecoder().decode(payload));
                            if (typeof viseme.target_level === 'number') {
                                setVisemeLevel(viseme.target_level);
                            }
                        } catch {
                            // Best-effort animation signal -- drop a malformed frame.
                        }
                    })
                    .on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
                        if (mounted && track.kind === 'audio') {
                            console.log('Subscribed to audio track', track.sid);
                            const element = track.attach();
                            element.autoplay = true;
                            element.playsInline = true;
                            element.dataset.livekitRemoteAudio = 'true';
                            element.style.display = 'none';
                            document.body.appendChild(element);
                            remoteAudioElements.add(element);
                            setInteractionState('speaking');
                        }
                    })
                    .on(RoomEvent.TrackUnsubscribed, (track) => {
                        track.detach().forEach((element) => {
                            remoteAudioElements.delete(element);
                            element.remove();
                        });
                        setVisemeLevel(0);
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
                        audioTrackRef.current = localTrack;
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
            if (audioTrackRef.current) {
                audioTrackRef.current.stop();
                audioTrackRef.current = null;
            }
            remoteAudioElements.forEach((element) => element.remove());
            remoteAudioElements.clear();
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
        visemeLevel,
        startRecording,
        stopRecording
    };
}
