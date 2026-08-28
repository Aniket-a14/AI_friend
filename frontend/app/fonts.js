import { Courier_Prime, IBM_Plex_Sans } from 'next/font/google';

// Shared across every route built to website/'s design system (Phase 5.0):
// the onboarding wizard and the app shell (chat/settings/memories) both need
// the same two fonts. next/font/google loaders must be called at module
// scope, so they live here once and every layout imports the resulting
// variable classes rather than each calling the loader itself.
export const ibmPlexSans = IBM_Plex_Sans({
    weight: ['300', '400', '500', '600'],
    subsets: ['latin'],
    variable: '--font-ibm-plex',
});

export const courierPrime = Courier_Prime({
    weight: ['400', '700'],
    subsets: ['latin'],
    variable: '--font-pixel',
});
