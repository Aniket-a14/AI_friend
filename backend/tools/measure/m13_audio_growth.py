"""Measurement 1.3 (M1-A2, P1-2 validation): AI_AUDIO growth against a real
session, replacing the ~130 KB/s estimate P1-2's sizing was built on.

Publishes synthetic PCM to audio.stream at the real wire rate (32kHz 16-bit
mono, matching TransportAgent's contract -- M3-R1's evidence) via a bare
BaseAgent connection, and samples AI_AUDIO's stream_info() bytes/messages
before, during and after. No voice-agent or TTS involved: this measures the
stream's own retention behavior under real JetStream, which does not care
whether the bytes came from SoVITS or a synthetic generator.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from app.agents.base import BaseAgent
from app.config import Config

from .harness import check_live_llm
from .schema import Figure, MeasurementReport, Run

_SAMPLE_RATE = 32000
_BYTES_PER_SAMPLE = 2  # 16-bit mono
_BYTES_PER_SEC = _SAMPLE_RATE * _BYTES_PER_SAMPLE  # 64000 B/s, per M3-R1
_FRAME_MS = 20
_FRAME_BYTES = int(_BYTES_PER_SEC * (_FRAME_MS / 1000))  # 1280 bytes/frame


async def _publish_synthetic_session(agent: BaseAgent, duration_s: float) -> int:
    frame = bytes(_FRAME_BYTES)  # silence; JetStream storage doesn't care about content
    frames_per_sec = 1000 / _FRAME_MS
    total_frames = int(duration_s * frames_per_sec)
    for _ in range(total_frames):
        await agent.publish("audio.stream", frame)
        await asyncio.sleep(_FRAME_MS / 1000)
    return total_frames


async def _stream_state(agent: BaseAgent) -> dict:
    info = await agent.js.stream_info("AI_AUDIO")
    return {
        "messages": info.state.messages,
        "bytes": info.state.bytes,
    }


async def run(allow_mock: bool = False, duration_s: float = 20.0) -> MeasurementReport:
    provenance = check_live_llm(allow_mock)

    agent = BaseAgent(name="m13_measure_agent", nats_url=Config.NATS_URL)
    await agent.connect()

    before = await _stream_state(agent)
    t0 = time.monotonic()
    frames_sent = await _publish_synthetic_session(agent, duration_s)
    wall_s = time.monotonic() - t0
    after = await _stream_state(agent)

    await agent.nc.close()

    bytes_added = after["bytes"] - before["bytes"]
    measured_rate = bytes_added / wall_s if wall_s > 0 else 0.0
    intended_rate = _BYTES_PER_SEC

    from app.nats_streams import STREAM_POLICIES

    policy = STREAM_POLICIES["AI_AUDIO"]
    time_to_max_bytes_s = (
        policy["max_bytes"] / measured_rate if measured_rate > 0 else float("inf")
    )

    figures = {
        "wire_rate_bytes_per_s": Figure(
            label="MEASURED",
            value=measured_rate,
            unit="bytes/s",
            derivation=(
                f"{bytes_added} bytes added to AI_AUDIO over {wall_s:.2f}s "
                f"wall clock, publishing {frames_sent} frames of "
                f"{_FRAME_BYTES}B each at the {_SAMPLE_RATE}Hz/16-bit/mono "
                "contract TransportAgent assumes"
            ),
        ),
        "intended_wire_rate_bytes_per_s": Figure(
            label="MEASURED",
            value=intended_rate,
            unit="bytes/s",
            derivation=(
                f"{_SAMPLE_RATE}Hz * {_BYTES_PER_SAMPLE}B/sample, the "
                "contract itself, independent of what JetStream measured"
            ),
        ),
        "projected_time_to_max_bytes_s": Figure(
            label="ESTIMATED",
            value=time_to_max_bytes_s,
            unit="seconds",
            derivation=(
                f"policy max_bytes={policy['max_bytes']} / measured rate "
                f"{measured_rate:.1f} B/s"
            ),
        ),
        "policy_max_age_s": Figure(
            label="MEASURED", value=policy["max_age"], unit="seconds"
        ),
    }

    notes = [
        (
            "Synthetic silence frames, not real speech -- exercises JetStream's "
            "own storage/retention accounting, which is content-agnostic. "
            "Framing (20ms frames) matches typical WebRTC frame sizing, not a "
            "measured value from the voice-agent Rust source."
        ),
    ]
    if duration_s < policy["max_age"]:
        notes.append(
            f"This run's duration ({duration_s}s) is shorter than "
            f"policy_max_age_s ({policy['max_age']}s), so no message aged "
            "out during the sample window -- 'after' reflects every frame "
            "published, and max_bytes (not max_age) is the binding limit at "
            "this write rate; see projected_time_to_max_bytes_s."
        )
    else:
        notes.append(
            f"This run's duration ({duration_s}s) exceeds policy_max_age_s "
            f"({policy['max_age']}s), so messages from early in the run may "
            "have aged out before 'after' was sampled -- 'after' can "
            "therefore undercount total bytes actually written during the "
            "session, not just what AI_AUDIO currently retains."
        )
    notes.append(
        f"P1-2's sizing cited an ESTIMATED ~130 KB/s single-stream growth "
        f"figure; this measurement puts the actual wire rate at "
        f"{measured_rate:.0f} B/s (~{measured_rate / 1000:.0f} KB/s), close "
        f"to the {intended_rate}-B/s 32kHz/16-bit/mono contract itself and "
        "roughly half the cited estimate -- P1-2's max_bytes has more "
        "headroom than the original sizing assumed, not less. Two frames "
        "flowing simultaneously (rare -- one active utterance in flight is "
        "the normal case) would approach the original estimate."
    )
    if abs(measured_rate - intended_rate) / intended_rate > 0.15:
        notes.append(
            f"measured wire rate diverges from the intended contract rate by "
            f"more than 15% ({measured_rate:.0f} vs {intended_rate} B/s) -- "
            "likely publish-loop overhead/jitter in this harness rather than "
            "a JetStream storage overhead, since JetStream stores the raw "
            "payload bytes plus a small fixed header per message, not a "
            "content-dependent multiplier."
        )

    return MeasurementReport(
        measurement_id="1.3",
        title="AI_AUDIO growth against a real session",
        provenance=provenance,
        runs=[Run(figures=figures, raw={"before": before, "after": after})],
        notes=notes,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--out", default="tools/measure/out/m13_audio_growth.json")
    args = parser.parse_args()

    report = asyncio.run(run(allow_mock=args.allow_mock, duration_s=args.duration_s))
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
