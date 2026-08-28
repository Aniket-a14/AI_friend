"""CLI for Stage 3 measurements (audit/ROADMAP.md §7) and the roadmap-leftovers
plan's own pre-wiring verification measurements (Item 4).

    python -m tools.measure run <name>|all [--out DIR] [--allow-mock]

<name> is one of: 1.1 1.2 1.3 1.5 1.6 4b (1.4 has no Python entry point here --
it needs the containerized stt-agent; see tools/measure/m14_stt_cost.py's
module docstring and the Stage 3 ledger entry for how it was run). "4b" is not
a Stage-3 roadmap measurement -- it verifies roadmap-leftovers Item 4b's
turn_taking_probability gate discriminates over the reachable state space
before wiring it, per that plan's "verify the benefit, then wire" discipline.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import (
    m4b_turn_taking_gate,
    m11_bargein,
    m12_consolidation,
    m13_audio_growth,
    m15_prompt_prefix,
    m16_retrieval,
    m17_pressure_scenarios,
)

_MEASUREMENTS = {
    "1.1": (m11_bargein, "m11_bargein.json"),
    "1.2": (m12_consolidation, "m12_consolidation.json"),
    "1.3": (m13_audio_growth, "m13_audio_growth.json"),
    "1.5": (m15_prompt_prefix, "m15_prompt_prefix.json"),
    "1.6": (m16_retrieval, "m16_retrieval.json"),
    "4b": (m4b_turn_taking_gate, "m4b_turn_taking_gate.json"),
    "17": (m17_pressure_scenarios, "m17_pressure_scenarios.json"),
}


async def _run_one(name: str, out_dir: Path, allow_mock: bool) -> None:
    module, filename = _MEASUREMENTS[name]
    print(f"--- {name} ---", file=sys.stderr)
    report = await module.run(allow_mock=allow_mock)
    out_path = out_dir / filename
    out_path.write_text(report.model_dump_json(indent=2))
    print(f"Wrote {out_path}", file=sys.stderr)


async def _main_async(names: list[str], out_dir: Path, allow_mock: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        await _run_one(name, out_dir, allow_mock)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tools.measure")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run one or more measurements")
    run_parser.add_argument(
        "name", choices=[*sorted(_MEASUREMENTS), "all"], help="measurement id or 'all'"
    )
    run_parser.add_argument("--out", default="tools/measure/out", type=Path)
    run_parser.add_argument("--allow-mock", action="store_true")

    args = parser.parse_args()

    if args.command == "run":
        names = sorted(_MEASUREMENTS) if args.name == "all" else [args.name]
        asyncio.run(_main_async(names, args.out, args.allow_mock))


if __name__ == "__main__":
    main()
