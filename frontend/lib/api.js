// Shared fetch helper for the onboarding wizard's calls into the Phase 5.1
// backend HTTP surface (app/api/persona.py, voice.py). Mirrors
// hooks/useWebRTCVoice.js's own auth pattern exactly: the access key travels
// as a query param, not a custom header, so a cross-origin request doesn't
// force a CORS preflight on every call, and same-machine dev (no key set)
// needs no config at all.

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const BACKEND_ACCESS_KEY = process.env.NEXT_PUBLIC_BACKEND_ACCESS_KEY || '';

export function backendUrl(path) {
    const url = new URL(path, BACKEND_URL);
    if (BACKEND_ACCESS_KEY) {
        url.searchParams.set('key', BACKEND_ACCESS_KEY);
    }
    return url.toString();
}

class ApiError extends Error {
    constructor(status, detail) {
        super(typeof detail === 'string' ? detail : JSON.stringify(detail));
        this.status = status;
        this.detail = detail;
    }
}

async function handle(res) {
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail ?? detail;
        } catch {
            // Response body wasn't JSON; fall back to the status text above.
        }
        throw new ApiError(res.status, detail);
    }
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        return res.json();
    }
    return res;
}

export async function apiPostJson(path, body) {
    const res = await fetch(backendUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return handle(res);
}

export async function apiPostForm(path, formData) {
    const res = await fetch(backendUrl(path), { method: 'POST', body: formData });
    return handle(res);
}

export async function apiGet(path) {
    const res = await fetch(backendUrl(path));
    return handle(res);
}

export { ApiError };
