"""CLI for the eval harness. Run from ``backend/``: ``python -m evals ...``."""

import argparse
import asyncio
import sys
from pathlib import Path

from app import config as config_module
from app.cognitive.identity import IdentityManager
from app.llm.ollama_client import OllamaClient

from .compare import PathMismatch, compare_reports, render_comparison
from .conversation import (
    FullHistory,
    RecentWindow,
    Retrieved,
    WindowPlusRetrieved,
    load_conversation_pack,
    run_conversation_eval,
    shipped_conversation_pack,
)
from .probes import collect_probes, shipped_packs
from .retrieval import LexicalRetriever, MemoryStoreRetriever
from .runner import run_eval
from .schema import RunOptions, load_report, save_report


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
        report = await run_eval(
            client, manager, probes,
            model=args.model,
            options=RunOptions(num_gpu=args.num_gpu),
            path=args.path,
        )
    finally:
        await client.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_report(report, str(out))

    total = len(report.results)
    passed = sum(1 for item in report.results if item.passed)
    print(f"model={report.model} persona={report.persona_name!r} "
          f"provenance={report.provenance} path={report.path}")
    for category, summary in report.by_category.items():
        print(f"  {category:<10} {summary.passed}/{summary.probes} "
              f"(mean {summary.mean_score:.2f})")
    print(f"{passed}/{total} probes passed -> {out}")
    if report.provenance == "mock":
        print("!! mock provenance — plumbing check only, not evidence.")
    return 0


async def _build_retrievers(args: argparse.Namespace):
    """Construct the retrievers the caller asked for, plus their teardown.

    The BM25 control needs nothing. The memory-layer retriever needs the real
    stack, built the way `brain_agent.main` builds it -- a parallel
    construction here would measure a MemoryStore nobody ships.

    Returns the retrievers and a teardown for the resources *this function*
    opened; the retrievers clean their own writes.
    """
    retrievers = []
    if "bm25" in args.retrieval:
        retrievers.append(LexicalRetriever())

    # Everything opened here is registered the moment it exists, so a failure
    # partway through construction still has a handle to close. `GraphDB()`
    # raises on a weak or placeholder password, and that happens *after* the
    # connection pool is up -- without this, that pool leaks with nothing left
    # holding a reference to it.
    opened: list = []

    async def teardown() -> None:
        for closer in reversed(opened):
            try:
                await closer()
            except Exception as exc:
                print(f"!! teardown step failed: {exc}", file=sys.stderr)

    if "memory" in args.retrieval:
        from app.state import ConversationHistoryStore, GraphDB, MemoryStore

        try:
            conversation_store = ConversationHistoryStore()
            await conversation_store.initialize()
            opened.append(conversation_store.close)

            graph_db = GraphDB()
            opened.append(graph_db.close)

            store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)
            # `MemoryStore.__init__` opens its own httpx client for embedding
            # calls and nothing else ever closes it.
            opened.append(store._http_client.aclose)
            retrievers.append(MemoryStoreRetriever(store))
        except Exception:
            await teardown()
            raise

    return retrievers, teardown


async def _cmd_run_conversation(args: argparse.Namespace) -> int:
    if _mock_active() and not args.allow_mock:
        print(
            "MOCK_LLM_TEXT is enabled: recall would be scored against canned "
            "text that never saw the planted fact, which measures nothing.\n"
            "Unset MOCK_LLM_TEXT, or pass --allow-mock to exercise the "
            "plumbing only.",
            file=sys.stderr,
        )
        return 2

    pack = Path(args.pack) if args.pack else shipped_conversation_pack()
    probes, filler = load_conversation_pack(pack)
    if not probes:
        print(f"no conversation probes in {pack}", file=sys.stderr)
        return 2

    # Checked here so a bad window exits like every other input error in this
    # command. `RecentWindow` raises, and an uncaught ValueError would print a
    # traceback and exit 1 where the caller is told to expect 2.
    if args.window < 1:
        print("--window needs at least one turn", file=sys.stderr)
        return 2

    strategies = [FullHistory(), RecentWindow(args.window)]
    # `num_ctx` is left to the RunOptions default unless the caller sets it, so
    # the two cannot drift apart.
    overrides = {"num_gpu": args.num_gpu}
    if args.num_ctx is not None:
        overrides["num_ctx"] = args.num_ctx
    options = RunOptions(**overrides)
    manager = IdentityManager(base_path=args.base_path)
    client = OllamaClient(base_url=args.url)

    retrievers: list = []

    async def teardown() -> None:
        return None

    try:
        retrievers, teardown = await _build_retrievers(args)
        for retriever in retrievers:
            strategies.append(Retrieved(retriever, args.window))
            strategies.append(
                WindowPlusRetrieved(retriever, args.window, args.window)
            )

        report = await run_conversation_eval(
            client, manager, probes, filler,
            strategies=tuple(strategies), model=args.model, options=options,
        )
    finally:
        # Deleting what the run wrote to the agent's own database comes first
        # and is individually guarded. It was previously sequenced after
        # `client.close()`, so an error closing an HTTP client -- which costs
        # nothing -- would have skipped the step that keeps scripted filler out
        # of the agent's memory.
        for retriever in retrievers:
            try:
                await retriever.close()
            except Exception as exc:
                print(f"!! failed to clean eval memories: {exc}",
                      file=sys.stderr)
        await teardown()
        await client.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_report(report, str(out))

    print(f"model={report.model} persona={report.persona_name!r} "
          f"provenance={report.provenance}")
    print(f"{'probe':<34}{'ctx turns':>10}{'chars':>8}{'plant':>9}"
          f"{'fits':>7}{'result':>8}")
    for item in report.results:
        print(f"{item.probe_id:<34}{item.context_turns or 0:>10}"
              f"{item.context_chars or 0:>8}"
              f"{'in' if item.plant_visible else 'out':>9}"
              f"{'yes' if item.context_fits else 'NO':>7}"
              f"{'pass' if item.passed else 'FAIL':>8}")

    # Two ways a probe can produce a verdict about nothing, both surfaced
    # rather than silently folded into the score: the strategy never showed the
    # model the fact, or the runtime truncated it away before generation. In
    # either case the number is invalid, not merely low.
    guessed = [
        item.probe_id for item in report.results
        if item.passed and item.plant_visible is False
    ]
    truncated = [
        item.probe_id for item in report.results if item.context_fits is False
    ]
    if guessed:
        print(f"!! passed without the fact in context: {', '.join(guessed)}")
    if truncated:
        print(f"!! context exceeded num_ctx, truncated before the plant: "
              f"{', '.join(truncated)}")
        print("   rerun with a larger --num-ctx; these rows are not evidence.")
    passed = sum(1 for item in report.results if item.passed)
    print(f"{passed}/{len(report.results)} probes passed -> {out}")
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

    try:
        comparison = compare_reports(baseline, candidate)
    except PathMismatch as exc:
        # Exit 2 like the other input errors in this CLI: the reports are
        # individually fine, the pairing is not.
        print(str(exc), file=sys.stderr)
        return 2

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
    run_parser.add_argument("--num-gpu", type=int, default=None,
                            help="GPU layers to offload; pin it so both sides "
                                 "of a comparison load the model identically")
    run_parser.add_argument("--allow-mock", action="store_true",
                            help="permit running under MOCK_LLM_TEXT "
                                 "(report is stamped mock)")
    run_parser.add_argument("--path", choices=["llm", "action"], default="llm",
                            help="what to measure. 'llm' (default) probes the "
                                 "persona prompt straight into the model -- "
                                 "the seam a fine-tuned adapter changes. "
                                 "'action' runs each probe through the real "
                                 "ActionService, so the report also covers "
                                 "action.py's prompt construction, <thought> "
                                 "stripping, sanitization and self-correction. "
                                 "Reports from the two paths cannot be "
                                 "compared with each other")

    conv_parser = sub.add_parser(
        "run-conversation",
        help="probe recall of a fact planted earlier in a conversation",
    )
    conv_parser.add_argument("--out", required=True, help="report JSON path")
    conv_parser.add_argument("--model", default=None)
    conv_parser.add_argument("--url", default="http://127.0.0.1:11434")
    conv_parser.add_argument("--base-path", default=None,
                             help="identity dir (default: the live persona)")
    conv_parser.add_argument("--pack", default=None,
                             help="conversation probe pack JSON "
                                  "(default: the shipped pack)")
    conv_parser.add_argument("--window", type=int, default=6,
                             help="turns kept by the recent_window strategy")
    conv_parser.add_argument("--num-ctx", type=int, default=None,
                             help="context window (default: the harness's "
                                  "pinned value); too small and the runtime "
                                  "truncates the planted fact away")
    conv_parser.add_argument("--num-gpu", type=int, default=None,
                             help="GPU layers to offload; pin it so both sides "
                                  "of a comparison load the model identically")
    conv_parser.add_argument("--retrieval", action="append", default=[],
                             choices=["bm25", "memory"],
                             help="add retrieval-backed strategies "
                                  "(repeatable). 'bm25' is the infra-free "
                                  "control. 'memory' is the real MemoryStore: "
                                  "it needs Postgres, Qdrant and Neo4j up and "
                                  "it WRITES every transcript turn into them, "
                                  "removing them again at the end -- point it "
                                  "at the agent's live databases only if that "
                                  "is what you mean to do")
    conv_parser.add_argument("--allow-mock", action="store_true")

    cmp_parser = sub.add_parser("compare", help="diff two reports")
    cmp_parser.add_argument("baseline")
    cmp_parser.add_argument("candidate")
    cmp_parser.add_argument("--fail-on-regression", action="store_true",
                            help="exit 1 if any baseline-passing probe fails")
    cmp_parser.add_argument("--allow-mock", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "run":
        return asyncio.run(_cmd_run(args))
    if args.command == "run-conversation":
        return asyncio.run(_cmd_run_conversation(args))
    return _cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
