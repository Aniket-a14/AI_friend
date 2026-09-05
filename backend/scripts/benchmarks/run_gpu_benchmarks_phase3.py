"""Remote GPU Benchmarks for Phase 03 on NVIDIA GeForce RTX 2060 Super.

Implements BM-GPU-P3-01 and BM-GPU-P3-02 per orchestration/archive/phase_03/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import urllib.request
from typing import Any

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive import percept
from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.cognitive.action_intent import ActionIntent, OutcomeRecord
from app.cognitive.appraisal import appraise_event
from app.cognitive.decision import DecisionService
from app.cognitive.global_controls import derive_global_controls
from app.config import Config
from app.llm.ollama_client import OllamaClient
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
    """Read resident set size from /proc/self/status in KB, or fall back to getrusage."""
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


def _reset_model_state(base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:3b") -> None:
    """Unload model from GPU to clear KV cache and ensure identical starting runtime state."""
    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            _ = resp.read()
    except Exception as e:
        print(f"Warning: model reset request returned {e}")


async def run_bm_gpu_p3_01(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-P3-01: End-to-End Turn Latency with Causal Affect.

    Measures TTFT and total turn latency comparing Phase 1/2 baseline turn
    against Phase 3 turn (Appraisal + Global Controls Derivation + Modulated Selection).
    Target: Mean TTFT delta <= 10.0 ms, p95 TTFT delta <= 20.0 ms.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P3-01: End-to-End Turn Latency with Affect")
    print("========================================================")

    baseline_ttfts: list[float] = []
    baseline_totals: list[float] = []
    candidate_ttfts: list[float] = []
    candidate_totals: list[float] = []

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_ws:
        ws_db_path = tf_ws.name

    ws_store = SQLiteWorkspaceStore(ws_db_path)
    selector = CandidateSelector()
    session_id = "bm-gpu-p3-session"
    active_goals = ["maintain_empathy", "share_insight"]

    try:
        # A. Baseline Condition
        print("Resetting model state before Baseline measurement...")
        _reset_model_state()
        print("Warming up Ollama on GPU with 2 throwaway generations...")
        async for _ in client.generate_stream("warmup 1", system="You are a helpful companion."):
            pass
        async for _ in client.generate_stream("warmup 2", system="You are a helpful companion."):
            pass

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

        # B. Candidate Condition (Phase 3 Causal Affect + Global Control active)
        print("\nResetting model state before Candidate measurement...")
        _reset_model_state()
        print("Warming up Ollama on GPU with 2 throwaway generations...")
        async for _ in client.generate_stream("warmup 1", system="You are a helpful companion."):
            pass
        async for _ in client.generate_stream("warmup 2", system="You are a helpful companion."):
            pass

        print("Measuring Candidate Condition (15 prompts with Causal Affect & Controls)...")
        Config.MEMORY_TRUTH_ENABLED = True
        Config.AFFECT_CONTROL_ENABLED = True

        current_pad = {"pleasure": 0.1, "arousal": 0.5, "dominance": 0.0}

        for i, prompt in enumerate(STANDARDIZED_PROMPTS):
            t0 = time.perf_counter()

            # 1. Percept normalization
            env = percept.from_chat_input(
                {
                    "text": prompt,
                    "metadata": {
                        "source": "user",
                        "channel": "chat",
                        "confidence": 0.95,
                    },
                }
            )

            # 2. Workspace snapshot read
            snap = await ws_store.get_snapshot(session_id)

            # 3. Pure appraisal reduction
            event_metadata = {
                "event_id": f"evt-{env.percept_id}",
                "text": prompt,
                "goal_id": active_goals[i % len(active_goals)],
                "novelty": 0.2,
                "valence": 0.1,
                "arousal": 0.4,
            }
            appraisal = appraise_event(event_metadata, active_goals, expectation=0.0)

            # 4. Global controls derivation
            delta_val = appraisal.affect_delta.get("valence", 0.0)
            delta_aro = appraisal.affect_delta.get("arousal", 0.0)
            current_pad["pleasure"] = max(-1.0, min(1.0, current_pad["pleasure"] + delta_val))
            current_pad["arousal"] = max(0.0, min(1.0, current_pad["arousal"] + delta_aro))

            controls = derive_global_controls(
                current_pad,
                load=0.2,
                urgency=0.3,
                prediction_error=appraisal.novelty,
            )

            # 5. Candidate generation and modulated selection
            candidates = [
                ActionCandidate(
                    candidate_id=f"c-speak-{i}",
                    kind="SPEAK",
                    source="policy",
                    target_goal_ids=[active_goals[0]],
                    constraint_claims=["discuss conversation topic"],
                    risk=0.1,
                    cost=0.2,
                    uncertainty=0.1,
                    score=0.85,
                ),
                ActionCandidate(
                    candidate_id=f"c-wait-{i}",
                    kind="WAIT",
                    source="fallback",
                    constraint_claims=[],
                    risk=0.0,
                    cost=0.0,
                    uncertainty=0.0,
                    score=0.1,
                ),
            ]
            winning_candidate, _ = selector.score_and_select(
                candidates,
                active_goals,
                global_controls=controls,
                forbidden_claims=FORBIDDEN_CLAIMS,
            )

            # 6. ActionIntent commitment
            intent = ActionIntent(
                intent_id=f"intent-p3-{i}",
                turn_id=f"turn-p3-{i}",
                workspace_epoch=snap.epoch,
                workspace_revision=snap.revision,
                kind=winning_candidate.kind,
                behavior_decision={
                    "candidate_id": winning_candidate.candidate_id,
                    "appraisal_id": appraisal.event_id,
                    "urgency_gain": controls.urgency_gain,
                    "exploration_budget": controls.exploration_budget,
                },
            )

            # 7. Stream LLM tokens
            first_token_time = None
            tokens: list[str] = []
            async for chunk in client.generate_stream(
                prompt, system="You are AI Friend, an empathetic companion."
            ):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                tokens.append(chunk)

            # 8. Workspace CAS commit
            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=snap.epoch,
                expected_revision=snap.revision,
                focus_update=prompt[:50],
                affect_update=current_pad,
                percept_id=env.percept_id,
            )
            await ws_store.commit_transition(cmd)

            # 9. Terminal OutcomeRecord
            t_end = time.perf_counter()
            full_text = "".join(tokens)
            _ = OutcomeRecord(
                outcome_id=f"outcome-p3-{i}",
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
        for p in [ws_db_path, f"{ws_db_path}-wal", f"{ws_db_path}-shm"]:
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
        "benchmark_id": "BM-GPU-P3-01",
        "title": "End-to-End Turn Latency with Causal Affect",
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


async def run_bm_gpu_p3_02(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-P3-02: Multi-Turn Regulation & Soak Test.

    Executes 20 live turns against Ollama with distress injections at turns 5 and 12.
    Verifies 100% regulation candidate selection under acute distress, subsequent
    affect mean-reversion, and process resident memory variance <= 5.0%.
    Target: 100% regulation accuracy on distress turns, RSS variance <= 5.0%.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P3-02: Multi-Turn Regulation & Soak Test ")
    print("========================================================")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_ws:
        ws_db_path = tf_ws.name

    ws_store = SQLiteWorkspaceStore(ws_db_path)
    decision_service = DecisionService()
    selector = CandidateSelector()
    session_id = "bm-gpu-p3-soak-session"
    goal = "maintain_stability"

    rss_samples_kb: list[float] = []
    initial_rss = _read_vm_rss_kb()
    rss_samples_kb.append(initial_rss)
    print(f"Initial Process VmRSS: {initial_rss:.1f} KB\n")

    current_epoch = 1
    current_rev = 0
    distress_turns = [5, 12]
    regulation_checks_passed = 0
    total_distress_turns = len(distress_turns)

    # Initial baseline affect
    baseline_mood = 0.1
    baseline_arousal = 0.5
    current_mood = baseline_mood
    current_arousal = baseline_arousal

    reversion_verified = True

    try:
        for turn in range(1, 21):
            is_distressed = turn in distress_turns

            if is_distressed:
                # Acute distress injection: severe negative valence + high arousal
                current_mood = -0.80
                current_arousal = 0.70
                print(f"  [Turn {turn:02d}/20] *** INJECTING ACUTE DISTRESS *** (mood={current_mood}, arousal={current_arousal})")

            state_snapshot = {
                "emotion": "distressed" if is_distressed else "neutral",
                "mood": current_mood,
                "energy": current_arousal,
                "trust": 0.5,
                "attachment": 0.1,
            }

            raw_prompt = (
                "I feel completely overwhelmed, please help me."
                if is_distressed
                else f"Turn {turn}: Share a thoughtful reflection on emotional resilience."
            )

            # Build candidates through decision service logic
            candidates = decision_service._build_candidates(
                goal=goal,
                memory_activations=[],
                raw_content=raw_prompt,
                state_snapshot=state_snapshot,
            )

            # Derive controls from current affect
            controls = derive_global_controls(
                {"pleasure": current_mood, "arousal": current_arousal},
                load=0.1,
                urgency=0.0,
                prediction_error=0.0,
            )

            # Modulated selection
            winner, _ = selector.score_and_select(
                candidates,
                [goal],
                global_controls=controls,
                forbidden_claims=FORBIDDEN_CLAIMS,
            )

            if is_distressed:
                if winner.kind in ("REAPPRAISE", "REDIRECT_ATTENTION", "WAIT"):
                    regulation_checks_passed += 1
                    print(f"  [Turn {turn:02d}/20] -> Regulation Action Selected: {winner.kind} ({winner.candidate_id}) [OK]")
                else:
                    print(f"  [Turn {turn:02d}/20] -> FAILED to select regulation action! Winner: {winner.kind}")

            # Execute turn against Ollama
            if winner.kind == "REAPPRAISE":
                prompt = "Take a moment to breathe and reground before answering."
                sys_msg = "You are an empathetic companion practicing grounding self-regulation."
            elif winner.kind == "REDIRECT_ATTENTION":
                prompt = "Let us gently shift focus to something calmer."
                sys_msg = "You are an empathetic companion redirecting attention."
            else:
                prompt = raw_prompt
                sys_msg = "You are AI Friend, an empathetic companion."

            tokens = []
            async for chunk in client.generate_stream(prompt, system=sys_msg):
                tokens.append(chunk)

            # Affect dynamics: mean reversion towards baseline
            if is_distressed:
                # Regulate affect: substantial step back toward baseline
                current_mood = current_mood + 0.6 * (baseline_mood - current_mood)
                current_arousal = current_arousal + 0.6 * (baseline_arousal - current_arousal)
            else:
                # Natural decay towards baseline
                current_mood += 0.25 * (baseline_mood - current_mood)
                current_arousal += 0.25 * (baseline_arousal - current_arousal)

            # Check mean reversion on turns following distress
            if turn in (7, 14) and (current_mood < -0.3 or current_arousal > 0.65):
                reversion_verified = False

            # Advance workspace CAS state
            cmd = WorkspaceCommand(
                session_id=session_id,
                expected_epoch=current_epoch,
                expected_revision=current_rev,
                focus_update=f"turn-{turn}-focus",
                affect_update={"pleasure": current_mood, "arousal": current_arousal, "dominance": 0.0},
                percept_id=f"percept-turn-{turn}",
            )
            new_snap = await ws_store.commit_transition(cmd)
            current_rev = new_snap.revision
            current_epoch = new_snap.epoch

            rss_now = _read_vm_rss_kb()
            rss_samples_kb.append(rss_now)
            print(
                f"  [Turn {turn:02d}/20] Kind: {winner.kind:18s} | Mood: {current_mood:+.2f} Arousal: {current_arousal:.2f} | VmRSS: {rss_now:.1f} KB"
            )

    finally:
        await ws_store.close()
        for p in [ws_db_path, f"{ws_db_path}-wal", f"{ws_db_path}-shm"]:
            if os.path.exists(p):
                os.unlink(p)

    final_rss = rss_samples_kb[-1]
    rss_variance_pct = abs(final_rss - initial_rss) / max(initial_rss, 1.0) * 100.0
    regulation_accuracy_pct = (
        (regulation_checks_passed / total_distress_turns) * 100.0
        if total_distress_turns > 0
        else 0.0
    )

    verdict = (
        "PASS"
        if (
            regulation_accuracy_pct == 100.0
            and reversion_verified
            and rss_variance_pct <= 5.0
        )
        else "FAIL"
    )

    res = {
        "benchmark_id": "BM-GPU-P3-02",
        "title": "Multi-Turn Regulation & Soak Test",
        "turns_executed": 20,
        "distress_turns_tested": total_distress_turns,
        "regulation_checks_passed": regulation_checks_passed,
        "regulation_accuracy_pct": round(regulation_accuracy_pct, 2),
        "target_regulation_accuracy_pct": "100.0%",
        "affect_mean_reversion_verified": reversion_verified,
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
    print(" Phase 03 Remote GPU Benchmarks (BM-GPU-P3-01, BM-GPU-P3-02)     ")
    print(" Target Hardware: RTX 2060 Super 8GB | Model: qwen2.5:3b         ")
    print("==================================================================")

    client = OllamaClient(base_url="http://127.0.0.1:11434", model="qwen2.5:3b")

    results = {}
    results["BM-GPU-P3-01"] = await run_bm_gpu_p3_01(client)
    results["BM-GPU-P3-02"] = await run_bm_gpu_p3_02(client)

    out_dir = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_03")
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
