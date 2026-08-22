"""Wire shape for Stage 3 measurement reports (audit/ROADMAP.md §7).

Mirrors evals/schema.py's provenance discipline on purpose: a report says
where its numbers came from, and every figure inside it carries one of
HARDWARE.md §0's three labels so a reader never has to guess whether a number
was produced by a command or invented to fill a table.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

REPORT_SCHEMA_VERSION = 1

Label = Literal["MEASURED", "ESTIMATED", "UNKNOWN"]


class Figure(BaseModel):
    """One reported number (or explicit absence of one)."""

    label: Label
    value: float | int | str | None = None
    unit: str = ""
    # For ESTIMATED: the measured inputs and the arithmetic, so the derivation
    # can be checked or rejected rather than taken on faith.
    derivation: str = ""
    # For UNKNOWN: why this could not be measured here.
    reason: str = ""


class Run(BaseModel):
    """One repetition of a measurement. evals/'s own history here is the
    reason repeats exist at all: a 'deterministic' harness was not
    reproducible until the runtime's starting state stopped being implicit.
    A single run with no second data point is an anecdote, not a measurement.
    """

    figures: dict[str, Figure]
    raw: dict[str, Any] = Field(default_factory=dict)


class MeasurementReport(BaseModel):
    schema_version: int = REPORT_SCHEMA_VERSION
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    measurement_id: str  # "1.1", "1.2", ...
    title: str
    # Same rule evals/ enforces: a mock-sourced report is never evidence
    # unless the caller explicitly says so.
    provenance: Literal["live", "mock"]
    runs: list[Run]
    notes: list[str] = Field(default_factory=list)

    def summary(self) -> dict[str, Figure]:
        """Merge figures across runs: MEASURED figures report min/max spread
        in their derivation text when they disagree across runs; a figure
        present in only one run is reported as-is with that noted.
        """
        if not self.runs:
            return {}
        if len(self.runs) == 1:
            return self.runs[0].figures

        merged: dict[str, Figure] = {}
        keys = {k for run in self.runs for k in run.figures}
        for key in keys:
            values = [run.figures[key] for run in self.runs if key in run.figures]
            first = values[0]
            if first.label != "MEASURED" or not all(
                isinstance(v.value, (int, float)) for v in values
            ):
                merged[key] = first
                continue
            nums = [float(v.value) for v in values]  # type: ignore[arg-type]
            spread = max(nums) - min(nums)
            merged[key] = Figure(
                label="MEASURED",
                value=sum(nums) / len(nums),
                unit=first.unit,
                derivation=(
                    f"mean of {len(nums)} runs; spread {spread:.4g} "
                    f"(min {min(nums):.4g}, max {max(nums):.4g})"
                ),
            )
        return merged
