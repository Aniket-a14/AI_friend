# 📚 AI Friend Documentation Map

This folder is the technical documentation suite for AI Friend, a
local-first cognitive voice system designed to simulate a persistent,
human-like conversation partner.

The docs are intentionally broad and descriptive. New readers should understand
not only what components exist, but why they exist and how they support the
larger goal: identity continuity, emotional stability, natural voice timing,
organic memory, and honest handling of what isn't built yet.

---

## Start Here

- **[BRINGING_IT_TO_LIFE.md](./BRINGING_IT_TO_LIFE.md)** — how to actually run the
  brain, voice and eyes on one laptop, and how to give the agent a personality and
  a cloned voice of its own. Start here if you want it *running*.
- **[FUTURE_WORK.md](./FUTURE_WORK.md)** — everything still open, with the
  decision, the reasoning, and the alternatives that were rejected. Start here if
  you want to *build on it*. Supersedes the `audit/` documents as a work queue.
- [ARCHITECTURE.md](./ARCHITECTURE.md) gives the system-level map: NATS mesh,
  agents, cognition, state, memory, voice, and feedback loops.
- [API_SPEC.md](./API_SPEC.md) defines the REST/WebSocket endpoints and NATS
  subjects used by the runtime.
- [ROBOTICS_ANALYSIS.md](./ROBOTICS_ANALYSIS.md) is speculative writing on
  what embodiment would take — explicitly not a product direction; see the
  status note at the top of that file.

---

## Voice and Training

- [GPT_SOVITS_INSTALL.md](./GPT_SOVITS_INSTALL.md) covers local GPT-SoVITS setup.
- [COLAB_PATHS_CHEATSHEET.md](./COLAB_PATHS_CHEATSHEET.md) helps map Colab
  training artifacts back into the local project.

---

## Operations and Research Archive

- **[RESEARCH_GUIDE.md](./RESEARCH_GUIDE.md)**: guide for testing, observing, and validating the architecture and mathematics for research purposes — points at the real `backend/evals/` and `backend/tools/measure/` harnesses rather than describing tooling that doesn't exist.
- **[ARCHIVE_TOC.md](./ARCHIVE_TOC.md)**: centralized index for archived technical documentation, historical research, and baseline optimizations.

---

## Future / Unbuilt Architecture

- **[FUTURE_FINETUNED_ADAPTER.md](./FUTURE_FINETUNED_ADAPTER.md)**: design notes for a possible future direction — fusing affective state into a fine-tuned model's weights instead of the current prompt-injection approach. Roadmap-only; nothing in it is built. (Previously named `cvs4_architecture_roadmap.md` and written as an approved specification — corrected.)

---

## Persistent Agent Context

Agents should also read:

- **[CONTEXT.md](../.agents/CONTEXT.md)**: That file is the durable handoff ledger for future coding agents. It records
current project intent, recent changes, verification commands, and next
recommended work. Update it whenever changes materially affect architecture,
behavior, tests, or runtime expectations. Where any doc in this repo
disagrees with it, the ledger is right.

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

- Describe the real, current architecture accurately — no version branding,
  invented benchmark figures, or claims about capabilities that don't exist.
  A prior pass through this folder found and fixed a "CVS-3.5 Premium
  Edition" fabrication pattern (fake version numbers, an unmeasured "80,000
  OPS" throughput claim, comparisons to humanoid robots this project isn't) —
  don't reintroduce it.
- Prefer explanations that connect implementation details to realism,
  continuity, latency, and modularity.
- Do not hide limitations. If something is theoretical, future-facing, or not
  yet fully wired, say so clearly — and say so in the document itself, not
  just in a separate ledger entry nobody reading the doc will see.
- Keep docs useful for humans and future agents. Include file names, subject
  names, commands, and expected behavior where possible.
- Before citing a specific number (latency, throughput, recall accuracy),
  confirm it's actually measured and cite where — see `CLAUDE.md`'s
  integrity constraints. State targets as targets until measured.
- Avoid reducing broad context unless replacing it with a clearer and more
  accurate version.
