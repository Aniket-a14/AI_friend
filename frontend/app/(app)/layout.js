import { courierPrime, ibmPlexSans } from '../fonts';
import AppNav from '@/components/AppNav';

// Shared shell for the routes built to website/'s design system alongside
// onboarding (Phase 5.0/5.2): chat, memories, settings. A route group
// (parens don't appear in the URL) so these three share one layout and one
// nav bar without nesting under /onboarding or touching the dark voice-orb
// page at app/page.js, which keeps its own theme entirely.
export const metadata = {
    title: 'AI Friend',
};

export default function AppShellLayout({ children }) {
    return (
        <div
            className={`${ibmPlexSans.variable} ${courierPrime.variable} bg-[#F5F4F0] text-[#111] min-h-screen antialiased`}
        >
            <AppNav />
            <div className="max-w-4xl mx-auto px-4 md:px-8 py-8 md:py-12">{children}</div>
        </div>
    );
}
