export interface ChangelogItem {
  version: string
  date: string
  title: string
  summary: string
  status?: "Released" | "Coming Soon"
  tags: ("Core" | "Voice" | "Memory" | "UI" | "Security" | "Benchmarks" | "Infrastructure")[]
  highlights: string[]
  breakingChanges?: string[]
  metrics?: { label: string; value: string }[]
}

export const CHANGELOG_DATA: ChangelogItem[] = [
  {
    version: "Unscheduled",
    date: "No committed date",
    title: "Roadmap: Not Yet Built",
    summary: "Items genuinely not built yet, with no target version or date committed -- see /roadmap for the full, itemized status of each (including why it isn't shipped).",
    status: "Coming Soon",
    tags: ["Core", "Voice", "Infrastructure", "UI"],
    highlights: [
      "WebGPU in-browser inference: quantized small-LLM and ONNX voice synthesis entirely client-side. Exploratory -- nothing built or benchmarked yet.",
      "1-click hosted Colab training runners for voice fine-tuning and benchmark sweeps, beyond the existing manual notebooks. Not started.",
      "Community persona registry for publishing and browsing authored persona presets. Not started -- raises real moderation/consent/hosting questions not yet worked through.",
      "Real GPT-SoVITS-rendered audio clips for the Voice Showcase, replacing the current static parameter table. In progress.",
    ],
    metrics: [
      { label: "Target Client RAM (WebGPU)", value: "< 2.0 GB (unverified target)" },
    ],
  },
  {
    version: "v7.1.0",
    date: "September 2026",
    title: "Brain-First Repositioning: Live Playground, Verified Research, Repo Cleanup",
    summary: "The Brain (cognitive/affect/memory architecture) is now presented as the primary novelty, Voice and Vision as explicitly secondary. Every remaining fake 'Coming Soon' demo is replaced with real, live client-side math or moved to an honest /roadmap page, the homepage and showcase reorder around the Brain, and the Research page is rewritten around 5 pillars with every citation mechanically verified.",
    status: "Released",
    tags: ["Core", "UI", "Memory", "Voice"],
    highlights: [
      "Repo cleanup: outreach/, partnership/, orchestration/, and evidence/IP_REVIEW_CANDIDATES.md gitignored (internal BD/process material, not a history rewrite); FINAL_HUMANOID_BRAIN_ARCHITECTURE.md repurposed into a public ARCHITECTURE.md.",
      "5 real backend formulas ported to TypeScript with unit tests against hand-computed values: ACT-R memory activation, Marsh trust + Bowlby attachment, metacognitive Brier-calibration, theory-of-mind concept tracking, and the persona compiler's _infer_temperament.",
      "4 new live playground demos (Trust & Attachment, Memory Activation & Decay, Metacognitive Abstention, Theory of Mind) and a rewritten Persona Compiler that recomputes synchronously instead of faking a compile with setTimeout.",
      "Homepage reordered to lead with the Brain (Endocrine -> Cognitive Turn -> Persona -> Trust -> Memory -> Mesh -> DevEx -> Voice -> Benchmarks -> Security -> CTA); the old fake roadmap-preview block is gone, replaced by a real /roadmap page.",
      "Showcase recipes reordered to lead with Affective Dynamics, plus 2 new recipes (trust/Theory-of-Mind tracking, metacognitive honesty), Voice last.",
      "Research page rewritten around 5 pillars with a new typed citation list; every citation mechanically checked against its claimed title/authors -- 6 of 35 had a real sourcing error (wrong author bylines, a wrong DOI digit, two stale arXiv IDs, a wrong ISBN) and were corrected, not dropped or left wrong.",
      "Fixed: hero heading could overlap the fixed nav on a narrow-tall or short-landscape viewport (width-only breakpoints missed both cases) -- now a vmin-based clamp() with a short-viewport safety net.",
      "Fixed: docs pages with LaTeX math rendered the raw $...$ text literally -- added remark-math + rehype-katex.",
      "Fixed: this changelog's own unreleased-roadmap entry claimed a Home Assistant integration and peer-to-peer friend syncing with no grounding anywhere in the codebase -- replaced with the real, vetted /roadmap items.",
    ],
    metrics: [
      { label: "Citations Verified", value: "35/35 (6 corrected)" },
      { label: "Live Playground Demos", value: "8/8 (0 fake)" },
      { label: "Vitest", value: "28/28 passing" },
    ],
  },
  {
    version: "v7.0.0",
    date: "August 2026",
    title: "Community Release: Fresh-Clone Boot, Persona Compiler, Web UI & Distribution",
    summary: "The first tagged release of the community roadmap: a clean clone that boots and speaks, natural-language persona and voice creation, persistent affect and proactive outreach across restarts, four-store export/import, a real web UI, nine pressure-tested benchmark scenarios, and one-line installers with a unified friend CLI.",
    status: "Released",
    tags: ["Core", "UI", "Voice", "Memory", "Benchmarks", "Infrastructure"],
    highlights: [
      "Safety-floor fix: AppraisalEngine.identity_values now reads the same immutable_core['boundaries'] validate_response already used, closing a gap where it had silently been an empty list.",
      "Fresh clone boots and speaks: bundled CC0 default voice sample, degrading GPT-SoVITS healthcheck, and a one-command start.sh across light/heavy/full/+vision profiles.",
      "Natural-language persona compiler and 8-second voice enrollment with automated Whisper transcription and quality validation, plus a terminal chat REPL (scripts/talk.py).",
      "Durable proactive outreach and affect state that survive a restart, with a reconnect queue for outreach missed while you were away.",
      "Four-store export/import (Postgres, Neo4j, identity state, state_cache.db) and a provider-agnostic cloud LLM fallback (Anthropic/OpenAI/OpenRouter).",
      "A real web UI: onboarding, WebSocket chat (/api/chat/ws), persona/voice/memory endpoints, all behind session auth.",
      "The nine AUDIT.md pressure scenarios actually run against live infrastructure, not left as placeholders.",
      "mypy, bandit, and the radon D/E/F complexity tier flipped from report-only to blocking in CI.",
      "New this release: one-line installers for macOS/Linux and Windows, a ~4.3 MB standalone runtime bundle, the unified friend CLI (init/start/stop/status/model/vision/talk/persona/voice/backup/logs/update), an interactive friend init wizard generating cryptographically secure credentials, and Moondream VLM visual appraisal wired into setup.",
      "Dedicated GPU Server & LiveKit WebRTC Voice Loop: real-time bidirectional voice over a physical SFU mesh with 39.95ms measured TTFT, zero-trust UFW firewall, and viseme data channel delivery.",
    ],
    metrics: [
      { label: "Python Tests", value: "1,412 passing" },
      { label: "Rust Tests", value: "130 passing" },
      { label: "LLM TTFT (RTX 2060S)", value: "39.95 ms (Measured)" },
      { label: "Peak RAM Headroom", value: "2.0 GB on 16GB Mac" },
    ],
  },
  {
    version: "v6.5.0",
    date: "May 2026",
    title: "HippoRAG Retrieval & Mesh Architecture v3.5",
    summary: "A HippoRAG-style personalized PageRank retrieval engine over a co-occurrence graph, Qdrant and Neo4j interconnected for graph-based spreading activation, and the mesh architecture's v3.5 upgrade.",
    status: "Released",
    tags: ["Core", "Memory", "Benchmarks"],
    highlights: [
      "HippoRAG PPR engine with co-occurrence graph edges and conditional seeding, plus ACT-R degree-scaled spreading-activation boosts.",
      "Qdrant and Neo4j interconnected so spreading activation runs directly over the graph rather than vector similarity alone.",
      "Cognitive appraisal (heuristic appraisal, APRA v2, SQLite ACT-R activation loops) migrated to the Rust cognitive-rust extension.",
      "Mesh architecture v3.5: layered memory, attentional interruption, and loopback security hardening.",
    ],
  },
  {
    version: "v6.0.0",
    date: "May 2026",
    title: "Theory of Mind & Dynamic Prosody Mapping",
    summary: "Theory of Mind integration, continuous prosody trajectories with overlap-add crossfade, and neuromodulatory memory consolidation with dimensional trust.",
    status: "Released",
    tags: ["Core", "Voice", "Memory", "Benchmarks"],
    highlights: [
      "Theory of Mind integration (Phase 5): the agent models what the user does and doesn't know.",
      "Dynamic Continuous Prosody Mapping with overlap-add (OLA) crossfade in the Rust voice agent.",
      "Memory consolidation with neuromodulatory gating and dimensional trust scoring.",
      "Physiology & sensory filters, plus a database-backed conversation store with automatic SQLite fallback.",
      "Extended 8-dimensional cognitive benchmark suite with a compiled academic report.",
    ],
  },
  {
    version: "v5.0.0",
    date: "May 2026",
    title: "Rust Migration & Endocrine-Driven Sampling",
    summary: "Core cognitive agents migrated from Python to Rust, ACT-R memory storage and retrieval, and endocrine state (cortisol/dopamine) driving LLM sampling parameters for the first time.",
    status: "Released",
    tags: ["Core", "Voice", "Memory", "Infrastructure"],
    highlights: [
      "Python cognitive agents deprecated in favor of a hardened Rust mesh; compose profiles streamlined around it.",
      "ActionService: endocrine-based LLM parameter control (cortisol/dopamine mapped to temperature/top_p) plus unified NATS SubjectMetrics.",
      "ACT-R memory storage and retrieval with integration testing.",
      "SenseVoice STT with emotional perception and paralinguistics tracking.",
      "Global Python stack standardized to 3.12 across Dockerfiles and CI.",
    ],
  },
  {
    version: "v4.1.5",
    date: "May 2026",
    title: "Release Pipeline Hardening",
    summary: "Conventional Commits and SBOM dependency graphs, signed release assets, and cross-platform (Windows/macOS) build matrix fixes.",
    status: "Released",
    tags: ["Infrastructure", "Security"],
    highlights: [
      "Enterprise-grade release pipeline: Conventional Commits, SBOM dependency graphs, and versioned manifests.",
      "Release assets now include SHA256 checksums, an offline CHANGELOG, LICENSE, and metadata.json.",
      "Fixed a macOS package suffix mismatch and upgraded CycloneDX to a compliant v1.4 output.",
      "Fixed a Windows Compress-Archive positional-argument bug by separating matrix shell targets.",
    ],
  },
  {
    version: "v4.0.0",
    date: "May 2026",
    title: "Endocrine System & Subconscious Processing",
    summary: "The endocrine simulation (cortisol/dopamine modulation of LLM generation parameters) and agent-based subconscious background processing land for the first time.",
    status: "Released",
    tags: ["Core", "Voice", "Security"],
    highlights: [
      "Endocrine system: cortisol and dopamine modulation of LLM generation parameters.",
      "Agent-based subconscious processing modules for background reflection.",
      "GPT-SoVITS orchestration, service configuration, and identity warmup scenarios updated.",
      "CI/CD suite expanded with security auditing and infrastructure validation workflows.",
    ],
  },
  {
    version: "v3.2.4",
    date: "April 2026",
    title: "AI Friend Core: Solid State Mesh",
    summary: "Zero-drift NATS micro-agent architecture: BaseAgent, BrainAgent, VoiceAgent, and Neo4j-backed cognitive memory, plus GPT-SoVITS voice cloning setup.",
    status: "Released",
    tags: ["Core", "Voice", "Memory", "Infrastructure"],
    highlights: [
      "AI Friend Core Solid State Mesh: zero-drift NATS-based micro-agent architecture with a shared BaseAgent.",
      "BrainAgent with semantic chunking; VoiceAgent with adaptive audio normalization and state-managed synthesis.",
      "Neo4j-backed cognitive memory and a SurfacingAgent for asynchronous long-term memory retrieval.",
      "GPT-SoVITS voice cloning setup, training documentation, and a voice-training notebook.",
    ],
  },
  {
    version: "v3.0.0",
    date: "February 2026",
    title: "Agent-Based Cognitive Mesh",
    summary: "The first cognitive mesh architecture: independent micro-agents, graph RAG, and a NATS event bus, with WebRTC voice and vision capabilities.",
    status: "Released",
    tags: ["Core", "Voice", "Infrastructure"],
    highlights: [
      "Agent-based architecture with WebRTC voice and vision capabilities.",
      "v3.0 cognitive mesh: micro-agents, graph RAG, and a NATS event bus.",
      "CI workflow for linting, security analysis, frontend build, and backend import validation.",
    ],
  },
  {
    version: "v2.2.0",
    date: "February 2026",
    title: "The Enterprise Era",
    summary: "CI/CD and security hardening on top of the imperfect-memory and dynamic-identity core: automated Docker publishing, dependency security enforcement, and broken-link checking.",
    status: "Released",
    tags: ["Core", "Security", "Infrastructure"],
    highlights: [
      "Automated Docker image publishing to GHCR alongside CI testing/validation and tag-triggered releases.",
      "Long-term memory, vision, and audio processing folded into a new interactive assistant UI.",
      "Dependency security enforcement pass across requirements.txt.",
      "Broken-link checking workflow for markdown documentation.",
    ],
  },
  {
    version: "v2.0.0",
    date: "January 2026",
    title: "The Humanized Era",
    summary: "The project's rebrand to AI Friend, and the first version of imperfect memory, a simulated biological clock, and identity driven by configuration rather than hardcoded prompts.",
    status: "Released",
    tags: ["Core", "Memory"],
    highlights: [
      "Imperfect Memory (Memory v2): short-term, blurry, and core memory layers.",
      "Biological Clock: temporal awareness and simulated biological rhythms.",
      "Dynamic Identity: personality and history derived from JSON configuration rather than hardcoded prompts.",
      "Human Growth Engine: session reflection and persistent learning.",
      "Rebranded the project to AI Friend, with a dynamic LLM service and centralized configuration.",
    ],
  },
]
