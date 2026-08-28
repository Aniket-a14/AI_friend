'use client';

import { useState } from 'react';
import { Heading, PrimaryButton, ErrorBanner } from './ui';

export default function DescribeStep({ initialValue, busy, error, onSubmit }) {
    const [description, setDescription] = useState(initialValue || '');

    return (
        <div className="max-w-2xl mx-auto">
            <Heading>Describe your friend</Heading>
            <p className="mt-4 text-black/50 leading-relaxed max-w-lg">
                Personality, how they talk, what annoys them, backstory — anything at
                all, in your own words. Write as much or as little as you like.
            </p>

            <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="She's blunt and loyal, hates small talk, gets genuinely annoyed when I dodge a question. Grew up somewhere cold..."
                rows={10}
                className="mt-8 w-full rounded-2xl border border-black/[0.08] bg-white p-5 text-[15px] leading-relaxed text-[#111] placeholder:text-black/25 focus:outline-none focus:border-black/25 transition-colors resize-none"
                disabled={busy}
            />

            <div className="mt-6 flex items-center gap-4">
                <PrimaryButton
                    onClick={() => onSubmit(description)}
                    disabled={busy || !description.trim()}
                >
                    {busy ? 'Thinking about who this is…' : 'Continue'}
                </PrimaryButton>
                <span className="text-xs text-black/30">
                    Nothing is saved until you confirm at the end.
                </span>
            </div>

            <div className="mt-4">
                <ErrorBanner>{error}</ErrorBanner>
            </div>
        </div>
    );
}
