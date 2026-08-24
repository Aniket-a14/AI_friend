"""
P2-1 (opt-in): proves `nats-accounts.conf` actually enforces the
per-agent permissions it declares, against a real `nats-server` -- not just
that the config file parses. Per the roadmap's own words: "A test asserts
the scoping actually denies a subject outside an agent's grant; without
that, the accounts file is decoration."

Needs a real `nats-server` binary on PATH (`brew install nats-server` or
equivalent) and skips loudly without one, the same shape every other
live-infra test in this suite uses (see e.g. stt-agent's
`real_model_loads_and_perceives_audio`, voice-agent's
`publish_pcm_does_not_wait_for_the_jetstream_ack`).
"""

import asyncio
import importlib
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ACCOUNTS_CONF = REPO_ROOT / "nats-accounts.conf"

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None,
    reason="SKIP: no nats-server binary on PATH -- install it to run these "
    "(e.g. `brew install nats-server`)",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def real_nats():
    """`conftest.py` replaces `sys.modules["nats"]` (and every `nats.*`
    submodule) with an in-memory simulator for the whole suite, so ordinary
    unit tests never need live infra -- see its "HIGH-FIDELITY IN-MEMORY
    NATS SIMULATOR" section. These tests are the deliberate exception: they
    need the real `nats.py` client talking to a real `nats-server`, not the
    simulator. Swaps the fake out only for this fixture's lifetime and
    restores it in `finally`, so no other test in the session is affected
    regardless of run order.
    """
    fake_entries = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "nats" or name.startswith("nats.")
    }
    for name in fake_entries:
        del sys.modules[name]
    try:
        yield importlib.import_module("nats")
    finally:
        for name in [
            n for n in sys.modules if n == "nats" or n.startswith("nats.")
        ]:
            del sys.modules[name]
        sys.modules.update(fake_entries)


@pytest.fixture
def nats_accounts_server(tmp_path):
    """Boots a real nats-server from the actual shipped `nats-accounts.conf`,
    not a hand-rolled stand-in -- a passing test here means the file this
    repo actually ships enforces what it claims to, not a lookalike."""
    assert ACCOUNTS_CONF.exists(), f"expected {ACCOUNTS_CONF} to exist"
    port = _free_port()
    store_dir = tmp_path / "jetstream"
    proc = subprocess.Popen(
        [
            "nats-server",
            "-p", str(port),
            "-c", str(ACCOUNTS_CONF),
            "-sd", str(store_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            proc.kill()
            raise RuntimeError("nats-server did not open its port in time")
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _url(port: int, user: str, password: str) -> str:
    return f"nats://{user}:{password}@127.0.0.1:{port}"


async def _bootstrap_stream(nats_module, port: int) -> None:
    """Any one grant's `$JS.API.>` publish permission is enough to create
    the stream every business-subject publish below needs a responder for
    -- JetStream `publish()` is a request-reply that times out with no
    stream covering the subject, which is a different failure mode than a
    permissions violation and would make these tests fail for the wrong
    reason if skipped."""
    nc = await nats_module.connect(_url(port, "brain_agent", "changeme_brain_agent"))
    js = nc.jetstream()
    await js.add_stream(
        name="TEST_MESH",
        subjects=[
            "chat.output", "chat.input", "audio.stream", "vision.description",
            "vision.frames", "audio.stop", "state.broadcast", "cache.sync",
        ],
    )
    await nc.close()


@pytest.mark.asyncio
async def test_agent_can_publish_its_own_declared_subject(real_nats, nats_accounts_server):
    port = nats_accounts_server
    await _bootstrap_stream(real_nats, port)

    nc = await real_nats.connect(_url(port, "vision_agent", "changeme_vision_agent"))
    try:
        js = nc.jetstream()
        ack = await js.publish("vision.description", b"ok")
        assert ack.stream == "TEST_MESH"
    finally:
        await nc.close()


@pytest.mark.asyncio
async def test_agent_cannot_publish_a_subject_outside_its_grant(real_nats, nats_accounts_server):
    """The security property this whole file exists for: vision_agent must
    not be able to forge a chat.output message claiming to be the brain."""
    port = nats_accounts_server
    await _bootstrap_stream(real_nats, port)

    nc = await real_nats.connect(_url(port, "vision_agent", "changeme_vision_agent"))
    try:
        js = nc.jetstream()
        with pytest.raises((real_nats.errors.Error, TimeoutError)):
            await asyncio.wait_for(js.publish("chat.output", b"forged"), timeout=3.0)
    finally:
        await nc.close()


@pytest.mark.asyncio
async def test_agent_cannot_subscribe_a_subject_outside_its_grant(real_nats, nats_accounts_server):
    """transport_agent has no business need to see vision.description --
    confirm the denial actually fires (via error_cb; see the accounts file's
    own "KNOWN LIMITATION" note on why this doesn't raise synchronously)."""
    port = nats_accounts_server
    await _bootstrap_stream(real_nats, port)

    violations = []

    async def _on_error(exc):
        violations.append(str(exc))

    nc = await real_nats.connect(
        _url(port, "transport_agent", "changeme_transport_agent"),
        error_cb=_on_error,
    )
    try:
        await nc.subscribe("vision.description")
        await asyncio.sleep(0.3)
        assert violations, "expected a permissions violation for an out-of-grant subscribe"
        assert "vision.description" in violations[0]
    finally:
        await nc.close()


@pytest.mark.asyncio
async def test_agent_can_subscribe_its_own_declared_subject(real_nats, nats_accounts_server):
    port = nats_accounts_server
    await _bootstrap_stream(real_nats, port)

    violations = []

    async def _on_error(exc):
        violations.append(str(exc))

    nc = await real_nats.connect(
        _url(port, "transport_agent", "changeme_transport_agent"),
        error_cb=_on_error,
    )
    try:
        await nc.subscribe("audio.stream")
        await asyncio.sleep(0.2)
        assert violations == []
    finally:
        await nc.close()


@pytest.mark.asyncio
async def test_wrong_password_is_rejected(real_nats, nats_accounts_server):
    port = nats_accounts_server
    with pytest.raises((real_nats.errors.Error, TimeoutError)):
        await asyncio.wait_for(
            real_nats.connect(_url(port, "vision_agent", "not-the-real-password")),
            timeout=3.0,
        )


@pytest.mark.asyncio
async def test_every_agents_baseline_grants_can_administer_jetstream(real_nats, nats_accounts_server):
    """Every agent's `_bootstrap_mesh` (app/agents/base.py) calls
    `jsm.add_stream`/`reconcile_existing_stream` on every startup -- if any
    agent's `$JS.API.>` grant were missing or misspelled, that agent would
    fail to self-heal a fresh mesh, silently (see `_bootstrap_mesh`'s own
    broad except clauses)."""
    port = nats_accounts_server
    creds = [
        ("brain_agent", "changeme_brain_agent"),
        ("subconscious_agent", "changeme_subconscious_agent"),
        ("surfacing_agent", "changeme_surfacing_agent"),
        ("system_agent", "changeme_system_agent"),
        ("transport_agent", "changeme_transport_agent"),
        ("vision_agent", "changeme_vision_agent"),
        ("stt_agent", "changeme_stt_agent"),
        ("voice_agent", "changeme_voice_agent"),
    ]
    for user, password in creds:
        nc = await real_nats.connect(_url(port, user, password))
        try:
            js = nc.jetstream()
            await js.add_stream(
                name=f"SELFTEST_{user.upper()}", subjects=[f"selftest.{user}"]
            )
        finally:
            await nc.close()
