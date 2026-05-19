# 📚 AI Friend Documentation Map

This folder is the technical documentation suite for **AI Friend CVS-2.0**, a
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
- [ROBOTICS_ANALYSIS.md](./ROBOTICS_ANALYSIS.md) provides a deep-dive into the 
  architectural performance and the roadmap for humanoid embodiment.

---

## Voice and Training

- [GPT_SOVITS_INSTALL.md](./GPT_SOVITS_INSTALL.md) covers local GPT-SoVITS setup
  and CVS-2.0 hardening requirements.
- [COLAB_PATHS_CHEATSHEET.md](./COLAB_PATHS_CHEATSHEET.md) helps map Colab
  training artifacts back into the local project.

---

## Operations and Research Archive

- **[RESEARCH_GUIDE.md](./RESEARCH_GUIDE.md)**: Comprehensive guide for training, testing, observing, and visualizing the Tier-5 Sovereign Mesh for research purposes.
- **[ARCHIVE_TOC.md](./ARCHIVE_TOC.md)**: Centralized index for archived CVS-2.0 technical documentation, historical research, and baseline optimizations.

---

## Roadmap & Future Architecture

- **[cvs3_architecture_roadmap.md](./cvs3_architecture_roadmap.md)**: The foundational baseline and planned architecture for **CVS-3.0**, encompassing Dual-Process Kahneman Engines, Hermetic SQLite Mocking, and Continuous Prosody Mapping.

---

## Persistent Agent Context

Agents should also read:

- [../.agents/CONTEXT.md](../.agents/CONTEXT.md)

That file is the durable handoff ledger for future coding agents. It records
current project intent, recent changes, verification commands, and next
recommended work. Update it whenever changes materially affect architecture,
behavior, tests, or runtime expectations.

---

## Planning Before Coding

For non-trivial work, use the Solution Architect planning skill first:

- `skills/solution-architect-agent/SKILL.md`

Use it to produce a codebase-grounded implementation plan before any edits,
especially for cross-module refactors or runtime behavior changes.

The required plan output is:

1. Problem statement
2. Affected files and dependencies
3. Options (minimum two)
4. Recommendation with rationale
5. Ordered implementation plan with file paths
6. Risks and open questions

This planning phase does not include implementation code.

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
