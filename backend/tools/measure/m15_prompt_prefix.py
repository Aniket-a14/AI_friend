"""Measurement 1.5 (PERFORMANCE.md §17 item 5): does a turn's six per-turn
LLM calls share a prompt prefix? Ollama's prompt cache only helps if they do,
and §3.1's cache effect is large enough that reordering prompts to exploit it
is tempting -- this settles whether there is anything to exploit before
anyone does that.

Drives one real cognitive turn through CognitiveService.process_event()
in-process, against real Postgres/Neo4j/Ollama (no NATS agent wiring needed:
CognitiveService.agent is None here, so process_event's mesh_signal publish
is a no-op and the pipeline still runs for real otherwise).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from app.cognitive.core import CognitiveService
from app.config import Config
from app.llm.ollama_client import OllamaClient
from app.state import ConversationHistoryStore, GraphDB, MemoryStore

from .harness import check_live_llm, collecting_trace, ensure_bootstrapped
from .schema import Figure, MeasurementReport, Run


def _longest_common_prefix(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


async def _run_one_turn(text: str) -> list[dict]:
    await ensure_bootstrapped()
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()
    graph_db = GraphDB()
    await graph_db.initialize()
    memory_store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)
    llm = OllamaClient(base_url=Config.OLLAMA_URL, model=Config.LLM_CHAT_MODEL)

    svc = CognitiveService(
        llm_service=llm,
        memory_store=memory_store,
        graph_db=graph_db,
    )

    raw_event = {
        "text": text,
        "utterance_id": str(uuid.uuid4()),
        "turn_id": str(uuid.uuid4()),
        "metadata": {},
    }

    with collecting_trace() as events:
        prior_full = Config.MEASURE_TRACE_FULL_PROMPTS
        Config.MEASURE_TRACE_FULL_PROMPTS = True
        try:
            async for _ in svc.process_event(raw_event):
                pass
        finally:
            Config.MEASURE_TRACE_FULL_PROMPTS = prior_full

    await llm.close()
    return [
        {
            "model": f["model"],
            "digest": f["digest"],
            "length": f["length"],
            "text": f["text"],
        }
        for (component, event, ts, f) in events
        if component == "ollama_client" and event == "prompt"
    ]


async def run(allow_mock: bool = False) -> MeasurementReport:
    provenance = check_live_llm(allow_mock)
    prompts = await _run_one_turn(
        "Hey, it's been a while -- what have we talked about before, and how are you doing?"
    )

    if len(prompts) < 2:
        figures = {
            "call_count": Figure(label="MEASURED", value=len(prompts), unit="calls"),
            "shared_prefix_chars": Figure(
                label="UNKNOWN",
                reason=f"turn produced only {len(prompts)} LLM call(s); need >=2 to compare",
            ),
        }
    else:
        prefixes = [
            _longest_common_prefix(prompts[i]["text"], prompts[i + 1]["text"])
            for i in range(len(prompts) - 1)
        ]
        figures = {
            "call_count": Figure(label="MEASURED", value=len(prompts), unit="calls"),
            "min_shared_prefix_chars": Figure(
                label="MEASURED", value=min(prefixes), unit="chars"
            ),
            "max_shared_prefix_chars": Figure(
                label="MEASURED", value=max(prefixes), unit="chars"
            ),
            "prompt_lengths": Figure(
                label="MEASURED",
                value=str([p["length"] for p in prompts]),
                unit="chars per call",
            ),
        }

    return MeasurementReport(
        measurement_id="1.5",
        title="Prompt-prefix sharing across one turn's LLM calls",
        provenance=provenance,
        runs=[Run(figures=figures, raw={"prompts": prompts})],
        notes=[
            (
                "Prompts are the flattened /api/generate-shape text (system + "
                "user), matching what OllamaClient actually sends when /api/chat "
                "is unavailable, and a superset of the structured /api/chat "
                "content for prefix-comparison purposes."
            ),
            (
                f"{len(prompts)} LLM call(s) observed for this turn. "
                "PERFORMANCE.md §17 item 5 refers to 'six per-turn calls' as an "
                "assumption this measurement was meant to check -- on this run "
                "only appraisal + the main response call fired (no intent "
                "classification, no reflection call: single-turn events with no "
                "prior history don't cross REFLECTION_MIN_INTERVAL_SECONDS or "
                "reach the consolidation path that fires the other four). A "
                "longer scripted conversation would be needed to observe all six "
                "in one measurement; this run answers the narrower question "
                "asked -- do the calls that DO fire share a prefix -- correctly."
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--out", default="tools/measure/out/m15_prompt_prefix.json")
    args = parser.parse_args()

    report = asyncio.run(run(allow_mock=args.allow_mock))
    with open(args.out, "w") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
