"""
Subject Metrics — Shared NATS Mesh Observability

Provides a unified counter + latency tracker for NATS subjects.
Used by BaseAgent, CognitiveService, and SurfacingAgent instead
of duplicated metric methods.
"""

import logging
import time
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class SubjectMetrics:
    """
    Accumulates per-subject message counts and end-to-end latency samples.
    Logs a summary line at configurable intervals.
    """

    def __init__(
        self,
        tracked_subjects: Set[str],
        log_every: int = 25,
        tag: str = "SubjectMetrics",
    ):
        self._tracked_subjects = tracked_subjects
        self._log_every = max(1, log_every)
        self._tag = tag
        self._metrics: Dict[str, Dict[str, float]] = {}

    def _ensure_key(self, key: str) -> Dict[str, float]:
        return self._metrics.setdefault(
            key,
            {"count": 0.0, "latency_total_ms": 0.0, "latency_samples": 0.0},
        )

    def record(
        self,
        subject: str,
        *,
        direction: str = "rx",
        latency_ms: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """Record a subject event with optional latency."""
        if subject not in self._tracked_subjects:
            return

        key = f"{direction}:{subject}"
        metric = self._ensure_key(key)
        metric["count"] += 1

        # Explicit latency
        if latency_ms is not None:
            metric["latency_total_ms"] += latency_ms
            metric["latency_samples"] += 1

        # Extract latency from embedded metadata
        if data and isinstance(data, dict):
            metadata = data.get("latency_metadata")
            if isinstance(metadata, dict) and metadata.get("start_time") is not None:
                try:
                    end_to_end_ms = max(
                        0.0, (time.time() - float(metadata["start_time"])) * 1000
                    )
                    metric["latency_total_ms"] += end_to_end_ms
                    metric["latency_samples"] += 1
                except (TypeError, ValueError):
                    pass

        count = int(metric["count"])
        if count == 1 or count % self._log_every == 0:
            avg_latency = 0.0
            if metric["latency_samples"] > 0:
                avg_latency = metric["latency_total_ms"] / metric["latency_samples"]
            logger.info(
                "[%s][%s] subject=%s count=%s avg_latency_ms=%.2f",
                self._tag,
                direction,
                subject,
                count,
                avg_latency,
            )

    @staticmethod
    def compute_latency(start_time) -> Optional[float]:
        """Compute millisecond latency from a monotonic start_time."""
        try:
            return max(0.0, (time.time() - float(start_time)) * 1000)
        except (TypeError, ValueError):
            return None
