"""Measurement 1.4 (M3-P1): fast-path STT cost as a function of utterance
length.

Requires the containerized stt-agent -- HARDWARE.md §8 documents that the
native macOS binary SIGKILLs on load (`libsherpa-onnx-c-api.dylib`, no
LC_RPATH; three fixes tried at M5, residual cause UNKNOWN, filed as P2-11,
not attempted again here). Run the container first:

    docker build -f Dockerfile.rust --target runtime -t ai_friend_stt_agent:measure .
    docker run --rm -d --name stt_agent_measure --network ai_mesh_network \\
        -e NATS_URL=nats://nats_mesh:4222 -e STT_BACKEND=whisper \\
        -e STT_SENSEVOICE=on -e STT_SENSEVOICE_DIR=/app/models/sensevoice \\
        -e STT_TARGET_SAMPLE_RATE=16000 \\
        -v "$(pwd)/models/sensevoice:/app/models/sensevoice:ro" \\
        ai_friend_stt_agent:measure stt-agent

Then: python -m tools.measure.m14_stt_cost --out tools/measure/out/m14_stt_cost.json

Publishes synthetic utterances of increasing length directly onto
audio.inbound (bypassing transport_agent/LiveKit -- audio.inbound is where
the real one publishes too), each followed by enough silence to trigger the
endpointer, and times the arrival of the corresponding chat.input transcript.
This measures end-to-end final-transcript latency vs. utterance length, the
practical form of M3-P1's question (does cost grow superlinearly with
length) -- it does not isolate per-partial cost in isolation, which would
need audio.perception timestamps correlated per partial; see notes.

**Run 2026-08-22, real finding, not a harness bug.** The container came up
cleanly (whisper base.en + SenseVoice both loaded, subscribed to
audio.inbound), and correctly endpointed 2 of 3 synthetic utterances
(container logs: "utterance endpointed; transcribing secs=2.9" and
"secs=4.9", matching the 2s/4s requests -- the 1s request's endpoint never
logged, independently worth another look). But the accurate-path (whisper)
transcription call that follows never completed for any of the three: no
chat.input ever arrived, no error was logged, and `docker stats` showed the
container sitting at **0.00% CPU** for 5+ minutes after the last "transcribing"
log line -- a real process, alive, doing no work, not merely slow CPU-bound
inference (which would show near-100% CPU on a single core instead). This is
a genuinely new, reproducible finding: whisper transcription hangs
indefinitely on at least the second sequential call within one stt-agent
process in this containerized configuration (arm64, no GPU, first run under
this specific image). Not root-caused here -- would need a debugger attached
inside the container or bisecting which whisper.cpp call blocks. Filed
alongside P2-11 (native macOS binary can't even start) as a second,
independent stt-agent reliability gap worth its own investigation, not
folded into this measurement's own scope.

**Bounded diagnostic pass, 2026-08-22 (backlog Part 2).** Three cheap,
falsifiable hypotheses were tested against fresh single-utterance
containers, in order, each ruled out by an identical symptom (stall
immediately after whisper's `compute buffer (decode)` init log, zero
completion, zero error, and `docker stats` pinned at **0.00% CPU** for the
full observation window rather than the near-100%-on-one-core signature of
slow-but-working inference):

1. `params.set_n_threads(1)` in `whisper.rs::transcribe` (temporary local
   build) -- still hung. Rules out an internal ggml multi-thread race: a
   single decode thread cannot deadlock against other ggml threads that
   don't exist in this run.
2. `STT_SENSEVOICE=off` -- still hung (this also falls back the fast path to
   Whisper `tiny.en`, so both paths were pure-Whisper and it still hung on
   the accurate call). Rules out resource contention between SenseVoice's
   ONNX Runtime and whisper.cpp's ggml runtime as the cause.
3. A 0.6s utterance, just above the `pcm_16k.len() < 16_000/2` floor --
   still hung at the same point. Rules out a length- or buffer-size-
   dependent path.

A fourth pass under `RUST_LOG=trace` added one real finding beyond ruling
hypotheses out: the tokio runtime keeps running normally for 70+ seconds
after the stall begins -- NATS PING/PONG keepalives and unrelated
`audio.inbound` message dispatch continue in the trace log throughout, with
no gap. This means the hang is *not* a runtime-wide stall (e.g. a blocking
call made without `spawn_blocking`) -- `run_final_job` correctly wraps the
accurate call in `spawn_blocking`, and that wrapping is doing its job; only
that one spawned blocking task itself never returns and burns no CPU while
not returning. That combination -- blocked, not busy -- is the signature of
a wait on a synchronization primitive (a mutex, condvar, or semaphore)
inside whisper.cpp's C code that is never signaled, not an infinite compute
loop.

No source change ships from this pass -- none of the three hypotheses
produced a fix to verify, and the plan's own rule is not to ship a blind fix
without the ability to confirm it resolves the real issue. Root-causing
further needs an actual debugger (lldb/gdb) attached inside the container,
out of reach of this harness. Filed as the same open reliability gap noted
above, now with three ruled-out causes and one substantive lead (blocked
inside a whisper.cpp synchronization primitive, not multi-threading, not
SenseVoice, not utterance length) for whoever picks up a debugger next.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import time

from app.agents.base import BaseAgent
from app.config import Config
from app.contracts import Topics

from .harness import check_live_llm
from .schema import Figure, MeasurementReport, Run

_SAMPLE_RATE = 16000
_BYTES_PER_SAMPLE = 2
_FRAME_MS = 20
_FRAME_SAMPLES = int(_SAMPLE_RATE * (_FRAME_MS / 1000))
_SILENCE_MARGIN_MS = 900  # > default STT_ENDPOINT_SILENCE_MS (700ms)


def _voiced_frame(t_offset_s: float) -> bytes:
    """440Hz tone, amplitude well above min_speech_rms (0.008 of full scale)."""
    amplitude = 6000
    samples = bytearray()
    for i in range(_FRAME_SAMPLES):
        t = t_offset_s + i / _SAMPLE_RATE
        val = int(amplitude * math.sin(2 * math.pi * 440 * t))
        samples += val.to_bytes(2, "little", signed=True)
    return bytes(samples)


def _silence_frame() -> bytes:
    return bytes(_FRAME_SAMPLES * _BYTES_PER_SAMPLE)


async def _publish_utterance(agent: BaseAgent, duration_s: float) -> float:
    """Publishes duration_s of tone then enough silence to endpoint.
    Returns the wall-clock timestamp of the last voiced frame published --
    the natural "user stopped talking" instant to measure latency from.
    """
    frame_count = int(duration_s * 1000 / _FRAME_MS)
    t_offset = 0.0
    for _ in range(frame_count):
        frame = _voiced_frame(t_offset)
        await agent.publish(
            "audio.inbound",
            frame,
            metadata={"sample_rate": _SAMPLE_RATE, "channels": 1},
        )
        t_offset += _FRAME_MS / 1000

    last_voiced_at = time.monotonic()

    silence_frames = int(_SILENCE_MARGIN_MS / _FRAME_MS)
    silence = _silence_frame()
    for _ in range(silence_frames):
        await agent.publish(
            "audio.inbound",
            silence,
            metadata={"sample_rate": _SAMPLE_RATE, "channels": 1},
        )

    return last_voiced_at


async def run(
    allow_mock: bool = False,
    lengths_s: tuple[float, ...] = (1, 2, 4, 8, 16, 30),
    per_utterance_timeout_s: float = 60.0,
) -> MeasurementReport:
    provenance = check_live_llm(allow_mock)

    agent = BaseAgent(name="m14_measure_agent", nats_url=Config.NATS_URL)
    await agent.connect()

    arrivals: asyncio.Queue[float] = asyncio.Queue()

    async def _on_chat_input(data, metadata=None):
        await arrivals.put(time.monotonic())

    await agent.subscribe(
        Topics.CHAT_INPUT,
        callback=_on_chat_input,
        durable="m14_measure_chat_input",
        deliver_policy="new",
    )

    results: dict[float, float] = {}
    errors: dict[float, str] = {}
    for length_s in lengths_s:
        # Drain any stale queued arrival from a prior (possibly timed-out) run.
        while not arrivals.empty():
            arrivals.get_nowait()

        last_voiced_at = await _publish_utterance(agent, length_s)
        try:
            arrived_at = await asyncio.wait_for(
                arrivals.get(), timeout=per_utterance_timeout_s
            )
            results[length_s] = arrived_at - last_voiced_at
        except TimeoutError:
            errors[length_s] = (
                f"no chat.input arrived within {per_utterance_timeout_s}s "
                "(endpointer may not have fired, or stt-agent is not running)"
            )

    await agent.nc.close()

    figures = {}
    for length_s in lengths_s:
        key = f"latency_s_at_{length_s:g}s_utterance"
        if length_s in results:
            figures[key] = Figure(
                label="MEASURED", value=results[length_s], unit="seconds"
            )
        else:
            figures[key] = Figure(label="UNKNOWN", reason=errors[length_s])

    if len(results) >= 2:
        xs = sorted(results)
        ys = [results[x] for x in xs]
        # Simple ratio check: if cost were purely linear in length, the last/
        # first latency ratio would track the length ratio. A materially
        # larger latency ratio than length ratio is consistent with M3-P1's
        # claim that fast-path cost is superlinear (each partial re-scans the
        # whole buffer); this is a coarse signal, not a fitted exponent.
        length_ratio = xs[-1] / xs[0]
        latency_ratio = ys[-1] / ys[0] if ys[0] > 0 else float("inf")
        figures["latency_ratio_vs_length_ratio"] = Figure(
            label="MEASURED",
            value=latency_ratio / length_ratio if length_ratio > 0 else float("nan"),
            unit="ratio (>1 suggests superlinear growth, consistent with M3-P1)",
            derivation=(
                f"length {xs[0]:g}s->{xs[-1]:g}s ({length_ratio:.1f}x), "
                f"latency {ys[0]:.3f}s->{ys[-1]:.3f}s ({latency_ratio:.1f}x)"
            ),
        )

    return MeasurementReport(
        measurement_id="1.4",
        title="Fast-path STT cost vs utterance length (end-to-end final-transcript latency)",
        provenance=provenance,
        runs=[Run(figures=figures, raw={"results": results, "errors": errors})],
        notes=[
            (
                "Measures end-to-end latency (last voiced frame published -> "
                "chat.input received), the practical form of M3-P1's question. "
                "It does NOT isolate per-partial cost on audio.perception in "
                "isolation -- that would need partial arrival timestamps "
                "correlated per 500ms interval, left for a follow-up if this "
                "coarser signal warrants it."
            ),
            (
                "Synthetic 440Hz tone, not real speech -- exercises the "
                "endpointer and buffer-rescan cost path identically (both are "
                "RMS/buffer-length driven, not content-driven), but whisper/"
                "SenseVoice transcription quality on a pure tone is undefined "
                "and irrelevant to this measurement."
            ),
            (
                f"{_SILENCE_MARGIN_MS}ms of trailing silence per utterance, "
                "above the 700ms default STT_ENDPOINT_SILENCE_MS, to reliably "
                "trigger finalization."
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument(
        "--lengths-s", type=float, nargs="+", default=[1, 2, 4, 8, 16, 30]
    )
    parser.add_argument("--out", default="tools/measure/out/m14_stt_cost.json")
    args = parser.parse_args()

    report = asyncio.run(
        run(allow_mock=args.allow_mock, lengths_s=tuple(args.lengths_s))
    )
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
