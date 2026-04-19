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
    SOVITS_URL = os.getenv("SOVITS_URL", "http://localhost:9871")
    
    # Custom Voice Models (Fine-tuned)
    # These paths are relative to the GPT-SoVITS workspace inside the container
    CUSTOM_GPT_PATH = os.getenv("CUSTOM_GPT_PATH", "GPT_weights/ai_friend_voice.ckpt")
    CUSTOM_SOVITS_PATH = os.getenv("CUSTOM_SOVITS_PATH", "SoVITS_weights/ai_friend_voice.pth")
    
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
