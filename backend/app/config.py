import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    LAN_ONLY = os.getenv("LAN_ONLY", "true").lower() == "true"
    LAN_CORS_ORIGIN_REGEX = (
        r"^https?://("
        r"localhost|"
        r"127(?:\.\d{1,3}){3}|"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
        r")(?::\d+)?$"
    )

    # NATS Configuration
    NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

    # LiveKit Configuration (Sovereign Mesh)
    LIVEKIT_URL = os.getenv("LIVEKIT_URL", "http://localhost:7880")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

    # Memory & Personality
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Neo4j Graph Configuration
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    NEO4J_AUTH = os.getenv("NEO4J_AUTH")  # user/pass format compatible with Docker

    AI_NAME = os.getenv("AI_NAME", "AI Friend")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    # LLM model routing defaults. Keep them overridable for different memory budgets.
    LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "llama3.2:1b")
    LLM_CHAT_MODEL = os.getenv("LLM_CHAT_MODEL", LLM_FAST_MODEL)
    LLM_REFLECTION_MODEL = os.getenv("LLM_REFLECTION_MODEL", LLM_CHAT_MODEL)
    LLM_STREAM_MAX_SECONDS = int(os.getenv("LLM_STREAM_MAX_SECONDS", "120"))
    LLM_INTENT_CLASSIFICATION_ENABLED = (
        os.getenv("LLM_INTENT_CLASSIFICATION_ENABLED", "true").lower() == "true"
    )

    REFLECTION_ENABLED = os.getenv("REFLECTION_ENABLED", "true").lower() == "true"
    REFLECTION_MIN_INTERVAL_SECONDS = float(
        os.getenv("REFLECTION_MIN_INTERVAL_SECONDS", "0")
    )

    # Proactive Engagement (Phase 1: Initiating Contact)
    PROACTIVE_ENABLED = os.getenv("PROACTIVE_ENABLED", "true").lower() == "true"
    PROACTIVE_IDLE_THRESHOLD_SECONDS = float(
        os.getenv("PROACTIVE_IDLE_THRESHOLD_SECONDS", "7200")  # 2 hours
    )
    PROACTIVE_COOLDOWN_SECONDS = float(
        os.getenv(
            "PROACTIVE_COOLDOWN_SECONDS", "3600"
        )  # 1 hour between proactive attempts
    )
    PROACTIVE_MIN_ENERGY = float(
        os.getenv("PROACTIVE_MIN_ENERGY", "0.2")  # Too tired below this
    )
    # Debug override: set to a low value (e.g. 30) for quick local testing
    PROACTIVE_DEBUG_THRESHOLD_OVERRIDE = os.getenv("PROACTIVE_DEBUG_THRESHOLD_OVERRIDE")

    # ── Psychological Layer Coefficients (psychological_layer.md §2.4) ──
    PSYCH_ALPHA = float(os.getenv("PSYCH_ALPHA", "0.3"))  # Valence drift rate
    PSYCH_BETA = float(os.getenv("PSYCH_BETA", "0.5"))  # Arousal response rate
    PSYCH_GAMMA = float(os.getenv("PSYCH_GAMMA", "0.2"))  # Dominance stability
    PSYCH_DELTA = float(os.getenv("PSYCH_DELTA", "0.1"))  # Trust change rate (Marsh)
    PSYCH_EPSILON = float(
        os.getenv("PSYCH_EPSILON", "0.03")
    )  # Attachment growth (Bowlby)
    PSYCH_LAMBDA_DECAY = float(os.getenv("PSYCH_LAMBDA_DECAY", "0.05"))  # ALMA decay

    # ── ACT-R Memory Retrieval (psychological_layer.md §6.2) ──
    ACTR_DECAY_RATE = float(os.getenv("ACTR_DECAY_RATE", "0.5"))  # d in Bᵢ formula
    ACTR_SPREAD_WEIGHT = float(
        os.getenv("ACTR_SPREAD_WEIGHT", "1.0")
    )  # Context relevance
    ACTR_EMOTION_WEIGHT = float(
        os.getenv("ACTR_EMOTION_WEIGHT", "0.5")
    )  # Emotional alignment

    # ── MAUT Decision Weights (psychological_layer.md §3.1) ──
    MAUT_W_GOAL = float(os.getenv("MAUT_W_GOAL", "0.35"))
    MAUT_W_EMOTION = float(os.getenv("MAUT_W_EMOTION", "0.25"))
    MAUT_W_IDENTITY = float(os.getenv("MAUT_W_IDENTITY", "0.20"))
    MAUT_W_CONTEXT = float(os.getenv("MAUT_W_CONTEXT", "0.20"))
    INTENT_PERSISTENCE_RATE = float(os.getenv("INTENT_PERSISTENCE_RATE", "0.5"))  # ρ
    CONTEXT_SHIFT_THRESHOLD = float(
        os.getenv("CONTEXT_SHIFT_THRESHOLD", "0.6")
    )  # θ_shift

    # ── Reappraisal Loop (psychological_layer.md §8) ──
    REAPPRAISAL_ENABLED = os.getenv("REAPPRAISAL_ENABLED", "true").lower() == "true"
    REAPPRAISAL_LEARNING_RATE = float(os.getenv("REAPPRAISAL_LEARNING_RATE", "0.05"))

    RUNTIME_AUTO_BOOTSTRAP = (
        os.getenv("RUNTIME_AUTO_BOOTSTRAP", "true").lower() == "true"
    )
    RUNTIME_BOOTSTRAP_RETRIES = int(os.getenv("RUNTIME_BOOTSTRAP_RETRIES", "12"))
    _required_models_env = os.getenv("OLLAMA_REQUIRED_MODELS", "").strip()
    if _required_models_env:
        OLLAMA_REQUIRED_MODELS = [
            model.strip() for model in _required_models_env.split(",") if model.strip()
        ]
    else:
        OLLAMA_REQUIRED_MODELS = list(
            dict.fromkeys(
                [
                    LLM_CHAT_MODEL,
                    LLM_FAST_MODEL,
                    LLM_REFLECTION_MODEL,
                    "nomic-embed-text",
                ]
            )
        )

    SOVITS_URL = os.getenv("SOVITS_URL", "http://localhost:9871")

    # Language Lock (English Priority)
    STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")
    TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")

    # Custom Voice Models (Fine-tuned)
    # These paths are relative to the GPT-SoVITS workspace inside the container
    CUSTOM_GPT_PATH = os.getenv("CUSTOM_GPT_PATH", "GPT_weights/ai_friend_voice.ckpt")
    CUSTOM_SOVITS_PATH = os.getenv(
        "CUSTOM_SOVITS_PATH", "SoVITS_weights/ai_friend_voice.pth"
    )
    VOICE_WEIGHT_LOAD_RETRIES = int(os.getenv("VOICE_WEIGHT_LOAD_RETRIES", "3"))
    VOICE_FILLER_HYDRATE_ON_STARTUP = (
        os.getenv("VOICE_FILLER_HYDRATE_ON_STARTUP", "true").lower() == "true"
    )

    STT_MODEL_SIZE = os.getenv("STT_MODEL_SIZE", "small")
    STT_DEVICE = os.getenv("STT_DEVICE", "cpu")

    # Audio Settings
    SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "32000"))
    BINARY_SUBJECTS = ["audio.inbound", "audio.stream"]
    # Phase 2 Calibration (Hardening Watchpoints)
    SYSTEM_TICK_INTERVAL = int(
        os.getenv("SYSTEM_TICK_INTERVAL", 60)
    )  # Heartbeat frequency
    FEEDBACK_ALPHA = 0.70  # Conversational smooth filter (BrainAgent)
    MAX_VOICE_QUEUE_SIZE = 10  # Backpressure guard (VoiceAgent)
    VOICE_SYNTH_CONCURRENCY = 1  # GPU safety semaphore (VoiceAgent)
    TRANSPORT_AUDIO_QUEUE_SIZE = int(os.getenv("TRANSPORT_AUDIO_QUEUE_SIZE", 256))
    VOICE_FILLER_MIN_INTERVAL_SECONDS = float(
        os.getenv("VOICE_FILLER_MIN_INTERVAL_SECONDS", 1.5)
    )
    VOICE_FILLER_MAX_PLAYBACK_BACKLOG = int(
        os.getenv("VOICE_FILLER_MAX_PLAYBACK_BACKLOG", 4)
    )

    INTENT_THRESHOLD = 0.75  # Temporal intent sensitivity (STTAgent)
    INTENT_STABILITY = 3  # Consecutive frames required for intent (STTAgent)
    STT_WHISPER_QUEUE_SIZE = int(os.getenv("STT_WHISPER_QUEUE_SIZE", 8))
    STT_PERCEPTION_QUEUE_SIZE = int(os.getenv("STT_PERCEPTION_QUEUE_SIZE", 4))

    GRAPH_CACHE_TTL = 300  # Belief freshness timeout in seconds (GraphDB)
    MIN_PERCEPTION_CONFIDENCE = float(os.getenv("MIN_PERCEPTION_CONFIDENCE", 0.55))
    STATE_SENSORY_WEIGHT = float(os.getenv("STATE_SENSORY_WEIGHT", 0.20))
    STATE_SENSORY_PERSIST_INTERVAL = float(
        os.getenv("STATE_SENSORY_PERSIST_INTERVAL", 2.0)
    )

    @staticmethod
    def validate():
        missing = []
        if not Config.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not Config.LIVEKIT_API_KEY:
            missing.append("LIVEKIT_API_KEY")
        if not Config.LIVEKIT_API_SECRET:
            missing.append("LIVEKIT_API_SECRET")
        if not Config.NEO4J_PASSWORD:
            missing.append("NEO4J_PASSWORD")
        if not Config.NEO4J_URI:
            missing.append("NEO4J_URI")

        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
