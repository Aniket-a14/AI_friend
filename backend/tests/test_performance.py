import time

import pytest

from app.metrics import SubjectMetrics
from app.utils.segmentation import HybridSegmenter

pytest.importorskip("pytest_benchmark")


@pytest.mark.benchmark
def test_hybrid_segmenter_benchmark(benchmark):
    segmenter = HybridSegmenter(target_size=8)
    words = ["hello", "there,", "how", "are", "you?", "today"] * 200

    def run():
        return [segmenter.score_split_point(word, i % 14) for i, word in enumerate(words)]

    scores = benchmark(run)
    assert len(scores) == len(words)


@pytest.mark.benchmark
def test_subject_metrics_record_benchmark(benchmark):
    metrics = SubjectMetrics(tracked_subjects={"chat.input"})
    payload = {"latency_metadata": {"start_time": time.time() - 0.01}}

    def run():
        metrics.record("chat.input", direction="rx", data=payload)
        return metrics._metrics["rx:chat.input"]["count"]

    count = benchmark(run)
    assert count >= 1


@pytest.mark.latency
def test_compute_latency_never_negative(monkeypatch):
    monkeypatch.setattr("app.metrics.time.time", lambda: 10.0)
    assert SubjectMetrics.compute_latency(20.0) == 0.0
