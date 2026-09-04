"""Domain calibration and deterministic metacognitive action directives."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MetacognitiveDirective(str, Enum):
    """An explicit next action selected from calibrated confidence."""

    PROCEED = "PROCEED"
    HEDGE = "HEDGE"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    VERIFY = "VERIFY"
    ABSTAIN = "ABSTAIN"


class DomainCalibration(BaseModel):
    """Incremental empirical confidence calibration for one domain."""

    domain: str
    sample_count: int = 0
    brier_score: float = 0.0
    expected_calibration_error: float = 0.0

    def record_observation(
        self, predicted_prob: float, actual_binary_outcome: int
    ) -> None:
        """Update the Brier score from one observed binary outcome."""
        count = self.sample_count
        squared_error = (predicted_prob - actual_binary_outcome) ** 2
        self.brier_score = (self.brier_score * count + squared_error) / (count + 1)
        self.sample_count = count + 1

    def calibrate(self, raw_confidence: float) -> float:
        """Discount raw confidence according to observed Brier error."""
        return raw_confidence * (1.0 - 0.5 * min(1.0, self.brier_score))


class CapabilityLimitationModel(BaseModel):
    """Known limitations and calibrated gating for a possible response."""

    known_limitations: list[str] = Field(default_factory=list)
    domain_calibrations: dict[str, DomainCalibration] = Field(default_factory=dict)

    def is_known_limitation(self, query: str) -> bool:
        """Return whether a query contains a declared limitation phrase."""
        normalized_query = query.lower()
        for limitation in self.known_limitations:
            if not limitation.strip():
                continue
            if limitation.lower() in normalized_query:
                return True
        return False

    def evaluate_directive(
        self, domain: str, raw_confidence: float, query: str = ""
    ) -> tuple[MetacognitiveDirective, float]:
        """Choose a deterministic directive from limitations and calibration."""
        if self.is_known_limitation(query):
            return MetacognitiveDirective.ABSTAIN, 0.0

        calibration = self.domain_calibrations.get(domain)
        calibrated = (
            calibration.calibrate(raw_confidence)
            if calibration is not None
            else raw_confidence
        )
        if calibrated >= 0.75:
            return MetacognitiveDirective.PROCEED, calibrated
        if calibrated >= 0.50:
            return MetacognitiveDirective.HEDGE, calibrated
        if calibrated >= 0.30:
            return MetacognitiveDirective.ASK_CLARIFICATION, calibrated
        return MetacognitiveDirective.VERIFY, calibrated
