"""Local Phase 07 micro-benchmarks (BM-LOC-P7-01, BM-LOC-P7-02, BM-LOC-P7-03, BM-LOC-P7-04).

Implements local benchmarks per orchestration/PHASE_07/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.agents.subconscious_agent import SubconsciousAgent
from app.cognitive.action import ActionService
from app.cognitive.core import CognitiveService
from app.cognitive.decision import ActionPlan
from app.cognitive.learning_governance import (
    LearningGovernor,
    LearningProposal,
    LearningProposalStatus,
    LearningRiskClass,
)


def run_bm_loc_p7_01(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P7-01: Runtime Composition & Initial Turn Overhead.

    Measures the latency overhead of initializing CognitiveService with all
    Phase 01-06 composed services (workspace store, temporal store, scheduler,
    verifier, governor, negotiator) and running perception/appraisal deliberation.
    """
    print("\n--- Running BM-LOC-P7-01: Runtime Composition & Initial Deliberation ---")
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="{\"goal_congruence\": 0.5, \"norm_alignment\": 0.8, \"expectedness\": 0.9}")
    mock_memory = MagicMock()
    mock_memory.search_memories = AsyncMock(return_value=[])
    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])

    with tempfile.TemporaryDirectory() as tmp_dir:
        latencies_ms: list[float] = []

        async def _run():
            for _ in range(num_iterations):
                t0 = time.perf_counter_ns()
                svc = CognitiveService(
                    llm_service=mock_llm,
                    memory_store=mock_memory,
                    graph_db=mock_graph,
                    base_path=tmp_dir,
                )
                raw_event = {"text": "Hello friend, how are you today?"}
                event = await svc.pipeline.perception.perceive(raw_event)
                state_snap = svc.pipeline.state.get_context_snapshot()
                _ = svc.pipeline.appraisal.appraise(
                    event_content=event.raw_content,
                    event_type=event.event_type,
                    emotional_bias=0.0,
                    state_snapshot=state_snap,
                    identity_boundaries=[],
                )
                t1 = time.perf_counter_ns()
                latencies_ms.append((t1 - t0) / 1_000_000.0)

        asyncio.run(_run())

    latencies_ms.sort()
    n = len(latencies_ms)
    mean_ms = sum(latencies_ms) / n
    p50_ms = latencies_ms[int(n * 0.50)]
    p95_ms = latencies_ms[int(n * 0.95)]
    p99_ms = latencies_ms[int(n * 0.99)]

    verdict = "PASS" if mean_ms < 5.0 else "FAIL"
    print(f"Iterations: {num_iterations} | Mean: {mean_ms:.3f} ms | p95: {p95_ms:.3f} ms | p99: {p99_ms:.3f} ms")
    print(f"Verdict: {verdict} (Target: mean < 5.0 ms)")

    return {
        "id": "BM-LOC-P7-01",
        "name": "Runtime Composition & Initial Deliberation Overhead",
        "iterations": num_iterations,
        "mean_latency_ms": round(mean_ms, 3),
        "p50_latency_ms": round(p50_ms, 3),
        "p95_latency_ms": round(p95_ms, 3),
        "p99_latency_ms": round(p99_ms, 3),
        "verdict": verdict,
    }


def run_bm_loc_p7_02(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P7-02: Action Selection & WAIT Action Silence Fidelity.

    Verifies that WAIT action executions emit zero spoken text chunks
    and execute with sub-millisecond dispatch latency.
    """
    print("\n--- Running BM-LOC-P7-02: Action Selection & WAIT Silence Fidelity ---")
    mock_llm = MagicMock()
    action_service = ActionService(llm_service=mock_llm)

    wait_plan = ActionPlan(
        action_type="WAIT",
        payload={"reason": "deliberative_wait", "timeout": 5.0},
        goal="ENGAGE",
        priority=1,
    )

    latencies_us: list[float] = []
    spoken_chunks_emitted = 0

    async def _run():
        nonlocal spoken_chunks_emitted
        for _ in range(num_iterations):
            t0 = time.perf_counter_ns()
            chunks: list[dict[str, Any]] = []
            async for chunk in action_service.execute(wait_plan):
                chunks.append(chunk)
            t1 = time.perf_counter_ns()
            latencies_us.append((t1 - t0) / 1000.0)

            for chunk in chunks:
                if chunk.get("type") == "content" and chunk.get("data"):
                    spoken_chunks_emitted += 1

    asyncio.run(_run())

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    silence_fidelity_pct = 100.0 if spoken_chunks_emitted == 0 else 0.0
    verdict = "PASS" if (mean_us < 1000.0 and silence_fidelity_pct == 100.0) else "FAIL"

    print(f"Iterations: {num_iterations} | Mean: {mean_us:.2f} us | p95: {p95_us:.2f} us")
    print(f"Spoken Chunks: {spoken_chunks_emitted} | Silence Fidelity: {silence_fidelity_pct:.1f}%")
    print(f"Verdict: {verdict} (Target: mean < 1000.0 us (1.0 ms), silence fidelity = 100%)")

    return {
        "id": "BM-LOC-P7-02",
        "name": "Action Selection & WAIT Action Silence Fidelity",
        "iterations": num_iterations,
        "mean_latency_us": round(mean_us, 2),
        "p50_latency_us": round(p50_us, 2),
        "p95_latency_us": round(p95_us, 2),
        "p99_latency_us": round(p99_us, 2),
        "silence_fidelity_pct": silence_fidelity_pct,
        "verdict": verdict,
    }


def run_bm_loc_p7_03(num_iterations: int = 500) -> dict[str, Any]:
    """BM-LOC-P7-03: Epistemic Dream Quarantine Verification.

    Verifies that SubconsciousAgent._run_dream_sequence strictly quarantines
    dream insights and commits 0 dream-derived memories to long-term memory.
    """
    print("\n--- Running BM-LOC-P7-03: Epistemic Dream Quarantine Verification ---")
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="In a surreal vision, stars spoke in riddles of old books.")
    mock_memory = MagicMock()
    mock_memory.add_memory = AsyncMock(return_value=None)
    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(
        return_value=[
            {"name": "Concept A"},
            {"name": "Concept B"},
            {"name": "Concept C"},
        ]
    )

    mock_state_service = MagicMock()
    mock_state_service.get_context_snapshot.return_value = {"fatigue": 0.9}

    agent = SubconsciousAgent(
        state_service=mock_state_service,
        graph_db=mock_graph,
        memory_store=mock_memory,
    )
    agent.llm = mock_llm

    dream_memories_committed = 0

    async def _run():
        nonlocal dream_memories_committed
        for _ in range(num_iterations):
            await agent._run_dream_sequence()

        for call in mock_memory.add_memory.call_args_list:
            source = call.kwargs.get("source", "")
            content = call.kwargs.get("content", "")
            if source == "subconscious_dream" or "surreal vision" in content:
                dream_memories_committed += 1

    asyncio.run(_run())

    quarantine_compliance_pct = 100.0 if dream_memories_committed == 0 else 0.0
    verdict = "PASS" if quarantine_compliance_pct == 100.0 else "FAIL"

    print(f"Iterations: {num_iterations} | Dream Memories Committed: {dream_memories_committed}")
    print(f"Quarantine Compliance: {quarantine_compliance_pct:.1f}%")
    print(f"Verdict: {verdict} (Target: 100% quarantine compliance, 0 committed)")

    return {
        "id": "BM-LOC-P7-03",
        "name": "Epistemic Dream Quarantine Verification",
        "iterations": num_iterations,
        "dream_memories_committed": dream_memories_committed,
        "quarantine_compliance_pct": quarantine_compliance_pct,
        "verdict": verdict,
    }


def run_bm_loc_p7_04(num_iterations: int = 1000) -> dict[str, Any]:
    """BM-LOC-P7-04: Governed Learning & Reflection Proposal Review Latency.

    Verifies the latency and atomic rollback fidelity of reflection proposals
    evaluated by LearningGovernor across risk tiers.
    """
    print("\n--- Running BM-LOC-P7-04: Governed Learning & Proposal Review Latency ---")
    current_state = {"adaptive_traits": ["reflective"], "relationship": "Companion"}

    def _state_applier(domain: str, value: Any) -> None:
        if domain == "adaptive_learning":
            current_state["adaptive_traits"] = list(value.get("new_traits", []))

    governor = LearningGovernor(state_applier=_state_applier)
    latencies_us: list[float] = []
    rollback_failures = 0

    risk_tiers = [LearningRiskClass.LOW, LearningRiskClass.MEDIUM, LearningRiskClass.HIGH]

    for i in range(num_iterations):
        risk = risk_tiers[i % len(risk_tiers)]
        state_before = {"adaptive_traits": list(current_state["adaptive_traits"]), "relationship": current_state["relationship"]}
        proposal = LearningProposal(
            source_records=[f"rec-{i}"],
            target_domain="adaptive_learning",
            proposed_value={"new_traits": ["reflective", f"curious-{i}"]},
            expected_effect="expand_adaptive_persona",
            risk_class=risk,
            rollback_value={"new_traits": list(state_before["adaptive_traits"])},
        )

        t0 = time.perf_counter_ns()
        governor.submit(proposal)
        governor.validate(proposal.proposal_id)
        approved_prop = governor.approve(proposal.proposal_id)
        if approved_prop.status == LearningProposalStatus.APPROVED:
            governor.activate(proposal.proposal_id)
            # Perform 1-step atomic rollback
            governor.rollback(proposal.proposal_id)
        t1 = time.perf_counter_ns()

        latencies_us.append((t1 - t0) / 1000.0)

        if current_state != state_before:
            rollback_failures += 1

    latencies_us.sort()
    n = len(latencies_us)
    mean_us = sum(latencies_us) / n
    p50_us = latencies_us[int(n * 0.50)]
    p95_us = latencies_us[int(n * 0.95)]
    p99_us = latencies_us[int(n * 0.99)]

    rollback_fidelity_pct = 100.0 if rollback_failures == 0 else 0.0
    verdict = "PASS" if (mean_us < 50.0 and rollback_fidelity_pct == 100.0) else "FAIL"

    print(f"Iterations: {num_iterations} | Mean: {mean_us:.2f} us | p95: {p95_us:.2f} us")
    print(f"Rollback Failures: {rollback_failures} | Rollback Fidelity: {rollback_fidelity_pct:.1f}%")
    print(f"Verdict: {verdict} (Target: mean < 50.0 us, rollback fidelity = 100%)")

    return {
        "id": "BM-LOC-P7-04",
        "name": "Governed Learning & Reflection Proposal Review Latency",
        "iterations": num_iterations,
        "mean_latency_us": round(mean_us, 2),
        "p50_latency_us": round(p50_us, 2),
        "p95_latency_us": round(p95_us, 2),
        "p99_latency_us": round(p99_us, 2),
        "rollback_fidelity_pct": rollback_fidelity_pct,
        "verdict": verdict,
    }


def main() -> None:
    print("===================================================================")
    print("      AI FRIEND PHASE 07 LOCAL MICRO-BENCHMARKS                   ")
    print("===================================================================")

    results: dict[str, Any] = {
        "phase": "PHASE_07",
        "timestamp": time.time(),
        "benchmarks": [
            run_bm_loc_p7_01(),
            run_bm_loc_p7_02(),
            run_bm_loc_p7_03(),
            run_bm_loc_p7_04(),
        ],
    }

    all_pass = all(b["verdict"] == "PASS" for b in results["benchmarks"])
    results["overall_verdict"] = "PASS" if all_pass else "FAIL"

    out_path = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_07", "local_benchmark_results.json")
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
