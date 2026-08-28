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
    version: "v8.0.0",
    date: "Late 2026",
    title: "WebGPU Neural Execution & Home Automation Signal Mesh",
    summary: "Roadmap milestone for zero-install client-side WebGPU inference, multi-modal vision spatial awareness, and Home Assistant smart-space plugins.",
    status: "Coming Soon",
    tags: ["Core", "Voice", "Infrastructure", "UI"],
    highlights: [
      "Zero-install in-browser WebGPU execution running quantized 1B models and ONNX neural voice directly in WebAssembly.",
      "Live 3D Neo4j memory topology & learned mental lexicon graph explorer in WebGL.",
      "Home Assistant integration agent: bi-directional room presence and physical environmental grounding.",
      "Peer-to-peer friend syncing across encrypted local network channels.",
    ],
    metrics: [
      { label: "Target Client RAM", value: "< 2.0 GB WebGPU" },
      { label: "Installation", value: "Zero Install (Browser)" },
    ],
  },
  {
    version: "v7.0.0",
    date: "August 2026",
    title: "Community Release Candidate & Full Multimodal Mesh",
    summary: "The culmination of the Community Release Roadmap: full multi-agent orchestration, web UI with WebSocket streaming chat, viseme animation aura, and complete Colab GPU acceleration tooling.",
    status: "Released",
    tags: ["Core", "UI", "Voice", "Benchmarks"],
    highlights: [
      "Full Web UI: Onboarding wizard, real-time WebSocket chat (/api/chat/ws), interactive memory card browser, and live hydrated persona inspector.",
      "LiveKit WebRTC viseme forwarding over data channels driving reactive aura modulation.",
      "Colab GPU Acceleration Suite: Runnable Jupyter notebooks for GPT-SoVITS voice fine-tuning and heavy benchmark evaluation.",
      "Zero-dependency offline Whisper STT transcription mode in Rust stt-agent binary.",
      "One-command start.sh launcher with automatic preflight checks, Ollama model tagging, and Prisma push.",
    ],
    metrics: [
      { label: "Python Tests", value: "1,382 passing" },
      { label: "Rust Tests", value: "124 passing" },
      { label: "Peak RAM Headroom", value: "2.0 GB on 16GB Mac" },
    ],
  },
  {
    version: "v6.0.0",
    date: "August 2026",
    title: "Empirical Hardware Benchmarks & Integration CI",
    summary: "Validation of all performance and latency claims against real physical hardware across 9 simultaneous multimodal pressure scenarios.",
    status: "Released",
    tags: ["Benchmarks", "Infrastructure", "Core"],
    highlights: [
      "Automated measurement harness (m17_pressure_scenarios.py) testing idle, voice, vision, multi-turn, and background reflection contention.",
      "Structural finding: VLM resident memory step cost (~0.8GB) is the primary driver of RAM pressure, rather than concurrency itself.",
      "Fixed identity-evolution reflection parsing on non-dict suggestions and non-string relationship coercion in SQLite fallback.",
      "New integration CI workflow (.github/workflows/integration-harness.yml) validating evals and tools/measure against live containerized models.",
    ],
    metrics: [
      { label: "Pressure Scenarios", value: "9 measured" },
      { label: "Host RAM Idle", value: "14.54 GB" },
      { label: "Host RAM Peak Load", value: "15.16 GB" },
    ],
  },
  {
    version: "v5.0.0",
    date: "August 2026",
    title: "Web Interface, Streaming WebSocket & Viseme Audio",
    summary: "Full browser-based interaction layer featuring real-time audio/text conversation, memory browsing, and visual state feedback.",
    status: "Released",
    tags: ["UI", "Voice", "Core"],
    highlights: [
      "FastAPI backend routes under /api/ for persona compilation, voice clip commitment, episodic memory browsing, and data archive downloads.",
      "Process-wide ChatBridge BaseAgent subscriber fanning out NATS chat.output streams to multiple connected WebSocket clients with client-side turn_id correlation.",
      "Next.js Onboarding Wizard utilizing browser-native Web Audio API (ScriptProcessorNode) for pristine 16kHz WAV recording with zero browser compression artifacts.",
      "Live hydrated persona inspector (/api/persona/live) reflecting true durable store evolution rather than static initial files.",
    ],
    metrics: [
      { label: "Web Routes", value: "6 Next.js routes" },
      { label: "REST Endpoints", value: "12 new APIs" },
      { label: "WebSocket Turnaround", value: "< 25ms" },
    ],
  },
  {
    version: "v4.0.0",
    date: "August 2026",
    title: "Data Sovereignty, 4-Store Portability & Cloud LLM Fallback",
    summary: "Complete disaster recovery archive packaging across four distinct datastores and provider-agnostic cloud LLM fallback protocols.",
    status: "Released",
    tags: ["Core", "Security", "Infrastructure"],
    highlights: [
      "Atomic friend backup and restore scripts (export_friend.py / import_friend.py) packaging Postgres (9 tables JSONL), Neo4j subgraphs (Cypher), and SQLite snapshots into a single portable .tar.gz archive.",
      "Cloud LLM Protocol abstraction (app/llm/) with AnthropicClient adapter keyed on LLM_PROVIDER=anthropic.",
      "Direct translation of biological endocrine parameters (cortisol temperature narrowing, dopamine top_p expansion) across cloud LLM APIs.",
      "Strict destructive operation guards requiring explicit --force confirmation for persona imports.",
    ],
    metrics: [
      { label: "Stores Captured", value: "4 Datastores" },
      { label: "Postgres Tables", value: "9 Authoritative" },
      { label: "Export Archive Size", value: "< 2.5 MB" },
    ],
  },
  {
    version: "v3.0.0",
    date: "August 2026",
    title: "Inter-Session Presence & Authentic Friction Audit",
    summary: "Transition from an ephemeral chatbot to a persistent friend with unprompted outreach, disconnected thought queuing, and preserved emotional friction.",
    status: "Released",
    tags: ["Core", "Memory", "Voice"],
    highlights: [
      "Durable proactive outreach state tracking (last_proactive_attempt) across AgentState, Redis hash, and state_cache.db.",
      "Presence-triggered reconnect queue (proactive_queue.py) caching up to 5 unreceived thoughts while user is away and delivering upon reconnect.",
      "Elimination of sycophantic agreeableness guards: refined _HOSTILE_TO_USER validation to allow ordinary expressive speech ('I hate small talk') without trigger-happy rejections.",
      "True words-per-minute rate computation (measured_tempo_wpm) calculated at final transcript completion in Rust stt-agent.",
    ],
    metrics: [
      { label: "Thought Queue Capacity", value: "5 thoughts" },
      { label: "Proactive Interval", value: "600s cooldown" },
    ],
  },
  {
    version: "v2.0.0",
    date: "August 2026",
    title: "Natural Language Persona Compiler & Voice Enrollment",
    summary: "The core personality creation engine: freeform natural language prose translation into structured, bounded PersonaProfile configurations.",
    status: "Released",
    tags: ["Core", "Voice", "UI"],
    highlights: [
      "Persona Compiler (compiler.py): Translates natural language descriptions into 13 bounded personality parameters and biography markdown with explicit, explainable mappings.",
      "Friction preservation testing ensuring edgy descriptions produce authentically blunt, non-sycophantic personas.",
      "Voice enrollment wizard (record_voice.py) featuring automated Whisper transcription and audio quality validation (loudness, clipping, silence ratio).",
      "Terminal chat REPL (scripts/talk.py) enabling direct text conversation over NATS chat.input / chat.output without audio hardware dependencies.",
    ],
    metrics: [
      { label: "Temperament Fields", value: "13 Parameters" },
      { label: "Voice Clip Duration", value: "8.0 seconds" },
      { label: "Enrollment Time", value: "< 60 seconds" },
    ],
  },
  {
    version: "v1.0.0",
    date: "August 2026",
    title: "Fresh Clone Boot & Bundled Voice Provisioning",
    summary: "Eliminated all startup blockers for new clones, bundled licensed default voice audio, and streamlined container orchestration.",
    status: "Released",
    tags: ["Voice", "Infrastructure"],
    highlights: [
      "Bundled CC0-licensed default voice sample (default_voice.wav) provisioned on first boot to sample_en_gold.wav.",
      "Non-blocking GPT-SoVITS healthcheck gracefully degrading to an endpoint liveness probe if audio clips are missing.",
      "Compose environment passthrough for all 8 REF_*_{CALM,WARM,CONCERNED,EXCITED} emotional reference clips.",
      "Unified audio volume mounts and Dockerfile.rust working directory alignments.",
    ],
    metrics: [
      { label: "Boot Commands", value: "1 command (start.sh)" },
      { label: "TTS Sample Rate", value: "32,000 Hz" },
    ],
  },
  {
    version: "v0.0.0",
    date: "August 2026",
    title: "Ground Truth & Safety Boundary Substrate",
    summary: "Foundational correctness fixes in runtime appraisal boundaries, elimination of duplicate safety definitions, and initialization of code quality baselines.",
    status: "Released",
    tags: ["Core", "Security", "Infrastructure"],
    highlights: [
      "Runtime safety boundary fix: Connected AppraisalEngine.identity_values directly to immutable_core['boundaries'].",
      "Centralized single source of truth for IMMUTABLE_CORE (Honesty, Privacy, Safety Boundaries) across Python and JavaScript seeders.",
      "Sanitized public tracked files and test fixtures from personal identifying information.",
      "Created Persona Guard schema validation script (validate_persona_file.py) in CI.",
      "Initialized non-blocking CI baselines for mypy, radon cyclomatic complexity, and bandit security analysis.",
    ],
    metrics: [
      { label: "Safety Tiers", value: "3 Enforced Tiers" },
      { label: "Lint Rules", value: "100% Ruff clean" },
    ],
  },
]
