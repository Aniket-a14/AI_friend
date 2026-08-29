# Security Policy

## Supported Versions

Tagged releases exist (currently through `v7.0.0`), but security fixes land
on `main` and only `main` — there is no separate backport policy, and older
tagged releases are not patched independently. Run the latest tag or `main`
to get a fix; an older release will not receive one in place.

## Privacy-first by design

- **Local by default**: Ollama and self-hosted GPT-SoVITS mean no voice or
  reasoning data leaves your network unless you explicitly opt into the
  cloud LLM fallback (`LLM_PROVIDER=anthropic`, off by default).
- **Works offline once cached**: no calls to an external service are required
  for a normal conversation once models are pulled/cached locally.
- **PCM audio over the mesh, not encrypted by that choice.** Voice frames
  travel as raw PCM rather than JSON for performance, not for security — the
  mesh is designed to run on a trusted LAN/loopback, not as a hardened
  transport. Don't expose NATS, Postgres, Neo4j, Qdrant, or LiveKit ports to
  an untrusted network without adding your own transport security (TLS,
  firewalling) in front of them; none of that is provided out of the box.
- **No telemetry.** Nothing here phones home or collects conversation logs.

## Known past disclosure

`dist/ai-friend-runtime.tar.gz`/`.zip` (a packaged release bundle,
tracked in git) briefly included the `personal/` directory —
gitignored everywhere else in this repo specifically because it holds a
real author's own persona and biography — across three commits
(`5e69b22`, `e9ba722`, `b9a468e`, all 2026-08-28). Fixed forward in
`450e467`: the packager no longer whitelists `personal/`, and a new
`.distignore` guards against it recurring; the `v7.0.0` release (cut
after the fix) does not carry it. The three leaking commits remain in
`main`'s git history — a decision recorded here rather than silently
left, not an oversight — so anyone with a full clone predating the
fix, or who fetches full history rather than the current tree, can
still reach the exposed data. Treat this the way any repo-history
exposure should be treated: fixed going forward, not erased.

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please follow these steps:

1.  **Do NOT create a public GitHub issue.** Global visibility of an exploit before a patch is ready puts all users at risk.
2.  Email the security team at **aniketsahaworkspace@gmail.com** or open a **Private Advisory** on GitHub.
3.  Include a detailed description of the vulnerability, steps to reproduce, and potential impact.

### Response Timeline
-   **Acknowledgement**: Within 48 hours.
-   **Assessment**: Within 1 week.
-   **Fix**: As soon as possible, prioritized by severity.

Thank you for helping keep AI Friend safe! 🛡️
