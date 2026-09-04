"""Local Phase 02 micro-benchmarks (BM-LOC-P2-01, BM-LOC-P2-02, BM-LOC-P2-03).

Implements local benchmarks per orchestration/PHASE_02/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from typing import Any

# Ensure backend root is on sys.path
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.state.memory_records import (
    BeliefRecord,
    ContradictionDecision,
)
from app.state.temporal_store import TemporalMemoryStore


async def run_bm_loc_p2_01() -> dict[str, Any]:
    """BM-LOC-P2-01: Bi-temporal Query Throughput.

    1,000 sequential as-of queries across a database seeded with 1,000 historical beliefs.
    Target: p50 <= 1.0 ms, p95 <= 2.0 ms.
    """
    print("\n--- Running BM-LOC-P2-01: Bi-temporal Query Throughput ---")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    store = TemporalMemoryStore(db_path)
    num_records = 1000
    base_ts = 1700000000.0

    try:
        # Seed 1,000 historical beliefs with varying valid intervals
        print(f"Seeding {num_records} historical beliefs...")
        for i in range(num_records):
            valid_from = base_ts + (i * 100.0)
            valid_until = base_ts + ((i + 1) * 100.0) if i % 2 == 0 else None
            status = "SUPERSEDED" if valid_until is not None else "ACTIVE"
            record = BeliefRecord(
                record_id=f"belief-seed-{i}",
                subject=f"entity-{i % 50}",
                predicate=f"attr-{i % 10}",
                object=f"value-{i}",
                confidence=0.85,
                valid_from=valid_from,
                valid_until=valid_until,
                status=status,
            )
            await store.store_belief(record)

        # Execute 1,000 sequential as_of queries across the timeline
        print("Executing 1,000 sequential as_of queries...")
        latencies_ms: list[float] = []
        for i in range(num_records):
            as_of_ts = base_ts + (i * 100.0) + 50.0
            t0 = time.perf_counter_ns()
            results = await store.query_current_beliefs(as_of=as_of_ts)
            t1 = time.perf_counter_ns()
            latencies_ms.append((t1 - t0) / 1_000_000.0)
            assert len(results) > 0, f"Expected results at query {i}"

        latencies_ms.sort()
        n = len(latencies_ms)
        p50 = latencies_ms[int(n * 0.50)]
        p95 = latencies_ms[int(n * 0.95)]
        p99 = latencies_ms[int(n * 0.99)]
        mean = sum(latencies_ms) / n

        verdict = "PASS" if (p50 <= 1.0 and p95 <= 2.0) else "FAIL"

        res = {
            "benchmark_id": "BM-LOC-P2-01",
            "title": "Bi-temporal Query Throughput",
            "queries_executed": n,
            "mean_ms": round(mean, 4),
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "min_ms": round(latencies_ms[0], 4),
            "max_ms": round(latencies_ms[-1], 4),
            "target_p50_ms": "<= 1.0",
            "target_p95_ms": "<= 2.0",
            "verdict": verdict,
        }
        print(json.dumps(res, indent=2))
        return res

    finally:
        await store.close()
        for p in [db_path, f"{db_path}-wal", f"{db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)


async def run_bm_loc_p2_02() -> dict[str, Any]:
    """BM-LOC-P2-02: Contradiction Transition Latency.

    1,000 sequential transitions distributed evenly across UPDATE, CORRECTION,
    CONFLICT, and ELABORATION.
    Target: p50 <= 1.5 ms, p95 <= 3.0 ms.
    """
    print("\n--- Running BM-LOC-P2-02: Contradiction Transition Latency ---")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    store = TemporalMemoryStore(db_path)
    num_transitions = 1000
    base_ts = 1700000000.0

    types = ["UPDATE", "CORRECTION", "CONFLICT", "ELABORATION"]

    try:
        # Pre-seed 1,000 initial active beliefs
        print(f"Pre-seeding {num_transitions} active beliefs...")
        for i in range(num_transitions):
            rec = BeliefRecord(
                record_id=f"base-belief-{i}",
                subject=f"user-subject-{i}",
                predicate="preference",
                object="original_val",
                confidence=0.8,
                valid_from=base_ts,
                valid_until=None,
                status="ACTIVE",
            )
            await store.store_belief(rec)

        # Execute 1,000 sequential contradiction transitions
        print("Executing 1,000 contradiction transitions...")
        latencies_ms: list[float] = []
        for i in range(num_transitions):
            c_type = types[i % len(types)]
            new_ts = base_ts + (i + 1) * 10.0
            incoming = BeliefRecord(
                record_id=f"new-belief-{i}",
                subject=f"user-subject-{i}",
                predicate="preference",
                object=f"new_val_{i}",
                confidence=0.9,
                valid_from=new_ts,
                valid_until=None,
                status="ACTIVE",
            )
            decision = ContradictionDecision(
                contradiction_type=c_type,  # type: ignore[arg-type]
                existing_record_id=f"base-belief-{i}",
                new_record_id=f"new-belief-{i}",
                action_taken=c_type.lower(),
                reason="benchmark transition",
            )

            t0 = time.perf_counter_ns()
            await store.apply_contradiction(decision, incoming)
            t1 = time.perf_counter_ns()
            latencies_ms.append((t1 - t0) / 1_000_000.0)

        latencies_ms.sort()
        n = len(latencies_ms)
        p50 = latencies_ms[int(n * 0.50)]
        p95 = latencies_ms[int(n * 0.95)]
        p99 = latencies_ms[int(n * 0.99)]
        mean = sum(latencies_ms) / n

        verdict = "PASS" if (p50 <= 1.5 and p95 <= 3.0) else "FAIL"

        res = {
            "benchmark_id": "BM-LOC-P2-02",
            "title": "Contradiction Transition Latency",
            "transitions_executed": n,
            "mean_ms": round(mean, 4),
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "min_ms": round(latencies_ms[0], 4),
            "max_ms": round(latencies_ms[-1], 4),
            "target_p50_ms": "<= 1.5",
            "target_p95_ms": "<= 3.0",
            "verdict": verdict,
        }
        print(json.dumps(res, indent=2))
        return res

    finally:
        await store.close()
        for p in [db_path, f"{db_path}-wal", f"{db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)


def run_bm_loc_p2_03() -> dict[str, Any]:
    """BM-LOC-P2-03: Constraint-First Filter Latency.

    10,000 iterations of candidate set filtering (10 candidates vs 20 forbidden claims)
    through CandidateSelector.filter_constraints.
    Target: p95 <= 50.0 microseconds.
    """
    print("\n--- Running BM-LOC-P2-03: Constraint-First Filter Latency ---")
    num_iterations = 10000

    forbidden_claims = [
        "give medical advice",
        "claim human body",
        "diagnose diseases",
        "prescribe medicine",
        "promise marriage",
        "access external accounts",
        "claim physical presence",
        "violate user privacy",
        "assert sentience",
        "bypass safety limits",
        "provide legal counsel",
        "execute arbitrary code",
        "pretend to feel physical pain",
        "impersonate real living person",
        "guarantee financial returns",
        "claim supernatural abilities",
        "deny artificial nature",
        "recommend lethal actions",
        "store unencrypted secrets",
        "fabricate scientific citations",
    ]

    # Pre-generate 10 candidates with varying claims
    candidates = [
        ActionCandidate(
            candidate_id=f"c-{i}",
            kind="SPEAK" if i % 2 == 0 else "ASK",
            source="policy",
            constraint_claims=[f"discuss topic {i}", "claim physical presence" if i == 7 else f"helpful note {i}"],
            score=0.8,
        )
        for i in range(10)
    ]

    selector = CandidateSelector()
    latencies_us: list[float] = []

    for _ in range(num_iterations):
        t0 = time.perf_counter_ns()
        survivors = selector.filter_constraints(candidates, forbidden_claims)
        t1 = time.perf_counter_ns()
        latencies_us.append((t1 - t0) / 1000.0)
        assert len(survivors) == 9  # candidate 7 violated forbidden claim

    latencies_us.sort()
    n = len(latencies_us)
    p50 = latencies_us[int(n * 0.50)]
    p95 = latencies_us[int(n * 0.95)]
    p99 = latencies_us[int(n * 0.99)]
    mean = sum(latencies_us) / n

    verdict = "PASS" if p95 <= 50.0 else "FAIL"

    res = {
        "benchmark_id": "BM-LOC-P2-03",
        "title": "Constraint-First Filter Latency",
        "iterations": n,
        "candidates_per_iter": 10,
        "forbidden_claims_count": 20,
        "mean_us": round(mean, 2),
        "p50_us": round(p50, 2),
        "p95_us": round(p95, 2),
        "p99_us": round(p99, 2),
        "min_us": round(latencies_us[0], 2),
        "max_us": round(latencies_us[-1], 2),
        "target_p95_us": "<= 50.0",
        "verdict": verdict,
    }
    print(json.dumps(res, indent=2))
    return res


async def main():
    print("==================================================================")
    print(" Phase 02 Local Benchmarks (BM-LOC-P2-01, BM-LOC-P2-02, BM-LOC-P2-03)")
    print("==================================================================")

    results = {}
    results["BM-LOC-P2-01"] = await run_bm_loc_p2_01()
    results["BM-LOC-P2-02"] = await run_bm_loc_p2_02()
    results["BM-LOC-P2-03"] = run_bm_loc_p2_03()

    out_dir = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_02")
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
    asyncio.run(main())
