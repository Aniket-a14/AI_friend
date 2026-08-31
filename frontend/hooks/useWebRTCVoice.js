import { useState, useEffect, useRef, useCallback } from 'react';
import { Room, RoomEvent, ConnectionState, Track, createLocalAudioTrack } from 'livekit-client';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const LIVEKIT_URL = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';
const BACKEND_ACCESS_KEY = process.env.NEXT_PUBLIC_BACKEND_ACCESS_KEY || '';

// Persistent module-level room singleton to survive React StrictMode mount/unmount cycles
let sharedRoom = null;
let sharedLocalAudioTrack = null;
let isInitializing = false;
let disconnectTimer = null;
const stateSubscribers = new Set();
const remoteElements = new Set();

function notifySubscribers(stateUpdate) {
    stateSubscribers.forEach(cb => cb(stateUpdate));
}

async function getOrInitRoom() {
    if (disconnectTimer) {
        clearTimeout(disconnectTimer);
        disconnectTimer = null;
    }

    if (sharedRoom && sharedRoom.state === ConnectionState.Connected) {
        return sharedRoom;
    }

    if (isInitializing) return null;
    isInitializing = true;

    try {
        notifySubscribers({ isConnecting: true });

        // 1. Fetch token
        const participantId = `user_${Date.now().toString(36)}`;
        const tokenUrl = BACKEND_ACCESS_KEY
            ? `${BACKEND_URL}/token?key=${encodeURIComponent(BACKEND_ACCESS_KEY)}&participant=${participantId}`
            : `${BACKEND_URL}/token?participant=${participantId}`;
        const res = await fetch(tokenUrl);
        if (!res.ok) throw new Error("Failed to fetch token from backend");
        const { token, url } = await res.json();

        if (sharedRoom) {
            try {
                await sharedRoom.disconnect();
            } catch {
                // Ignore disconnect errors during reinit
            }
            sharedRoom = null;
        }

        // 2. Instantiate Room
        const room = new Room({
            adaptiveStream: false,
            dynacast: false,
            publishDefaults: {
                red: false,
                dtx: true,
            },
            audioCaptureDefaults: {
                autoGainControl: true,
                echoCancellation: true,
                noiseSuppression: true,
            },
        });

        room
            .on(RoomEvent.Connected, () => {
                console.log('✅ Connected to LiveKit Room');
                notifySubscribers({ isConnected: true, isConnecting: false, interactionState: 'listening' });
            })
            .on(RoomEvent.Disconnected, () => {
                console.log('🔌 Disconnected from LiveKit Room');
                notifySubscribers({ isConnected: false, isConnecting: false, interactionState: 'idle', visemeLevel: 0 });
                remoteElements.forEach(el => el.remove());
                remoteElements.clear();
            })
            .on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
                if (topic !== 'visemes') return;
                try {
                    const viseme = JSON.parse(new TextDecoder().decode(payload));
                    if (typeof viseme.target_level === 'number') {
                        notifySubscribers({ visemeLevel: viseme.target_level });
                    }
                } catch {
                    // Drop malformed frame
                }
            })
            .on(RoomEvent.TrackSubscribed, (track) => {
                if (track.kind === Track.Kind.Audio || track.kind === 'audio') {
                    console.log('🔊 Subscribed to remote audio track:', track.sid);
                    const element = track.attach();
                    element.autoplay = true;
                    element.playsInline = true;
                    element.dataset.livekitRemoteAudio = 'true';
                    element.style.display = 'none';
                    document.body.appendChild(element);
                    remoteElements.add(element);
                    notifySubscribers({ interactionState: 'speaking' });
                }
            })
            .on(RoomEvent.TrackUnsubscribed, (track) => {
                track.detach().forEach((element) => {
                    remoteElements.delete(element);
                    element.remove();
                });
                notifySubscribers({ visemeLevel: 0, interactionState: 'listening' });
            });

        // 3. Connect to SFU
        await room.connect(url || LIVEKIT_URL, token, {
            autoSubscribe: true,
        });

        sharedRoom = room;

        // 4. Create and publish local microphone track explicitly
        try {
            await room.startAudio();
            if (sharedLocalAudioTrack) {
                sharedLocalAudioTrack.stop();
                sharedLocalAudioTrack = null;
            }

            const micTrack = await createLocalAudioTrack({
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            });
            sharedLocalAudioTrack = micTrack;

            await room.localParticipant.publishTrack(micTrack, {
                name: 'microphone',
                source: Track.Source.Microphone,
                red: false,
                dtx: true,
            });

            console.log('🎙️ Microphone track created and published successfully');
        } catch (micErr) {
            console.warn('Microphone activation notice:', micErr);
        }

        return room;
    } catch (err) {
        console.error('WebRTC Connection Error:', err);
        notifySubscribers({ isConnected: false, isConnecting: false });
        return null;
    } finally {
        isInitializing = false;
    }
}

function scheduleRoomTeardown() {
    if (stateSubscribers.size === 0) {
        disconnectTimer = setTimeout(() => {
            if (stateSubscribers.size === 0 && sharedRoom) {
                console.log('Tearing down idle LiveKit room...');
                if (sharedLocalAudioTrack) {
                    sharedLocalAudioTrack.stop();
                    sharedLocalAudioTrack = null;
                }
                sharedRoom.disconnect();
                sharedRoom = null;
            }
        }, 1000);
    }
}

export function useWebRTCVoice() {
    const [isConnected, setIsConnected] = useState(sharedRoom?.state === ConnectionState.Connected);
    const [isConnecting, setIsConnecting] = useState(isInitializing);
    const [interactionState, setInteractionState] = useState('idle'); // idle | listening | speaking
    const [visemeLevel, setVisemeLevel] = useState(0);

    const startRecording = useCallback(async () => {
        setInteractionState('listening');
        if (sharedLocalAudioTrack && sharedLocalAudioTrack.isMuted) {
            await sharedLocalAudioTrack.unmute();
        }
    }, []);

    const stopRecording = useCallback(async () => {
        setInteractionState('idle');
        if (sharedLocalAudioTrack && !sharedLocalAudioTrack.isMuted) {
            await sharedLocalAudioTrack.mute();
        }
    }, []);

    useEffect(() => {
        const handleStateUpdate = (update) => {
            if (update.isConnected !== undefined) setIsConnected(update.isConnected);
            if (update.isConnecting !== undefined) setIsConnecting(update.isConnecting);
            if (update.interactionState !== undefined) setInteractionState(update.interactionState);
            if (update.visemeLevel !== undefined) setVisemeLevel(update.visemeLevel);
        };

        stateSubscribers.add(handleStateUpdate);

        // Connect to room if not yet initiated
        if (!sharedRoom || sharedRoom.state === ConnectionState.Disconnected) {
            getOrInitRoom();
        }

        return () => {
            stateSubscribers.delete(handleStateUpdate);
            scheduleRoomTeardown();
        };
    }, []);

    // Autoplay Policy Fix: Resume AudioContext on any user gesture
    useEffect(() => {
        const handleInteraction = async () => {
            if (sharedRoom && sharedRoom.canPlaybackAudio === false) {
                try {
                    await sharedRoom.startAudio();
                    console.log('🔊 AudioContext unlocked by user gesture');
                } catch (err) {
                    console.warn('Could not resume audio context:', err);
                }
            }
        };

        window.addEventListener('click', handleInteraction);
        window.addEventListener('touchstart', handleInteraction);
        window.addEventListener('keydown', handleInteraction);

        return () => {
            window.removeEventListener('click', handleInteraction);
            window.removeEventListener('touchstart', handleInteraction);
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
