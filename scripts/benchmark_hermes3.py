#!/usr/bin/env python3
"""
Hermes 3 (8B) Empirical Latency & Throughput Benchmark
=====================================================
Measures:
  1. Time-To-First-Token (TTFT) in milliseconds
  2. Sustained Generation Throughput (tokens/second)
  3. Total Turn Latency (ms)
  4. Response Quality & JSON Schema Extraction

Run this in your Colab terminal or notebook while Ollama is running:
  python scripts/benchmark_hermes3.py
"""

import json
import subprocess
import time
import httpx

MODEL_TAG = "hermes3:8b"
OLLAMA_URL = "http://127.0.0.1:11434"

PROMPTS = [
    {
        "category": "Emotional Empathy",
        "prompt": "I had a really exhausting and frustrating day at work. I feel like none of my effort is being appreciated. Can you just talk with me for a moment?",
    },
    {
        "category": "Theory of Mind & Memory Grounding",
        "prompt": "Remember earlier when I mentioned I was learning guitar? What was that chord progression I said I was struggling with, or how should I practice finger placement?",
    },
    {
        "category": "Short Conversational Pacing (Voice Friendly)",
        "prompt": "What's the weather like in your mind right now? Give me a warm, poetic 2-sentence answer.",
    },
    {
        "category": "Multi-turn Roleplay / Presence",
        "prompt": "If we could take a walk anywhere right now, where would we go and what would we talk about?",
    },
    {
        "category": "Structured System 2 Appraisal (JSON Extraction)",
        "prompt": (
            "Analyze the emotional state of a user who says: 'I can't take this anymore, everything is piling up.' "
            "Output strictly valid JSON with keys: 'valence' (float -1 to 1), 'arousal' (float 0 to 1), "
            "'dominance' (float 0 to 1), 'inferred_need' (string), 'suggested_action' (string)."
        ),
    },
]


def get_gpu_info():
    try:
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "N/A (No nvidia-smi)"


def run_benchmark():
    print("=" * 70)
    print(f"🚀 AI Friend — Empirical Benchmark: {MODEL_TAG}")
    print(f"🖥️  GPU Info: {get_gpu_info()}")
    print("=" * 70)

    client = httpx.Client(base_url=OLLAMA_URL, timeout=120.0)

    # 1. Health check & model warm-up
    try:
        tags = client.get("/api/tags").json()
        available_models = [m["name"] for m in tags.get("models", [])]
        print(f"📦 Available Ollama Models: {available_models}")
        if not any(MODEL_TAG in m for m in available_models):
            print(f"⚠️ Model '{MODEL_TAG}' not found locally. Pulling now...")
            subprocess.run(["ollama", "pull", MODEL_TAG], check=True)
    except Exception as e:
        print(f"❌ Failed to reach Ollama at {OLLAMA_URL}: {e}")
        print("Please ensure Ollama is running (`ollama serve &`)")
        return

    print("\n🔥 Warming up KV-Cache...")
    client.post(
        "/api/generate", json={"model": MODEL_TAG, "prompt": "Hello", "stream": False}
    )
    print("✅ Model warm and ready.\n")

    results = []
    ttft_list = []
    tps_list = []
    latency_list = []

    for idx, item in enumerate(PROMPTS, 1):
        category = item["category"]
        prompt = item["prompt"]

        print(f"[{idx}/{len(PROMPTS)}] Testing: {category}")
        print(f'  Prompt: "{prompt[:60]}..."')

        start_time = time.perf_counter()
        first_token_time = None
        tokens = []

        with client.stream(
            "POST", "/api/generate", json={"model": MODEL_TAG, "prompt": prompt}
        ) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                try:
                    payload = json.loads(line)
                    tok = payload.get("response", "")
                    tokens.append(tok)
                except Exception:
                    pass

        end_time = time.perf_counter()

        ttft_ms = (first_token_time - start_time) * 1000.0 if first_token_time else 0.0
        total_latency_ms = (end_time - start_time) * 1000.0
        token_count = len(tokens)
        gen_duration_sec = end_time - first_token_time if first_token_time else 0.0
        tokens_per_sec = token_count / gen_duration_sec if gen_duration_sec > 0 else 0.0

        full_response = "".join(tokens).strip()

        ttft_list.append(ttft_ms)
        tps_list.append(tokens_per_sec)
        latency_list.append(total_latency_ms)

        result_entry = {
            "prompt_idx": idx,
            "category": category,
            "ttft_ms": round(ttft_ms, 2),
            "total_latency_ms": round(total_latency_ms, 2),
            "token_count": token_count,
            "tokens_per_sec": round(tokens_per_sec, 2),
            "sample_output": full_response[:120] + "...",
        }
        results.append(result_entry)

        print(
            f"  ⚡ TTFT: {ttft_ms:.1f} ms | Speed: {tokens_per_sec:.1f} tok/s | Total: {total_latency_ms:.1f} ms | Tokens: {token_count}"
        )
        print(f'  💬 Sample: "{full_response[:90]}..."\n')

    # Summary calculations
    mean_ttft = sum(ttft_list) / len(ttft_list)
    mean_tps = sum(tps_list) / len(tps_list)
    mean_latency = sum(latency_list) / len(latency_list)

    print("=" * 70)
    print("📊 EMPIRICAL BENCHMARK SUMMARY FOR HERMES 3 (8B)")
    print("=" * 70)
    print(f"  • Mean Time-To-First-Token (TTFT) : {mean_ttft:.2f} ms")
    print(f"  • Mean Generation Throughput       : {mean_tps:.2f} tokens/sec")
    print(f"  • Mean Total Turn Latency          : {mean_latency:.2f} ms")
    print(f"  • GPU Hardware                    : {get_gpu_info()}")
    print("=" * 70)

    # Save report
    report = {
        "model": MODEL_TAG,
        "timestamp": time.time(),
        "gpu": get_gpu_info(),
        "summary": {
            "mean_ttft_ms": round(mean_ttft, 2),
            "mean_tokens_per_sec": round(mean_tps, 2),
            "mean_total_latency_ms": round(mean_latency, 2),
        },
        "trials": results,
    }

    out_file = "scripts/results/hermes3_benchmark_results.json"
    try:
        import os

        os.makedirs("scripts/results", exist_ok=True)
        with open(out_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"💾 Results saved to {out_file}")
    except Exception as e:
        print(f"Could not save output file: {e}")


if __name__ == "__main__":
    run_benchmark()
