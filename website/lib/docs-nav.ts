// Single source of truth for the sidebar, search index, and prev/next links.
// Every slug here matches a markdown file at content/docs/<slug>.md.

export interface DocPage {
  title: string
  slug: string
  description?: string
  comingSoon?: boolean
}

export interface DocSection {
  title: string
  pages: DocPage[]
}

export const DOCS_NAV: DocSection[] = [
  {
    title: "Getting Started",
    pages: [
      { title: "Installation & Prerequisites", slug: "getting-started/installation", description: "System requirements, Docker setup, and one-command start.sh launcher." },
      { title: "Quickstart Guide", slug: "getting-started/quickstart", description: "Describe your friend in natural prose, record voice, and talk." },
      { title: "Configuration Reference", slug: "getting-started/configuration", description: "Complete .env parameters, launch flags, and compose profiles." },
      { title: "Docker Compose Guide", slug: "getting-started/docker-compose-guide", description: "Multi-container orchestration, port mappings, and volume persistence." },
    ],
  },
  {
    title: "Brain: Cognitive Architecture",
    pages: [
      { title: "Architecture of Mind", slug: "concepts/architecture-of-mind", description: "The 7-stage cognitive turn and the BDI loop underneath it, from perception to closure." },
      { title: "Endocrine & Affect System", slug: "concepts/endocrine-affect-system", description: "Tonic/phasic cortisol, dopamine, and adrenaline; Marsh trust and Bowlby attachment; LLM sampling modulation." },
      { title: "Memory & Learned Lexicon", slug: "concepts/memory-systems", description: "ACT-R power-law decay, Neo4j knowledge graphs, and subconscious REM reflection." },
      { title: "3-Tier Persona Constitution", slug: "concepts/persona-constitution", description: "Immutable safety core, constitutional temperament, and adaptive trait evolution." },
      { title: "Theory of Mind & Metacognition", slug: "concepts/theory-of-mind-and-metacognition", description: "Tracking what the user knows and believes, and calibrated confidence that gates when the agent hedges or abstains." },
    ],
  },
  {
    title: "Mesh & Systems Architecture",
    pages: [
      { title: "Mesh Architecture", slug: "concepts/architecture", description: "9-agent decoupled signal-bus coordinated over NATS JetStream." },
      { title: "Privacy & Data Sovereignty", slug: "concepts/privacy", description: "Local-first isolation, zero external data egress, and hardware confinement." },
    ],
  },
  {
    title: "Voice & Vision: Supporting Modalities",
    pages: [
      { title: "Speech & Voice Pipeline", slug: "concepts/speech-voice-pipeline", description: "Dual-path whisper.cpp/SenseVoice STT, GPT-SoVITS 32kHz, and barge-in mechanics." },
      { title: "Visual Appraisal System", slug: "concepts/vision-appraisal", description: "Moondream VLM screen and camera observer with habituation dampening. Opt-in and secondary to the Brain." },
    ],
  },
  {
    title: "API & Protocol Specifications",
    pages: [
      { title: "REST API Endpoints", slug: "api-reference/rest-endpoints", description: "FastAPI REST surface for persona compilation, voice, and memory." },
      { title: "WebSocket Streaming Protocol", slug: "api-reference/websocket-protocol", description: "Real-time /api/chat/ws protocol, turn_id correlation, and event schemas." },
      { title: "NATS Topics & Contracts", slug: "api-reference/nats-subjects-contracts", description: "Pydantic contract schemas and JetStream subject routing table." },
    ],
  },
  {
    title: "Developer & Operations Guides",
    pages: [
      { title: "Voice Training on GPU", slug: "guides/voice-training", description: "GPT-SoVITS fine-tuning on Google Colab or local NVIDIA hardware." },
      { title: "Colab GPU Acceleration", slug: "guides/colab-gpu-acceleration", description: "Remote training, SSH tunnels, and VS Code Remote integration." },
      { title: "Disaster Recovery & Backup", slug: "guides/backup-migration", description: "Atomic 4-store friend archive export, import, and cross-machine migration." },
      { title: "Cloud LLM Fallback", slug: "guides/cloud-llm-fallback", description: "Anthropic Claude API integration with endocrine parameter translation." },
      { title: "Custom Agents & Plugins", slug: "guides/custom-agents-plugins", description: "Extending the NATS mesh with custom Python or Rust worker agents." },
    ],
  },
  {
    title: "Testing & Quality Assurance",
    pages: [
      { title: "Evaluation Harness", slug: "testing/eval-harness", description: "Running single-turn and multi-turn probe suites and recall@k benchmarks." },
      { title: "Code Quality & Static Analysis", slug: "testing/quality-tooling", description: "mypy typing, radon cyclomatic complexity, and bandit security gates." },
      { title: "Mutation Testing Discipline", slug: "testing/mutation-testing", description: "Targeted mutation testing with mutmut to prevent mock leakage." },
    ],
  },
  {
    title: "Troubleshooting",
    pages: [
      { title: "Common Issues & Playbooks", slug: "troubleshooting/common-issues", description: "Resolving port conflicts, container health checks, and audio device errors." },
      { title: "Hardware Tuning & Optimization", slug: "troubleshooting/hardware-optimization", description: "RAM management, CPU thread tuning, and VLM residency optimization." },
    ],
  },
]

export const ALL_DOC_PAGES: DocPage[] = DOCS_NAV.flatMap((section) => section.pages)

export function findDocPage(slug: string): DocPage | undefined {
  return ALL_DOC_PAGES.find((p) => p.slug === slug)
}

export function findSectionForSlug(slug: string): DocSection | undefined {
  return DOCS_NAV.find((section) => section.pages.some((p) => p.slug === slug))
}

export function getAdjacentPages(slug: string): { prev?: DocPage; next?: DocPage } {
  const index = ALL_DOC_PAGES.findIndex((p) => p.slug === slug)
  if (index === -1) return {}
  return {
    prev: index > 0 ? ALL_DOC_PAGES[index - 1] : undefined,
    next: index < ALL_DOC_PAGES.length - 1 ? ALL_DOC_PAGES[index + 1] : undefined,
  }
}
