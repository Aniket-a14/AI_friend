import logging
import time

from app.metrics import SubjectMetrics


def test_record_ignores_untracked_subject():
    metrics = SubjectMetrics(tracked_subjects={"chat.input"})
    try:
        metrics.record("chat.output", direction="tx")
        metrics._queue.join()

        assert metrics._metrics == {}
    finally:
        metrics.shutdown()


def test_record_accumulates_count_and_latency(caplog):
    metrics = SubjectMetrics(tracked_subjects={"chat.input"}, log_every=2, tag="TestMetrics")
    try:
        with caplog.at_level(logging.INFO):
            metrics.record("chat.input", direction="rx", latency_ms=15.0)
            metrics.record(
                "chat.input",
                direction="rx",
                data={"latency_metadata": {"start_time": time.time() - 0.02}},
            )
            # Synchronize with background queue processing while log capturing is active
            metrics._queue.join()

        key = "rx:chat.input"
        assert metrics._metrics[key]["count"] == 2.0
        assert metrics._metrics[key]["latency_samples"] == 2.0
        assert metrics._metrics[key]["latency_total_ms"] >= 15.0
        assert any("[TestMetrics][rx] subject=chat.input count=2" in r.message for r in caplog.records)
    finally:
        metrics.shutdown()


def test_record_ignores_invalid_metadata():
    metrics = SubjectMetrics(tracked_subjects={"chat.input"})
    try:
        metrics.record("chat.input", data={"latency_metadata": {"start_time": "not-a-number"}})
        metrics._queue.join()

        key = "rx:chat.input"
        assert metrics._metrics[key]["count"] == 1.0
        assert metrics._metrics[key]["latency_samples"] == 0.0
        assert metrics._metrics[key]["latency_total_ms"] == 0.0
    finally:
        metrics.shutdown()


def test_compute_latency_handles_valid_and_invalid_start_time(monkeypatch):
    monkeypatch.setattr("app.metrics.time.time", lambda: 101.5)

    assert SubjectMetrics.compute_latency(100.0) == 1500.0
    assert SubjectMetrics.compute_latency("bad") is None
