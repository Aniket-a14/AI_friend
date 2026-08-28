'use client';

import { useCallback, useRef, useState } from 'react';

// Records raw PCM via the Web Audio API and encodes it to a WAV Blob
// directly, rather than `MediaRecorder` -- deliberately. `MediaRecorder`'s
// output format is compressed and browser-dependent (webm/opus in Chrome,
// mp4/aac in Safari, not WAV in either), and backend/app/api/voice.py's
// /validate and /commit endpoints only decode WAV (matching what
// `scripts/audio/record_voice.py` already produces -- see that endpoint's
// module docstring for why). Encoding to WAV client-side means every
// browser reaches the same server-side code path, with no server-side
// transcode step to add and keep correct.
//
// Uses `ScriptProcessorNode` rather than an `AudioWorklet`. It's
// deprecated but universally supported and needs no separate worklet
// module file; this hook runs for a handful of short recordings during
// onboarding, not on a latency-sensitive hot path, so the callback-based
// API's downsides don't apply here.

function encodeWav(chunks, sampleRate) {
    const totalLength = chunks.reduce((sum, c) => sum + c.length, 0);
    const pcm = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
        pcm.set(chunk, offset);
        offset += chunk.length;
    }

    const bytesPerSample = 2; // 16-bit PCM
    const buffer = new ArrayBuffer(44 + pcm.length * bytesPerSample);
    const view = new DataView(buffer);

    const writeString = (offset, str) => {
        for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + pcm.length * bytesPerSample, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * bytesPerSample, true); // byte rate
    view.setUint16(32, bytesPerSample, true); // block align
    view.setUint16(34, 16, true); // bits per sample
    writeString(36, 'data');
    view.setUint32(40, pcm.length * bytesPerSample, true);

    let pos = 44;
    for (let i = 0; i < pcm.length; i++) {
        const clamped = Math.max(-1, Math.min(1, pcm[i]));
        view.setInt16(pos, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
        pos += 2;
    }

    return new Blob([buffer], { type: 'audio/wav' });
}

export function useVoiceRecorder() {
    const [isRecording, setIsRecording] = useState(false);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const [error, setError] = useState(null);

    const audioContextRef = useRef(null);
    const streamRef = useRef(null);
    const processorRef = useRef(null);
    const sourceRef = useRef(null);
    const chunksRef = useRef([]);
    const startedAtRef = useRef(0);
    const tickRef = useRef(null);

    const cleanup = useCallback(() => {
        if (tickRef.current) {
            clearInterval(tickRef.current);
            tickRef.current = null;
        }
        processorRef.current?.disconnect();
        sourceRef.current?.disconnect();
        streamRef.current?.getTracks().forEach((t) => t.stop());
        audioContextRef.current?.close().catch(() => {});
        processorRef.current = null;
        sourceRef.current = null;
        streamRef.current = null;
        audioContextRef.current = null;
    }, []);

    const start = useCallback(async () => {
        setError(null);
        chunksRef.current = [];
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            const audioContext = new AudioCtx();
            const source = audioContext.createMediaStreamSource(stream);
            // 4096-sample buffer: small enough for a responsive stop(), large
            // enough not to spend most of the recording in callback overhead.
            const processor = audioContext.createScriptProcessor(4096, 1, 1);

            processor.onaudioprocess = (event) => {
                const input = event.inputBuffer.getChannelData(0);
                chunksRef.current.push(new Float32Array(input));
            };

            source.connect(processor);
            processor.connect(audioContext.destination);

            streamRef.current = stream;
            audioContextRef.current = audioContext;
            sourceRef.current = source;
            processorRef.current = processor;
            startedAtRef.current = Date.now();
            setElapsedSeconds(0);
            tickRef.current = setInterval(() => {
                setElapsedSeconds((Date.now() - startedAtRef.current) / 1000);
            }, 200);
            setIsRecording(true);
        } catch (err) {
            setError(err?.message || 'Could not access the microphone.');
            cleanup();
        }
    }, [cleanup]);

    const stop = useCallback(() => {
        if (!audioContextRef.current) return null;
        const sampleRate = audioContextRef.current.sampleRate;
        const blob = encodeWav(chunksRef.current, sampleRate);
        const durationS = chunksRef.current.reduce((sum, c) => sum + c.length, 0) / sampleRate;
        cleanup();
        setIsRecording(false);
        return { blob, durationS, sampleRate };
    }, [cleanup]);

    return { isRecording, elapsedSeconds, error, start, stop };
}
