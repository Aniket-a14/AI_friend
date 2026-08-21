"""
#113 (H2): `IdentityManager` used to default `base_path` to the package
directory itself, so `personality.json`/`history.json` -- both tracked in
git -- were both the shipped seed AND the runtime write target. Moving the
write default outside the repo means a brand-new install's write location has
nothing in it on the very first boot; without copying the shipped seed there
once, that silently boots an empty persona instead of the authored one. These
tests cover: the new default location, the copy-on-first-boot bootstrap, that
it only ever copies once, and that the test suite's own opt-out
(`IDENTITY_SEED_ON_FIRST_BOOT=false`, set in conftest.py) actually works.
"""

import json
import os

from app import config as config_module
from app.cognitive import identity as identity_module
from app.cognitive.identity import IdentityManager


def _package_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(identity_module.__file__)))


def test_default_write_path_is_outside_the_package_directory(monkeypatch):
    """The historical default resolved inside backend/app/ -- a git-tracked
    directory -- so save() dirtied a tracked file. Regressing to that default
    is exactly what #113 fixes."""
    monkeypatch.setattr(config_module.config_instance, "IDENTITY_BASE_PATH", None)
    monkeypatch.setattr(config_module.config_instance, "IDENTITY_SEED_ON_FIRST_BOOT", False)

    agent = IdentityManager(persona_file=None)

    assert os.path.dirname(agent.personality_path) != _package_dir()
    assert agent.personality_path == os.path.join(
        identity_module._DEFAULT_IDENTITY_STATE_DIR, "personality.json"
    )
    assert agent.history_path == os.path.join(
        identity_module._DEFAULT_IDENTITY_STATE_DIR, "history.json"
    )


def test_fresh_write_location_is_seeded_from_shipped_defaults(monkeypatch, tmp_path):
    """A write directory with nothing in it yet must pick up the shipped seed,
    not boot an empty persona. If copy-on-first-boot regresses, this fails
    because the write-target file never appears."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    write_dir = tmp_path / "write"

    seed_personality_path = seed_dir / "personality.json"
    seed_history_path = seed_dir / "history.json"
    seed_personality = {"name": "Seeded Friend"}
    seed_history = {"relationship": "Old Friend", "memories": ["a shared memory"]}
    seed_personality_path.write_text(json.dumps(seed_personality), encoding="utf-8")
    seed_history_path.write_text(json.dumps(seed_history), encoding="utf-8")

    monkeypatch.setattr(config_module.config_instance, "IDENTITY_BASE_PATH", str(write_dir))
    monkeypatch.setattr(
        config_module.config_instance, "PERSONALITY_SEED_PATH", str(seed_personality_path)
    )
    monkeypatch.setattr(
        config_module.config_instance, "HISTORY_SEED_PATH", str(seed_history_path)
    )
    monkeypatch.setattr(config_module.config_instance, "IDENTITY_SEED_ON_FIRST_BOOT", True)

    IdentityManager(persona_file=None)

    written_personality = json.loads((write_dir / "personality.json").read_text(encoding="utf-8"))
    written_history = json.loads((write_dir / "history.json").read_text(encoding="utf-8"))
    assert written_personality == seed_personality
    assert written_history["relationship"] == "Old Friend"
    assert "a shared memory" in written_history["memories"]


def test_seed_copy_never_overwrites_an_existing_write_target(monkeypatch, tmp_path):
    """Copy-on-first-boot must be a one-time bootstrap. If a mutation makes it
    re-copy on every construction, a friend's own accumulated state gets
    clobbered back to the shipped seed on every restart."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    write_dir = tmp_path / "write"
    write_dir.mkdir()

    seed_personality_path = seed_dir / "personality.json"
    seed_personality_path.write_text(json.dumps({"name": "Seeded Friend"}), encoding="utf-8")
    seed_history_path = seed_dir / "history.json"
    seed_history_path.write_text(json.dumps({"relationship": "Old Friend"}), encoding="utf-8")

    # The write target already exists with the agent's own lived-in state.
    (write_dir / "personality.json").write_text(
        json.dumps({"name": "Lived-In Friend"}), encoding="utf-8"
    )
    (write_dir / "history.json").write_text(
        json.dumps({"relationship": "Best Friend", "memories": []}), encoding="utf-8"
    )

    monkeypatch.setattr(config_module.config_instance, "IDENTITY_BASE_PATH", str(write_dir))
    monkeypatch.setattr(
        config_module.config_instance, "PERSONALITY_SEED_PATH", str(seed_personality_path)
    )
    monkeypatch.setattr(
        config_module.config_instance, "HISTORY_SEED_PATH", str(seed_history_path)
    )
    monkeypatch.setattr(config_module.config_instance, "IDENTITY_SEED_ON_FIRST_BOOT", True)

    agent = IdentityManager(persona_file=None)

    assert agent.personality["name"] == "Lived-In Friend"
    assert agent.history["relationship"] == "Best Friend"


def test_disabling_seed_on_first_boot_leaves_a_fresh_location_empty(monkeypatch, tmp_path):
    """Pins the exact opt-out conftest.py relies on for the whole suite's
    isolation: with the flag off, a fresh write directory must stay genuinely
    empty even though a shipped seed exists right next to it."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    write_dir = tmp_path / "write"

    seed_personality_path = seed_dir / "personality.json"
    seed_personality_path.write_text(json.dumps({"name": "Seeded Friend"}), encoding="utf-8")
    seed_history_path = seed_dir / "history.json"
    seed_history_path.write_text(json.dumps({"relationship": "Old Friend"}), encoding="utf-8")

    monkeypatch.setattr(config_module.config_instance, "IDENTITY_BASE_PATH", str(write_dir))
    monkeypatch.setattr(
        config_module.config_instance, "PERSONALITY_SEED_PATH", str(seed_personality_path)
    )
    monkeypatch.setattr(
        config_module.config_instance, "HISTORY_SEED_PATH", str(seed_history_path)
    )
    monkeypatch.setattr(config_module.config_instance, "IDENTITY_SEED_ON_FIRST_BOOT", False)

    IdentityManager(persona_file=None)

    assert not (write_dir / "personality.json").exists()
    assert not (write_dir / "history.json").exists()
