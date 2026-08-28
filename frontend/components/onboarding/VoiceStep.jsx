'use client';

import { useEffect, useRef, useState } from 'react';
import { Heading, Card, PrimaryButton, SecondaryButton, ErrorBanner } from './ui';
import { useVoiceRecorder } from '@/hooks/useVoiceRecorder';
import { apiPostForm } from '@/lib/api';

const CONSENT_NOTICE =
    'This records your voice to clone it. Please only use your own voice, or a ' +
    'voice you have the right to use — someone else’s likeness deserves their ' +
    'consent, not just yours.';

export default function VoiceStep({ busy, error, onSkip, onContinue }) {
    const { isRecording, elapsedSeconds, error: recorderError, start, stop } = useVoiceRecorder();
    const [consented, setConsented] = useState(false);
    const [clip, setClip] = useState(null); // { blob, durationS, url }
    const [validating, setValidating] = useState(false);
    const [problems, setProblems] = useState([]);
    const [transcript, setTranscript] = useState('');
    const [validateError, setValidateError] = useState(null);
    const audioRef = useRef(null);

    useEffect(() => {
        return () => {
            if (clip?.url) URL.revokeObjectURL(clip.url);
        };
    }, [clip]);

    const validateClip = async (blob) => {
        setValidating(true);
        setValidateError(null);
        try {
            const formData = new FormData();
            formData.append('file', blob, 'clip.wav');
            const result = await apiPostForm('/api/voice/validate', formData);
            setProblems(result.problems || []);
            setTranscript(result.transcript || '');
        } catch (err) {
            setValidateError(err.message || 'Could not validate the clip.');
        } finally {
            setValidating(false);
        }
    };

    const handleStop = () => {
        const result = stop();
        if (!result) return;
        const url = URL.createObjectURL(result.blob);
        setClip({ blob: result.blob, durationS: result.durationS, url });
        validateClip(result.blob);
    };

    const handleRerecord = () => {
        if (clip?.url) URL.revokeObjectURL(clip.url);
        setClip(null);
        setProblems([]);
        setTranscript('');
        setValidateError(null);
        start();
    };

    return (
        <div className="max-w-2xl mx-auto">
            <Heading>Record their voice</Heading>
            <p className="mt-4 text-black/50 leading-relaxed">{CONSENT_NOTICE}</p>

            {!consented ? (
                <div className="mt-8 flex flex-wrap items-center gap-3">
                    <PrimaryButton onClick={() => setConsented(true)}>I understand, continue</PrimaryButton>
                    <SecondaryButton onClick={onSkip}>Skip for now (use the default voice)</SecondaryButton>
                </div>
            ) : (
                <>
                    <Card className="mt-8">
                        {!clip ? (
                            <div className="flex flex-col items-center py-10 text-center">
                                {isRecording ? (
                                    <>
                                        <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse mb-4" />
                                        <div className="text-2xl font-light mb-6" style={{ fontFamily: 'var(--font-ibm-plex)' }}>
                                            {elapsedSeconds.toFixed(1)}s
                                        </div>
                                        <SecondaryButton onClick={handleStop}>Stop recording</SecondaryButton>
                                    </>
                                ) : (
                                    <>
                                        <p className="text-sm text-black/45 mb-6 max-w-sm">
                                            Speak naturally for about 8 seconds, as if talking to a friend.
                                        </p>
                                        <PrimaryButton onClick={start}>Start recording</PrimaryButton>
                                    </>
                                )}
                                <ErrorBanner>{recorderError}</ErrorBanner>
                            </div>
                        ) : (
                            <div>
                                <div className="text-xs text-black/30 tracking-widest uppercase mb-3">
                                    Recorded clip · {clip.durationS.toFixed(1)}s
                                </div>
                                <audio ref={audioRef} src={clip.url} controls className="w-full mb-4" />

                                {validating && <p className="text-sm text-black/40">Checking the recording…</p>}

                                {!validating && problems.length > 0 && (
                                    <div className="rounded-xl border border-amber-500/20 bg-amber-50 text-amber-800 text-sm px-4 py-3 mb-4">
                                        <p className="font-medium mb-1">This clip may not be great for voice cloning:</p>
                                        <ul className="list-disc list-inside space-y-0.5">
                                            {problems.map((p) => (
                                                <li key={p}>{p}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {!validating && (
                                    <label className="block mb-4">
                                        <span className="text-xs text-black/40 tracking-widest uppercase">Transcript</span>
                                        <textarea
                                            value={transcript}
                                            onChange={(e) => setTranscript(e.target.value)}
                                            rows={2}
                                            placeholder="What was said in the clip…"
                                            className="mt-2 w-full rounded-xl border border-black/[0.08] bg-white p-3 text-sm focus:outline-none focus:border-black/25 resize-none"
                                        />
                                    </label>
                                )}

                                <ErrorBanner>{validateError}</ErrorBanner>

                                <div className="flex flex-wrap gap-3">
                                    <PrimaryButton
                                        onClick={() => onContinue({ blob: clip.blob, transcript })}
                                        disabled={busy || validating || !transcript.trim() || problems.length > 0}
                                    >
                                        Use this clip
                                    </PrimaryButton>
                                    <SecondaryButton onClick={handleRerecord} disabled={busy}>
                                        Re-record
                                    </SecondaryButton>
                                    {problems.length > 0 && (
                                        <SecondaryButton
                                            onClick={() => onContinue({ blob: clip.blob, transcript, force: true })}
                                            disabled={busy || validating || !transcript.trim()}
                                        >
                                            Use it anyway
                                        </SecondaryButton>
                                    )}
                                </div>
                            </div>
                        )}
                    </Card>
                    <div className="mt-4">
                        <SecondaryButton onClick={onSkip} disabled={busy || isRecording}>
                            Skip for now (use the default voice)
                        </SecondaryButton>
                    </div>
                </>
            )}

            <div className="mt-4">
                <ErrorBanner>{error}</ErrorBanner>
            </div>
        </div>
    );
}
