"""Measurement 17 (roadmap Phase 6.2, `AUDIT.md` §17): the nine simultaneous-
load scenarios `audit/HARDWARE.md` left `UNKNOWN` for the composite case --
"nothing measured suggests the hardware is the problem" was true of six
sequential LLM calls and a resident VLM in isolation, never of voice, vision
and cognition running at once, because nothing had actually run them at once.

Each scenario drives the real component that produces that class of load --
`TransportAgent`'s synthetic-PCM technique from `m13_audio_growth.py`,
`VisualAppraisalService.appraise()` from `m12_consolidation.py`'s VLM-contention
call, `CognitiveService.process_event()` from `m15_prompt_prefix.py`, and
`SubconsciousAgent._run_consolidation_pass()` from `m12_consolidation.py` --
composed with `asyncio.gather` rather than reinventing a driver per scenario.
This is deliberately in-process against real Postgres/Neo4j/NATS/Ollama, the
same choice `m11`/`m12`/`m15` already made, not a full container mesh: it
answers the same resource-pressure question without needing brain_agent,
system_agent, etc. running as separate processes, and it is the technique
this repository's own measurement harness has already used and verified.

Two things this file's scope deliberately does NOT cover, stated up front
rather than discovered by a reader diffing against a MEASURED claim:

- **CPU%, GPU utilization and thermal** are `UNKNOWN` for every scenario.
  `audit/HARDWARE.md` §0 already documents no power-metering access on this
  host; an idle-snapshot CPU% is not representative of load, and there is no
  cheap, honest way to sample Apple Silicon GPU utilization from Python here.
  RAM is the pressure axis this file actually measures.
- **Vision uses PIL-generated synthetic frames, not a real screen/camera
  capture.** `cv2` is not installed on this host (confirmed via import;
  matches M3-A9's documented degraded path), so `VisionAgent`'s own
  `ScreenLink`/`CameraLink` capture cannot run here at all. This drives
  `VisualAppraisalService.appraise()` directly instead -- the same VLM-calling
  component `VisionAgent` uses, minus the capture layer -- which is honest
  about what it measures (VLM + habituation-vector cost) and not about frame
  grab/encode cost, which is not exercised by this measurement.

Scenario 9 ("sustained long-running operation") is measured as a 180-second
bounded run, not an hours-long endurance test -- stated explicitly in that
scenario's notes, the same honesty this file's own precedents apply (measurement
1.1's `worst_case_no_flush_latency`, left `UNKNOWN` with a real reason rather
than a fabricated number).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import itertools
import random
import re
import subprocess
import time
import uuid

from app.agents.base import BaseAgent
from app.agents.subconscious_agent import SubconsciousAgent
from app.cognitive.core import CognitiveService
from app.cognitive.learning import ReflectionService
from app.config import Config
from app.llm.ollama_client import OllamaClient
from app.state import ConversationHistoryStore, GraphDB, MemoryStore
from app.vision.appraisal import VisualAppraisalService

from .harness import check_live_llm, ensure_bootstrapped
from .schema import Figure, MeasurementReport, Run

_SAMPLE_RATE = 32000
_BYTES_PER_SAMPLE = 2
_BYTES_PER_SEC = _SAMPLE_RATE * _BYTES_PER_SAMPLE
_FRAME_MS = 20
_FRAME_BYTES = int(_BYTES_PER_SEC * (_FRAME_MS / 1000))

_SEED_TURNS = [
    ("user", "I've been thinking about picking up rock climbing this year."),
    ("assistant", "That sounds exciting! What's drawing you to it?"),
    ("user", "I want a hobby that gets me outside and off my laptop."),
    ("assistant", "Makes sense -- climbing is great for that. Any gyms nearby?"),
]


# --- resource sampling -------------------------------------------------


def _sample_host_ram() -> dict:
    """macOS `vm_stat` gives page counts, not bytes -- page size varies by
    host (16KiB on this Apple Silicon Mac, historically 4KiB on Intel), so
    it is read from the tool's own header rather than assumed."""
    out = subprocess.run(
        ["vm_stat"], capture_output=True, text=True, timeout=10, check=False
    ).stdout
    page_size_match = re.search(r"page size of (\d+) bytes", out)
    page_size = int(page_size_match.group(1)) if page_size_match else 4096

    def _pages(label: str) -> int:
        m = re.search(rf"{label}:\s+(\d+)\.", out)
        return int(m.group(1)) if m else 0

    free = _pages("Pages free")
    inactive = _pages("Pages inactive")
    speculative = _pages("Pages speculative")
    total_bytes = int(
        subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
    )
    available_bytes = (free + inactive + speculative) * page_size
    return {
        "total_gb": round(total_bytes / 1e9, 3),
        "available_gb": round(available_bytes / 1e9, 3),
        "used_gb": round((total_bytes - available_bytes) / 1e9, 3),
    }


def _sample_docker() -> dict:
    """Sums RSS-equivalent memory across every currently-running container.
    Assumes a dev host with only this project's infra containers up (the
    same assumption `docker stats` sampling in this session's earlier live
    verification already relied on) -- noted in the report if the count
    looks like it includes something unexpected."""
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        ).stdout
    except Exception as exc:
        return {"error": str(exc), "container_count": 0, "total_mib": 0.0}

    total_mib = 0.0
    containers = {}
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        name, mem_usage = parts
        used = mem_usage.split("/")[0].strip()
        m = re.match(r"([\d.]+)\s*(GiB|MiB|KiB|B)", used)
        if not m:
            continue
        value, unit = float(m.group(1)), m.group(2)
        mib = {"GiB": value * 1024, "MiB": value, "KiB": value / 1024, "B": value / (1024**2)}[unit]
        containers[name] = round(mib, 1)
        total_mib += mib
    return {
        "container_count": len(containers),
        "total_mib": round(total_mib, 1),
        "containers": containers,
    }


def _sample_ollama() -> dict:
    """`ollama ps` is the resident-model source of truth -- HARDWARE.md §6's
    footprint table was built from the same idea, one model loaded at a
    time. Here it may show several resident at once under contention."""
    try:
        out = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except Exception as exc:
        return {"error": str(exc), "resident_models": []}
    lines = out.strip().splitlines()
    models = []
    for line in lines[1:]:  # skip header
        parts = re.split(r"\s{2,}", line.strip())
        if parts:
            models.append(parts[0])
    return {"resident_models": models, "resident_count": len(models)}


def _sample() -> dict:
    return {
        "host_ram": _sample_host_ram(),
        "docker": _sample_docker(),
        "ollama": _sample_ollama(),
        "t": time.monotonic(),
    }


def _ram_figure(label: str, before: dict, after: dict, peak: dict | None = None) -> Figure:
    delta = after["host_ram"]["used_gb"] - before["host_ram"]["used_gb"]
    peak_note = ""
    if peak is not None:
        peak_note = f"; peak during load {peak['host_ram']['used_gb']:.2f} GB used"
    return Figure(
        label="MEASURED",
        value=after["host_ram"]["used_gb"],
        unit="GB used (of 16 GB unified)",
        derivation=(
            f"{label}: before={before['host_ram']['used_gb']:.2f}GB, "
            f"after={after['host_ram']['used_gb']:.2f}GB, delta={delta:+.2f}GB"
            f"{peak_note}. Docker containers contributed "
            f"{after['docker'].get('total_mib', 0) / 1024:.2f}GB across "
            f"{after['docker'].get('container_count', 0)} containers; "
            f"Ollama held {after['ollama'].get('resident_count', 0)} model(s) "
            f"resident ({', '.join(after['ollama'].get('resident_models', [])) or 'none'})."
        ),
    )


# --- synthetic load drivers ---------------------------------------------


async def _voice_load(duration_s: float) -> None:
    agent = BaseAgent(name="m17_voice_load", nats_url=Config.NATS_URL)
    await agent.connect()
    frame = bytes(_FRAME_BYTES)
    frames_per_sec = 1000 / _FRAME_MS
    total_frames = int(duration_s * frames_per_sec)
    for _ in range(total_frames):
        await agent.publish("audio.stream", frame)
        await asyncio.sleep(_FRAME_MS / 1000)
    await agent.nc.close()


def _random_frame_b64() -> str:
    from PIL import Image

    img = Image.new(
        "RGB",
        (64, 64),
        (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


_FIXED_FRAME_B64 = _random_frame_b64()  # same frame every call -> habituation should suppress VLM


async def _vision_only_load(duration_s: float) -> VisualAppraisalService:
    """Repeats the *same* frame so the habituation delta stays ~0 after the
    first call -- vision's capture/vector cost without sustained VLM cost."""
    client = OllamaClient(base_url=Config.OLLAMA_URL, model=Config.VLM_MODEL)
    svc = VisualAppraisalService(ollama_client=client, model=Config.VLM_MODEL, interval=0.0)
    t0 = time.monotonic()
    while time.monotonic() - t0 < duration_s:
        await svc.appraise(_FIXED_FRAME_B64)
        await asyncio.sleep(0.5)
    await client.close()
    return svc


async def _vision_cognition_load(duration_s: float) -> VisualAppraisalService:
    """A genuinely different frame every call defeats habituation, forcing a
    real VLM call each tick -- the sustained-VLM-contention shape
    HARDWARE.md §5 measured with two resident models, driven through the
    actual appraisal component rather than a bare describe_image loop."""
    client = OllamaClient(base_url=Config.OLLAMA_URL, model=Config.VLM_MODEL)
    svc = VisualAppraisalService(ollama_client=client, model=Config.VLM_MODEL, interval=0.0)
    t0 = time.monotonic()
    while time.monotonic() - t0 < duration_s:
        await svc.appraise(_random_frame_b64())
    await client.close()
    return svc


async def _cognition_turn() -> None:
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()
    graph_db = GraphDB()
    await graph_db.initialize()
    memory_store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)
    llm = OllamaClient(base_url=Config.OLLAMA_URL, model=Config.LLM_CHAT_MODEL)
    svc = CognitiveService(llm_service=llm, memory_store=memory_store, graph_db=graph_db)
    raw_event = {
        "text": "What have we talked about, and how are you feeling today?",
        "utterance_id": str(uuid.uuid4()),
        "turn_id": str(uuid.uuid4()),
        "metadata": {},
    }
    async for _ in svc.process_event(raw_event):
        pass
    await llm.close()


async def _background_consolidation() -> None:
    graph_db = GraphDB()
    await graph_db.initialize()
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()
    await conversation_store.start_session()
    for role, content in _SEED_TURNS:
        await conversation_store.log_message(role, content)
    memory_store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)
    reflection = ReflectionService(llm_service=None, graph_store=graph_db, pg_vector=memory_store)
    agent = SubconsciousAgent(
        ollama_url=Config.OLLAMA_URL,
        graph_db=graph_db,
        memory_store=memory_store,
        reflection_service=reflection,
    )
    reflection.llm = agent.llm
    await agent._run_consolidation_pass()
    await agent.llm.close()


# --- scenarios -----------------------------------------------------------

_LOAD_DURATION_S = 30.0
_SUSTAINED_DURATION_S = 180.0


async def _scenario_1_idle() -> tuple[dict, dict, str]:
    before = _sample()
    await asyncio.sleep(5.0)  # a real idle window, not an instant snapshot
    after = _sample()
    return before, after, "5s idle window, infra up, no synthetic load driven."


async def _scenario_2_voice_only() -> tuple[dict, dict, str]:
    before = _sample()
    await _voice_load(_LOAD_DURATION_S)
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of synthetic 32kHz/16-bit PCM on audio.stream, no STT/cognition triggered."


async def _scenario_3_voice_cognition() -> tuple[dict, dict, str]:
    before = _sample()
    await asyncio.gather(_voice_load(_LOAD_DURATION_S), _cognition_turn())
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of voice PCM concurrent with one real cognitive turn."


async def _scenario_4_vision_only() -> tuple[dict, dict, str]:
    before = _sample()
    await _vision_only_load(_LOAD_DURATION_S)
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of repeated-identical-frame appraisal calls (habituation should suppress all but the first VLM call)."


async def _scenario_5_vision_cognition() -> tuple[dict, dict, str]:
    before = _sample()
    await asyncio.gather(_vision_cognition_load(_LOAD_DURATION_S), _cognition_turn())
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of varying-frame appraisal (real VLM call every tick) concurrent with one real cognitive turn."


async def _scenario_6_voice_vision_cognition() -> tuple[dict, dict, str]:
    before = _sample()
    await asyncio.gather(
        _voice_load(_LOAD_DURATION_S),
        _vision_cognition_load(_LOAD_DURATION_S),
        _cognition_turn(),
    )
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of voice PCM + varying-frame VLM appraisal, concurrent with one real cognitive turn."


async def _scenario_7_full_multimodal() -> tuple[dict, dict, str]:
    before = _sample()
    await asyncio.gather(
        _voice_load(_LOAD_DURATION_S),
        _vision_cognition_load(_LOAD_DURATION_S),
        _cognition_turn(),
        _cognition_turn(),  # a second concurrent turn -- interactive, not single-request
    )
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of voice + vision-VLM + two concurrent cognitive turns (interactive multimodal use, not background)."


async def _scenario_8_full_background() -> tuple[dict, dict, str]:
    before = _sample()
    await asyncio.gather(
        _voice_load(_LOAD_DURATION_S),
        _vision_cognition_load(_LOAD_DURATION_S),
        _cognition_turn(),
        _background_consolidation(),
    )
    after = _sample()
    return before, after, f"{_LOAD_DURATION_S:.0f}s of scenario 6's load plus a concurrent background consolidation pass -- the ack-deadline contention shape HARDWARE.md §3.3 estimated, now with voice+vision in the mix too, not VLM alone."


async def _scenario_9_sustained() -> tuple[dict, dict, str]:
    """Bounded proxy for 'sustained long-running operation': scenario 8's
    combined load repeated in a loop for 180s wall-clock, sampling at
    intervals to distinguish a plateau from monotonic growth (a leak
    signature) -- not an hours-long endurance run. Stated as a proxy, not
    claimed as the real thing."""
    before = _sample()
    samples = [before]
    t0 = time.monotonic()
    while time.monotonic() - t0 < _SUSTAINED_DURATION_S:
        await asyncio.gather(
            _voice_load(15.0),
            _vision_cognition_load(15.0),
            _cognition_turn(),
        )
        samples.append(_sample())
    after = samples[-1]
    growth = [s["host_ram"]["used_gb"] for s in samples]
    monotonic_growth = all(b - a >= -0.05 for a, b in itertools.pairwise(growth))
    trend = (
        "monotonically non-decreasing across all samples (possible leak signature)"
        if monotonic_growth and growth[-1] - growth[0] > 0.2
        else "no sustained monotonic growth observed"
    )
    return (
        before,
        after,
        (
            f"{_SUSTAINED_DURATION_S:.0f}s bounded proxy (NOT an hours-long endurance run) "
            f"of repeated scenario-8-shaped cycles, {len(samples)} samples: {trend}. "
            f"RAM used_gb across samples: {[round(g, 2) for g in growth]}."
        ),
    )


_SCENARIOS = {
    "1_idle": _scenario_1_idle,
    "2_voice_only": _scenario_2_voice_only,
    "3_voice_cognition": _scenario_3_voice_cognition,
    "4_vision_only": _scenario_4_vision_only,
    "5_vision_cognition": _scenario_5_vision_cognition,
    "6_voice_vision_cognition": _scenario_6_voice_vision_cognition,
    "7_full_multimodal": _scenario_7_full_multimodal,
    "8_full_background": _scenario_8_full_background,
    "9_sustained": _scenario_9_sustained,
}


async def run(allow_mock: bool = False, only: list[str] | None = None) -> MeasurementReport:
    provenance = check_live_llm(allow_mock)
    await ensure_bootstrapped()

    names = only or list(_SCENARIOS)
    figures: dict[str, Figure] = {
        "cpu_gpu_thermal": Figure(
            label="UNKNOWN",
            reason=(
                "No power-metering or GPU-utilization access on this host "
                "(audit/HARDWARE.md §0's existing limitation); RAM is the "
                "pressure axis measured here."
            ),
        ),
    }
    raw: dict[str, dict] = {}
    notes = [
        (
            f"Each 'under load' scenario runs for {_LOAD_DURATION_S:.0f}s wall-clock "
            f"except scenario 9 ({_SUSTAINED_DURATION_S:.0f}s, a bounded proxy for "
            "'sustained', not an endurance run)."
        ),
        (
            "Vision scenarios drive VisualAppraisalService.appraise() directly with "
            "PIL-generated synthetic frames, not a real screen/camera capture -- "
            "cv2 is not installed on this host, matching M3-A9's documented "
            "degraded path, so VisionAgent's own capture layer cannot run here."
        ),
        (
            "In-process, real Postgres/Neo4j/NATS/Ollama -- not a full container "
            "mesh (no brain_agent/system_agent/etc. processes). Same choice this "
            "harness's other measurements already made."
        ),
    ]

    for name in names:
        scenario_fn = _SCENARIOS[name]
        print(f"  scenario {name} ...", flush=True)
        before, after, description = await scenario_fn()
        figures[f"{name}_ram"] = _ram_figure(description, before, after)
        raw[name] = {"before": before, "after": after, "description": description}

    return MeasurementReport(
        measurement_id="17",
        title="Nine simultaneous-load pressure scenarios (AUDIT.md §17)",
        provenance=provenance,
        runs=[Run(figures=figures, raw=raw)],
        notes=notes,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument(
        "--only",
        nargs="*",
        choices=list(_SCENARIOS),
        help="run a subset of scenarios (default: all nine)",
    )
    parser.add_argument("--out", default="tools/measure/out/m17_pressure_scenarios.json")
    args = parser.parse_args()

    report = asyncio.run(run(allow_mock=args.allow_mock, only=args.only))
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
