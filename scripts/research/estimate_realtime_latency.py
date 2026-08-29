#!/usr/bin/env python3
"""
Mesh Latency Profile Simulation Script.
Measures Tier 1 and Tier 2 database operations to verify sub-10ms latency SLOs.
"""

import sys
import os
import time
import json
import asyncio
import numpy as np

# Adjust paths to import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
)

from app.state.identity_core_store import IdentityCoreStore
from app.state.working_memory_store import WorkingMemoryStore
from app.state.semantic_recall_store import SemanticRecallStore


def generate_vector(dim=768):
    vec = np.random.randn(dim)
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        vec = np.zeros(dim)
        vec[0] = 1.0
        return vec.tolist()
    return (vec / norm).tolist()


async def run_latency_profile():
    print("======================================================================")
    print("🧬  AI FRIEND AI Friend LATENCY PROFILE & SLO VERIFICATION RUNNER  🧬")
    print("======================================================================\n")

    # --- 1. IDENTITY CORE STORE BENCHMARK ---
    print("--- [Tier 1] Identity Core Store (SQLite) ---")
    identity_store = IdentityCoreStore(db_path=":memory:")

    # Measure uncached load
    start = time.perf_counter()
    identity_store.load_into_cache()
    uncached_dur = (time.perf_counter() - start) * 1000.0

    # Measure cached read (Target <1ms)
    cached_runs = []
    for _ in range(100):
        start = time.perf_counter()
        _ = identity_store.get_identity()
        cached_runs.append((time.perf_counter() - start) * 1000.0)

    avg_cached = np.mean(cached_runs)
    p95_cached = np.percentile(cached_runs, 95)

    print(f"  Uncached DB Load:        {uncached_dur:.4f} ms")
    print(f"  Cached Memory Read (Avg): {avg_cached:.4f} ms")
    print(f"  Cached Memory Read (p95): {p95_cached:.4f} ms")
    status_cached = "✅ PASS" if avg_cached < 1.0 else "⚠️ WARN"
    print(f"  SLO Compliance (< 1ms):   {status_cached}\n")

    # --- 2. WORKING MEMORY STORE BENCHMARK ---
    print("--- [Tier 1] Working Memory Store (Redis with SQLite Fallback) ---")
    working_store = WorkingMemoryStore(db_path="test_working_memory.db", max_turns=8)
    if working_store.redis_client is None:
        raise ConnectionError(
            "❌ ERROR: Redis is offline. Production Working Memory latency cannot be measured without a live Redis server."
        )
    print("  Active Mode:             Redis (Distributed)")

    # Measure turn appending (Target <10ms)
    append_runs = []
    for i in range(50):
        start = time.perf_counter()
        await working_store.add_turn(
            role="user" if i % 2 == 0 else "assistant",
            content=f"This is turn {i} in the latency benchmark simulation.",
            metadata={"index": i, "timestamp": time.time()},
        )
        append_runs.append((time.perf_counter() - start) * 1000.0)

    avg_append = np.mean(append_runs)
    p95_append = np.percentile(append_runs, 95)

    # Measure recent turns fetch
    fetch_runs = []
    for _ in range(50):
        start = time.perf_counter()
        _ = await working_store.get_recent_turns(limit=8)
        fetch_runs.append((time.perf_counter() - start) * 1000.0)

    avg_fetch = np.mean(fetch_runs)
    p95_fetch = np.percentile(fetch_runs, 95)

    print(f"  Turn Append Latency (Avg):  {avg_append:.4f} ms")
    print(f"  Turn Append Latency (p95):  {p95_append:.4f} ms")
    print(f"  Recent Turns Fetch (Avg):   {avg_fetch:.4f} ms")
    print(f"  Recent Turns Fetch (p95):   {p95_fetch:.4f} ms")
    status_working_append = "✅ PASS" if avg_append < 10.0 else "⚠️ WARN"
    status_working_fetch = "✅ PASS" if avg_fetch < 10.0 else "⚠️ WARN"
    print(f"  SLO Compliance Append (< 10ms):  {status_working_append}")
    print(f"  SLO Compliance Fetch (< 10ms):   {status_working_fetch}\n")

    # Cleanup temp SQLite fallback file if any
    if os.path.exists("test_working_memory.db"):
        try:
            os.remove("test_working_memory.db")
        except Exception:
            pass

    # --- 3. SEMANTIC RECALL STORE BENCHMARK ---
    print("--- [Tier 2] Semantic Recall Store (Qdrant Vector Database) ---")
    semantic_store = SemanticRecallStore(
        collection_name="latency_bench_memories", vector_size=768
    )
    if semantic_store.client is None:
        raise ConnectionError(
            "❌ ERROR: Qdrant is offline. Production Semantic Vector Search latency cannot be measured without a live Qdrant server."
        )
    print("  Active Mode:             Qdrant Online")

    upsert_runs = []
    search_runs = []

    # Measure vector upsert
    for i in range(10):
        vec = generate_vector(768)
        start = time.perf_counter()
        semantic_store.add_vector_memory(
            memory_id=str(1000 + i),
            vector=vec,
            content=f"Benchmark recollection statement {i}.",
            metadata={"valence": 0.5, "importance": 0.8},
        )
        upsert_runs.append((time.perf_counter() - start) * 1000.0)

    # Measure cosine vector query (Target <10ms)
    for _ in range(20):
        q_vec = generate_vector(768)
        start = time.perf_counter()
        _ = semantic_store.search_vector_memories(query_vector=q_vec, limit=5)
        search_runs.append((time.perf_counter() - start) * 1000.0)

    # Cleanup test collection
    try:
        semantic_store.client.delete_collection("latency_bench_memories")
    except Exception:
        pass

    avg_upsert = np.mean(upsert_runs)
    avg_search = np.mean(search_runs)
    p95_search = np.percentile(search_runs, 95)

    print(f"  Vector Upsert Latency (Avg): {avg_upsert:.4f} ms")
    print(f"  Vector Search Latency (Avg): {avg_search:.4f} ms")
    print(f"  Vector Search Latency (p95): {p95_search:.4f} ms")
    status_search = "✅ PASS" if avg_search < 10.0 else "⚠️ WARN"
    print(f"  SLO Compliance (< 10ms):     {status_search}\n")

    # --- 4. SYSTEM 1 DSP & AUDIO PIPELINE BENCHMARK ---
    print("--- [System 1] DSP Feature Extraction & Attenuation loop ---")

    # Simulate DSP audio extraction (30ms of 16kHz PCM audio -> 480 samples)
    num_samples = 480
    dummy_pcm = np.random.randint(-1000, 1000, size=num_samples, dtype=np.int16)

    dsp_runs = []
    for _ in range(100):
        start = time.perf_counter()
        # 1. RMS Energy
        sum_sq = np.sum((dummy_pcm / 32767.0) ** 2)
        _energy_rms = np.sqrt(sum_sq / num_samples) if num_samples > 0 else 0.0

        # 2. Pitch f0 autocorrelation (vectorized for simulation speed)
        _pitch_f0 = 150.0
        if num_samples > 400:
            min_lag = 40
            max_lag = 200
            centered = dummy_pcm.astype(np.float64) - np.mean(dummy_pcm)
            corr = np.correlate(centered, centered, mode="full")
            corr = corr[num_samples - 1 :]
            best_lag = min_lag + np.argmax(corr[min_lag : max_lag + 1])
            if corr[0] > 0 and corr[best_lag] > 0.3 * corr[0]:
                _pitch_f0 = 16000.0 / best_lag

        # 3. ZCR and tempo
        zero_crossings = np.sum(np.diff(np.sign(dummy_pcm) >= 0))
        zcr = zero_crossings / num_samples if num_samples > 0 else 0.0
        _tempo_wpm = 120.0 + min(60.0, zcr * 200.0)

        dsp_runs.append((time.perf_counter() - start) * 1000.0)

    avg_dsp = np.mean(dsp_runs)
    p95_dsp = np.percentile(dsp_runs, 95)

    # Viseme profiling removed -- out of scope for physiological-marker metrics (no physiological markers)

    # Soft-attenuation volume ducking transition window simulation
    ducking_runs = []
    for _ in range(100):
        start = time.perf_counter()
        _attenuation_factor = 1.0
        target = 0.3
        # Linear OLA scaling simulation sample-by-sample for 160 samples (10ms)
        chunk = dummy_pcm[:160].astype(np.float32)
        for idx in range(160):
            progress = idx / 160.0
            scale = 1.0 - progress * (1.0 - target)
            chunk[idx] *= scale
        ducking_runs.append((time.perf_counter() - start) * 1000.0)

    avg_ducking = np.mean(ducking_runs)
    p95_ducking = np.percentile(ducking_runs, 95)

    print(f"  DSP Feature Extraction (Avg): {avg_dsp:.4f} ms")
    print(f"  DSP Feature Extraction (p95): {p95_dsp:.4f} ms")
    status_dsp = "✅ PASS" if avg_dsp < 1.0 else "⚠️ WARN"
    print(f"  SLO Compliance (< 1.0ms):      {status_dsp}\n")

    print(f"  Soft Ducking Transition (Avg): {avg_ducking:.4f} ms")
    print(f"  Soft Ducking Transition (p95): {p95_ducking:.4f} ms")
    status_ducking = "✅ PASS" if avg_ducking < 1.0 else "⚠️ WARN"
    print(f"  SLO Compliance (< 1.0ms):      {status_ducking}\n")

    # --- 4.5. COGNITIVE PROSODY TRAJECTORY GENERATION PIPELINE ---
    print("--- [System 2] Cognitive Prosody Trajectory Generation (APRA v2) ---")
    import cognitive_rust
    from app.contracts import ProsodyFrame

    arousal = 0.5
    valence = 0.3
    dominance = 0.7
    fatigue = 0.1

    prosody_runs = []
    for _ in range(100):
        start_t = time.perf_counter()
        trajectory_tuples = cognitive_rust.generate_apra_trajectory(
            valence, arousal, dominance, fatigue
        )
        _ = [
            ProsodyFrame(time_offset_ms=t_ms, rate=r, pitch=p, volume=v)
            for t_ms, r, p, v in trajectory_tuples
        ]
        prosody_runs.append((time.perf_counter() - start_t) * 1000.0)

    avg_prosody = np.mean(prosody_runs)
    p95_prosody = np.percentile(prosody_runs, 95)

    print(f"  Prosody Trajectory Gen (Avg): {avg_prosody:.4f} ms")
    print(f"  Prosody Trajectory Gen (p95): {p95_prosody:.4f} ms")
    status_prosody = "✅ PASS" if avg_prosody < 1.0 and p95_prosody < 1.0 else "⚠️ WARN"
    print(f"  SLO Compliance (< 1.0ms):      {status_prosody}\n")

    # --- 5. SUMMARY REPORT ---
    print("======================================================================")
    print("📊                      LATENCY METRICS SUMMARY                       ")
    print("======================================================================")
    print(
        f" {'Operation':<35} | {'Average (ms)':<15} | {'SLO Limit (ms)':<15} | {'Compliance':<10}"
    )
    print("-" * 83)
    search_avg_str = (
        f"{avg_search:<15.4f}" if avg_search != float("inf") else f"{'N/A':<15}"
    )
    search_status = (
        "✅ PASS"
        if avg_search < 10.0
        else ("⚠️ WARN" if avg_search != float("inf") else "❌ UNKNOWN")
    )
    print(
        f" {'Identity Cached Lookup':<35} | {avg_cached:<15.4f} | {'1.0000':<15} | {status_cached}"
    )
    print(
        f" {'Working Memory Append':<35} | {avg_append:<15.4f} | {'10.0000':<15} | {status_working_append}"
    )
    print(
        f" {'Working Memory Fetch':<35} | {avg_fetch:<15.4f} | {'10.0000':<15} | {status_working_fetch}"
    )
    print(
        f" {'Semantic Vector Search':<35} | {search_avg_str} | {'10.0000':<15} | {search_status}"
    )
    print(
        f" {'DSP Audio Feature Extraction':<35} | {avg_dsp:<15.4f} | {'1.0000':<15} | {status_dsp}"
    )

    print(
        f" {'Soft Ducking Transition':<35} | {avg_ducking:<15.4f} | {'1.0000':<15} | {status_ducking}"
    )
    print(
        f" {'Prosody Trajectory Generation':<35} | {avg_prosody:<15.4f} | {'1.0000':<15} | {status_prosody}"
    )
    print("======================================================================\n")

    # Write report as artifact
    report_data = {
        "timestamp": time.time(),
        "identity_cached_lookup_avg_ms": avg_cached,
        "working_memory_append_avg_ms": avg_append,
        "working_memory_fetch_avg_ms": avg_fetch,
        "semantic_vector_search_avg_ms": avg_search
        if avg_search != float("inf")
        else None,
        "dsp_extraction_avg_ms": avg_dsp,
        "soft_ducking_latency_avg_ms": avg_ducking,
        "prosody_trajectory_generation_avg_ms": avg_prosody,
    }

    os.makedirs("scripts/results", exist_ok=True)
    with open("scripts/results/latency_profile.json", "w") as f:
        json.dump(report_data, f, indent=2)

    print("💾 Profile metrics saved to: scripts/results/latency_profile.json")


if __name__ == "__main__":
    asyncio.run(run_latency_profile())
