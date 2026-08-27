"""voice_agent had no `env_file: .env` and its `environment:` block listed
only REF_AUDIO_PATH/REF_TEXT -- so the eight REF_*_{CALM,WARM,CONCERNED,
EXCITED} vars docs/BRINGING_IT_TO_LIFE.md instructs users to set, plus
TTS_CIRCUIT_BREAKER_*/TTS_READINESS_PROBE_INTERVAL_SECS, were silently
ignored under Compose (roadmap Phase 1.4). This class of bug is invisible
without a check that cross-references what the Rust binary actually reads
against what Compose actually wires through."""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.prod.yml"
VOICE_AGENT_MAIN_RS = (
    REPO_ROOT / "backend" / "crates" / "voice-agent" / "src" / "main.rs"
)

# Vars read via a literal env_or("NAME", ...) / std::env::var("NAME") call --
# not the REF_*_{BUCKET} family, which optional_ref_clip builds from a
# suffix, matched separately below.
ENV_OR_PATTERN = re.compile(r'env_or\("([A-Z0-9_]+)"')
ENV_VAR_PATTERN = re.compile(r'std::env::var\("([A-Z0-9_]+)"\)')
EMOTION_BUCKETS = ["CALM", "WARM", "CONCERNED", "EXCITED"]


def _voice_agent_service():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    return compose["services"]["voice_agent"]


def _env_vars_read_by_rust_source() -> set[str]:
    source = VOICE_AGENT_MAIN_RS.read_text()
    names = set(ENV_OR_PATTERN.findall(source)) | set(ENV_VAR_PATTERN.findall(source))
    for bucket in EMOTION_BUCKETS:
        names.add(f"REF_AUDIO_PATH_{bucket}")
        names.add(f"REF_TEXT_{bucket}")
    # NATS_USER/NATS_PASSWORD are read via std::env::var but not per-service --
    # every agent reads them and they're covered by the shared NATS_* wiring,
    # not the voice-specific vars this test exists to guard.
    return {n for n in names if n not in {"NATS_USER", "NATS_PASSWORD"}}


def test_every_env_var_the_rust_source_reads_is_wired_through_compose():
    service = _voice_agent_service()
    declared_keys = {
        entry.split("=", 1)[0] for entry in service.get("environment", [])
    }
    has_env_file = bool(service.get("env_file"))

    missing = _env_vars_read_by_rust_source() - declared_keys
    # env_file: .env makes any var present in .env reachable even if not
    # explicitly listed -- but the vars this bug was about (REF_*_CALM etc.)
    # must still be explicit, since that's what documents their defaults and
    # is what a user actually inspects to know the knob exists at all.
    assert not missing or has_env_file, (
        f"voice_agent service is missing these env vars entirely "
        f"(no env_file either): {sorted(missing)}"
    )
    assert missing == set(), (
        f"these env vars are only reachable via env_file, not listed "
        f"explicitly in voice_agent's environment: {sorted(missing)}"
    )


def test_voice_agent_has_env_file_wired():
    """Without env_file: .env, any var not explicitly enumerated above --
    including ones added later -- silently never reaches the container."""
    assert _voice_agent_service().get("env_file") == ".env"


def test_the_four_emotion_bucket_pairs_are_all_declared():
    service = _voice_agent_service()
    declared_keys = {
        entry.split("=", 1)[0] for entry in service.get("environment", [])
    }
    for bucket in EMOTION_BUCKETS:
        assert f"REF_AUDIO_PATH_{bucket}" in declared_keys
        assert f"REF_TEXT_{bucket}" in declared_keys
