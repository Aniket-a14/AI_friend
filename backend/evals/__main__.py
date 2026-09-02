"""CLI for the eval harness. Run from ``backend/``: ``python -m evals ...``."""

import argparse
import asyncio
import getpass
import json
import random
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
from .probes import collect_probes, forgetting_reference_probes, shipped_packs
from .retrieval import LexicalRetriever, MemoryStoreRetriever
from .runner import run_eval
from .schema import (
    EvalReport,
    HumanRating,
    PairwiseRating,
    RunOptions,
    load_report,
    save_report,
)


def _mock_active() -> bool:
    return bool(getattr(config_module.config_instance, "MOCK_LLM_TEXT", False))


def _provenance_lines(report: EvalReport) -> list[str]:
    """Lines stating where a report's model came from, for CLI output.

    Split out from the print block so it can be exercised on a hand-built
    report without a live model -- HUMANOID_ARCHITECTURE_RESEARCH.md's Phase
    0 finding was that this took a manual audit (grepping `.env` files,
    reading `/proc/<pid>/environ`) each time it came up; the report should
    say it outright instead.
    """
    lines = [f"model_source={report.model_source}"]
    deployment = report.deployment_llm_provenance
    if deployment:
        env_file = deployment.get("env_file", "?")
        source_note = (
            env_file
            if deployment.get("env_file_exists", True) is not False
            else f"{env_file} [not found, using env/defaults]"
        )
        lines.append(
            "deployment config (from {source}): chat={chat} fast={fast} "
            "reflection={reflection}".format(
                source=source_note,
                chat=deployment.get("llm_chat_model", "?"),
                fast=deployment.get("llm_fast_model", "?"),
                reflection=deployment.get("llm_reflection_model", "?"),
            )
        )
    lines.append(
        f"git_revision={report.git_revision or 'unknown'} "
        f"persona_version={report.persona_version or 'unknown'}"
    )
    return lines


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
    if args.include_forgetting_reference:
        extra = forgetting_reference_probes(manager)
        seen = {probe.id for probe in probes}
        for probe in extra:
            if probe.id in seen:
                raise ValueError(
                    f"duplicate probe id {probe.id!r} (forgetting-reference collides "
                    "with an already-collected probe)"
                )
            seen.add(probe.id)
        probes.extend(extra)

    client = OllamaClient(base_url=args.url)
    try:
        report = await run_eval(
            client,
            manager,
            probes,
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
    print(
        f"model={report.model} persona={report.persona_name!r} "
        f"provenance={report.provenance} path={report.path}"
    )
    for line in _provenance_lines(report):
        print(line)
    for category, summary in report.by_category.items():
        print(
            f"  {category:<10} {summary.passed}/{summary.probes} "
            f"(mean {summary.mean_score:.2f})"
        )
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
            strategies.append(WindowPlusRetrieved(retriever, args.window, args.window))

        report = await run_conversation_eval(
            client,
            manager,
            probes,
            filler,
            strategies=tuple(strategies),
            model=args.model,
            options=options,
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
                print(f"!! failed to clean eval memories: {exc}", file=sys.stderr)
        await teardown()
        await client.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_report(report, str(out))

    print(
        f"model={report.model} persona={report.persona_name!r} "
        f"provenance={report.provenance} path={report.path}"
    )
    for line in _provenance_lines(report):
        print(line)
    print(
        f"{'probe':<34}{'ctx turns':>10}{'chars':>8}{'plant':>9}"
        f"{'fits':>7}{'result':>8}"
    )
    for item in report.results:
        print(
            f"{item.probe_id:<34}{item.context_turns or 0:>10}"
            f"{item.context_chars or 0:>8}"
            f"{'in' if item.plant_visible else 'out':>9}"
            f"{'yes' if item.context_fits else 'NO':>7}"
            f"{'pass' if item.passed else 'FAIL':>8}"
        )

    # Two ways a probe can produce a verdict about nothing, both surfaced
    # rather than silently folded into the score: the strategy never showed the
    # model the fact, or the runtime truncated it away before generation. In
    # either case the number is invalid, not merely low.
    guessed = [
        item.probe_id
        for item in report.results
        if item.passed and item.plant_visible is False
    ]
    truncated = [item.probe_id for item in report.results if item.context_fits is False]
    if guessed:
        print(f"!! passed without the fact in context: {', '.join(guessed)}")
    if truncated:
        print(
            f"!! context exceeded num_ctx, truncated before the plant: "
            f"{', '.join(truncated)}"
        )
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


def _cmd_rate(args: argparse.Namespace, input_fn=input) -> int:
    """Blinded absolute rating: one response at a time, no model name shown.

    `input_fn` is swappable so tests can drive this without a real terminal
    (see `test_evals_rate_command.py`) -- the same reason a stand-in client
    is injectable elsewhere in this harness rather than only reachable
    through a live dependency.
    """
    report = load_report(args.report)
    rater_id = args.rater_id
    print(
        f"Rating {len(report.results)} probes from {args.report} "
        "(blinded: model name withheld)"
    )
    # A real rating session is interrupted by a Ctrl-D/Ctrl-C far more often
    # than it runs to completion cleanly -- whatever was already collected
    # must still be saved rather than lost with the exception.
    try:
        for result in report.results:
            print("-" * 60)
            print(f"probe_id: {result.probe_id}")
            print(f"prompt: {result.prompt}")
            print(f"response: {result.response}")
            raw = input_fn("character_fidelity (1-5, blank to skip): ").strip()
            if not raw:
                continue
            try:
                score = int(raw)
            except ValueError:
                print(f"!! {raw!r} is not an integer, skipping this probe", file=sys.stderr)
                continue
            if not 1 <= score <= 5:
                print(
                    f"!! {score} is out of range 1-5, skipping this probe",
                    file=sys.stderr,
                )
                continue
            # A score was already given by this point -- if the notes prompt
            # itself is what gets interrupted, that score must not be lost
            # along with it. Record it with empty notes, then let the
            # interruption propagate to the outer handler as normal.
            try:
                notes = input_fn("notes (optional): ").strip()
            except (EOFError, KeyboardInterrupt):
                report.human_ratings.append(
                    HumanRating(
                        probe_id=result.probe_id,
                        rater_id=rater_id,
                        character_fidelity=score,
                        notes="",
                    )
                )
                raise
            report.human_ratings.append(
                HumanRating(
                    probe_id=result.probe_id,
                    rater_id=rater_id,
                    character_fidelity=score,
                    notes=notes,
                )
            )
    except (EOFError, KeyboardInterrupt):
        print("\n!! rating session interrupted; saving what was collected", file=sys.stderr)
    finally:
        save_report(report, args.report)

    print(f"{len(report.human_ratings)} total human ratings -> {args.report}")
    return 0


def _cmd_rate_pairwise(args: argparse.Namespace, input_fn=input) -> int:
    """Blinded pairwise rating between two reports' answers to the same
    probe -- what §17's "Character voice" row asks for specifically. Order is
    randomized per probe to control for position bias; the rater sees
    "Response 1"/"Response 2" only, never which report or model produced
    which.

    Writes to `args.out` (a list of `PairwiseRating` dicts), appending to
    whatever is already there -- neither input report is touched, so
    recording a comparison can never corrupt either report's own provenance.
    """
    report_a = load_report(args.report_a)
    report_b = load_report(args.report_b)
    rater_id = args.rater_id
    rng = random.Random(args.seed)

    by_id_a = {result.probe_id: result for result in report_a.results}
    by_id_b = {result.probe_id: result for result in report_b.results}
    shared = [probe_id for probe_id in by_id_a if probe_id in by_id_b]
    if not shared:
        print("no probe_id is present in both reports; nothing to rate", file=sys.stderr)
        return 2

    ratings: list[PairwiseRating] = []
    try:
        for probe_id in shared:
            result_a, result_b = by_id_a[probe_id], by_id_b[probe_id]
            # "a"/"b" tags which underlying report a shown slot came from, so
            # the rater's "1"/"2" choice can be mapped back correctly even
            # though which one is shown first is randomized per probe.
            order = [("a", result_a), ("b", result_b)]
            if rng.random() < 0.5:
                order.reverse()

            print("-" * 60)
            print(f"probe_id: {probe_id}")
            print(f"prompt: {order[0][1].prompt}")
            print(f"Response 1: {order[0][1].response}")
            print(f"Response 2: {order[1][1].response}")
            raw = input_fn("preferred (1/2/tie, blank to skip): ").strip().lower()
            if not raw:
                continue
            if raw not in {"1", "2", "tie"}:
                print(f"!! {raw!r} is not 1/2/tie, skipping this probe", file=sys.stderr)
                continue
            preferred = "tie" if raw == "tie" else order[0 if raw == "1" else 1][0]
            # A preference was already given by this point -- if the notes
            # prompt itself is what gets interrupted, that preference must
            # not be lost along with it.
            try:
                notes = input_fn("notes (optional): ").strip()
            except (EOFError, KeyboardInterrupt):
                ratings.append(
                    PairwiseRating(
                        probe_id=probe_id,
                        rater_id=rater_id,
                        report_a_id=args.report_a,
                        report_b_id=args.report_b,
                        preferred=preferred,
                        notes="",
                    )
                )
                raise
            ratings.append(
                PairwiseRating(
                    probe_id=probe_id,
                    rater_id=rater_id,
                    report_a_id=args.report_a,
                    report_b_id=args.report_b,
                    preferred=preferred,
                    notes=notes,
                )
            )
    except (EOFError, KeyboardInterrupt):
        print("\n!! rating session interrupted; saving what was collected", file=sys.stderr)
    finally:
        out_path = Path(args.out)
        existing: list[dict] = []
        if out_path.exists():
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        existing.extend(rating.model_dump() for rating in ratings)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    print(f"{len(ratings)} pairwise ratings recorded -> {args.out}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="evals")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="probe one model and write a report")
    run_parser.add_argument("--out", required=True, help="report JSON path")
    run_parser.add_argument(
        "--model", default=None, help="Ollama model tag (default: client default)"
    )
    run_parser.add_argument("--url", default="http://127.0.0.1:11434")
    run_parser.add_argument(
        "--base-path", default=None, help="identity dir (default: the live persona)"
    )
    run_parser.add_argument(
        "--probes",
        action="append",
        default=[],
        help="extra probe pack JSON (repeatable)",
    )
    run_parser.add_argument(
        "--no-shipped-packs",
        action="store_true",
        help="persona-derived and --probes packs only",
    )
    run_parser.add_argument(
        "--include-forgetting-reference",
        action="store_true",
        help="add the frozen forgetting-reference probes (persona-derived, "
        "not a shipped pack -- see evals/probes.py::forgetting_reference_probes). "
        "Any regression here is disqualifying for an adapter/model-swap gate "
        "regardless of scores elsewhere",
    )
    run_parser.add_argument(
        "--num-gpu",
        type=int,
        default=None,
        help="GPU layers to offload; pin it so both sides "
        "of a comparison load the model identically",
    )
    run_parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="permit running under MOCK_LLM_TEXT (report is stamped mock)",
    )
    run_parser.add_argument(
        "--path",
        choices=["llm", "action"],
        default="llm",
        help="what to measure. 'llm' (default) probes the "
        "persona prompt straight into the model -- "
        "the seam a fine-tuned adapter changes. "
        "'action' runs each probe through the real "
        "ActionService, so the report also covers "
        "action.py's prompt construction, <thought> "
        "stripping, sanitization and self-correction. "
        "Reports from the two paths cannot be "
        "compared with each other",
    )

    conv_parser = sub.add_parser(
        "run-conversation",
        help="probe recall of a fact planted earlier in a conversation",
    )
    conv_parser.add_argument("--out", required=True, help="report JSON path")
    conv_parser.add_argument("--model", default=None)
    conv_parser.add_argument("--url", default="http://127.0.0.1:11434")
    conv_parser.add_argument(
        "--base-path", default=None, help="identity dir (default: the live persona)"
    )
    conv_parser.add_argument(
        "--pack",
        default=None,
        help="conversation probe pack JSON (default: the shipped pack)",
    )
    conv_parser.add_argument(
        "--window", type=int, default=6, help="turns kept by the recent_window strategy"
    )
    conv_parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="context window (default: the harness's "
        "pinned value); too small and the runtime "
        "truncates the planted fact away",
    )
    conv_parser.add_argument(
        "--num-gpu",
        type=int,
        default=None,
        help="GPU layers to offload; pin it so both sides "
        "of a comparison load the model identically",
    )
    conv_parser.add_argument(
        "--retrieval",
        action="append",
        default=[],
        choices=["bm25", "memory"],
        help="add retrieval-backed strategies "
        "(repeatable). 'bm25' is the infra-free "
        "control. 'memory' is the real MemoryStore: "
        "it needs Postgres, Qdrant and Neo4j up and "
        "it WRITES every transcript turn into them, "
        "removing them again at the end -- point it "
        "at the agent's live databases only if that "
        "is what you mean to do",
    )
    conv_parser.add_argument("--allow-mock", action="store_true")

    cmp_parser = sub.add_parser("compare", help="diff two reports")
    cmp_parser.add_argument("baseline")
    cmp_parser.add_argument("candidate")
    cmp_parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit 1 if any baseline-passing probe fails",
    )
    cmp_parser.add_argument("--allow-mock", action="store_true")

    rate_parser = sub.add_parser(
        "rate", help="blinded absolute human rating of one report's responses"
    )
    rate_parser.add_argument("report", help="report JSON path (rewritten in place)")
    rate_parser.add_argument(
        "--rater-id", default=getpass.getuser(), help="tag identifying the rater"
    )

    pairwise_parser = sub.add_parser(
        "rate-pairwise",
        help="blinded pairwise human rating between two reports' answers "
        "to the same probes",
    )
    pairwise_parser.add_argument("report_a", help="first report JSON path")
    pairwise_parser.add_argument("report_b", help="second report JSON path")
    pairwise_parser.add_argument(
        "--out",
        required=True,
        help="pairwise-comparison JSON path (appended to, neither input "
        "report is modified)",
    )
    pairwise_parser.add_argument(
        "--rater-id", default=getpass.getuser(), help="tag identifying the rater"
    )
    pairwise_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed the per-probe presentation-order randomization "
        "(default: OS randomness); set for a reproducible rating session",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        return asyncio.run(_cmd_run(args))
    if args.command == "run-conversation":
        return asyncio.run(_cmd_run_conversation(args))
    if args.command == "rate":
        return _cmd_rate(args)
    if args.command == "rate-pairwise":
        return _cmd_rate_pairwise(args)
    return _cmd_compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
