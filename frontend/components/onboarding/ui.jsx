'use client';

// Wizard-specific primitive. The rest of what used to live here (Tag, Card,
// Heading, PrimaryButton, SecondaryButton, ErrorBanner) moved to
// `@/components/ui` once the chat/settings/memories routes needed them too
// -- StepIndicator stays here because a numbered step progress dial only
// makes sense for a linear wizard.

export function StepIndicator({ steps, current }) {
    return (
        <div className="flex items-center gap-2">
            {steps.map((label, i) => (
                <div key={label} className="flex items-center gap-2">
                    <div
                        className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] transition-colors ${
                            i === current
                                ? 'bg-[#111] text-white'
                                : i < current
                                  ? 'bg-black/10 text-black/50'
                                  : 'bg-black/[0.04] text-black/25'
                        }`}
                        style={{ fontFamily: 'var(--font-pixel)' }}
                    >
                        {i + 1}
                    </div>
                    {i < steps.length - 1 && <div className="w-6 h-px bg-black/10" />}
                </div>
            ))}
        </div>
    );
}
