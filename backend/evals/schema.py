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

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

REPORT_SCHEMA_VERSION = 1


def fingerprint(text: str) -> str:
    """Short digest identifying a prompt without reproducing it.

    A digest rather than the text itself for two reasons: the persona prompt is
    authored character content and a report is a shareable artifact, and the
    only question ever asked of it is "was this the same one", which equality
    answers.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


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

    Validation ensures non-boundary checks have non-empty values and that
    regex checks compile successfully.
    """

    kind: CheckKind
    values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_check_values(self) -> "Check":
        """Ensure values are provided for non-boundary checks and regex patterns compile."""
        if self.kind != "boundary" and not self.values:
            raise ValueError(
                f"Check kind '{self.kind}' requires non-empty values list"
            )

        if self.kind in ("must_match", "must_not_match"):
            for pattern in self.values:
                try:
                    re.compile(pattern)
                except re.error as e:
                    raise ValueError(
                        f"Invalid regex pattern '{pattern}' for check kind '{self.kind}': {e}"
                    )

        return self


class Probe(BaseModel):
    id: str = Field(min_length=1)
    category: Category
    prompt: str = Field(min_length=1)
    checks: list[Check] = Field(min_length=1)
    # Where the probe came from: "persona-derived" or the pack filename.
    # Recorded so a report can be audited without the probe files at hand.
    source: str = "unknown"


class CheckResult(BaseModel):
    kind: CheckKind
    passed: bool
    detail: str = ""


class Plant(BaseModel):
    """One fact placed in the transcript at a stated depth.

    ``after_filler`` is how many filler exchanges precede it, which is what
    makes a probe able to say *when* something was said. One fact needs only
    position zero; the interesting probes need more than one, and need them
    apart:

    - a fact and its later correction, to ask whether retrieval returns the
      current answer or the first one it ever heard;
    - a crowd of near-identical facts, to ask whether retrieval can pick the
      one that was asked about rather than the topic they share.

    ``answers`` marks the plants the recall question is actually about.
    Everything else is a distractor that is *supposed* to compete, and the
    distinction is load-bearing: `plant_visible` reports whether the answering
    facts reached the model, because a pass without them is a guess. A
    strategy that drops a distractor has made the probe easier, not invalid,
    so distractors must not count towards that flag.
    """

    text: str = Field(min_length=1)
    reply: str = "Got it."
    after_filler: int = Field(default=0, ge=0)
    answers: bool = True


class ConversationProbe(BaseModel):
    """A fact planted early, asked about later.

    ``filler_turns`` is the distance the fact has to survive, and it is the
    independent variable of the whole suite: a probe is the same question at a
    different remove, so a pack spans distances rather than repeating one.
    With several plants it is the *total* filler; a plant's own distance from
    the question is ``filler_turns - after_filler``.

    ``plant_reply`` is scripted like the filler, because the assistant's
    acknowledgement is part of the context the recall has to reach past, and
    generating it would put model noise inside the thing being measured.

    A probe is written either as a single ``plant`` or as a list of ``plants``,
    never both. The single form is not legacy sugar to be migrated away: most
    probes plant one fact at position zero, and making them spell out a
    one-element list would obscure that the multi-plant probes are doing
    something different.
    """

    id: str = Field(min_length=1)
    category: Category = "memory"
    plant: str = ""
    plant_reply: str = "Got it."
    plants: list[Plant] = Field(default_factory=list)
    filler_turns: int = Field(ge=0)
    recall_prompt: str = Field(min_length=1)
    checks: list[Check] = Field(min_length=1)
    source: str = "unknown"

    @model_validator(mode="after")
    def validate_plants(self) -> "ConversationProbe":
        """Reject probes whose plants could not be placed as written.

        Each of these silently produces a transcript that does not match what
        the pack author described, and the report has no column that would
        show it -- the probe simply measures something else and reads as a
        result.
        """
        if self.plant and self.plants:
            raise ValueError(
                f"probe {self.id!r} sets both 'plant' and 'plants'; use one"
            )
        if not self.plant and not self.plants:
            raise ValueError(f"probe {self.id!r} plants no fact")

        resolved = self.resolved_plants
        # A plant placed deeper than the filler runs would be emitted after the
        # last filler exchange, landing next to the question it is supposed to
        # be remembered across -- a probe that measures nothing but reports a
        # distance.
        too_deep = [p.text for p in resolved if p.after_filler > self.filler_turns]
        if too_deep:
            raise ValueError(
                f"probe {self.id!r} plants past its own filler ({self.filler_turns}): "
                f"{too_deep}"
            )
        if not any(p.answers for p in resolved):
            raise ValueError(
                f"probe {self.id!r} has no plant marked 'answers'; nothing in "
                "the transcript is the answer and `plant_visible` would be "
                "vacuously true"
            )
        return self

    @property
    def resolved_plants(self) -> list[Plant]:
        """The probe's plants, however it was written."""
        if self.plants:
            return list(self.plants)
        return [Plant(text=self.plant, reply=self.plant_reply)]


class ProbeResult(BaseModel):
    probe_id: str
    category: Category
    prompt: str
    response: str
    checks: list[CheckResult]
    passed: bool
    score: float  # fraction of checks passed, in [0, 1]

    # Multi-turn fields, absent on single-turn probes. They live here rather
    # than on a separate result type so that one `compare` implementation
    # serves both suites -- the harness exists to diff runs, and a second
    # report shape would mean a second, drifting comparison path.
    context_strategy: str | None = None
    context_turns: int | None = None
    context_chars: int | None = None
    # Whether the planted fact was actually in the context the model saw. A
    # pass with the plant dropped is not recall, it is a guess, and it means
    # the probe is measuring nothing.
    plant_visible: bool | None = None
    # Whether the rendered context fits inside num_ctx. False means the runtime
    # truncated it before the model read a token of the plant, so the probe is
    # unsound regardless of what the strategy selected.
    context_fits: bool | None = None


class CategorySummary(BaseModel):
    probes: int
    passed: int
    mean_score: float


class EvalReport(BaseModel):
    schema_version: int = REPORT_SCHEMA_VERSION
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    model: str
    persona_name: str
    provenance: Literal["live", "mock"]
    options: dict[str, Any]
    # Digest of the system prompt every probe in this run was generated under.
    # It is the largest single input to every response and the one most likely
    # to drift unnoticed between two runs: adaptive traits evolve through
    # reflection, and the identity seeds are editable files on disk. Without
    # it, a comparison across a persona edit reads as a model behavior change,
    # and nothing in the report contradicts that reading. Empty on reports
    # written before this field existed.
    system_prompt_sha256: str = ""
    results: list[ProbeResult]
    by_category: dict[str, CategorySummary]


class ProbeDelta(BaseModel):
    probe_id: str
    category: Category
    baseline_score: float
    candidate_score: float
    delta: float


class OptionDiff(BaseModel):
    """One sampling option the two runs did not agree on.

    Presence is carried separately from value because a value alone cannot
    express it: ``None`` would mean both "absent from that report" and "present
    and explicitly null", and for ``num_gpu`` those are different settings --
    unpinned versus a pinned value that happens to be falsy. `as_override`
    drops nulls so a report this harness wrote never contains one, but reports
    are long-lived artifacts and hand-edited ones exist.
    """

    name: str
    baseline: Any = None
    candidate: Any = None
    in_baseline: bool = True
    in_candidate: bool = True

    def describe(self, side: str) -> str:
        present = self.in_baseline if side == "baseline" else self.in_candidate
        return repr(getattr(self, side)) if present else "<unset>"


class ComparisonReport(BaseModel):
    schema_version: int = REPORT_SCHEMA_VERSION
    baseline_model: str
    candidate_model: str
    baseline_provenance: Literal["live", "mock"]
    candidate_provenance: Literal["live", "mock"]
    # Sampling options the two runs disagreed on. Greedy decoding reproduces
    # only for a fixed load configuration, so a diff here means the comparison
    # is measuring the configuration as much as the model. Surfaced, never
    # gated on: the caller may have changed an option on purpose, and a gate
    # that blocks a deliberate change would just get bypassed.
    option_diffs: list[OptionDiff] = Field(default_factory=list)
    # True when both reports fingerprinted their system prompt and the two
    # differ: the persona itself changed, so every delta below describes a
    # different agent as much as a different model. False when either report
    # predates the field, because "unknown" must not read as "verified same".
    persona_prompt_differs: bool = False
    # A regression is a probe the baseline passed and the candidate failed —
    # the hard gate. Score dips that stay above passing land in `declines`.
    regressions: list[ProbeDelta]
    improvements: list[ProbeDelta]
    declines: list[ProbeDelta]
    unchanged: int
    only_in_baseline: list[str]
    only_in_candidate: list[str]
    by_category_delta: dict[str, float]

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
    # Pinned explicitly because `OllamaClient` defaults it to 2048 and Ollama
    # truncates an over-long prompt *from the front* without saying so. For a
    # multi-turn recall probe the front is where the planted fact lives, so the
    # default would silently delete the thing under test and score the model's
    # prior instead -- a confident number measuring nothing.
    num_ctx: int = 8192
    # How many layers Ollama offloads to the GPU. Left unset, Ollama picks the
    # split at load time from whatever VRAM is free, and the split is an input
    # to the output: measured here, the same prompt all-CPU and part-GPU
    # returned different text. On this box the split did not drift on its own
    # across reloads, so leaving it unset was not the source of the run-to-run
    # differences chased down in `reset_model_state` -- but a machine whose
    # free VRAM differs between the two halves of a comparison would load the
    # model differently for each. Unset by default, because a fixed layer count
    # that does not fit the next machine is worse than an honest unpinned run,
    # and `compare` warns when two reports disagree. Pin it when a verdict
    # matters.
    num_gpu: int | None = None

    def as_override(self) -> dict[str, Any]:
        # `OllamaClient` merges this over its defaults, so a `None` would be
        # forwarded to Ollama as a null rather than read as "unset".
        return self.model_dump(exclude_none=True)


DEFAULT_OPTIONS = RunOptions()


def summarize_by_category(results: list[ProbeResult]) -> dict[str, CategorySummary]:
    grouped: dict[str, list[ProbeResult]] = {}
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
