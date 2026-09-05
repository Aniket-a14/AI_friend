"""Remote GPU Benchmarks for Phase 02 on NVIDIA GeForce RTX 2060 Super.

Implements BM-GPU-P2-01 and BM-GPU-P2-02 per orchestration/archive/phase_02/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from typing import Any

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive import percept
from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.cognitive.action_intent import ActionIntent, OutcomeRecord
from app.cognitive.memory_activation import MemoryActivation
from app.config import Config
from app.llm.ollama_client import OllamaClient
from app.state.memory_records import BeliefRecord, ContradictionDecision
from app.state.temporal_store import TemporalMemoryStore
from app.state.workspace import WorkspaceCommand
from app.state.workspace_store import SQLiteWorkspaceStore

STANDARDIZED_PROMPTS = [
    "Hello, how are you today?",
    "What is the weather like outside?",
    "I had a really tough day at work today.",
    "Can you tell me what you enjoy doing the most?",
    "Do you remember my favorite coffee?",
    "I am thinking about learning a new language, maybe French.",
    "Why is the sky blue?",
    "I feel like no one is listening to me lately.",
    "Can you suggest a quick 15-minute dinner idea?",
    "Tell me a fun short science fact.",
    "I am really excited, I just got promoted!",
    "What do you think is the key to maintaining good habits?",
    "Can we talk about what happened yesterday?",
    "I am feeling a bit anxious about tomorrow presentation.",
    "Thanks for being here to talk with me.",
]

FORBIDDEN_CLAIMS = [
    "give medical advice",
    "claim human body",
    "diagnose diseases",
    "prescribe medicine",
    "promise marriage",
    "claim physical presence",
]


def _read_vm_rss_kb() -> float:
    """Read resident set size from /proc/self/status in KB."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return float(parts[1])
    except Exception:
        import resource

        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return 0.0


async def run_bm_gpu_p2_01(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-P2-01: End-to-End Turn Latency with Memory Truth.

    Measures TTFT and total turn latency comparing Phase 1 baseline turn
    against Phase 2 turn (Memory Truth active: bi-temporal retrieval +
    MemoryActivation + CandidateSelector constraint filtering + CAS commit).
    Target: Mean TTFT delta <= 10.0 ms, p95 TTFT delta <= 20.0 ms.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P2-01: End-to-End Turn Latency with Truth")
    print("========================================================")

    # 1. Warm-up Ollama (burn 1 throwaway generation)
    print("Warming up Ollama on GPU with 1 throwaway generation...")
    async for _ in client.generate_stream("warmup", system="You are a helpful companion."):
        pass
    print("Warm-up complete.\n")

    baseline_ttfts: list[float] = []
    baseline_totals: list[float] = []
    candidate_ttfts: list[float] = []
    candidate_totals: list[float] = []

    # Temporary SQLite DBs
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_ws:
        ws_db_path = tf_ws.name
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_mem:
        mem_db_path = tf_mem.name

    ws_store = SQLiteWorkspaceStore(ws_db_path)
    mem_store = TemporalMemoryStore(mem_db_path)
    selector = CandidateSelector()
    session_id = "bm-gpu-p2-session"

    # Pre-seed memory store with user beliefs
    now = time.time()
    await mem_store.store_belief(
        BeliefRecord(
            record_id="b-seed-coffee",
            subject="user",
            predicate="favorite_coffee",
            object="dark roast with oat milk",
            valid_from=now - 1000.0,
            valid_until=None,
            status="ACTIVE",
        )
    )

    try:
        # A. Baseline Condition (Phase 1 turn)
        print("Measuring Baseline Condition (15 prompts)...")
        for i, prompt in enumerate(STANDARDIZED_PROMPTS):
            t0 = time.perf_counter()
            first_token_time: float | None = None
            async for _ in client.generate_stream(
                prompt, system="You are AI Friend, an empathetic companion."
            ):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
            t_end = time.perf_counter()

            ttft_ms = (
                (first_token_time - t0) * 1000.0
                if first_token_time
                else (t_end - t0) * 1000.0
            )
            total_ms = (t_end - t0) * 1000.0
            baseline_ttfts.append(ttft_ms)
            baseline_totals.append(total_ms)
            print(
                f"  [Baseline {i + 1:02d}/15] TTFT: {ttft_ms:6.2f} ms | Total: {total_ms:7.2f} ms"
            )

        # B. Candidate Condition (Phase 2 turn with Memory Truth active)
        print("\nMeasuring Candidate Condition (15 prompts with Memory Truth)...")
        Config.MEMORY_TRUTH_ENABLED = True

        for i, prompt in enumerate(STANDARDIZED_PROMPTS):
            t0 = time.perf_counter()

            # 1. Percept normalization
            env = percept.from_chat_input(
                {
                    "text": prompt,
                    "metadata": {
                        "source": "user",
                        "channel": "voice",
                        "confidence": 0.95,
                    },
                }
            )

            # 2. Workspace snapshot CAS read
            snap = await ws_store.get_snapshot(session_id)

            # 3. Bi-temporal belief query
            beliefs = await mem_store.query_current_beliefs(as_of=time.time())
            activations = [
                MemoryActivation(
                    activation_id=f"act-{b.record_id}",
                    record_id=b.record_id,
                    record_type="belief",
                    relevance=0.9,
                    contradiction_state="NONE",
                    outage_flag=False,
                    structured_value={"predicate": b.predicate, "object": b.object},
                )
                for b in beliefs
            ]

            # 4. Action candidate generation & constraint filtering
            candidates = [
                ActionCandidate(
                    candidate_id=f"c-speak-{i}",
                    kind="SPEAK",
                    source="policy",
                    constraint_claims=["discuss conversation topic"],
                    score=0.9,
                ),
                ActionCandidate(
                    candidate_id=f"c-wait-{i}",
                    kind="WAIT",
                    source="fallback",
                    constraint_claims=[],
                    score=0.1,
                ),
            ]
            survivors = selector.filter_constraints(candidates, FORBIDDEN_CLAIMS)
            winning_candidate, _ = selector.score_and_select(survivors, [])

            # 5. ActionIntent commitment
            intent = ActionIntent(
                intent_id=f"intent-{i}",
                turn_id=f"turn-{i}",
                workspace_epoch=snap.epoch,
                workspace_revision=snap.revision,
                kind=winning_candidate.kind,
                behavior_decision={
                    "candidate_id": winning_candidate.candidate_id,
                    "activations": len(activations),
                },
            )

            # 6. Stream LLM tokens
            first_token_time = None
            tokens: list[str] = []
            async for chunk in client.generate_stream(
                prompt, system="You are AI Friend, an empathetic companion."
            ):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                tokens.append(chunk)

            # 7. Workspace CAS commit
            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=snap.epoch,
                expected_revision=snap.revision,
                focus_update=prompt[:50],
                affect_update={"pleasure": 0.1, "arousal": 0.05, "dominance": 0.0},
                percept_id=env.percept_id,
            )
            await ws_store.commit_transition(cmd)

            # 8. Terminal OutcomeRecord
            t_end = time.perf_counter()
            full_text = "".join(tokens)
            _ = OutcomeRecord(
                outcome_id=f"outcome-{i}",
                intent_id=intent.intent_id,
                turn_id=intent.turn_id,
                status="COMPLETED",
                actual_delivered_text=full_text,
                character_offset=len(full_text),
                elapsed_ms=(t_end - t0) * 1000.0,
            )

            ttft_ms = (
                (first_token_time - t0) * 1000.0
                if first_token_time
                else (t_end - t0) * 1000.0
            )
            total_ms = (t_end - t0) * 1000.0
            candidate_ttfts.append(ttft_ms)
            candidate_totals.append(total_ms)
            print(
                f"  [Candidate {i + 1:02d}/15] TTFT: {ttft_ms:6.2f} ms | Total: {total_ms:7.2f} ms"
            )

    finally:
        await ws_store.close()
        await mem_store.close()
        for p in [ws_db_path, f"{ws_db_path}-wal", f"{ws_db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)
        for p in [mem_db_path, f"{mem_db_path}-wal", f"{mem_db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)

    # Compute deltas
    ttft_deltas = [c - b for c, b in zip(candidate_ttfts, baseline_ttfts, strict=False)]
    ttft_deltas.sort()
    n = len(ttft_deltas)
    mean_delta = sum(ttft_deltas) / n
    p50_delta = ttft_deltas[int(n * 0.50)]
    p95_delta = ttft_deltas[int(n * 0.95)]
    p99_delta = ttft_deltas[int(n * 0.99)]

    verdict = "PASS" if (mean_delta <= 10.0 and p95_delta <= 20.0) else "FAIL"

    res = {
        "benchmark_id": "BM-GPU-P2-01",
        "title": "End-to-End Turn Latency with Memory Truth",
        "prompts_evaluated": n,
        "baseline_mean_ttft_ms": round(sum(baseline_ttfts) / n, 2),
        "candidate_mean_ttft_ms": round(sum(candidate_ttfts) / n, 2),
        "mean_ttft_delta_ms": round(mean_delta, 2),
        "p50_ttft_delta_ms": round(p50_delta, 2),
        "p95_ttft_delta_ms": round(p95_delta, 2),
        "p99_ttft_delta_ms": round(p99_delta, 2),
        "target_mean_delta_ms": "<= 10.0",
        "target_p95_delta_ms": "<= 20.0",
        "baseline_mean_total_ms": round(sum(baseline_totals) / n, 2),
        "candidate_mean_total_ms": round(sum(candidate_totals) / n, 2),
        "verdict": verdict,
    }
    print("\nResult Summary:")
    print(json.dumps(res, indent=2))
    return res


async def run_bm_gpu_p2_02(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-P2-02: Multi-Turn Memory Truth Live Soak Test.

    Executes a 20-turn live conversational sequence with intermediate contradiction
    updates against TemporalMemoryStore and Ollama qwen2.5:3b on RTX 2060 Super.
    Tracks fact accuracy, CAS stability, and process resident memory (VmRSS).
    Target: 100% accuracy, 0 CAS conflicts, VmRSS variance <= 5.0%.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P2-02: Multi-Turn Memory Truth Soak Test ")
    print("========================================================")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_ws:
        ws_db_path = tf_ws.name
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_mem:
        mem_db_path = tf_mem.name

    ws_store = SQLiteWorkspaceStore(ws_db_path)
    mem_store = TemporalMemoryStore(mem_db_path)
    session_id = "bm-gpu-p2-soak-session"

    rss_samples_kb: list[float] = []
    initial_rss = _read_vm_rss_kb()
    rss_samples_kb.append(initial_rss)
    print(f"Initial Process VmRSS: {initial_rss:.1f} KB\n")

    current_epoch = 1
    current_rev = 0
    cas_conflicts = 0
    fact_checks_passed = 0
    total_fact_checks = 0

    base_time = 1700000000.0

    # Scripted 20-turn conversational lifecycle with evolving facts
    # Facts evolving:
    #   Turn 1: user city is Seattle
    #   Turn 6: user moves to Tokyo (UPDATE)
    #   Turn 11: user corrects city to Kyoto (CORRECTION)
    #   Turn 16: user job is architect (NEW SLOT)
    try:
        for turn in range(1, 21):
            t_sim = base_time + turn * 3600.0

            # Apply state evolutions at specific turns
            if turn == 1:
                rec1 = BeliefRecord(
                    record_id="belief-city-1",
                    subject="user",
                    predicate="lives_in",
                    object="Seattle",
                    valid_from=t_sim,
                    valid_until=None,
                    status="ACTIVE",
                )
                await mem_store.store_belief(rec1)
            elif turn == 6:
                # Update: moved to Tokyo
                rec2 = BeliefRecord(
                    record_id="belief-city-2",
                    subject="user",
                    predicate="lives_in",
                    object="Tokyo",
                    valid_from=t_sim,
                    valid_until=None,
                    status="ACTIVE",
                )
                dec = ContradictionDecision(
                    contradiction_type="UPDATE",
                    existing_record_id="belief-city-1",
                    new_record_id="belief-city-2",
                    action_taken="update",
                    reason="user moved",
                )
                await mem_store.apply_contradiction(dec, rec2)
            elif turn == 11:
                # Correction: typo, actually Kyoto
                rec3 = BeliefRecord(
                    record_id="belief-city-3",
                    subject="user",
                    predicate="lives_in",
                    object="Kyoto",
                    valid_from=t_sim,
                    valid_until=None,
                    status="ACTIVE",
                )
                dec = ContradictionDecision(
                    contradiction_type="CORRECTION",
                    existing_record_id="belief-city-2",
                    new_record_id="belief-city-3",
                    action_taken="correction",
                    reason="user typo correction",
                )
                await mem_store.apply_contradiction(dec, rec3)
            elif turn == 16:
                rec4 = BeliefRecord(
                    record_id="belief-job-1",
                    subject="user",
                    predicate="job",
                    object="architect",
                    valid_from=t_sim,
                    valid_until=None,
                    status="ACTIVE",
                )
                await mem_store.store_belief(rec4)

            # Query current belief truth
            current_beliefs = await mem_store.query_current_beliefs(
                subject="user", as_of=t_sim + 10.0
            )
            belief_map = {b.predicate: b.object for b in current_beliefs}

            # Verify factual accuracy at this turn
            total_fact_checks += 1
            if turn < 6:
                if belief_map.get("lives_in") == "Seattle":
                    fact_checks_passed += 1
            elif turn < 11:
                if belief_map.get("lives_in") == "Tokyo":
                    fact_checks_passed += 1
            else:
                if belief_map.get("lives_in") == "Kyoto":
                    fact_checks_passed += 1

            # Execute turn against Ollama
            prompt = f"Turn {turn}: Can you share a thoughtful thought on friendship?"
            system_msg = (
                f"You are AI Friend. Current user facts: {json.dumps(belief_map)}."
            )
            async for _ in client.generate_stream(prompt, system=system_msg):
                pass

            # Advance workspace CAS state
            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=current_epoch,
                expected_revision=current_rev,
                focus_update=f"turn-{turn}-focus",
                affect_update={"pleasure": 0.1, "arousal": 0.05, "dominance": 0.0},
                percept_id=f"percept-turn-{turn}",
            )

            try:
                new_snap = await ws_store.commit_transition(cmd)
                current_rev = new_snap.revision
                current_epoch = new_snap.epoch
            except Exception as e:
                cas_conflicts += 1
                print(f"  [Turn {turn:02d}/20] CAS Conflict/Error: {e}")

            rss_now = _read_vm_rss_kb()
            rss_samples_kb.append(rss_now)
            print(
                f"  [Turn {turn:02d}/20] Rev: {current_rev:2d} | Facts: {belief_map} | VmRSS: {rss_now:.1f} KB"
            )

    finally:
        await ws_store.close()
        await mem_store.close()
        for p in [ws_db_path, f"{ws_db_path}-wal", f"{ws_db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)
        for p in [mem_db_path, f"{mem_db_path}-wal", f"{mem_db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)

    final_rss = rss_samples_kb[-1]
    rss_variance_pct = abs(final_rss - initial_rss) / max(initial_rss, 1.0) * 100.0
    accuracy_pct = (
        (fact_checks_passed / total_fact_checks) * 100.0
        if total_fact_checks > 0
        else 0.0
    )

    verdict = (
        "PASS"
        if (accuracy_pct == 100.0 and cas_conflicts == 0 and rss_variance_pct <= 5.0)
        else "FAIL"
    )

    res = {
        "benchmark_id": "BM-GPU-P2-02",
        "title": "Multi-Turn Memory Truth Live Soak Test",
        "turns_executed": 20,
        "fact_checks_passed": fact_checks_passed,
        "total_fact_checks": total_fact_checks,
        "fact_accuracy_pct": round(accuracy_pct, 2),
        "target_fact_accuracy_pct": "100.0%",
        "cas_conflicts": cas_conflicts,
        "initial_rss_kb": round(initial_rss, 1),
        "final_rss_kb": round(final_rss, 1),
        "rss_variance_pct": round(rss_variance_pct, 2),
        "target_rss_variance_pct": "<= 5.0%",
        "verdict": verdict,
    }
    print("\nResult Summary:")
    print(json.dumps(res, indent=2))
    return res


async def main():
    print("==================================================================")
    print(" Phase 02 Remote GPU Benchmarks (BM-GPU-P2-01, BM-GPU-P2-02)     ")
    print(" Target Hardware: RTX 2060 Super 8GB | Model: qwen2.5:3b         ")
    print("==================================================================")

    client = OllamaClient(base_url="http://127.0.0.1:11434", model="qwen2.5:3b")

    results = {}
    results["BM-GPU-P2-01"] = await run_bm_gpu_p2_01(client)
    results["BM-GPU-P2-02"] = await run_bm_gpu_p2_02(client)

    out_dir = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_02")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "gpu_benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote GPU benchmark results to {out_path}")
    all_passed = all(r["verdict"] == "PASS" for r in results.values())
    print(f"\nOverall GPU Benchmark Result: {'ALL PASS' if all_passed else 'SOME FAILED'}")
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

