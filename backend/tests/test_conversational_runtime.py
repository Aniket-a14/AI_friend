"""
Bucket 3 (VOICE_REMEDIATION_PLAN.md): `conversational_runtime.py` had no
dedicated test file before this bucket, and nothing in the suite called
`monitor_stream_and_fill` -- the largest coverage gap the plan's audit
flagged. A live capture (2026-09-01) showed the filler fired on every single
turn, for three independent reasons this file covers:

  1. The elapsed-time check started its clock before the deliberate
     conversational pacing sleep (300-900ms), so the filler's own budget was
     already spent before generation even began.
  2. `VOICE_FILLER_MIN_INTERVAL_SECONDS` and `VOICE_FILLER_MAX_PLAYBACK_BACKLOG`
     were declared in config.py and referenced nowhere else in the codebase.
  3. The payload's leading `<hesitate>` token synthesizes its own fixed
     "Mm..." in a separate GPT-SoVITS call from the filler word that follows
     it, so a firing filler was actually two different filler sounds.

Item 1 (the pacing-contamination fix) lives in brain_agent.py, at the call
site that captures `generation_start_time` -- this file tests the runtime's
half: that its elapsed calculation is driven by whatever start time it is
given, and that the two dead rate-limits and the double-fire are now fixed
here.
"""

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock

import pytest

from app.config import Config
from app.contracts import Topics
from app.utils.conversational_runtime import FILLERS, ConversationalRuntime


async def _never_yields_content():
    """An async generator standing in for a cognitive turn that never
    produces its first token inside the test's window -- long enough for
    the filler timer to fire, short enough the test never actually waits
    for it in real time (see the `generation_start_time` trick below)."""
    await asyncio.sleep(100)
    yield {"type": "content", "text": "unreachable"}  # pragma: no cover


async def _yields_content_immediately():
    yield {"type": "content", "text": "hi"}


async def _drain(agen):
    async for _ in agen:
        pass


async def _run_never_yields(runtime: ConversationalRuntime, turn_id: str, **kwargs):
    """Drives monitor_stream_and_fill against a generator that never
    completes, giving the background filler timer a chance to fire (its
    sleep floors to 10ms once `generation_start_time` is already in the
    past), then cancels the consumer -- mirroring how a real barge-in or
    turn cancellation tears down an in-flight generation."""
    consumer = asyncio.create_task(
        _drain(
            runtime.monitor_stream_and_fill(
                _never_yields_content(), turn_id=turn_id, state_snap={}, **kwargs
            )
        )
    )
    await asyncio.sleep(0.05)
    consumer.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await consumer


@pytest.fixture(autouse=True)
def _fast_filler_threshold(monkeypatch):
    monkeypatch.setattr(Config, "VOICE_FILLER_THRESHOLD", 0.05)
    monkeypatch.setattr(Config, "VOICE_FILLER_MIN_INTERVAL_SECONDS", 1.5)
    monkeypatch.setattr(Config, "VOICE_FILLER_MAX_PLAYBACK_BACKLOG", 4)


def _long_past(seconds: float = 10.0) -> float:
    """A `generation_start_time` far enough in the past that elapsed time
    already exceeds any threshold used in these tests, so send_filler's own
    sleep floors to its 10ms minimum instead of the full threshold -- tests
    run fast regardless of what VOICE_FILLER_THRESHOLD is set to."""
    return time.time() - seconds


@pytest.mark.asyncio
async def test_filler_fires_once_when_generation_exceeds_threshold():
    runtime = ConversationalRuntime(publish_cb=AsyncMock())

    await _run_never_yields(
        runtime, "turn-1", generation_start_time=_long_past()
    )

    runtime.publish_cb.assert_awaited_once()
    topic, payload = runtime.publish_cb.await_args.args
    assert topic == Topics.CHAT_OUTPUT
    assert payload["content"].endswith("<pause=200ms>")
    spoken_word = payload["content"].removesuffix("<pause=200ms>")
    assert spoken_word in FILLERS


@pytest.mark.asyncio
async def test_filler_is_suppressed_when_content_arrives_before_threshold():
    runtime = ConversationalRuntime(publish_cb=AsyncMock())

    results = [
        item
        async for item in runtime.monitor_stream_and_fill(
            _yields_content_immediately(),
            turn_id="turn-1",
            state_snap={},
            generation_start_time=_long_past(),
        )
    ]
    await asyncio.sleep(0.05)  # let the already-cancelled filler task settle

    assert results == [{"type": "content", "text": "hi"}]
    runtime.publish_cb.assert_not_awaited()


@pytest.mark.asyncio
async def test_filler_is_suppressed_when_playback_backlog_is_at_or_above_max():
    """VOICE_FILLER_MAX_PLAYBACK_BACKLOG was designed and never wired
    anywhere in the codebase before this bucket -- a new turn's filler must
    not fire while a previous turn's audio is still backed up in
    transport_agent's outbound queue (see AudioPlaybackBacklog)."""
    runtime = ConversationalRuntime(publish_cb=AsyncMock())

    await _run_never_yields(
        runtime,
        "turn-1",
        generation_start_time=_long_past(),
        playback_backlog=Config.VOICE_FILLER_MAX_PLAYBACK_BACKLOG,
    )

    runtime.publish_cb.assert_not_awaited()


@pytest.mark.asyncio
async def test_filler_still_fires_when_playback_backlog_is_below_max():
    runtime = ConversationalRuntime(publish_cb=AsyncMock())

    await _run_never_yields(
        runtime,
        "turn-1",
        generation_start_time=_long_past(),
        playback_backlog=Config.VOICE_FILLER_MAX_PLAYBACK_BACKLOG - 1,
    )

    runtime.publish_cb.assert_awaited_once()


@pytest.mark.asyncio
async def test_filler_is_suppressed_within_min_interval_of_a_previous_fire(
    monkeypatch,
):
    """VOICE_FILLER_MIN_INTERVAL_SECONDS was designed and never wired
    anywhere in the codebase before this bucket -- back-to-back turns (a
    rejected barge-in, a self-correction retry) must not each get their own
    filler."""
    runtime = ConversationalRuntime(publish_cb=AsyncMock())
    monkeypatch.setattr(Config, "VOICE_FILLER_MIN_INTERVAL_SECONDS", 10.0)

    await _run_never_yields(runtime, "turn-1", generation_start_time=_long_past())
    assert runtime.publish_cb.await_count == 1

    await _run_never_yields(runtime, "turn-2", generation_start_time=_long_past())
    assert runtime.publish_cb.await_count == 1  # unchanged: still within 10s


@pytest.mark.asyncio
async def test_filler_fires_again_after_min_interval_elapses():
    runtime = ConversationalRuntime(publish_cb=AsyncMock())
    runtime._last_filler_fired_at = time.time() - 10.0  # long past MIN_INTERVAL

    await _run_never_yields(runtime, "turn-1", generation_start_time=_long_past())

    runtime.publish_cb.assert_awaited_once()


@pytest.mark.asyncio
async def test_elapsed_time_is_measured_from_generation_start_time_not_call_time():
    """Bucket 3's root cause: the elapsed-time check used to start its clock
    before the conversational pacing sleep, so a 496ms pacing delay alone
    already exceeded a 250ms threshold before generation began (confirmed in
    a live capture, 2026-09-01: the filler log line always landed within
    ~15ms of the pacing sleep ending, never any later). This pins the
    contract that determines the fix: a `generation_start_time` far in the
    future (as if generation had *just* started) must make the runtime wait
    out the real threshold, not fire immediately."""
    runtime = ConversationalRuntime(publish_cb=AsyncMock())

    consumer = asyncio.create_task(
        _drain(
            runtime.monitor_stream_and_fill(
                _never_yields_content(),
                turn_id="turn-1",
                state_snap={},
                generation_start_time=time.time(),  # "generation just started"
            )
        )
    )
    await asyncio.sleep(0.01)  # well under VOICE_FILLER_THRESHOLD (0.05s)
    consumer.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await consumer

    runtime.publish_cb.assert_not_awaited()
