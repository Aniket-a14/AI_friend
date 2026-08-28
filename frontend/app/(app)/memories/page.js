'use client';

import { useEffect, useState } from 'react';

import { Card, ErrorBanner, Heading } from '@/components/ui';
import { apiGet } from '@/lib/api';

const SORTS = [
    { key: 'created_at', label: 'Newest' },
    { key: 'importance_score', label: 'Most important' },
    { key: 'last_recalled_at', label: 'Recently recalled' },
];
const PAGE_SIZE = 20;

function formatDate(value) {
    if (!value) return '—';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function MemoriesPage() {
    const [sortBy, setSortBy] = useState('created_at');
    const [offset, setOffset] = useState(0);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        apiGet(`/api/memory/recent?limit=${PAGE_SIZE}&offset=${offset}&sort_by=${sortBy}`)
            .then((res) => {
                if (!cancelled) {
                    setData(res);
                    setError(null);
                }
            })
            .catch((err) => {
                if (!cancelled) setError(err.message || 'Could not load memories.');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [sortBy, offset]);

    const changeSort = (key) => {
        setSortBy(key);
        setOffset(0);
        setLoading(true);
    };

    const goPrev = () => {
        setOffset((o) => Math.max(0, o - PAGE_SIZE));
        setLoading(true);
    };

    const goNext = () => {
        setOffset((o) => o + PAGE_SIZE);
        setLoading(true);
    };

    const total = data?.total ?? 0;
    const page = Math.floor(offset / PAGE_SIZE) + 1;
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between flex-wrap gap-3">
                <Heading>Memories</Heading>
                <div className="flex gap-1">
                    {SORTS.map((s) => (
                        <button
                            key={s.key}
                            onClick={() => changeSort(s.key)}
                            className={`px-3 py-1.5 rounded-lg text-xs tracking-wide transition-colors ${
                                sortBy === s.key
                                    ? 'bg-[#111] text-white'
                                    : 'text-black/50 hover:bg-black/[0.04]'
                            }`}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>
            </div>

            <ErrorBanner>{error}</ErrorBanner>

            {loading && <p className="text-sm text-black/40">Loading…</p>}

            {!loading && data && data.memories.length === 0 && (
                <p className="text-sm text-black/40">No memories yet.</p>
            )}

            <div className="flex flex-col gap-3">
                {data?.memories.map((m) => (
                    <Card key={m.id} className="p-4 md:p-5">
                        <p className="text-sm leading-relaxed">{m.content}</p>
                        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-black/40">
                            <span>{formatDate(m.created_at)}</span>
                            <span>importance {Number(m.importance_score ?? 0).toFixed(2)}</span>
                            {m.valence != null && (
                                <span>valence {Number(m.valence).toFixed(2)}</span>
                            )}
                            <span>recalled {m.recall_count ?? 0}×</span>
                            {m.wing && <span>{m.wing}</span>}
                            {m.modality && <span>{m.modality}</span>}
                        </div>
                    </Card>
                ))}
            </div>

            {data && total > 0 && (
                <div className="flex items-center justify-between text-sm text-black/40">
                    <button onClick={goPrev} disabled={offset === 0} className="disabled:opacity-30">
                        ← Prev
                    </button>
                    <span>
                        page {page} of {pageCount} · {total} total
                    </span>
                    <button
                        onClick={goNext}
                        disabled={offset + PAGE_SIZE >= total}
                        className="disabled:opacity-30"
                    >
                        Next →
                    </button>
                </div>
            )}
        </div>
    );
}
