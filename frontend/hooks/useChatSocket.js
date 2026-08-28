'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { backendWsUrl } from '@/lib/api';

// Reconnect with the same exponential-backoff-plus-jitter shape
// useWebRTCVoice.js's LiveKit room already assumes for its own connection --
// a text chat left open in a background tab should recover the same way a
// dropped voice call does, not require a manual page reload.
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

function mergeChatOutput(prev, output) {
    const turnId = output.turn_id || `untracked-${Date.now()}`;
    const idx = prev.findIndex((m) => m.role === 'friend' && m.turnId === turnId);
    const priorContent = idx >= 0 ? prev[idx].content : '';
    const accumulated = output.content
        ? `${priorContent}${priorContent && !priorContent.endsWith(' ') ? ' ' : ''}${output.content}`
        : priorContent;
    const entry = {
        turnId,
        role: 'friend',
        // The done message's full_response is the canonical text -- prefer
        // it over the client-side accumulation so a dropped chunk (a NAK'd
        // redelivery, a message that arrived out of order) can't leave the
        // rendered transcript permanently short of what was actually said.
        content: output.done && output.full_response ? output.full_response : accumulated,
        done: output.done,
        proactive: !!output.proactive,
        error: output.generation_error || null,
        timestamp: output.timestamp,
    };
    if (idx >= 0) {
        const next = [...prev];
        next[idx] = entry;
        return next;
    }
    return [...prev, entry];
}

export function useChatSocket() {
    const [messages, setMessages] = useState([]);
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);
    const reconnectAttempt = useRef(0);
    const reconnectTimer = useRef(null);
    const closedByUnmount = useRef(false);

    useEffect(() => {
        closedByUnmount.current = false;

        function connect() {
            let ws;
            try {
                ws = new WebSocket(backendWsUrl('/api/chat/ws'));
            } catch {
                setError('Could not open a chat connection.');
                return;
            }
            wsRef.current = ws;

            ws.onopen = () => {
                reconnectAttempt.current = 0;
                setConnected(true);
                setError(null);
            };

            ws.onmessage = (event) => {
                let output;
                try {
                    output = JSON.parse(event.data);
                } catch {
                    return;
                }
                setMessages((prev) => mergeChatOutput(prev, output));
            };

            ws.onerror = () => {
                setError('Chat connection error.');
            };

            ws.onclose = () => {
                setConnected(false);
                wsRef.current = null;
                if (closedByUnmount.current) return;
                const delay = Math.min(
                    RECONNECT_MAX_MS,
                    RECONNECT_BASE_MS * 2 ** reconnectAttempt.current
                );
                reconnectAttempt.current += 1;
                reconnectTimer.current = setTimeout(connect, delay);
            };
        }

        connect();

        return () => {
            closedByUnmount.current = true;
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            wsRef.current?.close();
        };
    }, []);

    const sendMessage = useCallback((text) => {
        const trimmed = text.trim();
        if (!trimmed) return false;
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            setError('Not connected -- your friend will see this once the connection is back.');
            return false;
        }
        setMessages((prev) => [
            ...prev,
            { turnId: `local-${Date.now()}`, role: 'user', content: trimmed, done: true },
        ]);
        ws.send(trimmed);
        return true;
    }, []);

    return { messages, connected, error, sendMessage };
}
