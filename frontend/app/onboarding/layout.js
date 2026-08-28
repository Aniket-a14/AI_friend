import { courierPrime, ibmPlexSans } from '../fonts';

// Fonts scoped to the onboarding route only (via this nested layout's own
// className), matching website/'s design system (Phase 5.0) without
// touching the site-wide font-family the existing voice-orb page already
// relies on (app/globals.css's `body { font-family: 'Inter', ... }`).

export const metadata = {
    title: 'Create your friend — AI Friend',
    description: 'Describe your friend, record their voice, and start talking.',
};

export default function OnboardingLayout({ children }) {
    return (
        <div className={`${ibmPlexSans.variable} ${courierPrime.variable} bg-[#F5F4F0] text-[#111] min-h-screen antialiased`}>
            {children}
        </div>
    );
}
