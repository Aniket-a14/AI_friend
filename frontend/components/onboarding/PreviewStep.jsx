'use client';

import { useState } from 'react';
import { Heading, Tag, Card, PrimaryButton, SecondaryButton, ErrorBanner } from './ui';
import { apiPostJson } from '@/lib/api';

function List({ items, empty = '—' }) {
    if (!items || items.length === 0) return <span className="text-black/30">{empty}</span>;
    return <span>{items.join(', ')}</span>;
}

function DryRunChat({ profile }) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);

    const send = async () => {
        const text = input.trim();
        if (!text || sending) return;
        setInput('');
        setMessages((prev) => [...prev, { role: 'you', text }]);
        setSending(true);
        try {
            const { reply } = await apiPostJson('/api/persona/dry-run-chat', {
                profile,
                message: text,
            });
            setMessages((prev) => [...prev, { role: 'them', text: reply }]);
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                { role: 'them', text: `(couldn't reach them: ${err.message})` },
            ]);
        } finally {
            setSending(false);
        }
    };

    if (!open) {
        return (
            <SecondaryButton onClick={() => setOpen(true)}>
                Talk to them first
            </SecondaryButton>
        );
    }

    return (
        <Card className="mt-2">
            <div className="text-xs text-black/30 tracking-widest uppercase mb-4">
                Preview conversation — not saved, no memory
            </div>
            <div className="space-y-3 max-h-64 overflow-y-auto mb-4">
                {messages.length === 0 && (
                    <p className="text-sm text-black/30">Say something to see how they respond.</p>
                )}
                {messages.map((m, i) => (
                    <div key={i} className={m.role === 'you' ? 'text-right' : 'text-left'}>
                        <span
                            className={`inline-block px-3 py-2 rounded-xl text-sm max-w-[80%] ${
                                m.role === 'you' ? 'bg-black/[0.06] text-[#111]' : 'bg-[#F5F4F0] text-[#111]'
                            }`}
                        >
                            {m.text}
                        </span>
                    </div>
                ))}
            </div>
            <div className="flex gap-2">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && send()}
                    placeholder="Say hi…"
                    className="flex-1 bg-white border border-black/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-black/25"
                    disabled={sending}
                />
                <SecondaryButton onClick={send} disabled={sending || !input.trim()}>
                    Send
                </SecondaryButton>
            </div>
        </Card>
    );
}

export default function PreviewStep({ compiled, busy, error, onRegenerate, onEditDescription, onContinue }) {
    const { profile, biography_markdown, inferences, immutable_core } = compiled;

    return (
        <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between">
                <Heading>{profile.name}</Heading>
                <Tag>Preview</Tag>
            </div>

            <div className="mt-8 space-y-4">
                <Card>
                    <div className="text-xs text-black/30 tracking-widest uppercase mb-4">
                        Immutable — fixed, not editable
                    </div>
                    <dl className="space-y-2 text-sm">
                        <div>
                            <dt className="text-black/40 inline">values&nbsp;</dt>
                            <dd className="inline text-[#111]">
                                <List items={immutable_core?.values} />
                            </dd>
                        </div>
                        <div>
                            <dt className="text-black/40 inline">boundaries&nbsp;</dt>
                            <dd className="inline text-[#111]">
                                <List items={immutable_core?.boundaries} />
                            </dd>
                        </div>
                    </dl>
                </Card>

                <Card>
                    <div className="text-xs text-black/30 tracking-widest uppercase mb-4">
                        Constitutional — who they fundamentally are
                    </div>
                    <dl className="space-y-2 text-sm">
                        <div><dt className="text-black/40 inline">tone&nbsp;</dt><dd className="inline text-[#111]">{profile.base_tone}</dd></div>
                        <div><dt className="text-black/40 inline">traits&nbsp;</dt><dd className="inline text-[#111]"><List items={profile.traits} /></dd></div>
                        <div><dt className="text-black/40 inline">speech patterns&nbsp;</dt><dd className="inline text-[#111]"><List items={profile.speech_patterns} /></dd></div>
                        <div><dt className="text-black/40 inline">never says&nbsp;</dt><dd className="inline text-[#111]"><List items={profile.avoid} /></dd></div>
                    </dl>
                    {profile.identity_summary && (
                        <p className="mt-4 text-sm text-black/60 leading-relaxed border-t border-black/[0.06] pt-4">
                            {profile.identity_summary}
                        </p>
                    )}
                    {inferences?.length > 0 && (
                        <div className="mt-4 border-t border-black/[0.06] pt-4 space-y-1.5">
                            <div className="text-[11px] text-black/30 tracking-widest uppercase mb-2">
                                Temperament inferred from what you wrote
                            </div>
                            {inferences.map((inf) => (
                                <div key={inf.field} className="text-xs text-black/45 flex gap-2">
                                    <span className="text-black/70 font-medium min-w-[11rem] shrink-0">{inf.field}</span>
                                    <span>{inf.value.toFixed(3)} — {inf.reason}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </Card>

                <Card>
                    <div className="text-xs text-black/30 tracking-widest uppercase mb-4">
                        Adaptive — where the relationship starts
                    </div>
                    <dl className="space-y-2 text-sm">
                        <div><dt className="text-black/40 inline">relationship&nbsp;</dt><dd className="inline text-[#111]">{profile.relationship}</dd></div>
                        <div><dt className="text-black/40 inline">initial trust&nbsp;</dt><dd className="inline text-[#111]">{profile.initial_trust}</dd></div>
                        <div><dt className="text-black/40 inline">initial attachment&nbsp;</dt><dd className="inline text-[#111]">{profile.initial_attachment}</dd></div>
                    </dl>
                </Card>

                {biography_markdown && (
                    <Card>
                        <div className="text-xs text-black/30 tracking-widest uppercase mb-4">Biography</div>
                        <pre className="whitespace-pre-wrap font-sans text-sm text-black/60 leading-relaxed">
                            {biography_markdown}
                        </pre>
                    </Card>
                )}
            </div>

            <div className="mt-6">
                <DryRunChat profile={profile} />
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-3">
                <PrimaryButton onClick={onContinue} disabled={busy}>
                    Continue to voice
                </PrimaryButton>
                <SecondaryButton onClick={onRegenerate} disabled={busy}>
                    {busy ? 'Regenerating…' : 'Regenerate'}
                </SecondaryButton>
                <SecondaryButton onClick={onEditDescription} disabled={busy}>
                    Edit description
                </SecondaryButton>
            </div>

            <div className="mt-4">
                <ErrorBanner>{error}</ErrorBanner>
            </div>
        </div>
    );
}
