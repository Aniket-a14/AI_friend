"""
Subject Metrics — Shared NATS Mesh Observability

Provides a unified counter + latency tracker for NATS subjects.
Used by BaseAgent, CognitiveService, and SurfacingAgent instead
of duplicated metric methods.
"""

import logging
import math
import threading
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class SubjectMetrics:
    """
    Accumulates per-subject message counts and end-to-end latency samples.
    Runs asynchronously using a daemon background worker thread to eliminate
    any synchronous logging/formatting overhead in critical real-time execution loops.
    """

    def __init__(
        self,
        tracked_subjects: set[str],
        log_every: int = 25,
        tag: str = "SubjectMetrics",
    ):
        self._tracked_subjects = tracked_subjects
        self._log_every = max(1, log_every)
        self._tag = tag
        self._metrics: dict[str, dict[str, Any]] = {}

        # High-performance list-based atomic double buffer
        self._buffer: list[tuple[str, str, float | None, dict[str, Any] | None, float]] = []
        self._lock = threading.Lock()

        # Thread-safe queue interface for compatibility with legacy tests
        class CompatibilityQueue:
            def __init__(self, parent):
                self.parent = parent

            def qsize(self):
                return len(self.parent._buffer)

            def join(self, timeout: float = 5.0):
                """Block until the buffer drains, or `timeout` elapses.

                Bounded deliberately. This spun on `while buffer or processing`
                with no exit, so if the worker thread died the caller hung
                forever with no diagnostic -- a dead metrics thread would
                present as a frozen test run or a hung shutdown, which is a long
                way from where the fault actually is.

                Returns True if the buffer drained, False on timeout, so a
                caller can tell the difference. `time` is imported at module
                scope; the local re-import here shadowed it for no reason.
                """
                deadline = time.monotonic() + timeout
                while self.parent._buffer or getattr(
                    self.parent, "_is_processing", False
                ):
                    if time.monotonic() >= deadline:
                        logger.warning(
                            "[Metrics] join() timed out after %.1fs with %d "
                            "buffered event(s); worker may have died.",
                            timeout,
                            len(self.parent._buffer),
                        )
                        return False
                    time.sleep(0.01)
                return True

        self._queue = CompatibilityQueue(self)
        self._is_processing = False

        self._shutdown_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._process_buffer, daemon=True, name="SubjectMetricsWorker"
        )
        self._worker_thread.start()

    def _ensure_key(self, key: str) -> dict[str, Any]:
        return self._metrics.setdefault(
            key,
            {
                "count": 0.0,
                "latency_total_ms": 0.0,
                "latency_samples": 0.0,
                "recent_latencies": deque(maxlen=1000),
                "last_event_time": None,
                "inter_arrival_times": deque(maxlen=1000),
            },
        )

    def _get_percentile(self, data: list, percentile: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        d0 = sorted_data[int(f)] * (c - k)
        d1 = sorted_data[int(c)] * (k - f)
        return d0 + d1

    def record(
        self,
        subject: str,
        *,
        direction: str = "rx",
        latency_ms: float | None = None,
        data: dict[str, Any] | None = None,
    ):
        """Record a subject event quickly using atomic appends."""
        if subject not in self._tracked_subjects:
            return

        # Pre-capture high-precision event timestamp on the calling thread
        event_time = time.time()

        # Atomic list append (completely lock-free and GIL-safe in CPython)
        self._buffer.append((subject, direction, latency_ms, data, event_time))

    def _process_buffer(self):
        """Background worker thread consuming and aggregating telemetry events from the atomic buffer."""
        while not self._shutdown_event.is_set():
            time.sleep(0.05)  # Rest CPU, batching up to 50ms worth of updates

            if not self._buffer:
                continue

            # Atomically swap active buffer under a quick lock
            with self._lock:
                batch = self._buffer
                self._buffer = []

            self._is_processing = True
            # Aggregate batch items
            for item in batch:
                try:
                    subject, direction, latency_ms, data, event_time = item
                    key = f"{direction}:{subject}"
                    metric = self._ensure_key(key)
                    metric["count"] += 1

                    # Track inter-arrival timings for Jitter Index
                    if metric["last_event_time"] is not None:
                        diff_ms = max(
                            0.0,
                            (event_time - float(metric["last_event_time"])) * 1000.0,
                        )
                        metric["inter_arrival_times"].append(diff_ms)
                    metric["last_event_time"] = event_time

                    # Explicit latency
                    recorded_latency = None
                    if latency_ms is not None:
                        metric["latency_total_ms"] += latency_ms
                        metric["latency_samples"] += 1
                        recorded_latency = latency_ms

                    # Extract latency from embedded metadata using pre-captured event_time
                    if data and isinstance(data, dict):
                        metadata = data.get("latency_metadata")
                        if (
                            isinstance(metadata, dict)
                            and metadata.get("start_time") is not None
                        ):
                            try:
                                end_to_end_ms = max(
                                    0.0,
                                    (event_time - float(metadata["start_time"])) * 1000,
                                )
                                metric["latency_total_ms"] += end_to_end_ms
                                metric["latency_samples"] += 1
                                recorded_latency = end_to_end_ms
                            except (TypeError, ValueError):
                                pass

                    if recorded_latency is not None:
                        metric["recent_latencies"].append(recorded_latency)

                    count = int(metric["count"])
                    if count == 1 or count % self._log_every == 0:
                        avg_latency = 0.0
                        p95 = 0.0
                        p99 = 0.0
                        jitter = 0.0

                        recent = list(metric["recent_latencies"])
                        if metric["latency_samples"] > 0:
                            avg_latency = (
                                metric["latency_total_ms"] / metric["latency_samples"]
                            )
                        if recent:
                            p95 = self._get_percentile(recent, 95)
                            p99 = self._get_percentile(recent, 99)

                        inter_arrivals = list(metric["inter_arrival_times"])
                        if len(inter_arrivals) > 1:
                            mean_ia = sum(inter_arrivals) / len(inter_arrivals)
                            variance = sum(
                                (x - mean_ia) ** 2 for x in inter_arrivals
                            ) / len(inter_arrivals)
                            jitter = math.sqrt(variance)

                        logger.info(
                            "[%s][%s] subject=%s count=%d avg_latency=%.2fms p95=%.2fms p99=%.2fms jitter=%.2fms",
                            self._tag,
                            direction,
                            subject,
                            count,
                            avg_latency,
                            p95,
                            p99,
                            jitter,
                        )
                except Exception as e:
                    logger.error("Error in SubjectMetrics batch processing: %s", e)

            self._is_processing = False

    def shutdown(self, timeout: float = 1.0):
        """Gracefully shut down the background telemetry thread and flush buffer."""
        self._shutdown_event.set()
        try:
            self._worker_thread.join(timeout=timeout)
        except RuntimeError:
            pass

        # Final drain of remaining items
        if self._buffer:
            batch = self._buffer
            self._buffer = []
            for item in batch:
                try:
                    subject, direction, latency_ms, data, event_time = item
                    key = f"{direction}:{subject}"
                    metric = self._ensure_key(key)
                    metric["count"] += 1
                    if latency_ms is not None:
                        metric["latency_total_ms"] += latency_ms
                        metric["latency_samples"] += 1
                    if data and isinstance(data, dict):
                        metadata = data.get("latency_metadata")
                        if (
                            isinstance(metadata, dict)
                            and metadata.get("start_time") is not None
                        ):
                            try:
                                end_to_end_ms = max(
                                    0.0,
                                    (event_time - float(metadata["start_time"])) * 1000,
                                )
                                metric["latency_total_ms"] += end_to_end_ms
                                metric["latency_samples"] += 1
                            except (TypeError, ValueError):
                                pass
                except Exception as e:
                    logger.debug("Skipping malformed metric item during shutdown drain: %s", e)

    @staticmethod
    def compute_latency(start_time) -> float | None:
        """Compute millisecond latency from a monotonic start_time."""
        try:
            return max(0.0, (time.time() - float(start_time)) * 1000)
        except (TypeError, ValueError):
            return None
