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
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from app.agents.transport_agent import TransportAgent
from app.config import Config

from .harness import check_live_llm, collecting_trace
from .schema import Figure, MeasurementReport, Run

_SAMPLE_RATE = 32000
_BYTES_PER_SAMPLE = 2
_FRAME_MS = 20
_FRAME_BYTES = int(_SAMPLE_RATE * _BYTES_PER_SAMPLE * (_FRAME_MS / 1000))


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

    with collecting_trace() as events:
        await agent.start()
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

        await agent.stop()

    drain_s = drain_complete - stop_instant
    buffer3_to_4_events = [f for (c, e, ts, f) in events if e == "buffer3_to_4"]

    figures = {
        "backlog_frames_at_stop_instant": Figure(
            label="MEASURED", value=queue_depth_at_stop, unit="frames (buffer 3)"
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
        "residual_drain_time_s": Figure(
            label="MEASURED",
            value=drain_s,
            unit="seconds",
            derivation=(
                f"{queue_depth_at_stop} frames still queued at the stop "
                f"instant; wall-clock to the last buffer3_to_4 crossing was "
                f"{drain_s:.3f}s"
            ),
        ),
        "worst_case_no_flush_latency": Figure(
            label="UNKNOWN",
            reason=(
                "this run's queue_depth_at_stop is near zero (see notes): "
                "capture_frame() does not pace to real-time or apply "
                "backpressure without a connected subscriber actually "
                "consuming the published track, so no realistic backlog "
                "accumulated in buffer 3 for this harness to time a drain of "
                "-- M3-R1's worst-case scenario needs a real (or "
                "artificially paced) consumer on the other end, which this "
                "run does not attach"
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
        "buffer4_livekit_internal": Figure(
            label="UNKNOWN",
            reason=(
                "requires a receiving LiveKit client actually subscribed to "
                "the published track to observe sink-side buffering; this "
                "run publishes a track but attaches no subscriber"
            ),
        ),
    }

    return MeasurementReport(
        measurement_id="1.1",
        title="End-to-end barge-in latency (buffer-drain timing, synthetic PCM)",
        provenance=provenance,
        runs=[Run(figures=figures, raw={"buffer3_to_4_event_count": len(buffer3_to_4_events)})],
        notes=[
            (
                "Synthetic PCM, not real speech synthesis -- no CUDA/GPT-SoVITS "
                "on this host. This measures the buffer-drain portion of the "
                "chain (JetStream -> NATS client -> audio_queue -> LiveKit "
                "capture_frame), not synthesis latency upstream of it."
            ),
            (
                f"IMPORTANT negative result: {drained_events_before_stop} of "
                f"{backlog_frames} frames had already crossed buffer3_to_4 "
                "(reached capture_frame) by the time the 'stop instant' was "
                f"sampled, leaving only {queue_depth_at_stop} still queued. "
                "rtc.AudioSource.capture_frame() does not block or pace to "
                "real-time when nothing is actually consuming the published "
                "track -- this run publishes a track but attaches no receiving "
                "client, so there is no playback-rate backpressure and the "
                "queue drains at publish speed instead of speech speed. This is "
                "itself informative: it means M3-R1's buffer-3 backlog scenario "
                "specifically requires an actively-playing listener, and cannot "
                "be reproduced by publishing alone."
            ),
            (
                "residual_drain_time_s and backlog_frames_at_stop_instant are "
                "real measurements of what they say, but do NOT answer M3-R1's "
                "actual question (see worst_case_no_flush_latency, UNKNOWN) -- "
                "that needs either a real LiveKit-connected client pacing "
                "consumption, or capture_frame() driven under an explicit clock "
                "budget so backpressure is simulated rather than absent. Left "
                "for a follow-up with that harness piece built; recorded here "
                "as UNKNOWN rather than reporting this run's near-zero number "
                "as if it were the answer."
            ),
            (
                "TransportAgent still has no audio.stop subscriber (P1-3 not "
                "yet built, correctly gated on this measurement per "
                "audit/ROADMAP.md §7's sequencing) -- even with a real backlog, "
                "nothing today drains it faster than playback pace regardless "
                "of when a stop is requested."
            ),
            (
                "buffer2 and buffer4 are UNKNOWN for the reasons stated per "
                "figure, matching HARDWARE.md §0's rule against filling an "
                "unmeasured figure with a plausible number."
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
