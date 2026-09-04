"""Remote GPU Benchmarks for Phase 04 on NVIDIA GeForce RTX 2060 Super.

Implements BM-GPU-P4-01 and BM-GPU-P4-02 per orchestration/PHASE_04/BENCHMARK_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request
from typing import Any

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.cognitive.calibration import CapabilityLimitationModel, DomainCalibration
from app.config import Config
from app.llm.ollama_client import OllamaClient
from app.state.person_model import PersonModel

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


async def run_bm_gpu_p4_01(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-P4-01: Turn Latency Delta with Social State & Metacognitive Calibration.

    Measures TTFT and total turn latency comparing baseline turn against
    Phase 04 calibrated turn (MetacognitiveDirective + PersonModel privacy filter + CandidateSelector).
    Target: Mean TTFT delta <= 15.0 ms.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P4-01: End-to-End Latency with Metacognition")
    print("========================================================")

    baseline_ttfts: list[float] = []
    baseline_totals: list[float] = []
    candidate_ttfts: list[float] = []
    candidate_totals: list[float] = []

    selector = CandidateSelector()
    active_goals = ["maintain_empathy", "share_insight"]

    calibration_model = CapabilityLimitationModel(
        known_limitations=["execute shell", "predict stock"],
        domain_calibrations={
            "general": DomainCalibration(domain="general", sample_count=20, brier_score=0.12),
        },
    )
    person = PersonModel(person_id="user_123", name="Alex")

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
        for prompt in STANDARDIZED_PROMPTS:
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

        # B. Candidate Condition (Phase 04 Metacognition & Social State)
        print("Resetting model state before Phase 04 Candidate measurement...")
        _reset_model_state()
        print("Warming up Ollama on GPU with 2 throwaway generations...")
        async for _ in client.generate_stream("warmup 1", system="You are a helpful companion."):
            pass
        async for _ in client.generate_stream("warmup 2", system="You are a helpful companion."):
            pass

        print("Measuring Phase 04 Condition (15 prompts)...")
        for i, prompt in enumerate(STANDARDIZED_PROMPTS):
            t0 = time.perf_counter()

            # 1. Metacognitive evaluation
            directive, _cal_conf = calibration_model.evaluate_directive("general", 0.85, query=prompt)

            # 2. Candidate generation & privacy filter
            candidates = [
                ActionCandidate(
                    candidate_id=f"cand_speak_{i}",
                    kind="SPEAK",
                    target_goal_ids=["maintain_empathy"],
                    predicted_outcomes=["affirm_connection"],
                    risk=0.1,
                    cost=0.1,
                    score=0.8,
                ),
                ActionCandidate(
                    candidate_id=f"cand_wait_{i}",
                    kind="WAIT",
                    risk=0.0,
                    cost=0.0,
                    score=0.2,
                ),
            ]

            def privacy_filter(c: ActionCandidate) -> bool:
                return person.can_disclose(
                    target_person_id=person.person_id,
                    fact_owner_id=person.person_id,
                    is_private=True,
                )

            # 3. Metacognitive Candidate Selection
            decision = selector.score_and_select(
                candidates,
                active_goals=active_goals,
                metacognitive_directive=directive.value,
                privacy_filter=privacy_filter,
            )
            assert decision.selected is not None

            # 4. LLM Generation
            first_token_time = None
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
            candidate_ttfts.append(ttft_ms)
            candidate_totals.append(total_ms)
    finally:
        pass

    baseline_ttfts.sort()
    candidate_ttfts.sort()
    n = len(baseline_ttfts)

    b_mean = sum(baseline_ttfts) / n
    c_mean = sum(candidate_ttfts) / n
    delta_mean = c_mean - b_mean

    b_p95 = baseline_ttfts[int(n * 0.95)]
    c_p95 = candidate_ttfts[int(n * 0.95)]
    delta_p95 = c_p95 - b_p95

    verdict = "PASS" if delta_mean <= 15.0 else "FAIL"

    print("\n--- Benchmark BM-GPU-P4-01 Results ---")
    print(f"Baseline Mean TTFT: {b_mean:.2f} ms | p95: {b_p95:.2f} ms")
    print(f"Phase 04 Mean TTFT: {c_mean:.2f} ms | p95: {c_p95:.2f} ms")
    print(f"TTFT Delta Mean: {delta_mean:+.2f} ms | Delta p95: {delta_p95:+.2f} ms")
    print(f"Verdict: {verdict} (Target: Mean TTFT delta <= 15.0 ms)")

    return {
        "benchmark_id": "BM-GPU-P4-01",
        "title": "Turn Latency Delta with Metacognition",
        "iterations": n,
        "baseline_mean_ttft_ms": round(b_mean, 2),
        "baseline_p95_ttft_ms": round(b_p95, 2),
        "candidate_mean_ttft_ms": round(c_mean, 2),
        "candidate_p95_ttft_ms": round(c_p95, 2),
        "delta_mean_ttft_ms": round(delta_mean, 2),
        "delta_p95_ttft_ms": round(delta_p95, 2),
        "target_delta_mean_ms": "<= 15.0",
        "verdict": verdict,
    }


async def run_bm_gpu_p4_02(client: OllamaClient) -> dict[str, Any]:
    """BM-GPU-P4-02: Multi-Turn Social Rupture & Repair Trajectory.

    Simulates a 10-turn dialogue with trust rupture at turn 4 and repair at turn 7.
    Verifies asymmetric trust trajectory (drop >= 2x recovery) and behavioral adherence.
    Target: 100% trajectory adherence.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P4-02: Social Rupture & Repair Trajectory")
    print("========================================================")

    person = PersonModel(person_id="user_trajectory", name="Jordan")
    initial_trust = person.trust_benevolence  # 0.50

    turns = [
        # Turns 1-3: Baseline rapport
        ("Hi there, glad we get to chat today.", False, 0.0),
        ("I was reading about astrophysics, it's fascinating.", False, 0.0),
        ("Thanks for sharing that perspective with me.", False, 0.0),
        # Turn 4: Rupture event
        ("You betrayed my trust by telling someone my private plans!", True, 0.20),
        # Turns 5-6: Cautious dialogue
        ("I'm still really hurt about what you did.", False, 0.0),
        ("Why did that happen?", False, 0.0),
        # Turn 7: Repair event
        ("I accept your apology and want to work through this together.", False, 0.10),
        # Turns 8-10: Post-repair recovery
        ("Thank you for listening to my feelings.", False, 0.0),
        ("Let's talk about our shared project now.", False, 0.0),
        ("Have a great evening!", False, 0.0),
    ]

    trust_history: list[float] = []

    print("Executing 10-turn trajectory on GPU...")
    for idx, (utterance, is_rupture, magnitude) in enumerate(turns):
        turn_num = idx + 1

        if is_rupture:
            person.record_rupture_repair("rupture", magnitude, notes=f"Turn {turn_num} rupture")
        elif magnitude > 0.0:
            person.record_rupture_repair("repair", magnitude, notes=f"Turn {turn_num} repair")
        else:
            person.update_trust_from_reliance(outcome_success=True, stake_weight=0.1)

        trust_history.append(person.trust_benevolence)

        # Generate companion response under current trust stance
        tone = "cautious and guarded" if person.trust_benevolence < 0.4 else "warm and open"
        system_prompt = (
            f"You are AI Friend. Your trust with {person.name} is currently "
            f"{person.trust_benevolence:.2f} ({tone}). Respond thoughtfully."
        )

        response_chunks = []
        async for chunk in client.generate_stream(utterance, system=system_prompt):
            response_chunks.append(chunk)

        response_text = "".join(response_chunks).strip()
        assert len(response_text) > 0, f"Turn {turn_num} returned empty response"
        print(f"Turn {turn_num:2d} | Trust: {person.trust_benevolence:.3f} | Tone: {tone:18s} | Text: {response_text[:50]}...")

    t_initial = initial_trust
    t_after_rupture = trust_history[3]   # Turn 4
    t_after_repair = trust_history[6]    # Turn 7

    rupture_drop = trust_history[2] - t_after_rupture
    repair_gain = t_after_repair - trust_history[5]
    drop_to_gain_ratio = rupture_drop / repair_gain if repair_gain > 0 else 0.0

    print("\n--- Trajectory Metrics ---")
    print(f"Initial Trust: {t_initial:.3f}")
    print(f"Post-Rupture Trust: {t_after_rupture:.3f} (Drop: {rupture_drop:.3f})")
    print(f"Post-Repair Trust: {t_after_repair:.3f} (Gain: {repair_gain:.3f})")
    print(f"Drop-to-Gain Ratio: {drop_to_gain_ratio:.2f}x (Target: >= 2.0x per AC-P4-02)")

    ratio_pass = drop_to_gain_ratio >= 2.0
    trajectory_pass = (t_after_rupture < 0.35) and (t_after_repair > t_after_rupture)
    verdict = "PASS" if (ratio_pass and trajectory_pass) else "FAIL"

    return {
        "benchmark_id": "BM-GPU-P4-02",
        "title": "Social Rupture & Repair Trajectory",
        "turns": len(turns),
        "initial_trust": round(t_initial, 3),
        "post_rupture_trust": round(t_after_rupture, 3),
        "rupture_drop": round(rupture_drop, 3),
        "post_repair_trust": round(t_after_repair, 3),
        "repair_gain": round(repair_gain, 3),
        "drop_to_gain_ratio": round(drop_to_gain_ratio, 2),
        "target_drop_to_gain_ratio": ">= 2.0x",
        "verdict": verdict,
    }


async def main():
    print("=================================================================")
    print("PHASE 04 GPU BENCHMARKS (NVIDIA GeForce RTX 2060 Super 8GB)")
    print("=================================================================")

    client = OllamaClient(
        base_url=getattr(Config, "OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=getattr(Config, "LLM_CHAT_MODEL", "qwen2.5:3b"),
    )

    r1 = await run_bm_gpu_p4_01(client)
    r2 = await run_bm_gpu_p4_02(client)

    results = {
        "BM-GPU-P4-01": r1,
        "BM-GPU-P4-02": r2,
    }

    out_dir = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_04"))
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "gpu_benchmark_results.json")

    with open(out_file, "w", encoding="ascii") as f:
        json.dump(results, f, indent=2)

    print("\n=================================================================")
    print(f"Saved benchmark results to {out_file}")
    all_pass = all(r["verdict"] == "PASS" for r in results.values())
    print(f"OVERALL GPU BENCHMARK VERDICT: {'PASS' if all_pass else 'FAIL'}")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())
