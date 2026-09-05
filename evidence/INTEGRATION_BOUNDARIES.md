# Humanoid Brain Architecture: Integration Boundaries & External Contracts

## Document Status
- **Classification:** External Integration Specification & Partnership Architecture
- **Audience:** Voice AI Partners (ElevenLabs, Sarvam), Humanoid Robotics Engineers, Research Labs
- **Character Encoding:** Strict 7-bit ASCII
- **Authoritative System Commit:** Merged on `main` (`156f3b7`)

---

## 1. Executive Summary

The Humanoid Brain Architecture is intentionally decoupled from specific foundation models, speech synthesis engines, visual perception models, and physical robot chassis. The cognitive system operates as an autonomous deliberation kernel communicating with external subsystems over strictly typed, versioned contracts.

An external partner (e.g. ElevenLabs, Sarvam AI, or a humanoid robotics OEM) can integrate directly with the brain without needing to understand or modify its internal neural weights, graph databases, or affective appraisal routines.

```
       +-------------------------------------------------------------+
       |                  EXTERNAL SENSORS & INPUTS                  |
       |  (Microphone / VAD)    (Camera / MediaPipe)   (Sensors/ROS) |
       +-------------------------------------------------------------+
                     |                     |                  |
              [AudioInbound]      [StructuredVision]   [Telemetry]
                     |                     |                  |
                     v                     v                  v
       +-------------------------------------------------------------+
       |             PERCEPT ENVELOPE NORMALIZATION LAYER            |
       |               (app/cognitive/percept.py)                    |
       +-------------------------------------------------------------+
                                     |
                          [PerceptEnvelope]
                                     |
                                     v
       +=============================================================+
       |                 HUMANOID BRAIN COGNITION                    |
       |                                                             |
       |  +---------------------+        +------------------------+  |
       |  | Cognitive Pipeline  |<------>| Single-Owner State     |  |
       |  | (Perception-Action) |        | (Affect, Trust, Mood)  |  |
       |  +---------------------+        +------------------------+  |
       |             |                                |              |
       |             v                                v              |
       |  +---------------------+        +------------------------+  |
       |  | Bi-Temporal Memory  |        | Endocrine Layer        |  |
       |  | (Graph, Vector, DB) |        | (Tonic/Phasic Scales)  |  |
       |  +---------------------+        +------------------------+  |
       |             |                                |              |
       |             +---------------+----------------+              |
       |                             |                               |
       |                             v                               |
       |                +--------------------------+                 |
       |                | Foundation Model Seam    |                 |
       |                | (KV Pinning, Sampling)   |                 |
       |                +--------------------------+                 |
       +=============================================================+
                                     |
                        [Committed Action / Intent]
                                     |
                     +---------------+---------------+
                     |                               |
                     v                               v
       +----------------------------+  +----------------------------+
       |   SPEECH INTENT COMPILER   |  | EXTERNAL ACTION DISPATCHER |
       | (app/voice/compiler.py)    |  | (app/cognitive/external)   |
       +----------------------------+  +----------------------------+
         |            |           |                  |
         v            v           v                  v
    [ElevenLabs]  [Sarvam]  [GPT-SoVITS]       [Robotics / Actuator]
```

---

## 2. Inbound Perceptual Contracts

All external inputs entering the cognitive pipeline are converted into a unified `PerceptEnvelope` (`app/cognitive/percept.py`). Raw audio streams, camera video feeds, and sensor arrays never directly invoke neural models inside the cognitive turn.

### 2.1 Audio & Speech Transcription Input
When an external STT engine (e.g. Whisper, SenseVoice, or cloud STT) finishes transcribing user speech, it emits `ChatInput` on the NATS subject `chat.input`:

```python
class ChatInput(BaseModel):
    text: str
    utterance_id: str | None = None
    turn_id: str | None = None
    metadata: ChatInputMetadata = Field(default_factory=ChatInputMetadata)
    latency_metadata: dict[str, Any] | None = None
```

Fast-path acoustic and speculative speech events arrive via `audio.perception`:
```python
class AudioPerception(BaseModel):
    text: str = ""
    intent: str | None = None
    intent_type: str = "CONVERSATIONAL"  # COMMAND, PERCEPTION, CONVERSATIONAL
    keywords: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    snr: float = 0.0
    paralinguistic_events: list[str] = Field(default_factory=list) # [laughter], [cough]
```

### 2.2 Visual Perception Input (`StructuredVisionPercept`)
The brain does not process raw camera frames directly during the cognitive turn. Instead, external vision pipelines (e.g. MediaPipe, YOLO, or a vision-language model) publish structured perceptual observations as `StructuredVisionPercept` (`app/cognitive/vision_percept.py`):

```python
class StructuredVisionPercept(BaseModel):
    entities: list[PerceivedEntity] = Field(default_factory=list)
    facial_expressions: list[FacialExpression] = Field(default_factory=list)
    gaze_direction: GazeTarget | None = None
    scene_description: str = ""
    spatial_relationships: list[SpatialRelation] = Field(default_factory=list)
    user_distance_m: float | None = None
    is_novel: bool = True
    confidence: float = 1.0
    timestamp: float = Field(default_factory=time.time)
```

The adapter function `to_percept_envelope(structured: StructuredVisionPercept) -> PerceptEnvelope` validates spatial invariants and translates this into cognitive working memory.

### 2.3 Environmental & Presence Telemetry
External sensors feed ambient and session presence data:
- `ambient.noise.telemetry`: RMS energy and background noise floor in dB (`AmbientNoiseTelemetry`).
- `state.presence`: Real-time participant connection status (`SessionPresence`).

---

## 3. Outbound Expressive & Action Contracts

The brain produces two categories of outbound intent: communicative speech intents and physical action intents.

### 3.1 Speech Intent Contract (`SpeechIntent`)
The brain determines what to say, why to say it, and how it should sound emotionally and socially, without coupling itself to provider-specific SSML or API parameters. This is encapsulated in `SpeechIntent` (`app/cognitive/speech_intent.py`):

```python
class SpeechIntent(BaseModel):
    schema_version: str = "1.0.0"
    intent_id: str
    turn_id: str
    addressee: str = "user"
    semantic_text: str
    dialogue_act: str = "STATEMENT"      # STATEMENT, QUESTION, APOLOGY, ACKNOWLEDGEMENT
    objective: str = "INFORM"            # INFORM, COMFORTS, DE-ESCALATE, ENTERTAIN
    claim_evidence_ids: list[str] = Field(default_factory=list)
    affect: SpeechAffect                 # PAD coordinates: valence, arousal, dominance
    epistemics: SpeechEpistemics         # confidence, uncertainty, hedge_required
    relationship: SpeechRelationship     # stance, familiarity, register
    delivery: SpeechDelivery             # urgency, relative_rate, relative_pitch, relative_energy
    timeline: list[SpeechTimelineMarker] # pauses, emphasis, vocalizations
    turn_policy: SpeechTurnPolicy        # barge_in_behavior, yield_after, interruptible
    locale: str = "en-US"
```

#### Brain Ownership vs. Voice Provider Ownership
- **Brain Owns:**
  - Semantic content and grammatical phrasing.
  - Communicative objective and dialogue act.
  - Emotional coordinates (PAD: Valence, Arousal, Dominance).
  - Epistemic certainty (whether the robot should hedge or assert).
  - Relationship register (casual, professional, intimate).
  - Timing intentions (where pauses and emphasis belong).
  - Interruption policy (whether this turn can be barged in on).
- **Voice Provider Owns:**
  - High-resolution waveform generation and streaming audio packets.
  - Neural voice timbre, speaker identity, and acoustic fidelity.
  - Phoneme alignment and viseme generation for lip synchronization.
  - Provider-specific acoustic inflection.

### 3.2 Voice Compiler Protocol & Loss Accounting
Every external voice engine implements the `VoiceCompilerProtocol` (`app/voice/compiler.py`):

```python
class VoiceCompilerProtocol(Protocol):
    compiler_id: str
    capabilities: VoiceCapability

    def compile(self, intent: SpeechIntent) -> tuple[CompiledVoicePayload, IntentLossRecord]:
        ...
```

When an intent is compiled for a specific vendor, unsupported features are recorded in an `IntentLossRecord`, providing full auditability:
- **ElevenLabs Compiler (`ElevenLabsVoiceCompiler`):**
  - Maps `affect` and `delivery.style` to ElevenLabs voice stability/similarity sliders.
  - Maps `timeline.pause` to silence insertions.
  - Discloses loss on pitch control (pitch is unrenderable).
- **Sarvam AI Compiler (`SarvamVoiceCompiler`):**
  - Maps semantic text and language locale (hi-IN, ta-IN, etc.) to Indic TTS endpoints.
  - Supports rate and pitch controls; flags unrenderable affect sliders.
- **GPT-SoVITS Compiler (`GPTSoVITSVoiceCompiler`):**
  - Generates localized SSML prosody tags (`<prosody rate=... pitch=... volume=...>`) and emphasis tags (`<emphasis level=...>`).

### 3.3 Physical Action Contract (`ExternalActionIntent`)
For humanoid robotics actuation, physical tools, or external system commands, the brain produces an `ExternalActionIntent` (`app/cognitive/external_action.py`):

```python
class ExternalActionIntent(BaseModel):
    action_id: str
    turn_id: str
    tool_or_actuator: str              # e.g. "robot_arm_left", "navigate_waypoint"
    parameters: dict[str, Any]         # Joint targets, coordinates, gripper pressure
    preconditions: list[str]           # Safety constraints (e.g. "path_clear", "battery>20")
    expected_effects: list[str]        # Expected state post-execution
    reversibility: ActionReversibility # REVERSIBLE, IRREVERSIBLE, PARTIALLY_REVERSIBLE
    risk_level: ActionRiskLevel        # LOW, MEDIUM, HIGH, CRITICAL
    authorization_token: str | None    # Required for HIGH/CRITICAL actions
    timeout_s: float = 10.0
```

`ExternalActionDispatcher` provides an authorization and fail-closed simulation gate. Unregistered robot actuators fail gracefully without crashing cognition.

---

## 4. Foundation Model Boundary

A foundational architectural rule of this system is:
"The model performs cognitive work, but the model is not the entire brain."

```
+-----------------------------------------------------------------------------+
|                           FOUNDATION MODEL BOUNDARY                         |
|                                                                             |
|   OUTSIDE THE MODEL (Brain Architecture)     INSIDE THE MODEL (Inference)   |
|   - Single-owner state kernel (PAD, mood)   - Semantic next-token prediction|
|   - Bi-temporal memory retrieval intervals   - Natural language generation  |
|   - Pre-prompt boundary assembly             - Dialogue act realization     |
|   - Dynamic KV-cache pinning                 - Candidate reflection text    |
|   - Endocrine sampling computation (T, p)                                   |
|   - Output thought parsing & regex gate                                     |
|   - Sub-millisecond barge-in cancellation                                   |
|   - Governed learning & rollback storage                                    |
+-----------------------------------------------------------------------------+
```

### 4.1 What Survives When the Foundation Model Is Swapped
When switching between model providers (e.g. `qwen2.5:3b` -> `llama3.2:3b` -> cloud models):
1. **Memory & Relational History:** Stored in Postgres/SQLite and Qdrant; persists independently of model context windows.
2. **Affective Trajectory:** Valence, arousal, dominance, trust, and fatigue persist in `AgentState`.
3. **Safety & Identity Boundaries:** Invariant rules enforced via regex filters and validation gates before and after LLM generation.
4. **Action Policies:** WAIT action silence, barge-in halting, and goal arbitration remain 100% deterministic.

### 4.2 Endocrine Generative Sampling Modulation
Rather than stuffing emotional prompts into the text ("Please respond angrily"), the brain modulates the generation engine's physical sampling parameters via `_compute_endocrine_options`:
- **Cortisol (Stress):** Narrows temperature (T -> 0.3), restricting generative entropy and forcing deterministic, focused output.
- **Dopamine (Reward):** Broadens nucleus sampling (top_p -> 0.95), encouraging exploratory and creative responses.
- **Fatigue (Exhaustion):** Decreases `num_predict`, shortening generation length.

---

## 5. Replaceable Infrastructure Components

The brain architecture does not mandate proprietary cloud services. Every infrastructure dependency is isolated behind a factory or interface:

| Component | Default Implementation | Fully Replaceable Alternative | Interface Seam |
|---|---|---|---|
| **Inter-Agent Bus** | NATS JetStream | ROS2 / Zenoh / Kafka / ZeroMQ | `BaseAgent.subscribe`, `BaseAgent.publish` |
| **Relational / Bi-Temporal DB** | SQLite / PostgreSQL | MySQL / Spanner / SQLite-Wasm | `MemoryStore.is_sqlite`, SQL schemas |
| **Vector Index** | Qdrant / PgVector | Chroma / Milvus / Pinecone | `app/state/memory_store.py` vector client |
| **Graph Database** | Neo4j | FalkorDB / Memgraph / Kuzu | `app/db/neo4j_client.py` execute_query |
| **Audio Transport** | LiveKit WebRTC | WebSockets / ALSA / GStreamer | `app/transport/livekit_transport.py` |
| **LLM Inference** | Ollama (Local GPU) | vLLM / llama.cpp / OpenRouter | `LLMClient` protocol |

---

## 6. Integration Guide for External Partners

### 6.1 Integrating a New Voice Provider (e.g. Sarvam AI)
To connect a new voice provider to the brain:
1. Subclass `VoiceCompilerProtocol` in `app/voice/compiler.py`:
   ```python
   class SarvamVoiceCompiler:
       compiler_id = "sarvam"
       capabilities = VoiceCapability(
           supports_pitch=True,
           supports_rate=True,
           supports_timeline_pause=True,
           supports_timeline_emphasis=False,
           supports_affect_modulation=False,
           supports_ssml=False,
           supported_styles=["conversational", "formal"],
       )

       def compile(self, intent: SpeechIntent) -> tuple[CompiledVoicePayload, IntentLossRecord]:
           # Translate intent.semantic_text, intent.delivery to Sarvam JSON request
           ...
   ```
2. Implement audio output streaming via `transport_agent`.

### 6.2 Integrating a Humanoid Robotics Body (e.g. ROS2)
To connect a physical robotic chassis:
1. Bind ROS2 publisher/subscribers to NATS JetStream topics:
   - Map joint/camera state to `StructuredVisionPercept`.
   - Map `ExternalActionIntent` to ROS2 Action Servers (`/navigate_to_pose`, `/joint_trajectory_controller`).
2. Register custom executors in `ExternalActionDispatcher`:
   ```python
   dispatcher = ExternalActionDispatcher(executors={
       "bipedal_walker": ros2_nav_executor,
       "dexterous_hand": ros2_hand_executor,
   })
   ```

---

## 7. Summary

The integration boundaries of the Humanoid Brain enforce clean separation of concerns:
- **Sensors & Cameras** produce `PerceptEnvelope`.
- **Cognition & Memory** deliberate and decide.
- **Voice & Actuators** consume `SpeechIntent` and `ExternalActionIntent`.

This architecture ensures long-term portability, vendor independence, and zero lock-in for commercial partners.
