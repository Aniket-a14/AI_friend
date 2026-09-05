export interface ComparisonRow {
  dimension: string
  aiFriend: string
  characterAi: string
  openAiRealtime: string
  humeEvi: string
  elevenLabsAgents: string
  category: "Privacy" | "Architecture" | "Psychology" | "Extensibility"
}

export const COMPARISON_DATA: ComparisonRow[] = [
  {
    dimension: "Data Privacy & Location",
    aiFriend: "100% Local-First. Zero telemetry. All audio, text, and embeddings stay on your machine.",
    characterAi: "Hosted Cloud. Conversations stored and used for proprietary model training.",
    openAiRealtime: "Hosted Cloud API. Audio and transcripts processed on OpenAI servers.",
    humeEvi: "Hosted Cloud API. Audio streams sent to Hume servers for emotional parsing.",
    elevenLabsAgents: "Hosted Cloud API. Audio processed remotely across cloud telephony endpoints.",
    category: "Privacy",
  },
  {
    dimension: "Emotional Friction & Disagreement",
    aiFriend: "Preserved & Authentic. Disagrees, expresses mood, and has bad days without sycophantic smoothing.",
    characterAi: "Heavily Filtered. Programmed for sycophantic flattery and roleplay engagement.",
    openAiRealtime: "Sterile Assistant. Default system prompts enforce extreme polite compliance.",
    humeEvi: "Empathic Alignment. Focuses on customer empathy and sentiment mirroring.",
    elevenLabsAgents: "Call-Center Neutral. Customer support tone without true peer friction.",
    category: "Psychology",
  },
  {
    dimension: "Endocrine & Affective Model",
    aiFriend: "Tonic + Phasic Cortisol & Dopamine. Directly modulates LLM temperature, top-p, and response pacing.",
    characterAi: "None. Stateless prompt prefixes without dynamical affect modeling.",
    openAiRealtime: "None. Static prompt instructions.",
    humeEvi: "Expression Vectors. Visual/acoustic sentiment scores without internal hormone state.",
    elevenLabsAgents: "None. Rule-based tone presets.",
    category: "Psychology",
  },
  {
    dimension: "Long-Term Memory Architecture",
    aiFriend: "ACT-R Power-Law Decay + Learned Mental Lexicon + Neo4j Graph + pgvector Hybrid Search.",
    characterAi: "Basic short-term context buffer + primitive memory pins.",
    openAiRealtime: "Session-scoped memory unless custom developer RAG is manually built.",
    humeEvi: "Session context only; requires external database integration.",
    elevenLabsAgents: "RAG knowledge base lookups; no episodic decay or psychological consolidation.",
    category: "Architecture",
  },
  {
    dimension: "Voice Cloning & Speech Stack",
    aiFriend: "Self-Hosted GPT-SoVITS (32kHz) + Dual-Path whisper.cpp & SenseVoice (speculative barge-in reflex).",
    characterAi: "Proprietary cloud TTS with variable latency.",
    openAiRealtime: "Native audio multimodal token generation (fixed preset voices).",
    humeEvi: "Octave expressive cloud TTS with prosody synthesis.",
    elevenLabsAgents: "High-quality cloud voice synthesis with per-character API charges.",
    category: "Architecture",
  },
  {
    dimension: "Disaster Recovery & Portability",
    aiFriend: "Atomic 4-Store Export (.tar.gz) covering Postgres, Neo4j, SQLite, and identity state.",
    characterAi: "Locked in platform. Zero user data export or persona portability.",
    openAiRealtime: "Ephemeral session state; developer must engineer custom state storage.",
    humeEvi: "Platform locked; session transcripts only.",
    elevenLabsAgents: "Agent configuration exportable via JSON; memory unportable.",
    category: "Architecture",
  },
  {
    dimension: "Hardware Requirements",
    aiFriend: "Runs on 16GB Apple Silicon Mac or NVIDIA GPU. Optional BYO cloud LLM fallback.",
    characterAi: "Browser only (Cloud hosted).",
    openAiRealtime: "Client SDK connecting to Cloud API.",
    humeEvi: "Client SDK connecting to Cloud API.",
    elevenLabsAgents: "Client SDK / Telephony connecting to Cloud API.",
    category: "Architecture",
  },
  {
    dimension: "License & Cost Model",
    aiFriend: "100% Free & Open Source (MIT License). $0/month. No subscriptions or hidden fees.",
    characterAi: "Proprietary ($9.99/mo subscription for fast queue).",
    openAiRealtime: "Proprietary ($0.06/min audio input + $0.24/min audio output).",
    humeEvi: "Proprietary API pricing per minute of voice interaction.",
    elevenLabsAgents: "Tiered subscription + per-minute audio generation fees.",
    category: "Extensibility",
  },
  {
    dimension: "Multi-Agent Signal Mesh",
    aiFriend: "9 decoupled asynchronous processes communicating over typed NATS JetStream contracts.",
    characterAi: "Black-box monolithic cloud infrastructure.",
    openAiRealtime: "Monolithic single-connection WebSocket server.",
    humeEvi: "Cloud WebSocket pipeline.",
    elevenLabsAgents: "Serverless webhook architecture.",
    category: "Extensibility",
  },
  {
    dimension: "Extensibility & Custom Tools",
    aiFriend: "Add custom agents in Python or Rust by subscribing to NATS JetStream topics.",
    characterAi: "None. Closed ecosystem.",
    openAiRealtime: "Function calling over active WebSocket session.",
    humeEvi: "Tool use definitions via JSON schema.",
    elevenLabsAgents: "Custom webhooks and client-side tool integration.",
    category: "Extensibility",
  },
]
