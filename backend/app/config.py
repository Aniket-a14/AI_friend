from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field, field_validator, model_validator

_env_file = Path(__file__).resolve().parent.parent.parent / ".env"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file), env_file_encoding="utf-8", extra="ignore"
    )

    DEBUG: bool = False
    TESTING_CONSOLIDATION_BYPASS_SILENCE: bool = False
    ALLOWED_ORIGINS_STR: str = Field(default="*", alias="ALLOWED_ORIGINS")
    LAN_ONLY: bool = True
    BACKEND_ACCESS_KEY: Optional[str] = None
    LAN_CORS_ORIGIN_REGEX: str = (
        r"^https?://("
        r"127\.0\.0\.1|"
        r"127(?:\.\d{1,3}){3}|"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
        r")(?::\d+)?$"
    )

    # NATS Configuration
    NATS_URL: str = "nats://127.0.0.1:4222"

    # Redis Configuration
    REDIS_URL: str = "redis://127.0.0.1:6379"

    # Qdrant Configuration
    QDRANT_HOST: str = "127.0.0.1"
    QDRANT_PORT: int = 6333

    # LiveKit Configuration
    LIVEKIT_URL: str = "ws://127.0.0.1:7880"
    LIVEKIT_API_KEY: Optional[str] = None
    LIVEKIT_API_SECRET: Optional[str] = None

    # Memory & Personality
    DATABASE_URL: Optional[str] = None
    PERSONALITY_SEED_PATH: Optional[str] = None
    HISTORY_SEED_PATH: Optional[str] = None

    # Neo4j Graph Configuration
    NEO4J_URI: Optional[str] = None
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: Optional[str] = None
    NEO4J_AUTH: Optional[str] = None

    AI_NAME: str = "AI Friend"
    OLLAMA_URL: str = "http://127.0.0.1:11434"

    LLM_FAST_MODEL: str = "llama3.2:3b"
    LLM_CHAT_MODEL: Optional[str] = None
    LLM_REFLECTION_MODEL: Optional[str] = None

    LLM_STREAM_MAX_SECONDS: int = 120
    LLM_INTENT_CLASSIFICATION_ENABLED: bool = True
    MOCK_LLM_TEXT: bool = False

    REFLECTION_ENABLED: bool = True
    REFLECTION_MIN_INTERVAL_SECONDS: float = 0.0

    PROACTIVE_ENABLED: bool = True
    PROACTIVE_IDLE_THRESHOLD_SECONDS: float = 7200.0
    PROACTIVE_COOLDOWN_SECONDS: float = 3600.0
    PROACTIVE_MIN_ENERGY: float = 0.2
    PROACTIVE_DEBUG_THRESHOLD_OVERRIDE: Optional[str] = None

    PSYCH_ALPHA: float = 0.3
    PSYCH_BETA: float = 0.5
    PSYCH_GAMMA: float = 0.2
    PSYCH_DELTA: float = 0.1
    PSYCH_EPSILON: float = 0.03
    PSYCH_LAMBDA_DECAY: float = 0.05

    ACTR_DECAY_RATE: float = 0.5
    ACTR_SPREAD_WEIGHT: float = 1.0
    ACTR_EMOTION_WEIGHT: float = 0.5

    MAUT_W_GOAL: float = 0.35
    MAUT_W_EMOTION: float = 0.25
    MAUT_W_IDENTITY: float = 0.20
    MAUT_W_CONTEXT: float = 0.20
    INTENT_PERSISTENCE_RATE: float = 0.5
    CONTEXT_SHIFT_THRESHOLD: float = 0.6

    REAPPRAISAL_ENABLED: bool = True
    REAPPRAISAL_LEARNING_RATE: float = 0.05

    RUNTIME_AUTO_BOOTSTRAP: bool = True
    RUNTIME_BOOTSTRAP_RETRIES: int = 12
    OLLAMA_REQUIRED_MODELS_STR: str = Field(default="", alias="OLLAMA_REQUIRED_MODELS")

    SOVITS_URL: str = "http://127.0.0.1:9871"
    STT_LANGUAGE: str = "en"
    TTS_LANGUAGE: str = "en"

    CUSTOM_GPT_PATH: str = "GPT_weights/ai_friend_voice.ckpt"
    CUSTOM_SOVITS_PATH: str = "SoVITS_weights/ai_friend_voice.pth"
    VOICE_WEIGHT_LOAD_RETRIES: int = 3
    VOICE_FILLER_HYDRATE_ON_STARTUP: bool = True
    VOICE_TTS_MOCK: bool = False

    # Vision / VLM Configuration
    VLM_MODEL: str = "moondream"
    VLM_ENABLED: bool = True
    VLM_APPRAISAL_INTERVAL: float = 5.0
    VLM_HABITUATION_THRESHOLD: float = 0.005
    VLM_PROMPT: str = (
        "Describe what you see in this image briefly. Focus on what the user is doing."
    )
    # Touched on every successful frame capture so a container healthcheck can
    # probe the real path rather than mere process liveness (see finding E1).
    VISION_HEALTH_FILE: str = "/tmp/vision_agent_healthy"

    STT_MODEL_SIZE: str = "small"
    STT_DEVICE: str = "cpu"

    SAMPLE_RATE: int = 32000
    BINARY_SUBJECTS: List[str] = ["audio.inbound", "audio.stream"]
    SYSTEM_TICK_INTERVAL: int = 60
    FEEDBACK_ALPHA: float = 0.70
    MAX_VOICE_QUEUE_SIZE: int = 10
    VOICE_SYNTH_CONCURRENCY: int = 1
    TRANSPORT_AUDIO_QUEUE_SIZE: int = 256
    VOICE_FILLER_MIN_INTERVAL_SECONDS: float = 1.5
    VOICE_FILLER_MAX_PLAYBACK_BACKLOG: int = 4
    VOICE_FILLER_THRESHOLD: float = 0.25

    INTENT_THRESHOLD: float = 0.75
    INTENT_STABILITY: int = 3
    # Reduced to 4 for smoother macOS/CPU performance during high-throughput research
    STT_WHISPER_QUEUE_SIZE: int = 4
    STT_PERCEPTION_QUEUE_SIZE: int = 4

    GRAPH_CACHE_TTL: int = 300
    MIN_PERCEPTION_CONFIDENCE: float = 0.55
    STATE_SENSORY_WEIGHT: float = 0.20
    STATE_SENSORY_PERSIST_INTERVAL: float = 2.0

    @model_validator(mode="after")
    def set_defaults(self):
        if not self.LLM_CHAT_MODEL:
            self.LLM_CHAT_MODEL = self.LLM_FAST_MODEL
        if not self.LLM_REFLECTION_MODEL:
            self.LLM_REFLECTION_MODEL = self.LLM_CHAT_MODEL
        return self

    @field_validator("LIVEKIT_URL")
    @classmethod
    def normalize_livekit_scheme(cls, v: str) -> str:
        """E3: both the frontend and transport_agent hand this straight to
        LiveKit's room.connect(), which needs ws(s)://, not http(s)://. Normalize
        here so an existing .env carrying the old http:// default (from before
        this fix) self-heals instead of requiring every deployment to be
        manually edited.
        """
        if v.startswith("https://"):
            return "wss://" + v[len("https://") :]
        if v.startswith("http://"):
            return "ws://" + v[len("http://") :]
        return v

    # F4: these were previously computed in ConfigMeta.__getattr__, which
    # special-cased these two names and silently delegated every other
    # attribute straight to config_instance - a surprising place to look for
    # derived config, and easy to miss when adding a third computed value.
    # Real computed_field properties are visible on AppSettings itself, so
    # ConfigMeta's job shrinks to "look up the instance," nothing more.
    @computed_field
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return self.ALLOWED_ORIGINS_STR.split(",")

    @computed_field
    @property
    def OLLAMA_REQUIRED_MODELS(self) -> List[str]:
        if self.OLLAMA_REQUIRED_MODELS_STR.strip():
            return [
                model.strip()
                for model in self.OLLAMA_REQUIRED_MODELS_STR.split(",")
                if model.strip()
            ]
        models = [
            self.LLM_CHAT_MODEL,
            self.LLM_FAST_MODEL,
            self.LLM_REFLECTION_MODEL,
            "nomic-embed-text",
        ]
        if self.VLM_ENABLED:
            models.append(self.VLM_MODEL)
        return list(dict.fromkeys(models))


config_instance = AppSettings()


class ConfigMeta(type):
    def __getattr__(cls, name):
        return getattr(config_instance, name)


class Config(metaclass=ConfigMeta):
    @staticmethod
    def validate():
        # Validation is now handled by Pydantic during instantiation.
        pass
