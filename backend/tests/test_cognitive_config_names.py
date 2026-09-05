"""Configuration renames must preserve deployment overrides and live consumers."""

import pytest

from app import config as config_module
from app.config import AppSettings, Config


@pytest.fixture(params=[
    ("MEMORY_TRUTH_ENABLED", "PHASE_02_MEMORY_TRUTH"),
    ("AFFECT_CONTROL_ENABLED", "PHASE_03_AFFECT_CONTROL"),
])
def flag_names(request, monkeypatch):
    for name in request.param:
        monkeypatch.delenv(name, raising=False)
    return request.param


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("source", ["constructor", "environment", "dotenv"])
def test_disabled_flag_reaches_runtime_from_either_input_name(
    flag_names, legacy, source, monkeypatch, tmp_path
):
    """An existing deployment's opt-out must still disable the live feature."""
    canonical, old = flag_names
    name = old if legacy else canonical
    kwargs = {"_env_file": None}
    if source == "constructor":
        kwargs[name] = False
    elif source == "environment":
        monkeypatch.setenv(name, "false")
    else:
        env_file = tmp_path / ".env"
        env_file.write_text(f"{name}=false\n")
        kwargs["_env_file"] = env_file
    settings = AppSettings(**kwargs)
    monkeypatch.setattr(config_module, "config_instance", settings)
    assert getattr(Config, canonical) is False
    assert old not in settings.model_dump()


def test_canonical_flag_wins_conflicting_environment_names(flag_names, monkeypatch):
    """Two spellings in one source must not create contradictory runtime gates."""
    canonical, old = flag_names
    monkeypatch.setenv(old, "true")
    monkeypatch.setenv(canonical, "false")
    assert getattr(AppSettings(_env_file=None), canonical) is False


def test_legacy_process_override_beats_canonical_dotenv(flag_names, monkeypatch, tmp_path):
    """Existing process overrides must keep priority over a newer .env template."""
    canonical, old = flag_names
    env_file = tmp_path / ".env"
    env_file.write_text(f"{canonical}=true\n")
    monkeypatch.setenv(old, "false")
    assert getattr(AppSettings(_env_file=env_file), canonical) is False


def test_constructor_override_beats_legacy_environment(flag_names, monkeypatch):
    """Programmatic opt-outs must retain priority over deployment settings."""
    canonical, old = flag_names
    monkeypatch.setenv(old, "true")
    assert getattr(AppSettings(_env_file=None, **{canonical: False}), canonical) is False


def test_runtime_flag_override_restores_the_loaded_value(flag_names, monkeypatch):
    """Temporary runtime overrides must restore the same single settings value."""
    canonical, old = flag_names
    settings = AppSettings(_env_file=None, **{old: False})
    monkeypatch.setattr(config_module, "config_instance", settings)
    with monkeypatch.context() as patch:
        patch.setattr(Config, canonical, True)
        assert getattr(Config, canonical) is True
    assert getattr(Config, canonical) is False
