# Security Policy

## Supported Versions

There are no tagged releases yet — this project is developed on `main`.
Security fixes land there and only there; there is no older version being
separately maintained.

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
