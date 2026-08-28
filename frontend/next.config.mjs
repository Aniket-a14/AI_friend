// M18: backend/LiveKit origins are per-deployment (self-hosted LAN, custom
// domain, or ws:// vs wss://), set via env at build time - so connect-src is
// built from those env vars rather than hardcoded, or every deployment but
// the default localhost one would have its own WebRTC/API calls blocked.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const LIVEKIT_URL = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';
// The chat WebSocket (Phase 5.2) talks to the same host as BACKEND_URL but
// over ws(s):, a distinct CSP scheme from http(s): -- a connect-src entry
// for one does not cover the other, so without this line the browser
// silently blocks `useChatSocket.js`'s connection with no network request
// ever leaving the page, just a CSP console error.
const BACKEND_WS_URL = BACKEND_URL.replace(/^http/, 'ws');

// 'unsafe-inline' on script-src is required because Next.js's App Router
// injects an inline bootstrap/hydration script (`self.__next_f.push(...)`)
// with no nonce attached; tightening this further needs nonce-based
// middleware generating a per-request nonce, which is a separate change.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `connect-src 'self' ${BACKEND_URL} ${BACKEND_WS_URL} ${LIVEKIT_URL}`,
  "img-src 'self' data: blob:",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

/** @type {import('next').NextConfig} */
const nextConfig = {
  /* config options here */
  reactCompiler: true,
  output: 'standalone',
  async headers() {
    // #155: HSTS is safe to ship unconditionally from Next's own headers()
    // (unlike the backend's, this isn't gated on an environment flag) because
    // a browser only honors it after receiving it over an HTTPS response in
    // the first place — serving it over plain HTTP in local dev is a no-op.
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'Content-Security-Policy', value: CSP },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
