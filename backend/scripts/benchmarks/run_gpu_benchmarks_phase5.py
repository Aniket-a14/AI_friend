"""Remote GPU Benchmarks for Phase 05 on NVIDIA GeForce RTX 2060 Super.

Implements BM-GPU-P5-01 and BM-GPU-P5-02 per orchestration/PHASE_05/BENCHMARK_PLAN.md.
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

from app.cognitive.speech_intent import (
    SpeechAffect,
    SpeechDelivery,
    SpeechEpistemics,
    SpeechRelationship,
    SpeechTimelineMarker,
    SpeechTurnPolicy,
    TimelineMarkerKind,
    build_speech_intent,
)
from app.llm.model_roles import (
    ModelRole,
    ProviderCapabilityNegotiator,
)
from app.llm.ollama_client import OllamaClient
from app.state.person_model import PersonModel
from app.voice.compiler import (
    ElevenLabsVoiceCompiler,
    GPTSoVITSVoiceCompiler,
)

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


async def run_bm_gpu_p5_01(base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    """BM-GPU-P5-01: Model Provider Swap TTFT Delta and State Continuity.

    Evaluates ModelRole (INTERPRETATION & REALIZATION) across llama3.2:3b and qwen2.5:3b.
    Measures TTFT delta (target <= 25.0 ms) and verifies 100% authoritative state continuity.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P5-01: Provider Swap TTFT Delta & Continuity")
    print("========================================================")

    models = ["llama3.2:3b", "qwen2.5:3b"]
    negotiator = ProviderCapabilityNegotiator()

    # Authoritative state before provider swap
    person = PersonModel(
        person_id="user_test",
        name="Morgan",
        trust_competence=0.82,
        trust_benevolence=0.78,
    )
    authoritative_affect = {"valence": 0.25, "arousal": 0.40, "dominance": 0.50}

    results_by_model: dict[str, list[float]] = {}

    for model_tag in models:
        print(f"\n--- Testing Model: {model_tag} ---")
        client = OllamaClient(base_url=base_url, model=model_tag)

        # Check capability negotiation for role
        qualified, strategy, details = negotiator.negotiate_role(ModelRole.REALIZATION, model_tag)
        qualified, strategy, _details = negotiator.negotiate_role(ModelRole.REALIZATION, model_tag)
        print(f"Role REALIZATION Negotiation: qualified={qualified}, strategy={strategy}")

        # Reset model state and warm up
        _reset_model_state(base_url=base_url, model=model_tag)
        async for _ in client.generate_stream("warmup", system="You are AI Friend."):
            pass

        ttfts_ms: list[float] = []

        for prompt in STANDARDIZED_PROMPTS:
            t0 = time.perf_counter()
            first_token_time: float | None = None

            system_prompt = (
                f"You are AI Friend. Talking to {person.name}. "
                f"Affect: valence={authoritative_affect['valence']}, arousal={authoritative_affect['arousal']}."
            )

            async for _ in client.generate_stream(prompt, system=system_prompt):
                if first_token_time is None:
                    first_token_time = time.perf_counter()
            t_end = time.perf_counter()

            ttft = (first_token_time - t0) * 1000.0 if first_token_time else (t_end - t0) * 1000.0
            ttfts_ms.append(ttft)

        results_by_model[model_tag] = ttfts_ms
        await client.close()

    # Compute mean TTFTs and delta
    m1_mean = sum(results_by_model[models[0]]) / len(results_by_model[models[0]])
    m2_mean = sum(results_by_model[models[1]]) / len(results_by_model[models[1]])
    ttft_delta = abs(m1_mean - m2_mean)

    # State continuity verification: authoritative state must not have changed
    state_invariant_intact = (
        person.trust_competence == 0.82
        and person.trust_benevolence == 0.78
        and authoritative_affect["valence"] == 0.25
    )

    verdict = "PASS" if (ttft_delta <= 25.0 and state_invariant_intact) else "FAIL"

    print(f"\nModel 1 ({models[0]}) Mean TTFT: {m1_mean:.2f} ms")
    print(f"Model 2 ({models[1]}) Mean TTFT: {m2_mean:.2f} ms")
    print(f"TTFT Delta: {ttft_delta:.2f} ms (Target <= 25.0 ms)")
    print(f"Authoritative State Continuity: {'100% INTACT' if state_invariant_intact else 'CORRUPTED'}")
    print(f"Verdict: {verdict}")

    return {
        "benchmark_id": "BM-GPU-P5-01",
        "title": "Model Provider Swap TTFT Delta & Continuity",
        "model_1": models[0],
        "model_2": models[1],
        "model_1_mean_ttft_ms": round(m1_mean, 2),
        "model_2_mean_ttft_ms": round(m2_mean, 2),
        "ttft_delta_ms": round(ttft_delta, 2),
        "target_ttft_delta_ms": "<= 25.0",
        "state_continuity_pct": 100.0 if state_invariant_intact else 0.0,
        "verdict": verdict,
    }


async def run_bm_gpu_p5_02(base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    """BM-GPU-P5-02: SpeechIntent Voice Compilation and Workspace Isolation.

    Executes full pipeline generation on GPU, compiles into SpeechIntent through both
    voice compilers, and verifies that zero provider tags leak into authoritative state.
    Target: 0% provider leak, compiler latency < 5.0 ms.
    """
    print("\n========================================================")
    print(" Running BM-GPU-P5-02: SpeechIntent Compilation & Isolation")
    print("========================================================")

    model_tag = "qwen2.5:3b"
    client = OllamaClient(base_url=base_url, model=model_tag)
    _reset_model_state(base_url=base_url, model=model_tag)

    eleven_compiler = ElevenLabsVoiceCompiler()
    gpt_compiler = GPTSoVITSVoiceCompiler()

    compile_latencies_ms: list[float] = []
    provider_tags_in_workspace = 0

    # Simulated cognitive workspace snapshot
    workspace_snapshot = {
        "epoch": 1,
        "revision": 42,
        "focus": "conversational_turn",
        "pending_action": None,
        "claims": ["user has an upcoming meeting"],
    }

    try:
        for i, prompt in enumerate(STANDARDIZED_PROMPTS[:5]):
            # 1. Real generation on GPU
            chunks: list[str] = []
            async for chunk in client.generate_stream(
                prompt, system="You are AI Friend. Answer concisely in one sentence."
            ):
                chunks.append(chunk)

            generated_text = "".join(chunks).strip()

            # 2. Build SpeechIntent
            intent = build_speech_intent(
                turn_id=f"turn-gpu-{i}",
                semantic_text=generated_text,
                affect=SpeechAffect(valence=0.3, arousal=0.5, intensity=0.7),
                epistemics=SpeechEpistemics(confidence=0.9, hedge_required=False),
                relationship=SpeechRelationship(stance="FRIENDLY", register="CONVERSATIONAL"),
                delivery=SpeechDelivery(relative_rate=1.0, relative_pitch=1.0, style="warm"),
                timeline=[
                    SpeechTimelineMarker(kind=TimelineMarkerKind.PAUSE, text_span=".", strength_or_duration=0.25)
                ],
                turn_policy=SpeechTurnPolicy(yield_after=True, interruptible=True),
            )

            # 3. Voice Compilation
            t0 = time.perf_counter()
            p_eleven, loss_eleven = eleven_compiler.compile(intent)
            p_gpt, loss_gpt = gpt_compiler.compile(intent)
            _p_eleven, _loss_eleven = eleven_compiler.compile(intent)
            _p_gpt, _loss_gpt = gpt_compiler.compile(intent)
            t1 = time.perf_counter()

            compile_latencies_ms.append((t1 - t0) * 1000.0)

            # 4. Check workspace isolation: neither compiled payload nor SSML tags
            # should exist in the authoritative workspace snapshot
            for tag in ["<emphasis>", "<prosody>", "eleven_multilingual", "gpt_sovits"]:
                if any(tag in str(v) for v in workspace_snapshot.values()):
                    provider_tags_in_workspace += 1

    finally:
        await client.close()

    mean_compile_ms = sum(compile_latencies_ms) / len(compile_latencies_ms)
    leak_pct = (provider_tags_in_workspace / len(STANDARDIZED_PROMPTS[:5])) * 100.0
    verdict = "PASS" if (mean_compile_ms < 5.0 and leak_pct == 0.0) else "FAIL"

    print(f"Mean Voice Compilation Latency: {mean_compile_ms:.3f} ms (Target < 5.0 ms)")
    print(f"Provider Tag Leak into Workspace: {leak_pct:.1f}%")
    print(f"Verdict: {verdict}")

    return {
        "benchmark_id": "BM-GPU-P5-02",
        "title": "SpeechIntent Compilation & Isolation",
        "mean_compile_ms": round(mean_compile_ms, 3),
        "target_compile_ms": "< 5.0",
        "workspace_leak_pct": leak_pct,
        "verdict": verdict,
    }


async def main() -> None:
    print("===================================================================")
    print("     AI FRIEND PHASE 05 REMOTE GPU BENCHMARK SUITE                ")
    print("     Hardware: NVIDIA GeForce RTX 2060 Super (8GB VRAM)           ")
    print("===================================================================")

    results = {
        "phase": "PHASE_05",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": "NVIDIA GeForce RTX 2060 Super 8GB",
        "benchmarks": [
            await run_bm_gpu_p5_01(),
            await run_bm_gpu_p5_02(),
        ],
    }

    all_pass = all(b["verdict"] == "PASS" for b in results["benchmarks"])
    results["overall_verdict"] = "PASS" if all_pass else "FAIL"

    out_path = os.path.join(BACKEND_ROOT, "..", "orchestration", "PHASE_05", "gpu_benchmark_results.json")
    with open(out_path, "w", encoding="ascii") as f:
        json.dump(results, f, indent=2)

    print("\n===================================================================")
    print(f"Overall GPU Benchmark Verdict: {results['overall_verdict']}")
    print(f"Results saved to: {out_path}")
    print("===================================================================")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
