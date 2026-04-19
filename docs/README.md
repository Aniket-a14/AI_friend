# 📚 AI Friend Documentation Map

This folder is the technical documentation suite for **AI Friend CVS-1.0**, a
local-first Cognitive Voice System designed to simulate a persistent, human-like
conversation partner.

The docs are intentionally broad and descriptive. New readers should understand
not only what components exist, but why they exist and how they support the
larger goal: identity continuity, emotional stability, natural voice timing,
organic memory, and future robotics compatibility.

---

## Start Here

- [ARCHITECTURE.md](./ARCHITECTURE.md) gives the system-level map: NATS mesh,
  agents, cognition, state, memory, voice, and feedback loops.
- [API_SPEC.md](./API_SPEC.md) defines the REST endpoints and NATS subjects used
  by the runtime.
- [IDENTITY_SYSTEM.md](./IDENTITY_SYSTEM.md) explains persistent identity,
  emotional state, adaptive variables, memory surfacing, and expression rules.
- [LATENCY_IMPROVEMENT.md](./LATENCY_IMPROVEMENT.md) explains why perceived
  latency matters more than full-response latency and how the signal runtime
  reduces silence.
- [DEPLOYMENT.md](./DEPLOYMENT.md) explains environment configuration,
  production hardening, Docker, and platform deployment.

---

## Voice And Training

- [VOICE_CLONING.md](./VOICE_CLONING.md) explains the real-time voice identity
  layer and GPT-SoVITS runtime assumptions.
- [TRAINING_GUIDE.md](./TRAINING_GUIDE.md) explains how to fine-tune a V4 voice
  model for AI Friend.
- [GPT_SOVITS_INSTALL.md](./GPT_SOVITS_INSTALL.md) covers local GPT-SoVITS setup.
- [COLAB_PATHS_CHEATSHEET.md](./COLAB_PATHS_CHEATSHEET.md) helps map Colab
  training artifacts back into the local project.

---

## Operations And Verification

- [docker_verification.md](./docker_verification.md) provides runtime smoke tests
  for Docker, NATS, Postgres, Neo4j, Ollama, SoVITS, and agent logs.
- [UPDATES.md](./UPDATES.md) is the historical evolution log. It includes older
  architecture research and the current CVS-1.0 hardening notes.

---

## Persistent Agent Context

Agents should also read:

- [../.agents/CONTEXT.md](../.agents/CONTEXT.md)

That file is the durable handoff ledger for future coding agents. It records
current project intent, recent changes, verification commands, and next
recommended work. Update it whenever changes materially affect architecture,
behavior, tests, or runtime expectations.

---

## Documentation Principles

When updating docs:

- Preserve the CVS framing. This is not a generic assistant project.
- Prefer explanations that connect implementation details to realism,
  continuity, latency, and modularity.
- Do not hide limitations. If something is theoretical, future-facing, or not
  yet fully wired, say so clearly.
- Keep docs useful for humans and future agents. Include file names, subject
  names, commands, and expected behavior where possible.
- Avoid reducing broad context unless replacing it with a clearer and more
  accurate version.
