"""
P1-2: both core streams were declared with `name` and `subjects` only,
inheriting JetStream's defaults -- limits retention, file storage, and
UNLIMITED count/bytes/age. NATS' own docs warn that "an unbounded stream
will eventually fill the disk", and AI_AUDIO binds `audio.>`, which carries
raw PCM (ESTIMATED ~130 KB/s; actual growth NOT TESTED).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from nats.js.api import StorageType

from app.nats_streams import (
    CORE_STREAMS,
    STREAM_POLICIES,
    _apply_policy_to_existing,
    build_stream_config,
)


def test_every_core_stream_declares_a_retention_policy():
    """Structural, so a stream added later cannot quietly ship unbounded --
    which is exactly how both current streams got that way: NATS permits a
    two-field declaration, so nobody was ever forced to decide."""
    for name in CORE_STREAMS:
        assert name in STREAM_POLICIES, f"{name} has no retention policy"


@pytest.mark.parametrize("stream_name", sorted(CORE_STREAMS))
def test_every_stream_config_names_storage_retention_and_a_limit(stream_name):
    """The three fields whose absence is the defect. A stream with retention
    set but no limit is still unbounded."""
    config = build_stream_config(stream_name, list(CORE_STREAMS[stream_name]))

    assert config.retention is not None
    assert config.storage is not None
    assert config.max_age and config.max_age > 0
    assert config.max_bytes and config.max_bytes > 0


def test_audio_stream_is_not_file_backed():
    """Raw PCM must not be durably written to disk: it is worthless once the
    utterance is transcribed, and a durable write sits directly in the audio
    hot path. This is the single most load-bearing assertion in the file."""
    config = build_stream_config("AI_AUDIO", ["audio.>"])

    assert config.storage == StorageType.MEMORY


def test_conversational_stream_is_file_backed():
    """The inverse guard: conversation must survive a restart, so the
    bounded-storage decision must not be applied to the wrong tier."""
    config = build_stream_config("AI_MESSAGES", ["chat.>"])

    assert config.storage == StorageType.FILE


def test_audio_is_aged_out_far_sooner_than_conversation():
    """The tiers exist because the data classes differ. If these ever
    converge, one of them is wrong -- either PCM is being kept for days or
    conversation is being discarded in minutes."""
    audio = build_stream_config("AI_AUDIO", ["audio.>"])
    messages = build_stream_config("AI_MESSAGES", ["chat.>"])

    assert audio.max_age < messages.max_age


def test_unknown_stream_degrades_to_subjects_only():
    """A stream with no policy entry must not inherit limits meant for
    something else -- it should behave exactly as it did before P1-2."""
    config = build_stream_config("SOME_OTHER_STREAM", ["other.>"])

    assert config.subjects == ["other.>"]
    assert config.max_age is None


def test_existing_stream_has_its_limits_brought_up_to_policy():
    """Every deployment that has run before already has unbounded streams.
    If only stream *creation* carried the policy, the fix would apply to
    brand-new meshes and nowhere else, while still logging success."""
    config = MagicMock()
    config.max_age = None
    config.max_bytes = -1
    config.storage = StorageType.FILE

    changed = _apply_policy_to_existing(config, "AI_MESSAGES")

    assert changed is True
    assert config.max_age == STREAM_POLICIES["AI_MESSAGES"]["max_age"]
    assert config.max_bytes == STREAM_POLICIES["AI_MESSAGES"]["max_bytes"]


def test_already_compliant_stream_reports_no_change():
    """Avoids issuing a pointless update_stream on every agent start."""
    policy = STREAM_POLICIES["AI_MESSAGES"]
    config = MagicMock()
    config.max_age = policy["max_age"]
    config.max_bytes = policy["max_bytes"]
    config.storage = StorageType.FILE

    assert _apply_policy_to_existing(config, "AI_MESSAGES") is False


@pytest.mark.asyncio
async def test_both_creation_paths_declare_the_same_config():
    """THE test for this item. There are two stream-creation paths --
    nats_streams.setup_streams() and BaseAgent._bootstrap_mesh(), the latter
    running on every agent start and usually reaching a fresh mesh first. If
    they disagree, whichever runs first silently decides the policy. They
    must be built from one definition."""
    from app.agents.base import BaseAgent

    agent = object.__new__(BaseAgent)
    agent.name = "test_agent"

    jsm = MagicMock()
    jsm.add_stream = AsyncMock()
    nc = MagicMock()
    nc.jsm = MagicMock(return_value=jsm)
    agent.nc = nc

    await agent._bootstrap_mesh()

    from_agent = {
        c.kwargs["config"].name: c.kwargs["config"] for c in jsm.add_stream.await_args_list
    }
    assert set(from_agent) == set(CORE_STREAMS)

    for name, subjects in CORE_STREAMS.items():
        expected = build_stream_config(name, list(subjects))
        actual = from_agent[name]
        assert actual.storage == expected.storage, name
        assert actual.max_age == expected.max_age, name
        assert actual.max_bytes == expected.max_bytes, name
        assert actual.retention == expected.retention, name
