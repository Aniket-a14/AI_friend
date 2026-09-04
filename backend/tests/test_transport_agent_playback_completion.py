"""FIX-CLD-02 (`orchestration/PHASE_01/FIX_PLAN.md` Part B): the normal
(non-interrupted) playback path never published a terminal
`AudioPlaybackProgress(completed=True, ...)` event -- only a confirmed
`audio.stop` interruption produced any terminal signal at all. Without it,
`BrainAgent._on_audio_playback_progress` (Phase 1 causal slice, §22/§38)
never saw `progress.completed` for a turn that simply finished speaking, so
it never emitted a COMPLETED `OutcomeRecord` for the common case.

These tests cover the fix at both ends: the producer side (`_on_nats_audio`
queuing a completion marker behind whatever real audio its own message
carried) and the consumer side (`_audio_playback_worker` only reporting
completion once every real frame ahead of the marker has actually reached
`audio_source.capture_frame` -- the closest observable "reached the
speaker" point in this architecture, per `_maybe_publish_playback_progress`'s
own docstring).
"""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.transport_agent import TransportAgent
from app.contracts import Topics


def _make_agent(queue_size: int = 8) -> TransportAgent:
    with patch("app.agents.transport_agent.Config") as mock_config:
        mock_config.NATS_URL = "nats://127.0.0.1:4222"
        mock_config.LIVEKIT_URL = "ws://127.0.0.1:7880"
        mock_config.LIVEKIT_API_KEY = "k"
        mock_config.LIVEKIT_API_SECRET = "s"
        mock_config.SAMPLE_RATE = 16000
        mock_config.TRANSPORT_AUDIO_QUEUE_SIZE = queue_size
        agent = TransportAgent()
    agent.publish = AsyncMock()
    return agent


def _stream_chunk(pcm: bytes, *, done: bool) -> dict:
    return {
        "audio": base64.b64encode(pcm).decode("ascii") if pcm else "",
        "done": done,
        "sample_rate": 16000,
        "channels": 1,
    }


def _metadata(turn_id="turn-1", character_offset=None, word_index=None) -> dict:
    meta: dict = {"turn_id": turn_id}
    if character_offset is not None:
        meta["character_offset"] = character_offset
    if word_index is not None:
        meta["word_index"] = word_index
    return meta


# --- Producer side: _on_nats_audio enqueues a completion marker ------------


@pytest.mark.asyncio
async def test_on_nats_audio_queues_a_completion_marker_behind_the_final_frame():
    """The marker must land strictly after the real PCM this same message
    carried, so a worker draining the queue FIFO never reports completion
    before that audio has actually been fed to the audio source."""
    agent = _make_agent()

    await agent._on_nats_audio(
        _stream_chunk(b"\x00\x00" * 4, done=True),
        metadata=_metadata(character_offset=42, word_index=7),
    )

    assert agent.audio_queue.qsize() == 2
    real_frame = agent.audio_queue.get_nowait()
    marker = agent.audio_queue.get_nowait()

    assert real_frame[0] == b"\x00\x00" * 4
    assert real_frame[3] == "turn-1"
    assert real_frame[6] is False  # not a completion marker

    assert marker[0] == b""  # no audio of its own
    assert marker[3] == "turn-1"
    assert marker[4] == 42
    assert marker[5] == 7
    assert marker[6] is True


@pytest.mark.asyncio
async def test_on_nats_audio_done_with_no_audio_still_queues_a_marker():
    """A bodiless trailer message (no PCM, just the done flag) must still
    produce a completion marker -- otherwise a stream whose very last
    message carries no audio of its own would never signal completion."""
    agent = _make_agent()

    await agent._on_nats_audio(
        _stream_chunk(b"", done=True),
        metadata=_metadata(character_offset=10, word_index=2),
    )

    assert agent.audio_queue.qsize() == 1
    marker = agent.audio_queue.get_nowait()
    assert marker[0] == b""
    assert marker[6] is True


@pytest.mark.asyncio
async def test_on_nats_audio_without_done_never_queues_a_marker():
    """The common per-chunk case (more audio still to come) must not emit a
    marker -- only the message actually flagged `done` does."""
    agent = _make_agent()

    await agent._on_nats_audio(
        _stream_chunk(b"\x00\x00" * 4, done=False), metadata=_metadata()
    )

    assert agent.audio_queue.qsize() == 1
    frame = agent.audio_queue.get_nowait()
    assert frame[6] is False


# --- Consumer side: the drain worker reports completion in FIFO order -----


@pytest.mark.asyncio
async def test_playback_worker_publishes_completed_progress_after_draining_real_frames():
    """Proves ordering, not just eventual publication: the real frame must
    reach `audio_source.capture_frame` before the completion event is
    published, and the completion payload must carry the marker's own
    offset/word_index -- not the real frame's."""
    agent = _make_agent()
    agent.audio_source = SimpleNamespace(capture_frame=AsyncMock())

    await agent.audio_queue.put((b"\x00\x00" * 8, 16000, 1, "turn-1", 5, 1, False))
    await agent.audio_queue.put((b"", 16000, 1, "turn-1", 20, 4, True))

    worker = asyncio.create_task(agent._audio_playback_worker())
    try:
        await asyncio.wait_for(agent.audio_queue.join(), timeout=2.0)
        await asyncio.sleep(0)  # let the spawned publish task(s) run
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

    agent.audio_source.capture_frame.assert_awaited_once()

    progress_calls = [
        call
        for call in agent.publish.await_args_list
        if call.args[0] == Topics.AUDIO_PLAYBACK_PROGRESS
    ]
    assert len(progress_calls) == 2
    real_payload, completed_payload = (call.args[1] for call in progress_calls)
    assert real_payload["completed"] is False
    assert real_payload["character_offset"] == 5
    assert completed_payload["completed"] is True
    assert completed_payload["character_offset"] == 20
    assert completed_payload["word_index"] == 4
    assert completed_payload["utterance_id"] == "turn-1"


@pytest.mark.asyncio
async def test_playback_worker_skips_audio_capture_for_a_marker_frame():
    """A marker carries empty PCM by design -- the worker must not attempt
    to feed it to `audio_source.capture_frame` at all (that call would be
    meaningless for zero-length audio and is reserved for real frames)."""
    agent = _make_agent()
    agent.audio_source = SimpleNamespace(capture_frame=AsyncMock())

    await agent.audio_queue.put((b"", 16000, 1, "turn-1", 0, 0, True))

    worker = asyncio.create_task(agent._audio_playback_worker())
    try:
        await asyncio.wait_for(agent.audio_queue.join(), timeout=2.0)
        await asyncio.sleep(0)
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

    agent.audio_source.capture_frame.assert_not_awaited()


# --- _maybe_publish_playback_progress unit behavior -------------------------


@pytest.mark.asyncio
async def test_completed_progress_bypasses_the_offset_dedupe_gate():
    """The non-completed de-dupe gate (skip a repeated/lower offset) exists
    to collapse several PCM chunks sharing one unchanged mid-utterance
    offset -- it must not also swallow the one completion event, even when
    its offset does not exceed the last one already reported."""
    agent = _make_agent()
    agent._last_progress_turn_id = "turn-1"
    agent._last_progress_offset = 50  # already past the completion's own offset

    agent._maybe_publish_playback_progress("turn-1", 30, 6, completed=True)
    await asyncio.sleep(0)

    agent.publish.assert_awaited_once()
    payload = agent.publish.await_args.args[1]
    assert payload["completed"] is True
    assert payload["character_offset"] == 30


@pytest.mark.asyncio
async def test_completed_progress_with_no_offset_falls_back_to_last_known():
    """A bodiless completion marker (no offset of its own) must still
    publish, using the last real offset this turn already reported --
    exactly the length actually delivered -- rather than being dropped."""
    agent = _make_agent()
    agent._last_progress_turn_id = "turn-1"
    agent._last_progress_offset = 17

    agent._maybe_publish_playback_progress("turn-1", None, None, completed=True)
    await asyncio.sleep(0)

    agent.publish.assert_awaited_once()
    payload = agent.publish.await_args.args[1]
    assert payload["completed"] is True
    assert payload["character_offset"] == 17
    assert payload["word_index"] == 0


@pytest.mark.asyncio
async def test_non_completed_progress_with_no_offset_still_does_nothing():
    """Companion to the fallback test above: only `completed=True` gets the
    fallback -- an ordinary mid-utterance frame with no offset metadata must
    stay a no-op, matching the pre-fix behavior for that path."""
    agent = _make_agent()

    agent._maybe_publish_playback_progress("turn-1", None, None, completed=False)
    await asyncio.sleep(0)

    agent.publish.assert_not_awaited()
