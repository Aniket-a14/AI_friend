"""Before this, the healthcheck hardcoded output/sample_en_gold.wav and
always attempted real synthesis -- a missing reference clip made every check
fail forever, and since voice_agent depends_on gpt-sovits: service_healthy,
the voice agent could never start at all (roadmap Phase 1's "the blocker,
precisely"). These tests run the real script against a fake curl so the
degrade-instead-of-hang behavior is verified without a live GPT-SoVITS."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "bootstrap" / "sovits_healthcheck.sh"
)

FAKE_CURL = """#!/bin/bash
# Records every invocation and fakes a response for /docs and /tts.
echo "$@" >> "$FAKE_CURL_LOG"
url=""
out=""
prev=""
for arg in "$@"; do
    if [ "$prev" = "-o" ]; then
        out="$arg"
    fi
    case "$arg" in
        http*) url="$arg" ;;
    esac
    prev="$arg"
done
case "$url" in
    */docs)
        echo "DOCS" >> "$FAKE_CURL_LOG"
        exit 0
        ;;
    */tts)
        if [ "$out" != "" ] && [ "$out" != "/dev/null" ]; then
            printf '%s' "$FAKE_CURL_TTS_BODY" > "$out"
        fi
        exit 0
        ;;
esac
exit 1
"""


@pytest.fixture
def fake_curl_bin(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl_path = bin_dir / "curl"
    curl_path.write_text(FAKE_CURL)
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _run(fake_curl_bin, sovits_root, tts_body="audio-bytes", extra_env=None):
    env = dict(os.environ)
    env["PATH"] = f"{fake_curl_bin}:{env['PATH']}"
    env["SOVITS_ROOT"] = str(sovits_root)
    env["FAKE_CURL_LOG"] = str(sovits_root / "curl.log")
    env["FAKE_CURL_TTS_BODY"] = tts_body
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=10, check=False
    )


def test_degrades_to_liveness_probe_when_clip_is_missing(tmp_path, fake_curl_bin):
    """Without this, a genuinely missing clip means the healthcheck can
    never pass, and voice_agent's service_healthy gate keeps it from ever
    starting -- the exact silent-startup-deadlock this fix targets."""
    result = _run(fake_curl_bin, sovits_root=tmp_path)

    assert result.returncode == 0
    log = (tmp_path / "curl.log").read_text()
    assert "/docs" in log
    assert "/tts" not in log


def test_attempts_real_synthesis_when_clip_is_present(tmp_path, fake_curl_bin):
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "sample_en_gold.wav").write_bytes(b"clip")

    result = _run(fake_curl_bin, sovits_root=tmp_path)

    assert result.returncode == 0
    log = (tmp_path / "curl.log").read_text()
    assert "/tts" in log
    assert "/docs" not in log


def test_fails_on_empty_synthesis_response_even_with_clip_present(tmp_path, fake_curl_bin):
    """A 200 with an empty body is still curl-successful -- GPT-SoVITS has
    open reports of returning blank audio under load. The degrade path must
    not accidentally swallow this real failure mode."""
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "sample_en_gold.wav").write_bytes(b"clip")

    result = _run(fake_curl_bin, sovits_root=tmp_path, tts_body="")

    assert result.returncode != 0


def test_respects_a_custom_ref_audio_path(tmp_path, fake_curl_bin):
    (tmp_path / "custom").mkdir()
    (tmp_path / "custom" / "my_voice.wav").write_bytes(b"clip")

    result = _run(
        fake_curl_bin,
        sovits_root=tmp_path,
        extra_env={"REF_AUDIO_PATH": "custom/my_voice.wav"},
    )

    assert result.returncode == 0
    log = (tmp_path / "curl.log").read_text()
    assert "/tts" in log
