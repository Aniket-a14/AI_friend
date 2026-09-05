"""Local Phase 03 micro-benchmarks (BM-LOC-P3-01, BM-LOC-P3-02, BM-LOC-P3-03).

Implements local benchmarks per orchestration/archive/phase_03/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

# Ensure backend root is on sys.path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.cognitive.appraisal import appraise_event
from app.cognitive.global_controls import derive_global_controls


def run_bm_loc_p3_01() -> dict[str, Any]:
    """BM-LOC-P3-01: Event Appraisal Throughput.

    10,000 sequential event evaluations through appraise_event.
    Target: p50 <= 10.0 us, p95 <= 20.0 us.
    """
    print("\n--- Running BM-LOC-P3-01: Event Appraisal Throughput ---")
    num_iterations = 10000
    active_goals = ["maintain_empathy", "share_insight", "support_user"]

    latencies_us: list[float] = []

    event_samples = [
        {
            "event_id": f"evt-{i}",
            "goal_id": active_goals[i % len(active_goals)],
            "novelty": (i % 10) / 10.0,
            "valence": ((i % 20) - 10) / 10.0,
            "arousal": (i % 10) / 10.0,
            "dominance": 0.0,
        }
        for i in range(100)
    ]

    for i in range(num_iterations):
        sample = event_samples[i % 100]
        expectation = (i % 5) / 5.0

        t0 = time.perf_counter_ns()
        record = appraise_event(sample, active_goals, expectation=expectation)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)
        assert record.event_id == sample["event_id"]

    latencies_us.sort()
    n = len(latencies_us)
    p50 = latencies_us[int(n * 0.50)]
    p95 = latencies_us[int(n * 0.95)]
    p99 = latencies_us[int(n * 0.99)]
    mean = sum(latencies_us) / n

    verdict = "PASS" if (p50 <= 10.0 and p95 <= 20.0) else "FAIL"

    res = {
        "benchmark_id": "BM-LOC-P3-01",
        "title": "Event Appraisal Throughput",
        "iterations": n,
        "mean_us": round(mean, 3),
        "p50_us": round(p50, 3),
        "p95_us": round(p95, 3),
        "p99_us": round(p99, 3),
        "min_us": round(latencies_us[0], 3),
        "max_us": round(latencies_us[-1], 3),
        "target_p50_us": "<= 10.0",
        "target_p95_us": "<= 20.0",
        "verdict": verdict,
    }
    print(json.dumps(res, indent=2))
    return res


def run_bm_loc_p3_02() -> dict[str, Any]:
    """BM-LOC-P3-02: Global Controls Derivation Latency.

    10,000 iterations of derive_global_controls.
    Target: p50 <= 5.0 us, p95 <= 10.0 us.
    """
    print("\n--- Running BM-LOC-P3-02: Global Controls Derivation Latency ---")
    num_iterations = 10000

    pad_samples = [
        {
            "pleasure": ((i % 20) - 10) / 10.0,
            "arousal": (i % 10) / 10.0,
            "dominance": 0.0,
        }
        for i in range(100)
    ]

    latencies_us: list[float] = []

    for i in range(num_iterations):
        affect_pad = pad_samples[i % 100]
        load = (i % 10) / 10.0
        urgency = (i % 8) / 10.0
        prediction_error = (i % 6) / 10.0

        t0 = time.perf_counter_ns()
        ctrls = derive_global_controls(affect_pad, load, urgency, prediction_error)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)
        assert 0.0 <= ctrls.urgency_gain <= 1.0

    latencies_us.sort()
    n = len(latencies_us)
    p50 = latencies_us[int(n * 0.50)]
    p95 = latencies_us[int(n * 0.95)]
    p99 = latencies_us[int(n * 0.99)]
    mean = sum(latencies_us) / n

    verdict = "PASS" if (p50 <= 5.0 and p95 <= 10.0) else "FAIL"

    res = {
        "benchmark_id": "BM-LOC-P3-02",
        "title": "Global Controls Derivation Latency",
        "iterations": n,
        "mean_us": round(mean, 3),
        "p50_us": round(p50, 3),
        "p95_us": round(p95, 3),
        "p99_us": round(p99, 3),
        "min_us": round(latencies_us[0], 3),
        "max_us": round(latencies_us[-1], 3),
        "target_p50_us": "<= 5.0",
        "target_p95_us": "<= 10.0",
        "verdict": verdict,
    }
    print(json.dumps(res, indent=2))
    return res


def run_bm_loc_p3_03() -> dict[str, Any]:
    """BM-LOC-P3-03: Modulated Candidate Selection Latency.

    10,000 iterations of scoring and selecting among 10 candidates with active
    global controls modulation through CandidateSelector.score_and_select.
    Target: p95 <= 50.0 us.
    """
    print("\n--- Running BM-LOC-P3-03: Modulated Candidate Selection Latency ---")
    num_iterations = 10000

    selector = CandidateSelector()
    active_goals = ["goal-friendship", "goal-support"]

    candidates = [
        ActionCandidate(
            candidate_id=f"c-{i}",
            kind="SPEAK" if i % 2 == 0 else "ASK",
            source="policy",
            target_goal_ids=["goal-friendship"] if i % 3 == 0 else [],
            constraint_claims=[f"claim_{i}"],
            risk=(i % 5) / 10.0,
            cost=(i % 4) / 10.0,
            uncertainty=(i % 6) / 10.0,
            score=0.5 + (i % 5) * 0.05,
        )
        for i in range(10)
    ]

    ctrl_samples = [
        derive_global_controls(
            {"pleasure": ((i % 20) - 10) / 10.0, "arousal": (i % 10) / 10.0},
            load=(i % 10) / 10.0,
            urgency=(i % 8) / 10.0,
            prediction_error=(i % 6) / 10.0,
        )
        for i in range(100)
    ]

    latencies_us: list[float] = []

    for i in range(num_iterations):
        controls = ctrl_samples[i % 100]

        t0 = time.perf_counter_ns()
        winner, rejected = selector.score_and_select(
            candidates, active_goals, global_controls=controls
        )
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)
        assert winner is not None
        assert len(rejected) == 9

    latencies_us.sort()
    n = len(latencies_us)
    p50 = latencies_us[int(n * 0.50)]
    p95 = latencies_us[int(n * 0.95)]
    p99 = latencies_us[int(n * 0.99)]
    mean = sum(latencies_us) / n

    verdict = "PASS" if p95 <= 50.0 else "FAIL"

    res = {
        "benchmark_id": "BM-LOC-P3-03",
        "title": "Modulated Candidate Selection Latency",
        "iterations": n,
        "candidates_per_iter": 10,
        "mean_us": round(mean, 3),
        "p50_us": round(p50, 3),
        "p95_us": round(p95, 3),
        "p99_us": round(p99, 3),
        "min_us": round(latencies_us[0], 3),
        "max_us": round(latencies_us[-1], 3),
        "target_p95_us": "<= 50.0",
        "verdict": verdict,
    }
    print(json.dumps(res, indent=2))
    return res


def main():
    print("==================================================================")
    print(" Phase 03 Local Benchmarks (BM-LOC-P3-01, BM-LOC-P3-02, BM-LOC-P3-03)")
    print("==================================================================")

    results = {}
    results["BM-LOC-P3-01"] = run_bm_loc_p3_01()
    results["BM-LOC-P3-02"] = run_bm_loc_p3_02()
    results["BM-LOC-P3-03"] = run_bm_loc_p3_03()

    out_dir = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_03")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "local_benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote local benchmark results to {out_path}")
    all_passed = all(r["verdict"] == "PASS" for r in results.values())
    print(f"\nOverall Local Benchmark Result: {'ALL PASS' if all_passed else 'SOME FAILED'}")
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
