"""Diff two eval reports: the before/after half of the harness.

This is the piece Fine-Tuned Adapter actually gates on. A consolidation run produces a
candidate model; the loop runs the same probes against baseline and candidate
and adopts the adapter only if `gate_passed` — no probe the baseline passed
now fails — while memory-recall improvements are what it was hoping to buy.

"Regression" is deliberately pass/fail, not a score threshold. A score delta
of -0.1 on a three-check probe is one check flipping; deciding how much of
that is tolerable would be a tuning knob nobody has measured yet. Pass/fail
regressions are unarguable, which is what a gate needs to be.
"""

from .schema import ComparisonReport, EvalReport, OptionDiff, ProbeDelta


class ComparisonInputError(ValueError):
    """The two reports cannot be treated as one before/after experiment."""


class PathMismatch(ComparisonInputError):
    """Raised when the two reports were produced by different execution paths.

    This is the one input disagreement `compare` refuses outright, and the
    asymmetry is deliberate. Sampling options and persona edits are *inputs to
    the same measurement*: the caller may have changed one on purpose, the
    deltas still mean something, and `diff_options`'s own docstring argues that
    a gate blocking a deliberate change would simply get bypassed. Both are
    therefore surfaced loudly and left to the reader.

    A path difference is not that. "llm" and "action" do not sample the same
    quantity -- one is the model's answer to the persona prompt, the other is
    what a full turn produced after `action.py` rebuilt the prompt around it,
    stripped `<thought>`, sanitized markup and possibly ran a self-correction
    retry. Every probe delta between them is attributable to the harness. There
    is no reading of such a diff that says anything about the model, so there
    is nothing for a reader to weigh and no deliberate case to preserve.
    """


class SuiteMismatch(ComparisonInputError):
    """Reports came from different eval suites despite sharing a path label."""


class ProbeSetMismatch(ComparisonInputError):
    """The reports do not identify the same executed probe fixture."""


class NoSharedProbes(ComparisonInputError):
    """A comparison with no common probes cannot establish a green gate."""


def require_same_path(baseline: EvalReport, candidate: EvalReport) -> None:
    if baseline.path != candidate.path:
        raise PathMismatch(
            f"baseline was run on the {baseline.path!r} path and candidate on "
            f"the {candidate.path!r} path. These do not measure the same "
            "thing: every probe difference between them is the harness, not "
            "the model. Re-run both on one path before comparing."
        )
    if baseline.suite != candidate.suite or baseline.suite == "unknown":
        raise SuiteMismatch(
            f"baseline suite={baseline.suite!r}, candidate suite={candidate.suite!r}; "
            "compare reports from one known suite only"
        )


def diff_options(baseline: EvalReport, candidate: EvalReport) -> list[OptionDiff]:
    """Sampling options the two runs did not share.

    Worth its own pass because the harness's whole claim is that a probe flip
    means the model changed. That holds only if everything else held, and the
    options are the everything else. An option present in one report and absent
    from the other counts as a difference: absence is a real setting, not a
    missing field to be forgiven.
    """
    names = sorted(set(baseline.options) | set(candidate.options))
    diffs: list[OptionDiff] = []
    for name in names:
        in_baseline = name in baseline.options
        in_candidate = name in candidate.options
        base_value = baseline.options.get(name)
        cand_value = candidate.options.get(name)
        # Presence is compared before value, so an option that is absent on one
        # side and explicitly null on the other is still a difference. Reading
        # both as `None` would collapse "unpinned" and "pinned to null" into
        # agreement.
        if (in_baseline, base_value) == (in_candidate, cand_value):
            continue
        diffs.append(
            OptionDiff(
                name=name,
                baseline=base_value,
                candidate=cand_value,
                in_baseline=in_baseline,
                in_candidate=in_candidate,
            )
        )
    return diffs


def compare_reports(baseline: EvalReport, candidate: EvalReport) -> ComparisonReport:
    require_same_path(baseline, candidate)

    base_by_id = {result.probe_id: result for result in baseline.results}
    cand_by_id = {result.probe_id: result for result in candidate.results}
    shared = [pid for pid in base_by_id if pid in cand_by_id]
    only_in_baseline = sorted(set(base_by_id) - set(cand_by_id))
    only_in_candidate = sorted(set(cand_by_id) - set(base_by_id))
    if not shared:
        raise NoSharedProbes(
            "baseline and candidate have no shared probe ids; a green gate "
            "cannot be established"
        )
    if only_in_baseline or only_in_candidate:
        raise ProbeSetMismatch(
            "baseline and candidate did not execute the same probe ids; "
            "regenerate both with one identical probe set"
        )
    if (
        baseline.probe_set_sha256
        and candidate.probe_set_sha256
        and baseline.probe_set_sha256 != candidate.probe_set_sha256
    ):
        raise ProbeSetMismatch(
            "baseline and candidate used different probe-set fixtures; "
            "regenerate both with the same pack"
        )

    regressions: list[ProbeDelta] = []
    improvements: list[ProbeDelta] = []
    declines: list[ProbeDelta] = []
    unchanged = 0

    for pid in shared:
        base, cand = base_by_id[pid], cand_by_id[pid]
        if base.category != cand.category or (
            base.prompt_sha256
            and cand.prompt_sha256
            and base.prompt_sha256 != cand.prompt_sha256
        ):
            raise ProbeSetMismatch(
                f"probe {pid!r} differs between reports; regenerate both "
                "with one identical probe set"
            )
        delta = ProbeDelta(
            probe_id=pid,
            category=base.category,
            baseline_score=base.score,
            candidate_score=cand.score,
            delta=cand.score - base.score,
        )
        if base.passed and not cand.passed:
            regressions.append(delta)
        elif cand.score > base.score:
            improvements.append(delta)
        elif cand.score < base.score:
            declines.append(delta)
        else:
            unchanged += 1

    by_category_delta: dict[str, float] = {}
    categories = set(baseline.by_category) | set(candidate.by_category)
    for category in sorted(categories):
        base_mean = (
            baseline.by_category[category].mean_score
            if category in baseline.by_category
            else 0.0
        )
        cand_mean = (
            candidate.by_category[category].mean_score
            if category in candidate.by_category
            else 0.0
        )
        by_category_delta[category] = cand_mean - base_mean

    return ComparisonReport(
        baseline_model=baseline.model,
        candidate_model=candidate.model,
        baseline_provenance=baseline.provenance,
        candidate_provenance=candidate.provenance,
        path=baseline.path,
        option_diffs=diff_options(baseline, candidate),
        persona_prompt_differs=bool(
            baseline.system_prompt_sha256
            and candidate.system_prompt_sha256
            and baseline.system_prompt_sha256 != candidate.system_prompt_sha256
        ),
        regressions=regressions,
        improvements=improvements,
        declines=declines,
        unchanged=unchanged,
        only_in_baseline=only_in_baseline,
        only_in_candidate=only_in_candidate,
        by_category_delta=by_category_delta,
    )


def render_comparison(comparison: ComparisonReport) -> str:
    lines = [
        (f"baseline:  {comparison.baseline_model} [{comparison.baseline_provenance}]"),
        (
            f"candidate: {comparison.candidate_model} "
            f"[{comparison.candidate_provenance}]"
        ),
        f"path:      {comparison.path}",
        "",
    ]
    if comparison.path == "action":
        lines += [
            "(action path: responses came through the real ActionService, so",
            "this diff covers action.py's prompt construction, <thought>",
            "stripping, sanitization and self-correction as well as the model.)",
            "",
        ]
    if "mock" in (comparison.baseline_provenance, comparison.candidate_provenance):
        lines += [
            "!! MOCK PROVENANCE — these responses came from the deterministic",
            "!! mock, not a model. This comparison is a plumbing check, not",
            "!! evidence about model behavior.",
            "",
        ]

    if comparison.persona_prompt_differs:
        lines += [
            "!! PERSONA PROMPT DIFFERS between these runs. The agent was not",
            "!! the same one in both, so a probe flip is at least as likely to",
            "!! be the persona edit as the model.",
            "",
        ]

    if comparison.option_diffs:
        lines.append("!! SAMPLING OPTIONS DIFFER between these runs:")
        for item in comparison.option_diffs:
            lines.append(
                f"!!   {item.name}: {item.describe('baseline')} -> "
                f"{item.describe('candidate')}"
            )
        lines += [
            "!! Every delta below is attributable to the option change as well",
            "!! as to the model. Re-run both under one configuration before",
            "!! reading a probe flip as a behavior change.",
            "",
        ]

    for category, delta in comparison.by_category_delta.items():
        lines.append(f"  {category:<10} mean score delta {delta:+.3f}")
    lines.append("")

    if comparison.regressions:
        lines.append("REGRESSIONS (baseline passed, candidate failed):")
        for item in comparison.regressions:
            lines.append(
                f"  - {item.probe_id} ({item.category}) "
                f"{item.baseline_score:.2f} -> {item.candidate_score:.2f}"
            )
    else:
        lines.append("No regressions.")

    if comparison.improvements:
        lines.append("Improvements:")
        for item in comparison.improvements:
            lines.append(f"  + {item.probe_id} ({item.delta:+.2f})")
    if comparison.declines:
        lines.append("Score declines (still passing):")
        for item in comparison.declines:
            lines.append(f"  ~ {item.probe_id} ({item.delta:+.2f})")

    for label, ids in (
        ("Only in baseline", comparison.only_in_baseline),
        ("Only in candidate", comparison.only_in_candidate),
    ):
        if ids:
            lines.append(f"{label}: {', '.join(ids)}")

    lines.append("")
    lines.append(f"GATE: {'PASS' if comparison.gate_passed else 'FAIL'}")
    return "\n".join(lines)
