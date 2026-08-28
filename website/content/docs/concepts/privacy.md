# Privacy & data

## Local by default

Ollama and self-hosted GPT-SoVITS mean no voice or reasoning data leaves
your network unless you explicitly opt into the cloud LLM fallback
(`LLM_PROVIDER=anthropic` in `.env`, off by default). No account, no
conversation leaves your hardware unless you turn that on.

## No telemetry

Nothing here phones home or collects conversation logs.

## What stays on your machine

| Store | What |
| :--- | :--- |
| Postgres + pgvector | Identity and episodic memory |
| Neo4j | Knowledge graph |
| Qdrant | Vector similarity index |
| `.identity_state/` | Personality, history |
| `personal/` | Your authored persona — fully gitignored, never tracked |

## Yours to export

Export your friend's identity and memory, wipe the machine, import it back
on another one. It's their memory, not the deployment's.

## Transport is not hardened by default

Voice frames travel as raw PCM rather than JSON for performance, not for
security — the mesh is designed to run on a trusted LAN/loopback, not as a
hardened transport. Don't expose NATS, Postgres, Neo4j, Qdrant, or LiveKit
ports to an untrusted network without adding your own transport security
(TLS, firewalling) in front of them; none of that is provided out of the
box. See [SECURITY.md](https://github.com/Aniket-a14/AI_friend/blob/main/SECURITY.md)
on GitHub for the full policy and how to report a vulnerability.
