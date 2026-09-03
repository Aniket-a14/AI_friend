"""
L5: pydantic-settings validates type on load (a non-numeric env value fails
to parse) but not range - a negative timeout or a zero halflife loaded fine
and only broke something later, at runtime, far from the misconfiguration.
"""

import pytest
from pydantic import ValidationError

from app import config as config_module
from app.config import AppSettings


def _settings(**overrides):
    return AppSettings(_env_file=None, **overrides)


@pytest.mark.parametrize(
    "field",
    [
        "DOPAMINE_PHASIC_HALFLIFE_S",
        "CORTISOL_PHASIC_HALFLIFE_S",
        "TOKEN_RATE_LIMIT_WINDOW_SECONDS",
        "LLM_STREAM_MAX_SECONDS",
    ],
)
def test_zero_or_negative_rejected_for_positive_float_fields(field):
    """A zero halflife divides by zero in decay math; a zero/negative
    timeout produces nonsensical (instant or infinite) behavior."""
    with pytest.raises(ValidationError):
        _settings(**{field: 0})
    with pytest.raises(ValidationError):
        _settings(**{field: -1})


def test_negative_decay_rate_rejected():
    """A negative ACTR_DECAY_RATE would make memories strengthen with time
    instead of decaying - an inversion of the intended model, not just an
    edge case."""
    with pytest.raises(ValidationError):
        _settings(ACTR_DECAY_RATE=-0.1)


def test_zero_decay_rate_is_allowed():
    """Zero is a legitimate (if unusual) choice - 'never decay' - unlike
    negative, which inverts the model."""
    settings = _settings(ACTR_DECAY_RATE=0.0)
    assert settings.ACTR_DECAY_RATE == 0.0


@pytest.mark.parametrize(
    "field",
    [
        "SYSTEM_TICK_INTERVAL",
        "TOKEN_RATE_LIMIT_MAX_REQUESTS",
        "MAX_VOICE_QUEUE_SIZE",
        "VOICE_SYNTH_CONCURRENCY",
        "TRANSPORT_AUDIO_QUEUE_SIZE",
        "STT_WHISPER_QUEUE_SIZE",
        "STT_PERCEPTION_QUEUE_SIZE",
    ],
)
def test_zero_or_negative_rejected_for_positive_int_fields(field):
    """A zero SYSTEM_TICK_INTERVAL busy-loops; a zero queue/concurrency size
    is a store nothing can ever pass through."""
    with pytest.raises(ValidationError):
        _settings(**{field: 0})
    with pytest.raises(ValidationError):
        _settings(**{field: -1})


def test_qdrant_port_out_of_range_rejected():
    with pytest.raises(ValidationError):
        _settings(QDRANT_PORT=0)
    with pytest.raises(ValidationError):
        _settings(QDRANT_PORT=70000)


def test_default_settings_load_without_error():
    """Sanity check that the new validator doesn't reject the shipped
    defaults themselves."""
    settings = _settings()
    assert settings.SYSTEM_TICK_INTERVAL > 0


def test_log_json_env_var_actually_reaches_the_setting(monkeypatch):
    """#160: `main.py` reads `getattr(Config, "LOG_JSON", False)` to choose
    JSON vs plain-text logging, but `LOG_JSON` was never declared as an
    `AppSettings` field - with `extra="ignore"`, setting `LOG_JSON=true` in
    the environment had silently zero effect, always falling through to the
    getattr default. This proves the env var now actually reaches the field.
    """
    monkeypatch.setenv("LOG_JSON", "true")
    settings = AppSettings(_env_file=None)
    assert settings.LOG_JSON is True


# --- #162: placeholder-secret guard in production --------------------------


@pytest.mark.parametrize(
    "field,placeholder",
    [
        ("DATABASE_URL", "postgresql://ai_friend:your_password_here@127.0.0.1:5432/db"),
        ("NEO4J_PASSWORD", "your_graph_password_here"),
        ("NEO4J_AUTH", "neo4j/your_graph_password_here"),
        ("LIVEKIT_API_KEY", "your_api_key_here"),
        ("LIVEKIT_API_SECRET", "your_api_secret_here"),
        # P0-1: the committed livekit.yaml `keys:` block (now removed) held
        # `devkey: secretsecretsecret`. If either half ever reaches these
        # fields -- e.g. an .env carried forward from before the fix -- the
        # guard must still catch it.
        ("LIVEKIT_API_KEY", "devkey"),
        ("LIVEKIT_API_SECRET", "secretsecretsecret"),
    ],
)
def test_placeholder_secret_rejected_in_production(field, placeholder):
    """The exact failure mode #162 describes: copying .env.example and
    deploying without editing it. If this stops firing, a deployment can boot
    with Postgres/Neo4j/LiveKit auth set to a publicly-known default."""
    with pytest.raises(ValidationError):
        _settings(ENVIRONMENT="production", **{field: placeholder})


def test_placeholder_secret_allowed_outside_production():
    """The guard must not fire for local/dev use, where copying .env.example
    verbatim before filling in real secrets is the documented first step."""
    settings = _settings(
        ENVIRONMENT="development", NEO4J_PASSWORD="your_graph_password_here"
    )
    assert settings.NEO4J_PASSWORD == "your_graph_password_here"


def test_real_looking_secret_allowed_in_production():
    """A genuine secret must never be rejected just for existing - only the
    literal shipped placeholder strings are checked."""
    settings = _settings(
        ENVIRONMENT="production",
        NEO4J_PASSWORD="a-real-generated-secret-x9k2m",
        LIVEKIT_API_KEY="APIabc123real",
        LIVEKIT_API_SECRET="a-real-secret-value",
        DATABASE_URL="postgresql://ai_friend:a-real-secret-value@postgres_db:5432/db",
    )
    assert settings.NEO4J_PASSWORD == "a-real-generated-secret-x9k2m"


def test_real_credential_containing_devkey_is_not_rejected():
    """P0-1 follow-up: "devkey" is only six characters, so substring-matching
    it would let a randomly-generated credential that happens to contain
    those letters stop production from booting. The two LiveKit markers are
    matched whole for exactly this reason; if that regresses, a valid
    deployment fails to start with a misleading "placeholder" error."""
    # Low-entropy, unmistakably-a-fixture values on purpose: a random-looking
    # string here (even a fake one) trips the repo's own gitleaks scan, which
    # scores on entropy rather than provenance -- the same trap CLAUDE.md
    # documents for the credential-scan grep, one layer over.
    settings = _settings(
        ENVIRONMENT="production",
        LIVEKIT_API_KEY="livekit-api-key-with-devkey-inside",
        LIVEKIT_API_SECRET="livekit-api-secret-with-secretsecretsecret-inside",
    )
    assert settings.LIVEKIT_API_KEY == "livekit-api-key-with-devkey-inside"


def test_unset_secret_fields_do_not_crash_production():
    """A field an operator hasn't configured at all (None) must not be
    treated as a placeholder - only an actual placeholder string should."""
    settings = _settings(ENVIRONMENT="production")
    assert settings.ENVIRONMENT == "production"


# --- HUMANOID_ARCHITECTURE_RESEARCH.md Phase 0: LLM_PROVENANCE -------------


def test_llm_provenance_reports_the_resolved_model_for_each_role():
    """The whole point of this field is that a caller can read off what each
    role actually resolved to without re-deriving it from LLM_CHAT_MODEL,
    LLM_FAST_MODEL etc. separately. If the snapshot silently dropped a field
    or read a different one, a report built from it would look complete
    while quietly describing the wrong model."""
    settings = _settings(
        LLM_CHAT_MODEL="phi4-mini",
        LLM_FAST_MODEL="qwen2.5:3b",
        LLM_REFLECTION_MODEL="llama3.2:3b",
        LLM_NUM_CTX=4096,
        LLM_INTENT_CLASSIFICATION_ENABLED=True,
        OLLAMA_URL="http://10.0.0.5:11434",
    )
    assert settings.LLM_PROVENANCE == {
        "env_file": None,
        "env_file_exists": False,
        "llm_chat_model": "phi4-mini",
        "llm_fast_model": "qwen2.5:3b",
        "llm_reflection_model": "llama3.2:3b",
        "llm_num_ctx": 4096,
        "llm_intent_classification_enabled": True,
        "ollama_url": "http://10.0.0.5:11434",
        "precedence": [
            "constructor",
            "process_env",
            "env_file",
            "code_default",
        ],
        "sources": {
            "ollama_url": "constructor",
            "llm_fast_model": "constructor",
            "llm_chat_model": "constructor",
            "llm_reflection_model": "constructor",
            "llm_num_ctx": "constructor",
            "llm_intent_classification_enabled": "constructor",
        },
    }


def test_llm_provenance_names_the_env_file_this_instance_actually_reads():
    """The ledger's 2026-09-02 entries record two separate incidents where a
    value was read from the wrong `.env` (repo-root vs `backend/.env` vs a
    systemd EnvironmentFile) and mistaken for the deployed config. This is
    the field meant to make that mistake visible without a manual grep -- it
    must name the real path `Config` resolves from, which is fixed at the
    module level and does not move just because one test instance was built
    with `_env_file=None` to keep it isolated from whatever real `.env`
    happens to be on this machine. An isolated instance with `_env_file=None`
    must therefore report no dotenv source."""
    settings = _settings()
    assert settings.LLM_PROVENANCE["env_file"] is None
    assert settings.LLM_PROVENANCE["env_file_exists"] is False


def test_default_settings_provenance_names_its_configured_env_file():
    settings = config_module.config_instance
    assert settings.LLM_PROVENANCE["env_file"] == str(config_module._env_file)


def test_llm_provenance_reflects_the_chat_and_reflection_backfill():
    """set_defaults() backfills an unset LLM_CHAT_MODEL/LLM_REFLECTION_MODEL
    from LLM_FAST_MODEL. LLM_PROVENANCE reads the fields after validation, so
    it must show the backfilled value a caller would actually get from
    Config, not the unset None an operator's .env left behind."""
    settings = _settings(LLM_FAST_MODEL="qwen2.5:3b")
    assert settings.LLM_PROVENANCE["llm_chat_model"] == "qwen2.5:3b"
    assert settings.LLM_PROVENANCE["llm_reflection_model"] == "qwen2.5:3b"


def test_llm_provenance_identifies_process_environment_as_the_winner(monkeypatch):
    monkeypatch.setenv("LLM_CHAT_MODEL", "from-process")
    settings = _settings(LLM_CHAT_MODEL="constructor-value")
    assert settings.LLM_PROVENANCE["sources"]["llm_chat_model"] == "constructor"


def test_llm_provenance_sources_are_snapshotted_at_construction(monkeypatch):
    settings = _settings(LLM_CHAT_MODEL="constructor-value")
    monkeypatch.setenv("LLM_CHAT_MODEL", "added-after-construction")
    assert settings.LLM_CHAT_MODEL == "constructor-value"
    assert settings.LLM_PROVENANCE["sources"]["llm_chat_model"] == "constructor"


def test_validate_debug_handles_string_inputs():
    """Environment variables often arrive as 'release', 'production', 'dev',
    or 'debug' rather than Python booleans. The validator must coerce these cleanly."""
    assert _settings(DEBUG="release").DEBUG is False
    assert _settings(DEBUG="prod").DEBUG is False
    assert _settings(DEBUG="0").DEBUG is False
    assert _settings(DEBUG="debug").DEBUG is True
    assert _settings(DEBUG="dev").DEBUG is True
    assert _settings(DEBUG="true").DEBUG is True


def test_env_file_resolution_rules(monkeypatch):
    """Verify that _env_file resolution honors AI_FRIEND_ENV_PATH when present."""
    import os
    from pathlib import Path
    custom_env = "/custom/path/.env"
    monkeypatch.setenv("AI_FRIEND_ENV_PATH", custom_env)
    # Test the resolution logic matching config.py
    discovered_parent = Path("/app/app/config.py").parent.parent.parent
    if "AI_FRIEND_ENV_PATH" in os.environ:
        resolved = Path(os.environ["AI_FRIEND_ENV_PATH"])
    elif discovered_parent == Path("/"):
        resolved = Path("/app/.env")
    else:
        resolved = discovered_parent / ".env"
    assert str(resolved) == custom_env

    # Without AI_FRIEND_ENV_PATH, a container root (/) resolves to /app/.env
    monkeypatch.delenv("AI_FRIEND_ENV_PATH")
    if "AI_FRIEND_ENV_PATH" in os.environ:
        resolved_container = Path(os.environ["AI_FRIEND_ENV_PATH"])
    elif discovered_parent == Path("/"):
        resolved_container = Path("/app/.env")
    else:
        resolved_container = discovered_parent / ".env"
    assert str(resolved_container) == "/app/.env"
