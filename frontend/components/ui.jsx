'use client';

// Shared primitives matching website/'s visual language (Phase 5.0): warm
// off-white background, near-black text, IBM Plex Sans headings, bordered
// rounded-2xl cards, tracking-widest pixel-font tags. Deliberately
// hand-rolled rather than pulling in website/'s shadcn/radix component
// library -- frontend/ has stayed intentionally light on dependencies
// (LiveKit + framer-motion, nothing else), and a handful of Tailwind classes
// covers what these routes actually need. Used by both the onboarding
// wizard and the app shell (chat/settings/memories) -- any route rendered
// under a layout that sets `--font-ibm-plex`/`--font-pixel` (see
// `app/fonts.js`).

export function Tag({ children }) {
    return (
        <span
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] tracking-widest text-black/40 bg-black/[0.04]"
            style={{ fontFamily: 'var(--font-pixel)' }}
        >
            {children}
        </span>
    );
}

export function Card({ children, className = '' }) {
    return (
        <div
            className={`rounded-2xl border border-black/[0.07] bg-white p-6 md:p-8 ${className}`}
        >
            {children}
        </div>
    );
}

export function Heading({ children, className = '' }) {
    return (
        <h1
            className={`text-3xl md:text-4xl font-light tracking-tight leading-[1.1] ${className}`}
            style={{ fontFamily: 'var(--font-ibm-plex)' }}
        >
            {children}
        </h1>
    );
}

export function PrimaryButton({ children, className = '', ...props }) {
    return (
        <button
            className={`px-6 py-3 bg-[#111] text-white text-sm rounded-xl hover:bg-[#333] transition-colors tracking-wide font-medium disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-[#111] ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

export function SecondaryButton({ children, className = '', ...props }) {
    return (
        <button
            className={`px-6 py-3 border border-black/10 text-black/60 text-sm rounded-xl hover:border-black/25 hover:text-black hover:bg-black/[0.04] transition-all tracking-wide disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

export function ErrorBanner({ children }) {
    if (!children) return null;
    return (
        <div className="rounded-xl border border-red-500/20 bg-red-50 text-red-700 text-sm px-4 py-3">
            {children}
        </div>
    );
}
