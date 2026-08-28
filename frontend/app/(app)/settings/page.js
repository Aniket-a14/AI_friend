'use client';

import { useEffect, useState } from 'react';

import VoiceStep from '@/components/onboarding/VoiceStep';
import { Card, ErrorBanner, Heading, SecondaryButton } from '@/components/ui';
import { apiGet, apiPostForm } from '@/lib/api';

export default function SettingsPage() {
    const [persona, setPersona] = useState(null);
    const [loadError, setLoadError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [reRecording, setReRecording] = useState(false);
    const [voiceBusy, setVoiceBusy] = useState(false);
    const [voiceError, setVoiceError] = useState(null);
    const [voiceSaved, setVoiceSaved] = useState(false);

    useEffect(() => {
        let cancelled = false;
        apiGet('/api/persona/live')
            .then((data) => {
                if (!cancelled) setPersona(data);
            })
            .catch((err) => {
                if (!cancelled) setLoadError(err.message || 'Could not load your friend.');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const commitVoice = async ({ blob, transcript, force }) => {
        setVoiceBusy(true);
        setVoiceError(null);
        try {
            const formData = new FormData();
            formData.append('file', blob, 'clip.wav');
            formData.append('transcript', transcript);
            if (force) formData.append('force', 'true');
            await apiPostForm('/api/voice/commit', formData);
            setVoiceSaved(true);
            setReRecording(false);
        } catch (err) {
            setVoiceError(err.message || 'Could not save the clip.');
        } finally {
            setVoiceBusy(false);
        }
    };

    return (
        <div className="flex flex-col gap-10">
            <Heading>Settings</Heading>

            <section>
                <div className="text-xs text-black/30 tracking-widest uppercase mb-3">
                    About your friend
                </div>
                {loading && <p className="text-sm text-black/40">Loading…</p>}
                <ErrorBanner>{loadError}</ErrorBanner>
                {persona && (
                    <Card>
                        <div className="text-lg font-medium mb-1">{persona.persona.name}</div>
                        <p className="text-sm text-black/50 mb-4">{persona.persona.base_tone}</p>
                        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
                            <dt className="text-black/40">Relationship</dt>
                            <dd>{persona.relationship}</dd>
                            <dt className="text-black/40">Traits</dt>
                            <dd>{persona.persona.traits.join(', ') || '—'}</dd>
                            <dt className="text-black/40">Adaptive traits</dt>
                            <dd>{persona.persona.adaptive_traits.join(', ') || 'none learned yet'}</dd>
                            <dt className="text-black/40">Seeded</dt>
                            <dd>
                                {persona.seeded_from_file
                                    ? new Date(persona.seeded_from_file).toLocaleString()
                                    : 'never — running on defaults'}
                            </dd>
                        </dl>
                        <p className="mt-4 text-xs text-black/35 leading-relaxed">
                            Trust, attachment, and adaptive traits are grown through
                            conversation, not edited here — the persona file only ever seeds a
                            friend once, on its first boot.
                        </p>
                    </Card>
                )}
            </section>

            <section>
                <div className="text-xs text-black/30 tracking-widest uppercase mb-3">Voice</div>
                {!reRecording ? (
                    <Card className="flex items-center justify-between gap-4 flex-wrap">
                        <p className="text-sm text-black/50">
                            {voiceSaved
                                ? 'New voice saved -- restart the mesh to hear it.'
                                : 'Record a new reference clip for your friend to speak with.'}
                        </p>
                        <SecondaryButton onClick={() => setReRecording(true)}>
                            Re-record
                        </SecondaryButton>
                    </Card>
                ) : (
                    <VoiceStep
                        busy={voiceBusy}
                        error={voiceError}
                        onSkip={() => setReRecording(false)}
                        onContinue={commitVoice}
                    />
                )}
            </section>
        </div>
    );
}
