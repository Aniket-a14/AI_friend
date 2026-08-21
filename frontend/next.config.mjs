// M18: backend/LiveKit origins are per-deployment (self-hosted LAN, custom
// domain, or ws:// vs wss://), set via env at build time - so connect-src is
// built from those env vars rather than hardcoded, or every deployment but
// the default localhost one would have its own WebRTC/API calls blocked.
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const LIVEKIT_URL = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';

// 'unsafe-inline' on script-src is required because Next.js's App Router
// injects an inline bootstrap/hydration script (`self.__next_f.push(...)`)
// with no nonce attached; tightening this further needs nonce-based
// middleware generating a per-request nonce, which is a separate change.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `connect-src 'self' ${BACKEND_URL} ${LIVEKIT_URL}`,
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
    return [
      {
        source: '/(.*)',
        headers: [{ key: 'Content-Security-Policy', value: CSP }],
      },
    ];
  },
};

export default nextConfig;
