from pathlib import Path

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_file = Path(__file__).resolve().parent.parent.parent / ".env"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file), env_file_encoding="utf-8", extra="ignore"
    )

    DEBUG: bool = False
    # #162: the one signal `validate_no_placeholder_secrets_in_production`
    # gates on. Deliberately not derived from `DEBUG` (which defaults False in
    # every CI run and most local dev sessions too, so gating on it would fire
    # the placeholder check constantly where it shouldn't) or from `DATABASE_
    # URL`'s shape (which says nothing about whether this deployment is meant
    # to be reachable by anyone but its operator). Unset -- the default --
    # means the check never runs, so nothing about existing behavior changes
    # until an operator explicitly opts in.
    ENVIRONMENT: str = "development"
    # #160: `main.py` already reads this via `getattr(Config, "LOG_JSON",
    # False)` to pick JSON vs plain-text logging, but the field was never
    # actually declared here - `extra="ignore"` meant setting LOG_JSON=true
    # in .env had silently no effect at all, always falling through to the
    # getattr default. The JSON formatter itself (logging_config.py) was
    # already correct; only the toggle to reach it was dead.
    LOG_JSON: bool = False
    TESTING_CONSOLIDATION_BYPASS_SILENCE: bool = False
    ALLOWED_ORIGINS_STR: str = Field(default="*", alias="ALLOWED_ORIGINS")
    LAN_ONLY: bool = True
    BACKEND_ACCESS_KEY: str | None = None
    # C4: unchanged default (0.0.0.0) so nothing breaks today -- Docker
    # deployments need this regardless of LAN_ONLY, since Docker's port
    # publishing forwards to the container's network interface, not loopback.
    # This exists for the bare `python main.py` / no-Docker path, where an
    # operator who wants to restrict exposure (e.g. behind their own reverse
    # proxy) now has a lever instead of needing a code change.
    BACKEND_BIND_HOST: str = "0.0.0.0"
    # H3: caps how many session tokens one client IP can mint per window.
    # BACKEND_ACCESS_KEY already gates *who* can call /token; this bounds how
    # often, since a valid key doesn't imply unlimited LiveKit room creation.
    TOKEN_RATE_LIMIT_MAX_REQUESTS: int = 5
    TOKEN_RATE_LIMIT_WINDOW_SECONDS: float = 60.0
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
    LIVEKIT_API_KEY: str | None = None
    LIVEKIT_API_SECRET: str | None = None

    # Memory & Personality
    DATABASE_URL: str | None = None
    PERSONALITY_SEED_PATH: str | None = None
    HISTORY_SEED_PATH: str | None = None
    # A user-authored persona (see app/persona/profile.py). Unset means "use the
    # PSYCH_* / AI_NAME defaults below", which is exactly the previous behaviour.
    PERSONA_PROFILE_PATH: str | None = None
    # The authored biography (see app/persona/biography.py). Unset means "walk
    # up for config/biography.md", the historical behaviour. Set, it can point
    # anywhere — which is the point: a biography is a real person's life, and
    # keeping it out of the repo should not require a code change.
    BIOGRAPHY_PATH: str | None = None
    # Where `IdentityManager` writes runtime `personality.json`/`history.json`
    # evolution. Unset means a `.identity_state/` directory beside (not inside)
    # the `app/` package — outside the git-tracked tree, unlike the historical
    # default of "beside the code", which made the package directory itself
    # writable state and let a save without a durable store dirty a tracked
    # file (see H2 / issue #113). Containers should point this at a mounted
    # volume, e.g. `/app/data`.
    IDENTITY_BASE_PATH: str | None = None
    # Whether a fresh write location with no existing personality.json/
    # history.json gets seeded from the shipped `PERSONALITY_SEED_PATH`/
    # `HISTORY_SEED_PATH` (or package-directory defaults) on first use. True in
    # every real deployment, so a fresh install still boots with the shipped
    # persona instead of an empty one now that the write default no longer
    # matches the seed location. The test suite disables this (like it already
    # disables `PERSONA_PROFILE_PATH` discovery) so a fresh per-session temp
    # directory stays genuinely empty rather than picking up the repo's seed.
    IDENTITY_SEED_ON_FIRST_BOOT: bool = True

    # Neo4j Graph Configuration
    NEO4J_URI: str | None = None
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str | None = None
    NEO4J_AUTH: str | None = None

    AI_NAME: str = "AI Friend"
    OLLAMA_URL: str = "http://127.0.0.1:11434"

    LLM_FAST_MODEL: str = "llama3.2:3b"
    LLM_CHAT_MODEL: str | None = None
    LLM_REFLECTION_MODEL: str | None = None

    LLM_STREAM_MAX_SECONDS: int = 120
    LLM_INTENT_CLASSIFICATION_ENABLED: bool = True
    MOCK_LLM_TEXT: bool = False

    REFLECTION_ENABLED: bool = True
    REFLECTION_MIN_INTERVAL_SECONDS: float = 0.0

    PROACTIVE_ENABLED: bool = True
    PROACTIVE_IDLE_THRESHOLD_SECONDS: float = 7200.0
    PROACTIVE_COOLDOWN_SECONDS: float = 3600.0
    PROACTIVE_MIN_ENERGY: float = 0.2
    PROACTIVE_DEBUG_THRESHOLD_OVERRIDE: str | None = None

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

    # P1-6: Q-M2-2 answered SQLite as emergency-only, not a supported runtime
    # mode. A Postgres connection failure at bootstrap defaults to refusing
    # to start under ENVIRONMENT=production rather than silently downgrading
    # (losing pgvector) into a mode nobody chose to run. Set true only for a
    # deliberate degraded deployment, not as a standing default.
    ALLOW_SQLITE_FALLBACK: bool = False
    # Written by runtime_bootstrap.py (a different process than the backend
    # API) when the SQLite fallback is entered, so /health can surface it.
    # Same pattern as VISION_HEALTH_FILE below.
    SQLITE_FALLBACK_HEALTH_FILE: str = "/tmp/sqlite_fallback_active"

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

    # P1-7: measured (this repo's audit/) that two resident 3B models roughly
    # halve each other's decode rate on one GPU/one Ollama endpoint -- the
    # VLM and the conversational LLM otherwise contend on every turn. Since
    # OLLAMA_MAX_LOADED_MODELS=1 was measured to trade that for a ~2s
    # model-swap on every contention event (worse for VLM_APPRAISAL_INTERVAL-
    # frequency calls than the throughput hit it removes), the fix is
    # scheduling, not eviction: suspend VLM appraisal for the duration of a
    # cognitive turn instead.
    VISION_SUSPEND_DURING_TURN: bool = True
    # M3-R3: the VLM caller had no circuit breaker, so a failing Ollama (or
    # missing VLM model) was retried every capture tick with a full base64
    # frame. Modeled on the Rust CircuitBreaker in
    # crates/voice-agent/src/main.rs -- consecutive-failure threshold, then a
    # cooldown before the next real attempt.
    VLM_BREAKER_FAILURE_THRESHOLD: int = 3
    VLM_BREAKER_COOLDOWN_S: float = 30.0

    # Half-life of a phasic hormone burst, in seconds. Real phasic bursts last
    # only hundreds of milliseconds; these are the *felt* afterglow at
    # conversational timescale, so both are deliberately much slower than
    # biology and much faster than the ALMA mood decay (PSYCH_LAMBDA_DECAY,
    # hours). These are now only the
    # *defaults* a PersonaProfile inherits when a persona file does not name
    # them (see app/persona/profile.py); AgentState reads the persona's values,
    # not these. Cortisol's is the longer of the two deliberately: an acute
    # stress response outlasts a reward burst.
    DOPAMINE_PHASIC_HALFLIFE_S: float = 90.0
    CORTISOL_PHASIC_HALFLIFE_S: float = 600.0

    STT_MODEL_SIZE: str = "small"
    STT_DEVICE: str = "cpu"

    SAMPLE_RATE: int = 32000
    BINARY_SUBJECTS: list[str] = ["audio.inbound", "audio.stream"]
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

    # L5: pydantic-settings already validates *type* (a non-numeric
    # TOKEN_RATE_LIMIT_WINDOW_SECONDS fails to load at all), but not *range* -
    # a negative timeout or a zero halflife loads fine and only breaks
    # something at runtime. This is deliberately a short, curated list of
    # fields where an out-of-range value causes a specific concrete failure
    # (division by zero in decay math, a busy-loop tick, a rate limiter that
    # blocks everything or nothing), not an exhaustive sweep of every numeric
    # setting - most of the ~40 others have no failure mode worth guarding.
    _POSITIVE_FLOAT_FIELDS = (
        "DOPAMINE_PHASIC_HALFLIFE_S",
        "CORTISOL_PHASIC_HALFLIFE_S",
        "TOKEN_RATE_LIMIT_WINDOW_SECONDS",
        "LLM_STREAM_MAX_SECONDS",
    )
    _NON_NEGATIVE_FLOAT_FIELDS = ("ACTR_DECAY_RATE",)
    _POSITIVE_INT_FIELDS = (
        "SYSTEM_TICK_INTERVAL",
        "TOKEN_RATE_LIMIT_MAX_REQUESTS",
        "MAX_VOICE_QUEUE_SIZE",
        "VOICE_SYNTH_CONCURRENCY",
        "TRANSPORT_AUDIO_QUEUE_SIZE",
        "STT_WHISPER_QUEUE_SIZE",
        "STT_PERCEPTION_QUEUE_SIZE",
    )

    @model_validator(mode="after")
    def validate_numeric_ranges(self):
        for name in self._POSITIVE_FLOAT_FIELDS:
            value = getattr(self, name)
            if not (value > 0):
                raise ValueError(f"{name} must be > 0 (got {value!r})")
        for name in self._NON_NEGATIVE_FLOAT_FIELDS:
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"{name} must be >= 0 (got {value!r})")
        for name in self._POSITIVE_INT_FIELDS:
            value = getattr(self, name)
            if value < 1:
                raise ValueError(f"{name} must be >= 1 (got {value!r})")
        if not (0 < self.QDRANT_PORT <= 65535):
            raise ValueError(f"QDRANT_PORT must be a valid port (got {self.QDRANT_PORT!r})")
        return self

    # #162: the literal placeholder strings this repo's own `.env.example`
    # ships. Deliberately this narrow set, not a generic "looks like a weak
    # password" heuristic -- a heuristic strong enough to catch real weak
    # passwords is also strong enough to reject a legitimate one that happens
    # to contain a common word, and a false positive here means production
    # refuses to boot. This only catches the exact templates a deployment gets
    # by copying `.env.example` and forgetting to edit it, which is the
    # failure mode the issue describes.
    _PLACEHOLDER_SECRET_MARKERS = (
        "your_password_here",
        "your_graph_password_here",
        "your_api_key_here",
        "your_api_secret_here",
    )
    # Only the fields that gate a real, network-reachable service if left at
    # the shipped placeholder -- Postgres/Neo4j auth and the LiveKit room
    # credentials. Optional integrations (Gemini, ElevenLabs, Porcupine) are
    # deliberately excluded: a placeholder there disables a feature, it
    # doesn't expose one.
    _SECRET_BEARING_FIELDS = (
        "DATABASE_URL",
        "NEO4J_PASSWORD",
        "NEO4J_AUTH",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
    )

    @model_validator(mode="after")
    def validate_no_placeholder_secrets_in_production(self):
        if self.ENVIRONMENT != "production":
            return self
        for name in self._SECRET_BEARING_FIELDS:
            value = getattr(self, name, None)
            if not value:
                continue
            if any(marker in value for marker in self._PLACEHOLDER_SECRET_MARKERS):
                raise ValueError(
                    f"{name} still contains a placeholder value from .env.example "
                    "-- refusing to start with ENVIRONMENT=production. Set a real "
                    "secret before deploying."
                )
        return self

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
    def ALLOWED_ORIGINS(self) -> list[str]:
        return self.ALLOWED_ORIGINS_STR.split(",")

    @computed_field
    @property
    def OLLAMA_REQUIRED_MODELS(self) -> list[str]:
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
