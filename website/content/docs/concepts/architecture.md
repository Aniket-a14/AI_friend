# Architecture

Agents are separate processes coordinated over **NATS JetStream**, not
function calls — a decoupled signal-bus mesh, not a monolith with internal
method calls. The full diagram lives in
[README.md](https://github.com/Aniket-a14/AI_friend/blob/main/README.md#architecture)
on GitHub; this page is the prose version.

## The agents

| Agent | Technology | Role |
| :--- | :--- | :--- |
| Signaling | Python / FastAPI | LiveKit token issuance; the frontend's REST entry point. Not a NATS agent. |
| Brain Agent | Python / Ollama | Cognitive core — appraisal, decision, action, state. |
| Voice Agent | Rust / GPT-SoVITS | Renders affect-aware 32kHz audio through one cloned-voice engine, no fallback to a different voice. |
| STT Agent | Rust / whisper.cpp + sherpa-onnx | Dual-path: whisper.cpp for the final transcript, SenseVoice for a fast speculative path with speech-emotion classification. |
| Transport Agent | Python / LiveKit | WebRTC gateway; raw PCM chunking and stream bridging. |
| Surfacing Agent | Python / pgvector | ACT-R-style episodic memory retrieval and proactive recall. |
| Subconscious Agent | Python / Neo4j | Background reflection, internal monologue, proactive outreach. |
| Vision Agent | Ollama / moondream | Host-native visual appraisal. Opt-in, and must run natively on Windows/macOS. |
| Pulse Agent | Python / asyncio | Mesh heartbeat. |

## The cognitive turn

1. **Perception** — Transport Agent publishes raw PCM to `audio.inbound`.
2. **Speculation** — STT Agent's fast path identifies high-confidence intent and any classified emotion.
3. **Reflex** — Voice Agent immediately soft-attenuates on a speculative interruption signal.
4. **Appraisal** — Brain Agent computes emotional valence and updates PAD + endocrine state.
5. **Deliberation** — Decision Service scores candidate intents.
6. **Synthesis** — Voice Agent renders the response using the current affect vector.
7. **Closure** — Voice Agent reports playback telemetry back to the Brain for the next turn's pacing.

## Signal bus contracts

Every subject has a Pydantic schema in `backend/app/contracts.py` — never a
raw dictionary crossing an agent boundary. `chat.output`, for example,
carries `content`, `affect` (an 8-field vector: valence, arousal,
dominance, trust, attachment, emotion, fatigue, user_distance), and a
`turn_id` used to correlate the whole exchange.

## Persona: three enforced tiers

Every persona field is sorted into a tier declared in the schema, so the
boundary is checked in code rather than assumed:

- **Immutable** — a small hard-coded safety floor no authored persona can
  touch.
- **Constitutional** — temperament fixed at creation: half-lives, drift
  rates, baselines.
- **Adaptive** — seeded by you, then owned and slowly evolved by the agent
  itself, capped at 5 traits.

A persona file naming an immutable field is rejected outright, not silently
accepted.

## Endocrine layer

`cortisol` and `dopamine` are each *tonic + phasic* — a slow baseline
that's a pure function of current affect, plus a decaying burst on top
(half-life 90s for reward, 600s for stress) fired by real events. Because
the burst channels are independent of the anti-correlated tonic terms, the
agent can be stressed and rewarded at the same time. These hormones
modulate LLM sampling directly: cortisol narrows temperature, dopamine
widens `top_p`, fatigue shortens the response length.

## Memory

Retrieval expands query cues through a **learned mental lexicon** — built
from the agent's own conversations, not a hardcoded thesaurus. Episodic
memories decay on an ACT-R-style curve
(`activation = ln(recall_count) - d·ln(hours_since_created + 1)`); memories
below the retention threshold move to an archive tier rather than being
deleted outright, and can be promoted back.

Next: [Privacy & data](/docs/concepts/privacy).
