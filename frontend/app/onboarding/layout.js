import { IBM_Plex_Sans, Courier_Prime } from 'next/font/google';

// Fonts scoped to the onboarding route only (via this nested layout's own
// className), matching website/'s design system (Phase 5.0) without
// touching the site-wide font-family the existing voice-orb page already
// relies on (app/globals.css's `body { font-family: 'Inter', ... }`).
const ibmPlexSans = IBM_Plex_Sans({
    weight: ['300', '400', '500', '600'],
    subsets: ['latin'],
    variable: '--font-ibm-plex',
});
const courierPrime = Courier_Prime({
    weight: ['400', '700'],
    subsets: ['latin'],
    variable: '--font-pixel',
});

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
