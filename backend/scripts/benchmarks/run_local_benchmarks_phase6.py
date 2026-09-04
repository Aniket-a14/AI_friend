"""Local Phase 06 micro-benchmarks (BM-LOC-P6-01, BM-LOC-P6-02, BM-LOC-P6-03, BM-LOC-P6-04).

Implements local benchmarks per orchestration/PHASE_06/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
from typing import Any

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive.learning_governance import (
    LearningGovernor,
    LearningProgressCuriosity,
    LearningProposal,
    LearningProposalStatus,
    LearningRiskClass,
)
from app.cognitive.planning import (
    DeterministicPlanVerifier,
    PlanArtifact,
    PlanEffect,
    PlanEffectOp,
    PlanPrecondition,
    PlanStep,
    PreconditionOp,
)
from app.cognitive.simulation import (
    EpisodicSimulator,
    SimulationQuarantineViolationError,
)


def run_bm_loc_p6_01(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P6-01: Deterministic Plan Verifier Latency and Soundness."""
    verifier = DeterministicPlanVerifier()

    valid_plan = PlanArtifact(
        plan_id="bm-valid-plan",
        goal_id="goal-01",
        steps=[
            PlanStep(
                step_id="step-1",
                name="init_step",
                action_type="ACT",
                effects=[PlanEffect(key="step1_done", op=PlanEffectOp.SET, value=True)],
            ),
            PlanStep(
                step_id="step-2",
                name="dependent_step",
                action_type="ACT",
                preconditions=[
                    PlanPrecondition(key="step1_done", op=PreconditionOp.EQUAL, value=True)
                ],
                effects=[PlanEffect(key="goal_achieved", op=PlanEffectOp.SET, value=True)],
            ),
        ],
        terminal_conditions=[
            PlanPrecondition(key="goal_achieved", op=PreconditionOp.EQUAL, value=True)
        ],
    )

    invalid_cyclic_plan = PlanArtifact(
        plan_id="bm-cyclic-plan",
        goal_id="goal-02",
        steps=[
            PlanStep(
                step_id="cycle-1",
                name="c1",
                action_type="ACT",
                fallback_step_id="cycle-2",
            ),
            PlanStep(
                step_id="cycle-2",
                name="c2",
                action_type="ACT",
                fallback_step_id="cycle-1",
            ),
        ],
    )

    latencies_us: list[float] = []
    invalid_rejected = 0

    for i in range(num_iterations):
        plan = valid_plan if (i % 2 == 0) else invalid_cyclic_plan
        t0 = time.perf_counter_ns()
        result = verifier.verify(plan)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        if i % 2 == 0:
            assert result.valid, f"Valid plan unexpectedly rejected: {result.errors}"
        else:
            if not result.valid and (result.cycle_detected or result.errors):
                invalid_rejected += 1

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    expected_invalid = num_iterations // 2
    soundness_rate = (invalid_rejected / expected_invalid) * 100.0 if expected_invalid else 100.0
    verdict = "PASS" if (mean_us < 50.0 and soundness_rate == 100.0) else "FAIL"

    print("\n--- Running BM-LOC-P6-01: Deterministic Plan Verifier Latency & Soundness ---")
    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Soundness Rate: {soundness_rate:.1f}% ({invalid_rejected}/{expected_invalid})")
    print(f"Verdict: {verdict} (Target: mean < 50.0 us, soundness = 100%)")

    return {
        "id": "BM-LOC-P6-01",
        "name": "Deterministic Plan Verifier Latency and Soundness",
        "iterations": num_iterations,
        "mean_latency_us": round(mean_us, 3),
        "p50_latency_us": round(p50_us, 3),
        "p95_latency_us": round(p95_us, 3),
        "p99_latency_us": round(p99_us, 3),
        "soundness_rate_pct": round(soundness_rate, 2),
        "verdict": verdict,
    }


def run_bm_loc_p6_02(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P6-02: Episodic Simulation Sandbox Quarantine and Throughput."""
    simulator = EpisodicSimulator()
    base_workspace = {"agent_id": "friend", "step_count": 42, "status": "idle"}
    sample_percepts = [{"modality": "text", "content": "hello prospect"}]

    def test_policy(state: dict[str, Any], percept: dict[str, Any]) -> dict[str, Any]:
        return {"action": "reply", "candidate": "test candidate", "target": percept.get("content")}

    latencies_us: list[float] = []
    quarantine_blocks = 0
    state_leakage_detected = False

    for _ in range(num_iterations):
        ws_copy = copy.deepcopy(base_workspace)
        t0 = time.perf_counter_ns()
        res = simulator.rollout(ws_copy, sample_percepts, test_policy)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        if ws_copy != base_workspace:
            state_leakage_detected = True

        # Test quarantine invariant by attempting to commit the simulated outcome
        if res.outcomes:
            simulated_outcome = res.outcomes[0]
            try:
                simulator.commit_to_production_memory(simulated_outcome)
            except SimulationQuarantineViolationError:
                quarantine_blocks += 1

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    block_rate = (quarantine_blocks / num_iterations) * 100.0
    verdict = (
        "PASS"
        if (mean_us < 20.0 and block_rate == 100.0 and not state_leakage_detected)
        else "FAIL"
    )

    print("\n--- Running BM-LOC-P6-02: Episodic Simulation Quarantine & Throughput ---")
    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Quarantine Block Rate: {block_rate:.1f}% ({quarantine_blocks}/{num_iterations})")
    print(f"State Leakage: {'DETECTED' if state_leakage_detected else 'None (0.0%)'}")
    print(f"Verdict: {verdict} (Target: mean < 20.0 us, block rate = 100%, 0% leakage)")

    return {
        "id": "BM-LOC-P6-02",
        "name": "Episodic Simulation Sandbox Quarantine and Throughput",
        "iterations": num_iterations,
        "mean_latency_us": round(mean_us, 3),
        "p50_latency_us": round(p50_us, 3),
        "p95_latency_us": round(p95_us, 3),
        "p99_latency_us": round(p99_us, 3),
        "quarantine_block_rate_pct": round(block_rate, 2),
        "state_leakage": state_leakage_detected,
        "verdict": verdict,
    }


def run_bm_loc_p6_03(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P6-03: Learning Governance Gate and Rollback Latency."""
    external_state: dict[str, Any] = {"conversation.style": "formal"}

    def applier(domain: str, value: dict[str, Any]) -> None:
        external_state[domain] = value

    governor = LearningGovernor(state_applier=applier)

    latencies_us: list[float] = []
    immutable_blocks = 0
    rollback_successes = 0

    for i in range(num_iterations):
        is_protected = i % 5 == 0
        target = "persona.name" if is_protected else f"conversation.style_{i}"
        prop = LearningProposal(
            proposal_id=f"bm-prop-{i}",
            source_records=[f"outcome-{i}"],
            target_domain=target,
            proposed_value={"style": "friendly"},
            expected_effect="warmer responses",
            risk_class=LearningRiskClass.LOW,
            rollback_value={"style": "formal"},
            status=LearningProposalStatus.PROPOSED,
        )

        t0 = time.perf_counter_ns()
        if is_protected:
            try:
                governor.submit(prop)
            except ValueError:
                immutable_blocks += 1
            t1 = time.perf_counter_ns()
        else:
            governor.submit(prop)
            governor.validate(prop.proposal_id)
            governor.approve(prop.proposal_id)
            governor.activate(prop.proposal_id)
            assert external_state[target] == {"style": "friendly"}
            governor.rollback(prop.proposal_id)
            t1 = time.perf_counter_ns()
            if external_state[target] == {"style": "formal"}:
                rollback_successes += 1

        latencies_us.append((t1 - t0) / 1000.0)

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    expected_immutable = (num_iterations + 4) // 5
    expected_valid = num_iterations - expected_immutable
    immutable_rate = (immutable_blocks / expected_immutable) * 100.0
    rollback_rate = (rollback_successes / expected_valid) * 100.0

    verdict = (
        "PASS"
        if (mean_us < 50.0 and immutable_rate == 100.0 and rollback_rate == 100.0)
        else "FAIL"
    )

    print("\n--- Running BM-LOC-P6-03: Learning Governance Gate & Rollback Latency ---")
    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Immutable Core Rejection: {immutable_rate:.1f}% ({immutable_blocks}/{expected_immutable})")
    print(f"Rollback Fidelity: {rollback_rate:.1f}% ({rollback_successes}/{expected_valid})")
    print(f"Verdict: {verdict} (Target: mean < 50.0 us, 100% rejection, 100% rollback)")

    return {
        "id": "BM-LOC-P6-03",
        "name": "Learning Governance Gate and Rollback Latency",
        "iterations": num_iterations,
        "mean_latency_us": round(mean_us, 3),
        "p50_latency_us": round(p50_us, 3),
        "p95_latency_us": round(p95_us, 3),
        "p99_latency_us": round(p99_us, 3),
        "immutable_rejection_rate_pct": round(immutable_rate, 2),
        "rollback_fidelity_pct": round(rollback_rate, 2),
        "verdict": verdict,
    }


def run_bm_loc_p6_04(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P6-04: Learning-Progress Curiosity Signal Computation."""
    curiosity = LearningProgressCuriosity(window_size=5)

    # Pre-populate domain history:
    # 1. 'active_learning': steady error reduction from 0.8 to 0.1
    # 2. 'mastered': error flat at 0.02
    # 3. 'chaotic_noise': high-variance oscillations between 0.0 and 1.0
    active_seq = [0.8, 0.75, 0.7, 0.65, 0.6, 0.3, 0.25, 0.2, 0.15, 0.1]
    mastered_seq = [0.02] * 10
    noise_seq = [0.9, 0.1, 0.8, 0.2, 0.9, 0.1, 0.8, 0.2, 0.9, 0.1]

    for val in active_seq:
        curiosity.record("active_learning", val)
    for val in mastered_seq:
        curiosity.record("mastered", val)
    for val in noise_seq:
        curiosity.record("chaotic_noise", val)

    latencies_us: list[float] = []
    correct_rankings = 0

    for _ in range(num_iterations):
        t0 = time.perf_counter_ns()
        ranked = curiosity.rank()
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        # Ranked should prioritize active_learning at the top,
        # while mastered is filtered out or ranked lower, and noise is filtered out
        ranked_domains = [domain for domain, _ in ranked]
        if ranked_domains and ranked_domains[0] == "active_learning" and "chaotic_noise" not in ranked_domains:
            correct_rankings += 1

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    ranking_acc = (correct_rankings / num_iterations) * 100.0
    verdict = "PASS" if (mean_us < 10.0 and ranking_acc == 100.0) else "FAIL"

    print("\n--- Running BM-LOC-P6-04: Learning-Progress Curiosity Signal Computation ---")
    print(f"Iterations: {num_iterations} | Mean: {mean_us:.3f} us | p95: {p95_us:.3f} us")
    print(f"Ranking Accuracy: {ranking_acc:.1f}% ({correct_rankings}/{num_iterations})")
    print(f"Verdict: {verdict} (Target: mean < 10.0 us, ranking accuracy = 100%)")

    return {
        "id": "BM-LOC-P6-04",
        "name": "Learning-Progress Curiosity Signal Computation",
        "iterations": num_iterations,
        "mean_latency_us": round(mean_us, 3),
        "p50_latency_us": round(p50_us, 3),
        "p95_latency_us": round(p95_us, 3),
        "p99_latency_us": round(p99_us, 3),
        "ranking_accuracy_pct": round(ranking_acc, 2),
        "verdict": verdict,
    }


def main() -> None:
    print("===================================================================")
    print("      AI FRIEND PHASE 06 LOCAL MICRO-BENCHMARKS                   ")
    print("===================================================================")

    results: dict[str, Any] = {
        "phase": "PHASE_06",
        "timestamp": time.time(),
        "benchmarks": [
            run_bm_loc_p6_01(),
            run_bm_loc_p6_02(),
            run_bm_loc_p6_03(),
            run_bm_loc_p6_04(),
        ],
    }

    all_pass = all(b["verdict"] == "PASS" for b in results["benchmarks"])
    results["overall_verdict"] = "PASS" if all_pass else "FAIL"

    out_path = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_06", "local_benchmark_results.json")
    with open(out_path, "w", encoding="ascii") as f:
        json.dump(results, f, indent=2)

    print("\n===================================================================")
    print(f"Overall Local Benchmark Verdict: {results['overall_verdict']}")
    print(f"Results saved to: {out_path}")
    print("===================================================================")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
