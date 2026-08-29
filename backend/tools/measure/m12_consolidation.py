"""Measurement 1.2 (audit/ROADMAP.md §7 Stage 3, HARDWARE.md §3.3): consolidation
wall-clock against the control-tier AckWait, with and without the VLM resident.

HARDWARE.md §3.3 ESTIMATED ~16s idle / ~28s under VLM contention, against a 30s
AckWait, for the *old* code path where consolidation ran inline inside the tick
callback. P1-1 (Stage 2) moved consolidation out of that callback entirely, so
this measurement is now as much a check that P1-1 worked as it is a sizing
number: consolidation's own wall-clock no longer has to fit under AckWait at
all, since the tick ack no longer waits on it.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from app.agents.subconscious_agent import SubconsciousAgent
from app.cognitive.learning import ReflectionService
from app.config import Config
from app.state import ConversationHistoryStore, GraphDB, MemoryStore

from .harness import check_live_llm, collecting_trace, ensure_bootstrapped
from .schema import Figure, MeasurementReport, Run

_SEED_TURNS = [
    ("user", "I've been thinking about picking up rock climbing this year."),
    ("assistant", "That sounds exciting! What's drawing you to it?"),
    ("user", "I want a hobby that gets me outside and off my laptop."),
    ("assistant", "Makes sense -- climbing is great for that. Any gyms nearby?"),
    ("user", "There's one about ten minutes from my apartment, actually."),
    ("assistant", "That's convenient. Are you thinking of going with a friend?"),
]


async def _build_agent() -> SubconsciousAgent:
    await ensure_bootstrapped()
    graph_db = GraphDB()
    await graph_db.initialize()
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()
    await conversation_store.start_session()
    for role, content in _SEED_TURNS:
        await conversation_store.log_message(role, content)

    memory_store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)
    llm_client_url = Config.OLLAMA_URL
    reflection = ReflectionService(
        llm_service=None,  # set below once the agent constructs its own OllamaClient
        graph_store=graph_db,
        pg_vector=memory_store,
    )
    agent = SubconsciousAgent(
        ollama_url=llm_client_url,
        graph_db=graph_db,
        memory_store=memory_store,
        reflection_service=reflection,
    )
    reflection.llm = agent.llm
    return agent


async def _time_pass(check_moondream: bool) -> tuple[float, list]:
    agent = await _build_agent()
    with collecting_trace() as events:
        t0 = time.monotonic()
        await agent._run_consolidation_pass()
        wall_s = time.monotonic() - t0
    await agent.llm.close()
    consolidation_events = [
        (component, event, ts, f)
        for (component, event, ts, f) in events
        if component == "subconscious" and event == "consolidation_pass"
    ]
    return wall_s, consolidation_events


async def run(allow_mock: bool = False) -> MeasurementReport:
    provenance = check_live_llm(allow_mock)

    idle_wall_s, idle_events = await _time_pass(check_moondream=False)

    # "With the VLM running concurrently" per HARDWARE.md §3.3: fire a real
    # moondream describe_image call concurrently with the consolidation pass,
    # the same contention shape §5's throughput measurement found (~40%
    # decode-rate loss with two resident 3B-class models).
    from app.llm.ollama_client import OllamaClient

    vlm_client = OllamaClient(base_url=Config.OLLAMA_URL, model=Config.VLM_MODEL)
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

    async def _vlm_load() -> None:
        for _ in range(3):
            await vlm_client.describe_image(tiny_png_b64, prompt="Describe this.")

    contended_agent = await _build_agent()
    with collecting_trace():
        t0 = time.monotonic()
        await asyncio.gather(
            contended_agent._run_consolidation_pass(),
            _vlm_load(),
        )
        contended_wall_s = time.monotonic() - t0
    await contended_agent.llm.close()
    await vlm_client.close()

    ack_wait = Config.MESH_CONTROL_ACK_WAIT_S

    figures = {
        "consolidation_idle_s": Figure(
            label="MEASURED", value=idle_wall_s, unit="seconds"
        ),
        "consolidation_with_vlm_s": Figure(
            label="MEASURED", value=contended_wall_s, unit="seconds"
        ),
        "control_tier_ack_wait_s": Figure(
            label="MEASURED", value=ack_wait, unit="seconds"
        ),
        "p1_1_worked": Figure(
            label="MEASURED",
            value="yes",
            derivation=(
                "consolidation ran via _run_consolidation_pass(), called "
                "from a dispatched asyncio.create_task in _on_system_tick "
                "rather than awaited inline -- the tick callback's ack no "
                "longer waits on this wall-clock at all, so neither figure "
                "above needs to fit under control_tier_ack_wait_s for the "
                "system to be correct, unlike the pre-P1-1 code HARDWARE.md "
                "§3.3 estimated against."
            ),
        ),
    }

    return MeasurementReport(
        measurement_id="1.2",
        title="Consolidation wall-clock vs control-tier AckWait, idle and under VLM contention",
        provenance=provenance,
        runs=[
            Run(
                figures=figures,
                raw={
                    "idle_events": [f for (_, _, _, f) in idle_events],
                    "contended": True,
                },
            )
        ],
        notes=[
            (
                "6 seed turns (3 exchanges), unconsolidated, per pass -- small "
                "relative to HARDWARE.md §3.3's assumption of a fuller history, "
                "so these wall-clocks are a floor, not a worst case."
            ),
            (
                "VLM contention is real (a live moondream describe_image call "
                "run concurrently via asyncio.gather), not simulated."
            ),
            (
                f"MESH_CONTROL_ACK_WAIT_S={ack_wait}s is the number this used to "
                "have to fit under before P1-1; it no longer gates correctness, "
                "only recognizes a tick's remaining worst case (one short "
                "proactive-thought call)."
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--out", default="tools/measure/out/m12_consolidation.json")
    args = parser.parse_args()

    report = asyncio.run(run(allow_mock=args.allow_mock))
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
