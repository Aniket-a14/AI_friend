"""CLI for the eval harness. Run from ``backend/``: ``python -m evals ...``."""

import argparse
import asyncio
import sys
from pathlib import Path

from app import config as config_module
from app.cognitive.identity import IdentityManager
from app.llm.ollama_client import OllamaClient

from .compare import compare_reports, render_comparison
from .probes import collect_probes, shipped_packs
from .runner import run_eval
from .schema import load_report, save_report


def _mock_active() -> bool:
    return bool(getattr(config_module.config_instance, "MOCK_LLM_TEXT", False))


async def _cmd_run(args: argparse.Namespace) -> int:
    if _mock_active() and not args.allow_mock:
        print(
            "MOCK_LLM_TEXT is enabled: responses would come from the mock, not "
            "a model, and the report would be meaningless as evidence.\n"
            "Unset MOCK_LLM_TEXT, or pass --allow-mock if you are only "
            "exercising the harness plumbing.",
            file=sys.stderr,
        )
        return 2

    manager = IdentityManager(base_path=args.base_path)
    packs = [] if args.no_shipped_packs else shipped_packs()
    packs.extend(Path(p) for p in args.probes)
    probes = collect_probes(manager, packs)

    client = OllamaClient(base_url=args.url)
    try:
        report = await run_eval(client, manager, probes, model=args.model)
    finally:
        await client.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_report(report, str(out))

    total = len(report.results)
    passed = sum(1 for item in report.results if item.passed)
    print(f"model={report.model} persona={report.persona_name!r} "
          f"provenance={report.provenance}")
    for category, summary in report.by_category.items():
        print(f"  {category:<10} {summary.passed}/{summary.probes} "
              f"(mean {summary.mean_score:.2f})")
    print(f"{passed}/{total} probes passed -> {out}")
    if report.provenance == "mock":
        print("!! mock provenance — plumbing check only, not evidence.")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)

    if not args.allow_mock and "mock" in (baseline.provenance, candidate.provenance):
        print(
            "Refusing to compare mock-provenance reports as evidence; pass "
            "--allow-mock to inspect them anyway.",
            file=sys.stderr,
        )
        return 2

    comparison = compare_reports(baseline, candidate)
    print(render_comparison(comparison))
    if args.fail_on_regression and not comparison.gate_passed:
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="evals")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="probe one model and write a report")
    run_parser.add_argument("--out", required=True, help="report JSON path")
    run_parser.add_argument("--model", default=None,
                            help="Ollama model tag (default: client default)")
    run_parser.add_argument("--url", default="http://127.0.0.1:11434")
    run_parser.add_argument("--base-path", default=None,
                            help="identity dir (default: the live persona)")
    run_parser.add_argument("--probes", action="append", default=[],
                            help="extra probe pack JSON (repeatable)")
    run_parser.add_argument("--no-shipped-packs", action="store_true",
                            help="persona-derived and --probes packs only")
    run_parser.add_argument("--allow-mock", action="store_true",
                            help="permit running under MOCK_LLM_TEXT "
                                 "(report is stamped mock)")

    cmp_parser = sub.add_parser("compare", help="diff two reports")
    cmp_parser.add_argument("baseline")
    cmp_parser.add_argument("candidate")
    cmp_parser.add_argument("--fail-on-regression", action="store_true",
                            help="exit 1 if any baseline-passing probe fails")
    cmp_parser.add_argument("--allow-mock", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "run":
        return asyncio.run(_cmd_run(args))
    return _cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
