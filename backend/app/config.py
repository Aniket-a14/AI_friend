import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

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
    NEO4J_AUTH = os.getenv("NEO4J_AUTH") # user/pass format compatible with Docker
    
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

    RUNTIME_AUTO_BOOTSTRAP = os.getenv("RUNTIME_AUTO_BOOTSTRAP", "true").lower() == "true"
    RUNTIME_BOOTSTRAP_RETRIES = int(os.getenv("RUNTIME_BOOTSTRAP_RETRIES", "12"))
    _required_models_env = os.getenv("OLLAMA_REQUIRED_MODELS", "").strip()
    if _required_models_env:
        OLLAMA_REQUIRED_MODELS = [
            model.strip() for model in _required_models_env.split(",") if model.strip()
        ]
    else:
        OLLAMA_REQUIRED_MODELS = list(
            dict.fromkeys(
                [LLM_CHAT_MODEL, LLM_FAST_MODEL, LLM_REFLECTION_MODEL, "nomic-embed-text"]
            )
        )

    SOVITS_URL = os.getenv("SOVITS_URL", "http://localhost:9871")
    
    # Language Lock (English Priority)
    STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")
    TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")
    
    # Custom Voice Models (Fine-tuned)
    # These paths are relative to the GPT-SoVITS workspace inside the container
    CUSTOM_GPT_PATH = os.getenv("CUSTOM_GPT_PATH", "GPT_weights/ai_friend_voice.ckpt")
    CUSTOM_SOVITS_PATH = os.getenv("CUSTOM_SOVITS_PATH", "SoVITS_weights/ai_friend_voice.pth")
    VOICE_WEIGHT_LOAD_RETRIES = int(os.getenv("VOICE_WEIGHT_LOAD_RETRIES", "3"))
    VOICE_FILLER_HYDRATE_ON_STARTUP = (
        os.getenv("VOICE_FILLER_HYDRATE_ON_STARTUP", "true").lower() == "true"
    )
    
    STT_MODEL_SIZE = os.getenv("STT_MODEL_SIZE", "small")
    STT_DEVICE = os.getenv("STT_DEVICE", "cpu")

    # Audio Settings
    SAMPLE_RATE = 32000
    BINARY_SUBJECTS = ["audio.inbound", "audio.stream"]
    # Phase 2 Calibration (Hardening Watchpoints)
    SYSTEM_TICK_INTERVAL = int(os.getenv("SYSTEM_TICK_INTERVAL", 60)) # Heartbeat frequency
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
    INTENT_STABILITY = 3     # Consecutive frames required for intent (STTAgent)
    STT_WHISPER_QUEUE_SIZE = int(os.getenv("STT_WHISPER_QUEUE_SIZE", 8))
    STT_PERCEPTION_QUEUE_SIZE = int(os.getenv("STT_PERCEPTION_QUEUE_SIZE", 4))
    
    GRAPH_CACHE_TTL = 300    # Belief freshness timeout in seconds (GraphDB)
    MIN_PERCEPTION_CONFIDENCE = float(os.getenv("MIN_PERCEPTION_CONFIDENCE", 0.55))
    STATE_SENSORY_WEIGHT = float(os.getenv("STATE_SENSORY_WEIGHT", 0.20))
    STATE_SENSORY_PERSIST_INTERVAL = float(os.getenv("STATE_SENSORY_PERSIST_INTERVAL", 2.0))

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
