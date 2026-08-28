export interface ScenarioBenchmark {
  id: number
  name: string
  description: string
  ramUsedGB: number
  deltaFromIdleGB: number
  activeComponents: string[]
  concurrencyLevel: number
  notes: string
  measuredProvenance: string
}

export interface ContainerFootprint {
  service: string
  role: string
  memoryMiB: number
  port: number
}

export interface MicroBenchmark {
  measurementId: string
  title: string
  measuredValue: string
  benchmarkUnit: string
  conditions: string
  provenance: "live" | "empirical"
}

export const PRESSURE_SCENARIOS: ScenarioBenchmark[] = [
  {
    id: 1,
    name: "System Idle",
    description: "Full container mesh running (Postgres, Neo4j, Redis, Qdrant, NATS, LiveKit) with no active conversation.",
    ramUsedGB: 14.54,
    deltaFromIdleGB: 0.0,
    activeComponents: ["NATS JetStream", "Postgres + pgvector", "Neo4j Graph", "Redis Cache", "Qdrant Vector DB", "LiveKit SFU"],
    concurrencyLevel: 0,
    notes: "Measured on 17.18 GB unified memory host. Docker containers consume 752.4 MiB total; Ollama holds 3 resident models.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §1",
  },
  {
    id: 2,
    name: "Voice-Only Stream",
    description: "Continuous synthetic 32kHz/16-bit PCM streaming into audio.stream without STT/cognition triggered.",
    ramUsedGB: 14.51,
    deltaFromIdleGB: -0.03,
    activeComponents: ["stt-agent (Rust)", "voice-agent (Rust)", "LiveKit SFU", "NATS"],
    concurrencyLevel: 1,
    notes: "Rust ring buffer and memory reuse keep audio pipeline flat; no buffer growth observed over 30s stream.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §2",
  },
  {
    id: 3,
    name: "Voice + Cognitive Turn",
    description: "Active voice streaming paired with continuous multi-stage cognitive processing in brain_agent.",
    ramUsedGB: 14.43,
    deltaFromIdleGB: -0.11,
    activeComponents: ["stt-agent", "brain_agent", "Ollama LLM (Llama 3.2 3B)", "voice-agent"],
    concurrencyLevel: 1,
    notes: "Ollama model weights stay in resident page cache; zero leak observed during cognitive turn generation.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §3",
  },
  {
    id: 4,
    name: "Vision-Only (Habituated)",
    description: "Visual appraisal loop receiving continuous identical camera frames with biological habituation active.",
    ramUsedGB: 14.36,
    deltaFromIdleGB: -0.18,
    activeComponents: ["vision_agent", "VisualAppraisalService", "NATS"],
    concurrencyLevel: 1,
    notes: "Habituation filter suppresses redundant VLM inference after initial frame inspection, saving compute cycles.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §4",
  },
  {
    id: 5,
    name: "Vision + Cognitive Turn",
    description: "Novel visual stimulus defeating habituation filter, forcing real Moondream VLM inference alongside Brain turn.",
    ramUsedGB: 15.15,
    deltaFromIdleGB: 0.61,
    activeComponents: ["Moondream VLM (Ollama)", "brain_agent", "Ollama LLM (Llama 3.2 3B)"],
    concurrencyLevel: 2,
    notes: "Primary memory step cost is the residency of the 1.7GB Moondream model weights (+0.77 GB delta).",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §5",
  },
  {
    id: 6,
    name: "Voice + Vision + Cognition",
    description: "Simultaneous voice streaming, forced visual appraisal, and real cognitive deliberation.",
    ramUsedGB: 15.10,
    deltaFromIdleGB: 0.56,
    activeComponents: ["stt-agent", "voice-agent", "Moondream VLM", "brain_agent", "Full Mesh"],
    concurrencyLevel: 3,
    notes: "All sensory modalities actively ingesting and deliberating concurrently under unified memory.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §6",
  },
  {
    id: 7,
    name: "Full Multimodal (2 Concurrent Turns)",
    description: "Two simultaneous independent conversational turns with active vision and speech processing.",
    ramUsedGB: 15.07,
    deltaFromIdleGB: 0.53,
    activeComponents: ["Full Mesh", "Ollama Queue", "LiveKit WebRTC Data Channels"],
    concurrencyLevel: 4,
    notes: "Multi-turn task queuing executes cleanly without unbounded memory expansion (Docker: 0.86 GB).",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §7",
  },
  {
    id: 8,
    name: "Full + Background Consolidation",
    description: "Heavy multimodal turns executed simultaneously with subconscious REM sleep reflection and Neo4j graph writes.",
    ramUsedGB: 15.16,
    deltaFromIdleGB: 0.62,
    activeComponents: ["Full Mesh", "subconscious_agent", "Neo4j Graph Writer", "SQLite State Cache"],
    concurrencyLevel: 5,
    notes: "Neo4j auto-retries handle write contention; SQLite fallback mirrors state atomically without deadlock.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §8",
  },
  {
    id: 9,
    name: "Sustained Endurance Load (180s)",
    description: "Continuous 180-second multi-turn load across 11 sequential test samples: [15.05, 15.12, 15.10, 15.11, 15.16, 15.10, 15.10, 15.09, 15.15, 15.03, 15.15] GB.",
    ramUsedGB: 15.15,
    deltaFromIdleGB: 0.61,
    activeComponents: ["Full Mesh", "Endurance Harvester", "Postgres", "Neo4j"],
    concurrencyLevel: 5,
    notes: "Zero monotonic memory leak signature detected over test window. Retains ~2.0 GB headroom on 16GB host.",
    measuredProvenance: "backend/tools/measure/out/m17_pressure_scenarios.json §9",
  },
]

export const CONTAINER_FOOTPRINTS: ContainerFootprint[] = [
  { service: "brain_graph", role: "Neo4j Relational Knowledge Graph", memoryMiB: 590.8, port: 7687 },
  { service: "brain_vectors", role: "Qdrant Semantic Vector Index", memoryMiB: 62.0, port: 6333 },
  { service: "local_sfu", role: "LiveKit WebRTC Media Server", memoryMiB: 38.3, port: 7880 },
  { service: "postgres_db", role: "PostgreSQL Identity & Vector Store", memoryMiB: 34.0, port: 5432 },
  { service: "nats_mesh", role: "NATS JetStream Signal Broker", memoryMiB: 17.2, port: 4222 },
  { service: "brain_cache", role: "Redis Ephemeral State Cache", memoryMiB: 10.1, port: 6379 },
]

export const REAL_MICRO_BENCHMARKS: MicroBenchmark[] = [
  {
    measurementId: "M1.6-GraphWarm",
    title: "Neo4j Knowledge Graph Warm Fetch",
    measuredValue: "3.58 µs",
    benchmarkUnit: "microseconds (<0.004 ms)",
    conditions: "1,003 entities & 4,002 relations fetched with 300s TTL memory cache",
    provenance: "live",
  },
  {
    measurementId: "M1.6-GraphCold",
    title: "Neo4j Knowledge Graph Cold Query",
    measuredValue: "56.2 ms",
    benchmarkUnit: "milliseconds",
    conditions: "Full Cypher graph traversal over 1,003 un-cached entity nodes",
    provenance: "live",
  },
  {
    measurementId: "M1.2-ConsolidationIdle",
    title: "Subconscious REM Consolidation (Idle)",
    measuredValue: "7.48 s",
    benchmarkUnit: "seconds wall-clock",
    conditions: "Extracts facts and updates Neo4j beliefs across 6 recent turns",
    provenance: "live",
  },
  {
    measurementId: "M1.2-ConsolidationVLM",
    title: "Subconscious REM Consolidation (VLM Load)",
    measuredValue: "10.08 s",
    benchmarkUnit: "seconds wall-clock",
    conditions: "Consolidation pass executed during continuous Moondream VLM inference",
    provenance: "live",
  },
  {
    measurementId: "M1.1-AudioBurst",
    title: "LiveKit Audio Frame Burst Delivery",
    measuredValue: "23.5 ms",
    benchmarkUnit: "milliseconds",
    conditions: "50 sequential 32kHz PCM audio frames published over NATS",
    provenance: "live",
  },
  {
    measurementId: "M1.1-BargeIn",
    title: "Speculative Speech Interruption Reflex",
    measuredValue: "< 150 ms",
    benchmarkUnit: "milliseconds",
    conditions: "SenseVoice acoustic onset triggers instant Voice Agent audio ducking",
    provenance: "live",
  },
]

export const HARDWARE_MATRIX = [
  {
    platform: "Apple Silicon M1 / M2 / M3 (16GB Unified)",
    profile: "Full Stack (Voice + Brain + Memory)",
    llmInference: "Llama 3.2 3B (Metal / MLX)",
    voiceEngine: "GPT-SoVITS (CPU / Metal)",
    ttftMs: "320 - 450 ms",
    totalTurnaroundMs: "680 - 950 ms",
    status: "Measured & Verified (Development Target)",
  },
  {
    platform: "NVIDIA RTX 3060 / 4060 (12GB VRAM + 16GB Host)",
    profile: "Full Stack + Vision Profile",
    llmInference: "Llama 3.2 3B (CUDA)",
    voiceEngine: "GPT-SoVITS 32kHz (CUDA)",
    ttftMs: "120 - 180 ms",
    totalTurnaroundMs: "350 - 480 ms",
    status: "Ultra Low Latency Tier",
  },
  {
    platform: "Modern x86_64 CPU (16GB RAM, No GPU)",
    profile: "Heavy Mode (Local Whisper STT + Brain)",
    llmInference: "Llama 3.2 1B (AVX-512 / OpenVINO)",
    voiceEngine: "Bundled Pre-synthesized Reference",
    ttftMs: "450 - 650 ms",
    totalTurnaroundMs: "900 - 1400 ms",
    status: "Supported Baseline",
  },
  {
    platform: "Weak Laptop + Cloud Fallback (8GB RAM)",
    profile: "Light Mode (Claude 3.5 Sonnet Fallback)",
    llmInference: "Anthropic Claude API (Streaming)",
    voiceEngine: "Remote TTS or WebRTC Voice",
    ttftMs: "280 - 400 ms",
    totalTurnaroundMs: "600 - 850 ms",
    status: "Cloud Hybrid Tier",
  },
]

export const LATENCY_WATERFALL = [
  { step: "Speech Detection & VAD Cutoff", latencyMs: 15, agent: "stt-agent (Rust)", detail: "Energy-based thresholding & silero VAD" },
  { step: "Speculative Intent & Emotion", latencyMs: 135, agent: "SenseVoice (sherpa-onnx)", detail: "Early barge-in reflex & 7-class emotion classification" },
  { step: "Final Speech Transcription", latencyMs: 180, agent: "whisper.cpp (Rust)", detail: "High-precision word-level transcript generation" },
  { step: "Appraisal & Endocrine State", latencyMs: 4, agent: "brain_agent (Python)", detail: "PAD computation, boundary check, cortisol/dopamine update" },
  { step: "Deliberation & Intent MAUT", latencyMs: 12, agent: "brain_agent (Python)", detail: "Behavior tree traversal and candidate scoring" },
  { step: "LLM Time-To-First-Token (TTFT)", latencyMs: 190, agent: "Ollama (Llama 3.2 3B)", detail: "Streaming first token dispatch with filler fallback (<400ms)" },
  { step: "GPT-SoVITS 32kHz Synthesis", latencyMs: 160, agent: "voice-agent (Rust)", detail: "Streaming chunk synthesis with prosody trajectory & pause bias" },
  { step: "LiveKit WebRTC Transmission", latencyMs: 18, agent: "transport_agent (Python)", detail: "PCM audio frames + visemes data channel dispatch" },
]
