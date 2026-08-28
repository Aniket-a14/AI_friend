'use client';

import { useState } from 'react';
import { StepIndicator } from '@/components/onboarding/ui';
import DescribeStep from '@/components/onboarding/DescribeStep';
import PreviewStep from '@/components/onboarding/PreviewStep';
import VoiceStep from '@/components/onboarding/VoiceStep';
import DoneStep from '@/components/onboarding/DoneStep';
import { apiPostJson, apiPostForm, ApiError } from '@/lib/api';

const STEPS = ['describe', 'preview', 'voice', 'done'];

export default function OnboardingPage() {
    const [step, setStep] = useState('describe');
    const [description, setDescription] = useState('');
    const [compiled, setCompiled] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const [voiceSaved, setVoiceSaved] = useState(false);
    const [forceOverwrite, setForceOverwrite] = useState(false);

    const compile = async (text) => {
        setBusy(true);
        setError(null);
        try {
            const result = await apiPostJson('/api/persona/compile', { description: text });
            setDescription(text);
            setCompiled(result);
            setStep('preview');
        } catch (err) {
            setError(err.message || 'Could not compile a persona from that.');
        } finally {
            setBusy(false);
        }
    };

    const commitPersona = async () => {
        return apiPostJson('/api/persona/commit', {
            profile: compiled.profile,
            biography_markdown: compiled.biography_markdown,
            force: forceOverwrite,
        });
    };

    const finish = async (voiceClip) => {
        setBusy(true);
        setError(null);
        try {
            await commitPersona();
        } catch (err) {
            if (err instanceof ApiError && err.status === 409) {
                setError(
                    'A friend already exists at personal/persona.toml. Continuing will ' +
                        'overwrite them — this cannot be undone. Press "Use this clip" / ' +
                        '"Skip" again to confirm.'
                );
                setForceOverwrite(true);
            } else {
                setError(err.message || 'Could not save the persona.');
            }
            setBusy(false);
            return;
        }

        if (voiceClip) {
            try {
                const formData = new FormData();
                formData.append('file', voiceClip.blob, 'clip.wav');
                formData.append('transcript', voiceClip.transcript);
                if (voiceClip.force) formData.append('force', 'true');
                await apiPostForm('/api/voice/commit', formData);
                setVoiceSaved(true);
            } catch (err) {
                setError(
                    `The persona saved, but the voice clip did not: ${err.message || 'unknown error'}. ` +
                        'The default bundled voice will be used instead.'
                );
                setBusy(false);
                setStep('done');
                return;
            }
        }

        setBusy(false);
        setStep('done');
    };

    return (
        <main className="px-6 md:px-12 py-12 md:py-20">
            <div className="max-w-3xl mx-auto mb-12 flex items-center justify-between">
                <span className="text-xs tracking-[0.25em] text-black/40" style={{ fontFamily: 'var(--font-pixel)' }}>
                    CREATE YOUR FRIEND
                </span>
                {step !== 'done' && <StepIndicator steps={STEPS.slice(0, 3)} current={STEPS.indexOf(step)} />}
            </div>

            {step === 'describe' && (
                <DescribeStep initialValue={description} busy={busy} error={error} onSubmit={compile} />
            )}

            {step === 'preview' && compiled && (
                <PreviewStep
                    compiled={compiled}
                    busy={busy}
                    error={error}
                    onRegenerate={() => compile(description)}
                    onEditDescription={() => setStep('describe')}
                    onContinue={() => {
                        setError(null);
                        setStep('voice');
                    }}
                />
            )}

            {step === 'voice' && (
                <VoiceStep
                    busy={busy}
                    error={error}
                    onSkip={() => finish(null)}
                    onContinue={(clip) => finish(clip)}
                />
            )}

            {step === 'done' && compiled && (
                <DoneStep name={compiled.profile.name} voiceSaved={voiceSaved} />
            )}
        </main>
    );
}
