"""Wire shapes for the behavioral eval harness.

Everything a run produces is meant to be diffed later — possibly months later,
against a fine-tuned descendant of today's model — so reports are versioned,
self-describing Pydantic models serialized to JSON, never ad-hoc dicts.

Provenance is load-bearing, not metadata. This repo has already shipped one
evaluation path whose numbers came from a mock fitted to the corpus (finding
B1); every report therefore carries where its text actually came from, and the
CLI refuses to treat a mock-provenance report as evidence unless explicitly
overridden.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

REPORT_SCHEMA_VERSION = 1

Category = Literal["identity", "boundary", "memory", "custom"]

CheckKind = Literal[
    "must_include",
    "must_include_any",
    "must_not_include",
    "must_match",
    "must_not_match",
    "boundary",
]


class Check(BaseModel):
    """One deterministic assertion against a response.

    ``boundary`` takes no values: it delegates to the production
    ``IdentityManager.validate_response``, so eval and runtime share one
    definition of what crosses a line.
    """

    kind: CheckKind
    values: List[str] = Field(default_factory=list)


class Probe(BaseModel):
    id: str = Field(min_length=1)
    category: Category
    prompt: str = Field(min_length=1)
    checks: List[Check] = Field(min_length=1)
    # Where the probe came from: "persona-derived" or the pack filename.
    # Recorded so a report can be audited without the probe files at hand.
    source: str = "unknown"


class CheckResult(BaseModel):
    kind: CheckKind
    passed: bool
    detail: str = ""


class ProbeResult(BaseModel):
    probe_id: str
    category: Category
    prompt: str
    response: str
    checks: List[CheckResult]
    passed: bool
    score: float  # fraction of checks passed, in [0, 1]


class CategorySummary(BaseModel):
    probes: int
    passed: int
    mean_score: float


class EvalReport(BaseModel):
    schema_version: int = REPORT_SCHEMA_VERSION
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model: str
    persona_name: str
    provenance: Literal["live", "mock"]
    options: Dict[str, Any]
    results: List[ProbeResult]
    by_category: Dict[str, CategorySummary]


class ProbeDelta(BaseModel):
    probe_id: str
    category: Category
    baseline_score: float
    candidate_score: float
    delta: float


class ComparisonReport(BaseModel):
    schema_version: int = REPORT_SCHEMA_VERSION
    baseline_model: str
    candidate_model: str
    baseline_provenance: Literal["live", "mock"]
    candidate_provenance: Literal["live", "mock"]
    # A regression is a probe the baseline passed and the candidate failed —
    # the hard gate. Score dips that stay above passing land in `declines`.
    regressions: List[ProbeDelta]
    improvements: List[ProbeDelta]
    declines: List[ProbeDelta]
    unchanged: int
    only_in_baseline: List[str]
    only_in_candidate: List[str]
    by_category_delta: Dict[str, float]

    @property
    def gate_passed(self) -> bool:
        return not self.regressions


class RunOptions(BaseModel):
    """Sampling options pinned for reproducibility.

    Greedy decoding plus a fixed seed is as deterministic as Ollama gets; it is
    still only reproducible on the same build and hardware, which is why the
    options travel inside the report instead of being assumed.
    """

    temperature: float = 0.0
    seed: int = 42
    top_p: float = 1.0
    num_predict: int = 192

    def as_override(self) -> Dict[str, Any]:
        return self.model_dump()


DEFAULT_OPTIONS = RunOptions()


def summarize_by_category(results: List[ProbeResult]) -> Dict[str, CategorySummary]:
    grouped: Dict[str, List[ProbeResult]] = {}
    for result in results:
        grouped.setdefault(result.category, []).append(result)
    return {
        category: CategorySummary(
            probes=len(items),
            passed=sum(1 for item in items if item.passed),
            mean_score=sum(item.score for item in items) / len(items),
        )
        for category, items in grouped.items()
    }


def load_report(path: str) -> EvalReport:
    with open(path, "r", encoding="utf-8") as handle:
        return EvalReport.model_validate_json(handle.read())


def save_report(report: EvalReport, path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report.model_dump_json(indent=2))
