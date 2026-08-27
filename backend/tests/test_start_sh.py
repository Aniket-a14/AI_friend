"""start.sh (roadmap Phase 1.6) is meant to refuse to half-boot rather than
leave some containers up and others crash-looping with no obvious cause.
These tests run a copy of the real script -- it cd's to its own directory
via BASH_SOURCE, so copying it into an isolated tmp dir sandboxes every
check that follows (.env, Docker, Ollama) without touching the real repo's
.env or a live Docker daemon.

Every external command the script can call (docker, curl, ollama, npx) is
faked by default so that verifying a guard clause -- including by
deliberately breaking one, as mutation testing does -- can never fall
through to a real Docker daemon or a real `ollama pull` on the machine
running the tests, even when the guard itself is what's under test."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
START_SH = REPO_ROOT / "start.sh"

# Sane, successful-by-default fakes -- individual tests override just the
# one binary whose failure they're exercising.
DEFAULT_FAKE_BINS = {
    "docker": "exit 0",
    "curl": "exit 0",
    "ollama": 'echo "NAME"\necho "llama3.2:3b"\necho "nomic-embed-text:latest"\nexit 0',
    "npx": "exit 0",
}


def _write_fake_bin(bin_dir: Path, name: str, body: str):
    path = bin_dir / name
    path.write_text(f"#!/bin/bash\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def sandbox(tmp_path):
    """A tmp dir containing a copy of start.sh plus a bin/ of fake external
    commands (all succeeding by default) on PATH ahead of the real ones."""
    dest = tmp_path / "start.sh"
    shutil.copyfile(START_SH, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in DEFAULT_FAKE_BINS.items():
        _write_fake_bin(bin_dir, name, body)

    return tmp_path


def _run(sandbox, args=(), overrides=None):
    """Runs the sandboxed start.sh. `overrides` replaces one or more of the
    default fake binaries' bodies (e.g. {"curl": "exit 1"})."""
    bin_dir = sandbox / "bin"
    for name, body in (overrides or {}).items():
        _write_fake_bin(bin_dir, name, body)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(sandbox / "start.sh"), *args],
        cwd=sandbox,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_rejects_an_unrecognized_mode_before_touching_anything(sandbox):
    """Argument validation runs before the .env/Docker/Ollama checks, so an
    invalid mode must fail immediately without those side effects."""
    result = _run(sandbox, args=["not-a-real-mode"])

    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_refuses_to_start_without_a_dot_env_file(sandbox):
    """Asserts the specific guard-clause message, not just any mention of
    ".env" -- `source .env` failing on a genuinely missing file also
    produces a stderr line containing ".env", which would let this test
    pass even if the explicit check above it were deleted entirely."""
    result = _run(sandbox)

    assert result.returncode == 1
    assert "ERROR: .env not found" in result.stderr


def test_refuses_to_start_when_docker_is_not_running(sandbox):
    (sandbox / ".env").write_text("POSTGRES_PASSWORD=test\n")

    result = _run(sandbox, overrides={"docker": "exit 1"})

    assert result.returncode == 1
    assert "ERROR: Docker does not appear to be running" in result.stderr


def test_refuses_to_start_when_ollama_is_unreachable(sandbox):
    (sandbox / ".env").write_text("POSTGRES_PASSWORD=test\n")

    result = _run(sandbox, overrides={"curl": "exit 1"})

    assert result.returncode == 1
    assert "ERROR: Ollama is not reachable" in result.stderr


# `ollama list` names models with a tag suffix (nomic-embed-text:latest); a
# required model given bare (nomic-embed-text, the documented default) must
# be recognized as already present, not re-pulled every single run.
_FAKE_OLLAMA_WITH_TAGGED_MODELS = (
    'if [ "$1" = "list" ]; then\n'
    '    echo "NAME"\n'
    '    echo "llama3.2:3b"\n'
    '    echo "nomic-embed-text:latest"\n'
    "    exit 0\n"
    'elif [ "$1" = "pull" ]; then\n'
    '    touch "$PULL_MARKER_DIR/pulled_$2"\n'
    "    exit 0\n"
    "fi\n"
)


def test_does_not_repull_a_model_only_differing_by_a_latest_tag(sandbox):
    (sandbox / ".env").write_text("POSTGRES_PASSWORD=test\n")
    marker_dir = sandbox / "markers"
    marker_dir.mkdir()

    result = _run(
        sandbox,
        overrides={
            "ollama": f'PULL_MARKER_DIR="{marker_dir}"\n' + _FAKE_OLLAMA_WITH_TAGGED_MODELS
        },
    )

    assert not (marker_dir / "pulled_nomic-embed-text").exists()
    assert not (marker_dir / "pulled_llama3.2:3b").exists()
    # The script fails later in the sandbox (no real backend/ dir to run
    # ensure_default_voice_sample.py against) -- irrelevant here, since the
    # model loop above runs and completes before that point either way.
    assert result.returncode != 0


def test_pulls_a_model_that_is_genuinely_absent(sandbox):
    (sandbox / ".env").write_text(
        "POSTGRES_PASSWORD=test\nOLLAMA_REQUIRED_MODELS=totally-fake-model\n"
    )
    marker_dir = sandbox / "markers"
    marker_dir.mkdir()

    _run(
        sandbox,
        overrides={
            "ollama": f'PULL_MARKER_DIR="{marker_dir}"\n' + _FAKE_OLLAMA_WITH_TAGGED_MODELS
        },
    )

    assert (marker_dir / "pulled_totally-fake-model").exists()
