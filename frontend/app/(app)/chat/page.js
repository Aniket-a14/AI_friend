'use client';

import { useEffect, useRef, useState } from 'react';

import { Card, ErrorBanner, Heading, PrimaryButton, Tag } from '@/components/ui';
import { useChatSocket } from '@/hooks/useChatSocket';

function Bubble({ message }) {
    const isUser = message.role === 'user';
    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] ${isUser ? 'text-right' : 'text-left'}`}>
                {message.proactive && <Tag>reached out first</Tag>}
                <div
                    className={`mt-1 px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                        isUser
                            ? 'bg-[#111] text-white'
                            : 'bg-white border border-black/[0.07] text-[#111]'
                    }`}
                >
                    {message.content || (!message.done ? '…' : '')}
                </div>
                {message.error && (
                    <p className="mt-1 text-xs text-red-600">{message.error}</p>
                )}
            </div>
        </div>
    );
}

export default function ChatPage() {
    const { messages, connected, error, sendMessage } = useChatSocket();
    const [draft, setDraft] = useState('');
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const submit = (e) => {
        e.preventDefault();
        if (sendMessage(draft)) setDraft('');
    };

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
                <Heading>Chat</Heading>
                <div className="flex items-center gap-2 text-xs text-black/40">
                    <span
                        className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-400'}`}
                    />
                    {connected ? 'Connected' : 'Reconnecting…'}
                </div>
            </div>

            <ErrorBanner>{error}</ErrorBanner>

            <Card className="flex flex-col h-[60vh] p-4 md:p-6">
                <div className="flex-1 overflow-y-auto flex flex-col gap-4 pr-1">
                    {messages.length === 0 && (
                        <p className="text-sm text-black/40 text-center my-auto">
                            Say something -- this goes through the real mesh: memory,
                            affect, everything. Voice replies land here too.
                        </p>
                    )}
                    {messages.map((m) => (
                        <Bubble key={m.turnId} message={m} />
                    ))}
                    <div ref={bottomRef} />
                </div>

                <form onSubmit={submit} className="mt-4 flex gap-2">
                    <input
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        placeholder="Type a message…"
                        className="flex-1 rounded-xl border border-black/10 px-4 py-2.5 text-sm outline-none focus:border-black/30 bg-white"
                    />
                    <PrimaryButton type="submit" disabled={!draft.trim()}>
                        Send
                    </PrimaryButton>
                </form>
            </Card>
        </div>
    );
}
