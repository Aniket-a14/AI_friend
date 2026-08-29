"""Behavioral eval harness — the before/after gate for model changes.

Separate from `app/` by design: production code must never import from here
(the audit's B1 rule — eval tooling out of production paths), while this
package freely imports production code, because the thing under test *is* the
production persona prompt and client.

Entry points:

    python -m evals run --out evals/out/baseline.json
    python -m evals compare evals/out/baseline.json evals/out/candidate.json

See ``evals/README.md`` for what this measures, what it refuses to claim, and
how the Fine-Tuned Adapter consolidation loop is expected to use it.
"""

from .compare import compare_reports, render_comparison
from .probes import collect_probes, load_pack, persona_probes, shipped_packs
from .runner import run_eval
from .schema import ComparisonReport, EvalReport, Probe, load_report, save_report

__all__ = [
    "ComparisonReport",
    "EvalReport",
    "Probe",
    "collect_probes",
    "compare_reports",
    "load_pack",
    "load_report",
    "persona_probes",
    "render_comparison",
    "run_eval",
    "save_report",
    "shipped_packs",
]
