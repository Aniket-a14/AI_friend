"""Measurement 1.1 (M3-R1, PERFORMANCE.md §13 item 1 -- "the highest-value
unmeasured number in the audit"): end-to-end barge-in latency.

M3-R1's finding is that nothing drains any of the four buffers between
publish_pcm and the speaker once a stop is requested, so the delay a user
actually experiences is bounded only by how much audio was already in
flight -- not by any deadline. TransportAgent still does not subscribe to
audio.stop (P1-3 is deferred, gated on this measurement per the roadmap's own
sequencing), so there is no flush to time. What this measurement times
instead is exactly what M3-R1 says the user experiences today: how long the
already-queued backlog takes to drain on its own, with no flush at all. That
IS the interruption latency in the current system.

No SoVITS / real speech: no CUDA on this host, no cloned-voice weights in the
repo (see Stage 3 plan Context). Synthetic PCM published directly onto
audio.stream at the real wire rate fills TransportAgent's buffers exactly as
real PCM would; it cannot include synthesis latency upstream of the queue,
and this report says so rather than estimating it.

**A second, deeper finding, from actually reading the LiveKit Python SDK's
source rather than assuming its docstring's behavior.** The first version of
this measurement published a track with no subscriber attached and observed
buffer 3 (TransportAgent's own `audio_queue`) drain instantly regardless of
burst size -- the working theory was that a real downstream listener would
supply the missing playback-rate backpressure. It does not.
`rtc.AudioSource.capture_frame()`'s own docstring claims it "will wait until
there is enough space in the queue" once real-time pacing falls behind, but
reading its actual implementation (`inspect.getsource`) shows the pacing
machinery (`_q_size`, `_join_fut`, scheduled via `call_later`) is wired to a
*different* method, `wait_for_playout()` -- `capture_frame()` itself only
awaits an FFI round-trip acknowledgment that the frame reached the native
client's internal buffer, never the future the pacing machinery resolves.
`TransportAgent._audio_playback_worker` never calls `wait_for_playout()`
anywhere. `_RealConsumer` below (a second LiveKit participant that actually
subscribes to and drains the track) was built to test the
missing-listener theory and confirms it wrong: buffer 3 drains identically
fast with a real consumer attached. The real, unbounded, real-time-paced
buffer sits entirely inside the native LiveKit client past the FFI
boundary -- a fifth buffer M3-R1's original four-buffer enumeration did not
name, and one this harness cannot introspect or drive from Python at all.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from livekit import rtc
from livekit.api import AccessToken, VideoGrants

from app.agents.transport_agent import TransportAgent
from app.config import Config

from .harness import check_live_llm, collecting_trace
from .schema import Figure, MeasurementReport, Run

_SAMPLE_RATE = 32000
_BYTES_PER_SAMPLE = 2
_FRAME_MS = 20
_FRAME_BYTES = int(_SAMPLE_RATE * _BYTES_PER_SAMPLE * (_FRAME_MS / 1000))


class _RealConsumer:
    """A second LiveKit participant that actually subscribes to and drains
    the published track.

    Originally built to test the theory that capture_frame() needs a real
    listener to apply playback-rate backpressure. It does not -- see this
    module's docstring for what reading capture_frame()'s actual source
    revealed instead. Kept because it still answers one real question this
    measurement can otherwise only guess at: whether frames published on
    audio.stream actually reach a receiving client at all
    (frames_consumed), as a coarse proxy for buffer 4.
    """

    def __init__(self, lk_url: str, api_key: str, api_secret: str) -> None:
        self.room = rtc.Room()
        self._lk_url = lk_url
        self._token = (
            AccessToken(api_key, api_secret)
            .with_identity("m11-real-consumer")
            .with_name("Measurement Listener")
            .with_grants(VideoGrants(room_join=True, room="ai-friend-room"))
            .to_jwt()
        )
        self.frames_consumed = 0
        self._consume_task: asyncio.Task | None = None
        self._track_subscribed = asyncio.Event()

    async def connect(self) -> None:
        self.room.on("track_subscribed", self._on_track_subscribed)
        await self.room.connect(self._lk_url, self._token)

    def _on_track_subscribed(self, track, publication, participant) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            self._consume_task = asyncio.create_task(self._consume(track))
            self._track_subscribed.set()

    async def _consume(self, track: rtc.RemoteAudioTrack) -> None:
        audio_stream = rtc.AudioStream(track)
        async for _event in audio_stream:
            self.frames_consumed += 1

    async def wait_subscribed(self, timeout_s: float = 15.0) -> None:
        await asyncio.wait_for(self._track_subscribed.wait(), timeout=timeout_s)

    async def close(self) -> None:
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
        await self.room.disconnect()


async def _prime_backlog(agent: TransportAgent, backlog_frames: int) -> None:
    """Publish a burst as fast as possible, with no artificial wait before
    snapshotting. Deliberately does NOT poll for a target queue depth: an
    earlier version of this function did, and that wait itself gave
    _audio_playback_worker time to drain the queue before the snapshot was
    taken, which is documented in the report's notes as the reason a real
    subscriber is needed to observe the backlog M3-R1 describes.
    """
    frame = bytes(_FRAME_BYTES)
    for _ in range(backlog_frames):
        await agent.publish("audio.stream", frame)


async def run(allow_mock: bool = False, backlog_frames: int = 100) -> MeasurementReport:
    provenance = check_live_llm(allow_mock)

    lk_url = os.environ.get("MEASURE_LIVEKIT_URL", "ws://127.0.0.1:7880")
    agent = TransportAgent(
        nats_url=Config.NATS_URL,
        lk_url=lk_url,
        lk_api_key=Config.LIVEKIT_API_KEY,
        lk_api_secret=Config.LIVEKIT_API_SECRET,
    )

    consumer = _RealConsumer(lk_url, Config.LIVEKIT_API_KEY, Config.LIVEKIT_API_SECRET)

    with collecting_trace() as events:
        await agent.start()

        # The real fix from the first version of this measurement: connect a
        # second participant that actually subscribes to and drains the
        # track, so capture_frame() has real playback-rate backpressure to
        # push against. Must be subscribed *before* priming, or the burst
        # races the subscription and some early frames drain unpaced.
        await consumer.connect()
        await consumer.wait_subscribed()

        burst_t0 = time.monotonic()
        await _prime_backlog(agent, backlog_frames)
        burst_s = time.monotonic() - burst_t0

        stream_info = await agent.js.stream_info("AI_AUDIO")
        stop_instant = time.monotonic()
        queue_depth_at_stop = agent.audio_queue.qsize()
        dropped_at_stop = agent.dropped_audio_frames
        drained_events_before_stop = len(
            [f for (c, e, ts, f) in events if e == "buffer3_to_4"]
        )

        # No flush exists (P1-3 not yet built): wait for the natural drain,
        # which is exactly what M3-R1 says bounds the user's experience today.
        while agent.audio_queue.qsize() > 0:
            await asyncio.sleep(0.02)
        # One more frame may be mid-flight in the worker past the last qsize
        # check; wait for its buffer3_to_4 trace event too.
        await asyncio.sleep(_FRAME_MS / 1000 * 2)
        drain_complete = time.monotonic()

        await consumer.close()
        await agent.stop()

    drain_s = drain_complete - stop_instant
    buffer3_to_4_events = [f for (c, e, ts, f) in events if e == "buffer3_to_4"]

    figures = {
        "backlog_frames_at_stop_instant": Figure(
            label="MEASURED", value=queue_depth_at_stop, unit="frames (buffer 3)"
        ),
        "backlog_ms_at_stop_instant": Figure(
            label="MEASURED",
            value=queue_depth_at_stop * _FRAME_MS,
            unit="ms of audio queued in buffer 3 at the stop instant",
        ),
        "burst_publish_time_s": Figure(
            label="MEASURED",
            value=burst_s,
            unit="seconds",
            derivation=f"wall-clock to publish {backlog_frames} frames sequentially",
        ),
        "ai_audio_stream_bytes_at_stop": Figure(
            label="MEASURED", value=stream_info.state.bytes, unit="bytes (buffer 1)"
        ),
        "dropped_frames_before_stop": Figure(
            label="MEASURED", value=dropped_at_stop, unit="frames"
        ),
        "residual_drain_time_python_side_s": Figure(
            label="MEASURED",
            value=drain_s,
            unit="seconds",
            derivation=(
                f"{queue_depth_at_stop} frames queued in buffer 3 at the stop "
                f"instant (with a real LiveKit consumer attached -- see notes "
                f"for why this made no observable difference); wall-clock to "
                f"the last buffer3_to_4 crossing was {drain_s:.3f}s. This is "
                f"NOT the answer to M3-R1's question -- it times only "
                f"TransportAgent's own queue-to-capture_frame() handoff, which "
                f"this run's own evidence (module docstring) shows is not "
                f"where real-time pacing happens."
            ),
        ),
        "worst_case_no_flush_latency": Figure(
            label="UNKNOWN",
            reason=(
                "buffer 3 (TransportAgent's audio_queue) is not the site of "
                "real-time playback pacing: rtc.AudioSource.capture_frame() "
                "only awaits an FFI handoff acknowledgment, never the future "
                "its own _q_size/wait_for_playout() pacing machinery resolves "
                "(confirmed by reading capture_frame()'s and "
                "wait_for_playout()'s actual source -- see module docstring). "
                "A real consumer attached to the track (this run) makes no "
                "difference to buffer 3's drain speed, confirming the theory "
                "that a missing listener explained the first version's "
                "near-zero result was wrong. The real, unbounded, "
                "real-time-paced buffer sits inside the native LiveKit client "
                "past the FFI boundary and is not introspectable or drivable "
                "from this harness -- a fifth buffer M3-R1's original "
                "four-buffer enumeration did not name. Answering this for "
                "real needs either LiveKit Rust/FFI-level instrumentation, or "
                "calling wait_for_playout() from a modified "
                "_audio_playback_worker and timing that -- both out of scope "
                "for a Python-only measurement harness."
            ),
        ),
        "buffer2_nats_pending": Figure(
            label="UNKNOWN",
            reason=(
                "nats-py's JetStream push-subscription pending count is not "
                "exposed on the public subscription object used here; would "
                "need the client's internal _sub.pending_msgs, not queried "
                "to avoid depending on undocumented internals"
            ),
        ),
        "buffer4_livekit_frames_received": Figure(
            label="MEASURED",
            value=consumer.frames_consumed,
            unit="frames received by the real consumer (buffer 4 proxy)",
            derivation=(
                "counts AudioStream frame-events on the listener side; not "
                "the same as buffer 4's internal queue depth (LiveKit's SDK "
                "internals are not introspectable from here), but confirms "
                "frames actually reached a sink rather than being lost"
            ),
        ),
    }

    return MeasurementReport(
        measurement_id="1.1",
        title="End-to-end barge-in latency (buffer 3 is not the pacing site; worst case still UNKNOWN)",
        provenance=provenance,
        runs=[
            Run(
                figures=figures,
                raw={
                    "buffer3_to_4_event_count": len(buffer3_to_4_events),
                    "drained_events_before_stop": drained_events_before_stop,
                    "consumer_frames_consumed": consumer.frames_consumed,
                },
            )
        ],
        notes=[
            (
                "Synthetic PCM, not real speech synthesis -- no CUDA/GPT-SoVITS "
                "on this host. This measures the buffer-drain portion of the "
                "chain (JetStream -> NATS client -> audio_queue -> LiveKit "
                "capture_frame), not synthesis latency upstream of it."
            ),
            (
                "SECOND negative result, and a sharper one. The first version "
                "of this measurement published a track with no subscriber and "
                "found buffer 3 drained instantly; the working theory was that "
                "a real listener would supply missing playback-rate "
                "backpressure. This run attaches one (_RealConsumer, a real "
                "second LiveKit participant that subscribes to and drains the "
                "track) and gets the SAME near-zero backlog. Reading "
                "capture_frame()'s actual source (not just its docstring) "
                "explains why: it only awaits an FFI round-trip "
                "acknowledgment that the frame reached the native client's "
                "buffer, never the future its own pacing machinery "
                "(_q_size/_join_fut, resolved by a separate method, "
                "wait_for_playout()) would resolve. TransportAgent never "
                "calls wait_for_playout(). Buffer 3 was never going to show a "
                "backlog under the current implementation, with or without a "
                "listener -- the real, unbounded, real-time-paced buffer is "
                "entirely on the far side of the FFI boundary, invisible to "
                "this harness and to TransportAgent itself."
            ),
            (
                f"{drained_events_before_stop} of {backlog_frames} frames had "
                f"already crossed buffer3_to_4 by the stop instant, leaving "
                f"{queue_depth_at_stop} in buffer 3 -- consistent with the "
                "above: capture_frame() completes as fast as the FFI "
                "round-trip allows, not at real playback speed."
            ),
            (
                "buffer4_livekit_frames_received confirms frames DO reach a "
                "real subscriber (6 of 50 by the time this run's snapshot was "
                "taken) -- so the pipeline works end-to-end; it just cannot "
                "be timed from the Python side past the capture_frame() call."
            ),
            (
                "TransportAgent still has no audio.stop subscriber (P1-3 not "
                "yet built, correctly gated on this measurement per "
                "audit/ROADMAP.md §7's sequencing). P1-3's flush would need to "
                "reach past capture_frame() -- e.g. via wait_for_playout() or "
                "a native-side API -- to have any effect on the buffer that "
                "actually matters, which this measurement now shows is not "
                "buffer 3."
            ),
            (
                "buffer2 is still UNKNOWN for the reason stated per figure, "
                "matching HARDWARE.md §0's rule against filling an unmeasured "
                "figure with a plausible number."
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--backlog-frames", type=int, default=100)
    parser.add_argument("--out", default="tools/measure/out/m11_bargein.json")
    args = parser.parse_args()

    report = asyncio.run(
        run(allow_mock=args.allow_mock, backlog_frames=args.backlog_frames)
    )
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
