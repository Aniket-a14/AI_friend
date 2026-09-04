"""Remote GPU Benchmarks for Phase 01 on NVIDIA GeForce RTX 2060 Super.

Implements BM-GPU-01, BM-GPU-02, BM-GPU-03 per BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import tempfile
import time
from typing import Any

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive import percept
from app.cognitive.action_intent import ActionIntent, OutcomeRecord
from app.llm.ollama_client import OllamaClient
from app.state.workspace import WorkspaceCommand
from app.state.workspace_store import SQLiteWorkspaceStore

STANDARDIZED_PROMPTS = [
    "Hello, how are you today?",
    "What's the weather like outside?",
    "I had a really tough day at work today.",
    "Can you tell me what you enjoy doing the most?",
    "Do you remember my favorite coffee?",
    "I'm thinking about learning a new language, maybe French.",
    "Why is the sky blue?",
    "I feel like no one is listening to me lately.",
    "Can you suggest a quick 15-minute dinner idea?",
    "Tell me a fun short science fact.",
    "I'm really excited, I just got promoted!",
    "What do you think is the key to maintaining good habits?",
    "Can we talk about what happened yesterday?",
    "I'm feeling a bit anxious about tomorrow's presentation.",
    "Thanks for being here to talk with me.",
]


def _read_vm_rss_kb() -> float:
    """Read resident set size from /proc/self/status in KB."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return float(parts[1])
    except Exception:
        import resource
        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return 0.0


async def run_bm_gpu_01(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-01: End-to-End Cognitive Turn Latency (Baseline vs Candidate).
    
    Measures TTFT and total duration over 15 standardized prompts on RTX 2060 Super.
    """
    print("\n========================================================")
    print(" Running BM-GPU-01: End-to-End Cognitive Turn Latency   ")
    print("========================================================")

    # 1. Warm-up Ollama (burn 1 throwaway generation)
    print("Warming up Ollama with 1 throwaway generation...")
    async for _ in client.generate_stream("warmup", system="You are a helpful companion."):
        pass
    print("Warm-up complete.\n")

    baseline_ttfts: list[float] = []
    baseline_totals: list[float] = []
    candidate_ttfts: list[float] = []
    candidate_totals: list[float] = []

    # Temporary SQLite DB for candidate workspace CAS
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    store = SQLiteWorkspaceStore(db_path)
    session_id = "bm-gpu-01-session"

    try:
        # A. Run Baseline Condition (direct unversioned prompt streaming)
        print("Measuring Baseline Condition (15 prompts)...")
        for i, prompt in enumerate(STANDARDIZED_PROMPTS):
            t0 = time.perf_counter()
            first_token_time: float | None = None
            async for _ in client.generate_stream(prompt, system="You are AI Friend, an empathetic companion."):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
            t_end = time.perf_counter()

            ttft_ms = (first_token_time - t0) * 1000.0 if first_token_time else (t_end - t0) * 1000.0
            total_ms = (t_end - t0) * 1000.0
            baseline_ttfts.append(ttft_ms)
            baseline_totals.append(total_ms)
            print(f"  [Baseline {i+1:02d}/15] TTFT: {ttft_ms:6.2f} ms | Total: {total_ms:7.2f} ms")

        # B. Run Candidate Condition (PerceptEnvelope + Workspace CAS + ActionIntent + Ollama + CAS Commit)
        print("\nMeasuring Candidate Condition (15 prompts)...")
        for i, prompt in enumerate(STANDARDIZED_PROMPTS):
            t0 = time.perf_counter()

            # 1. PerceptEnvelope normalization
            env = percept.from_chat_input({"text": prompt, "metadata": {"source": "user", "channel": "voice", "confidence": 0.95}})
            
            # 2. Workspace snapshot CAS read
            snap = await store.get_snapshot(session_id)
            
            # 3. ActionIntent commitment
            intent = ActionIntent(
                intent_id=f"intent-{i}",
                turn_id=f"turn-{i}",
                workspace_epoch=snap.epoch,
                workspace_revision=snap.revision,
                kind="SPEAK",
                behavior_decision={"goal": "ENGAGE", "percept_id": env.percept_id},
            )

            # 4. Stream tokens
            first_token_time = None
            tokens: list[str] = []
            async for chunk in client.generate_stream(prompt, system="You are AI Friend, an empathetic companion."):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                tokens.append(chunk)

            # 5. Advance workspace with CAS transition
            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=snap.epoch,
                expected_revision=snap.revision,
                focus_update=prompt[:50],
                affect_update={"pleasure": 0.1, "arousal": 0.05, "dominance": 0.0},
                percept_id=env.percept_id,
            )
            await store.commit_transition(cmd)

            # 6. Terminal OutcomeRecord
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

            ttft_ms = (first_token_time - t0) * 1000.0 if first_token_time else (t_end - t0) * 1000.0
            total_ms = (t_end - t0) * 1000.0
            candidate_ttfts.append(ttft_ms)
            candidate_totals.append(total_ms)
            print(f"  [Candidate {i+1:02d}/15] TTFT: {ttft_ms:6.2f} ms | Total: {total_ms:7.2f} ms")

    finally:
        await store.close()
        for fpath in [db_path, f"{db_path}-wal", f"{db_path}-shm"]:
            if os.path.exists(fpath):
                os.unlink(fpath)

    # Calculate statistics
    n = len(baseline_ttfts)
    mean_baseline_ttft = sum(baseline_ttfts) / n
    mean_candidate_ttft = sum(candidate_ttfts) / n
    mean_ttft_delta = mean_candidate_ttft - mean_baseline_ttft

    sorted_base = sorted(baseline_ttfts)
    sorted_cand = sorted(candidate_ttfts)
    p50_baseline = sorted_base[int(n * 0.50)]
    p50_candidate = sorted_cand[int(n * 0.50)]
    p95_baseline = sorted_base[int(n * 0.95)]
    p95_candidate = sorted_cand[int(n * 0.95)]
    p95_ttft_delta = p95_candidate - p95_baseline

    mean_baseline_total = sum(baseline_totals) / n
    mean_candidate_total = sum(candidate_totals) / n

    verdict = "PASS" if mean_ttft_delta <= 10.0 and p95_ttft_delta <= 20.0 else "FAIL"

    res = {
        "benchmark_id": "BM-GPU-01",
        "hardware": "NVIDIA GeForce RTX 2060 Super 8GB",
        "model": client.model,
        "runs_per_condition": n,
        "mean_baseline_ttft_ms": round(mean_baseline_ttft, 2),
        "mean_candidate_ttft_ms": round(mean_candidate_ttft, 2),
        "mean_ttft_delta_ms": round(mean_ttft_delta, 2),
        "target_mean_ttft_delta_ms": "<= 10.0",
        "p50_baseline_ttft_ms": round(p50_baseline, 2),
        "p50_candidate_ttft_ms": round(p50_candidate, 2),
        "p95_baseline_ttft_ms": round(p95_baseline, 2),
        "p95_candidate_ttft_ms": round(p95_candidate, 2),
        "p95_ttft_delta_ms": round(p95_ttft_delta, 2),
        "target_p95_ttft_delta_ms": "<= 20.0",
        "mean_baseline_total_ms": round(mean_baseline_total, 2),
        "mean_candidate_total_ms": round(mean_candidate_total, 2),
        "verdict": verdict,
    }
    print("\nResult Summary:")
    print(json.dumps(res, indent=2))
    return res


async def run_bm_gpu_02() -> dict[str, Any]:
    """BM-GPU-02: Acoustic Barge-In to OutcomeRecord Latency.
    
    10 simulated interruptions measuring stop signal arrival to OutcomeRecord emission.
    """
    print("\n========================================================")
    print(" Running BM-GPU-02: Acoustic Barge-In to Outcome Latency")
    print("========================================================")

    from app.agents.brain_agent import BrainAgent

    # Build agent test double with dummy stores
    agent = object.__new__(BrainAgent)
    agent._generation_lock = asyncio.Lock()
    agent._turn_state_lock = asyncio.Lock()
    agent._active_generation_task = None
    agent._active_response_turn_id = None
    agent._active_action_intent = None
    agent._last_outcome_record = None
    agent._outcome_history = []
    agent.last_audio_progress = None
    agent.last_assistant_response = None
    agent.conversation_store = None
    agent.publish = None

    stop_to_outcome_latencies_ms: list[float] = []
    precision_errors: list[int] = []
    statuses: list[str] = []

    for i in range(10):
        turn_id = f"bargein-turn-{i}"
        full_text = f"This is a long synthetic conversational utterance generated for turn {i} to test acoustic barge-in truncation."
        interrupted_offset = random.randint(25, 75)
        heard_text = full_text[:interrupted_offset]

        # 1. Active intent seeded
        intent = ActionIntent(
            intent_id=f"intent-{turn_id}",
            turn_id=turn_id,
            workspace_epoch=1,
            workspace_revision=i + 1,
            kind="SPEAK",
            behavior_decision={"goal": "ENGAGE"},
        )
        agent._active_action_intent = intent
        agent._active_response_turn_id = turn_id
        agent.last_assistant_response = full_text

        # 2. Simulate playback progress reaching interrupted_offset
        await agent._on_audio_playback_progress({
            "utterance_id": turn_id,
            "character_offset": interrupted_offset,
            "word_index": len(heard_text.split()),
            "completed": False,
        })

        # 3. Simulate audio.stop arrival and measure latency to OutcomeRecord
        t0 = time.perf_counter()
        await agent._on_audio_stop({
            "interrupt": True,
            "speculative": False,
            "reason": "user_speech_detected",
            "intent_type": "VOICE_INTERRUPTION",
            "turn_id": turn_id,
        })
        t1 = time.perf_counter()

        latency_ms = (t1 - t0) * 1000.0
        stop_to_outcome_latencies_ms.append(latency_ms)

        record = agent._last_outcome_record
        assert record is not None, "OutcomeRecord must be emitted on interruption"
        statuses.append(record.status)
        offset_diff = abs(record.character_offset - interrupted_offset)
        precision_errors.append(offset_diff)

        print(f"  [Interruption {i+1:02d}/10] Latency: {latency_ms:6.3f} ms | Status: {record.status} | Offset: {record.character_offset}/{interrupted_offset} (Diff: {offset_diff})")

    mean_latency = sum(stop_to_outcome_latencies_ms) / len(stop_to_outcome_latencies_ms)
    max_latency = max(stop_to_outcome_latencies_ms)
    all_truncated = all(s == "TRUNCATED" for s in statuses)
    zero_precision_error = all(d == 0 for d in precision_errors)

    verdict = "PASS" if all_truncated and zero_precision_error and max_latency <= 50.0 else "FAIL"

    res = {
        "benchmark_id": "BM-GPU-02",
        "interruptions_tested": 10,
        "mean_latency_ms": round(mean_latency, 3),
        "max_latency_ms": round(max_latency, 3),
        "target_max_latency_ms": "<= 50.0",
        "all_truncated": all_truncated,
        "zero_precision_error": zero_precision_error,
        "verdict": verdict,
    }
    print("\nResult Summary:")
    print(json.dumps(res, indent=2))
    return res


async def run_bm_gpu_03() -> dict[str, Any]:
    """BM-GPU-03: 20-Turn Longitudinal State Stability & Drift.
    
    Executes 20 sequential turns on SQLiteWorkspaceStore, verifying monotonicity and memory stability.
    """
    print("\n========================================================")
    print(" Running BM-GPU-03: 20-Turn Longitudinal State Stability")
    print("========================================================")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    store = SQLiteWorkspaceStore(db_path)
    session_id = "longitudinal-session-20"

    revisions: list[int] = []
    cas_conflicts: int = 0
    rss_samples_kb: list[float] = []

    try:
        initial_snap = await store.get_snapshot(session_id)
        current_epoch = initial_snap.epoch
        current_rev = initial_snap.revision

        rss_before = _read_vm_rss_kb()
        rss_samples_kb.append(rss_before)

        for turn in range(1, 21):
            snap = await store.get_snapshot(session_id)
            if snap.revision != turn - 1 or snap.epoch != current_epoch:
                cas_conflicts += 1

            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=snap.epoch,
                expected_revision=snap.revision,
                focus_update=f"Topic discussion turn {turn}",
                add_goals=[f"goal_turn_{turn}"],
                affect_update={"pleasure": round(0.1 * (turn % 5), 2), "arousal": 0.05, "dominance": 0.0},
                pending_action={"act": "SPEAK", "turn": turn},
                percept_id=f"percept:text:turn-{turn}",
            )

            try:
                new_snap = await store.commit_transition(cmd)
                revisions.append(new_snap.revision)
                current_rev = new_snap.revision
                current_epoch = new_snap.epoch
            except Exception as e:
                cas_conflicts += 1
                print(f"  [Turn {turn:02d}/20] Conflict/Error: {e}")

            rss_now = _read_vm_rss_kb()
            rss_samples_kb.append(rss_now)
            print(f"  [Turn {turn:02d}/20] Revision: {current_rev:2d} (Expected: {turn:2d}) | VmRSS: {rss_now:.1f} KB")

    finally:
        await store.close()
        for fpath in [db_path, f"{db_path}-wal", f"{db_path}-shm"]:
            if os.path.exists(fpath):
                os.unlink(fpath)

    monotonic = revisions == list(range(1, 21))
    initial_rss = rss_samples_kb[0]
    final_rss = rss_samples_kb[-1]
    rss_variance_pct = abs(final_rss - initial_rss) / max(initial_rss, 1.0) * 100.0

    verdict = "PASS" if monotonic and cas_conflicts == 0 and rss_variance_pct <= 5.0 else "FAIL"

    res = {
        "benchmark_id": "BM-GPU-03",
        "turns_executed": len(revisions),
        "revisions_monotonic": monotonic,
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
    client = OllamaClient(base_url="http://127.0.0.1:11434", model="qwen2.5:3b")
    
    results = {}
    results["BM-GPU-01"] = await run_bm_gpu_01(client)
    results["BM-GPU-02"] = await run_bm_gpu_02()
    results["BM-GPU-03"] = await run_bm_gpu_03()

    out_path = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_01", "gpu_benchmark_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote GPU benchmark results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
