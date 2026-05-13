from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env", env_file_encoding="utf-8", extra="ignore"
    )

    DEBUG: bool = False
    ALLOWED_ORIGINS_STR: str = Field(default="*", alias="ALLOWED_ORIGINS")
    LAN_ONLY: bool = True
    LAN_CORS_ORIGIN_REGEX: str = (
        r"^https?://("
        r"localhost|"
        r"127(?:\.\d{1,3}){3}|"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
        r")(?::\d+)?$"
    )

    # NATS Configuration
    NATS_URL: str = "nats://localhost:4222"

    # LiveKit Configuration
    LIVEKIT_URL: str = "http://localhost:7880"
    LIVEKIT_API_KEY: Optional[str] = None
    LIVEKIT_API_SECRET: Optional[str] = None

    # Memory & Personality
    DATABASE_URL: Optional[str] = None

    # Neo4j Graph Configuration
    NEO4J_URI: Optional[str] = None
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: Optional[str] = None
    NEO4J_AUTH: Optional[str] = None

    AI_NAME: str = "AI Friend"
    OLLAMA_URL: str = "http://localhost:11434"

    LLM_FAST_MODEL: str = "llama3.2:1b"
    LLM_CHAT_MODEL: Optional[str] = None
    LLM_REFLECTION_MODEL: Optional[str] = None

    LLM_STREAM_MAX_SECONDS: int = 120
    LLM_INTENT_CLASSIFICATION_ENABLED: bool = True

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

    SOVITS_URL: str = "http://localhost:9871"
    STT_LANGUAGE: str = "en"
    TTS_LANGUAGE: str = "en"

    CUSTOM_GPT_PATH: str = "GPT_weights/ai_friend_voice.ckpt"
    CUSTOM_SOVITS_PATH: str = "SoVITS_weights/ai_friend_voice.pth"
    VOICE_WEIGHT_LOAD_RETRIES: int = 3
    VOICE_FILLER_HYDRATE_ON_STARTUP: bool = True

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

    INTENT_THRESHOLD: float = 0.75
    INTENT_STABILITY: int = 3
    STT_WHISPER_QUEUE_SIZE: int = 8
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


config_instance = AppSettings()


class ConfigMeta(type):
    def __getattr__(cls, name):
        if name == "ALLOWED_ORIGINS":
            return config_instance.ALLOWED_ORIGINS_STR.split(",")
        if name == "OLLAMA_REQUIRED_MODELS":
            if config_instance.OLLAMA_REQUIRED_MODELS_STR.strip():
                return [
                    model.strip()
                    for model in config_instance.OLLAMA_REQUIRED_MODELS_STR.split(",")
                    if model.strip()
                ]
            else:
                return list(
                    dict.fromkeys(
                        [
                            config_instance.LLM_CHAT_MODEL,
                            config_instance.LLM_FAST_MODEL,
                            config_instance.LLM_REFLECTION_MODEL,
                            "nomic-embed-text",
                        ]
                    )
                )
        return getattr(config_instance, name)


class Config(metaclass=ConfigMeta):
    @staticmethod
    def validate():
        # Validation is now handled by Pydantic during instantiation.
        pass
