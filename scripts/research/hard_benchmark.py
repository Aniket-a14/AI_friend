import asyncio
import json
import time
import nats
import os
import statistics
from datetime import datetime

# Sovereign Mesh: Architectural Performance Benchmarker
# Use this to generate the "Results" section for your research paper.
# Measures: Cognitive Response Latency (E2E), Time-to-First-Token (TTFT), and Jitter.

async def run_benchmark(iterations=50):
    print(f"\n🚀 --- Sovereign Mesh Hard Benchmark (Tier-4/5) ---")
    print(f"Iterations: {iterations} | Metrics: E2E Latency, TTFT, Jitter")
    
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    try:
        nc = await nats.connect(nats_url)
    except Exception as e:
        print(f"❌ Failed to connect to NATS at {nats_url}: {e}")
        print("💡 Please ensure your NATS mesh Docker container is active: docker compose up -d")
        return
    
    js = nc.jetstream()
    
    # Track per-pulse timing
    pulse_send_times = {}   # pulse_num -> send_time
    ttft_results = []       # Time to first token per pulse
    e2e_results = []        # End-to-end latency per pulse (done=True)
    seen_first = set()      # Track which pulses have seen their first chunk
    pulse_count = 0

    async def output_handler(msg):
        nonlocal pulse_count
        now = time.time()
        try:
            data = json.loads(msg.data.decode())
        except Exception:
            return
        
        # The original metadata is passed through the brain_agent pipeline
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        
        # Also check latency_metadata for start_time
        lat_meta = data.get("latency_metadata") or {}
        if not isinstance(lat_meta, dict):
            lat_meta = {}
        
        bench_id = metadata.get("benchmark_id", "")
        pulse_num = metadata.get("pulse_num", -1)
        start_time = metadata.get("start_time", 0)
        
        # Fallback: check pulse_send_times
        if start_time == 0 and pulse_num in pulse_send_times:
            start_time = pulse_send_times[pulse_num]
        
        if bench_id != "bench_pulse" or start_time <= 0:
            return
        
        latency_ms = (now - start_time) * 1000
        done = data.get("done", False)
        content = data.get("content", "")
        
        # Time to First Token
        if pulse_num not in seen_first and content:
            seen_first.add(pulse_num)
            ttft_results.append(latency_ms)
        
        # End-to-End (done signal)
        if done:
            e2e_results.append(latency_ms)
            pulse_count += 1
            full_resp = data.get("full_response", "")
            resp_preview = (full_resp or "")[:60].replace("\n", " ")
            print(f"  ✅ Pulse {pulse_count}/{iterations}: E2E={latency_ms:.0f}ms | \"{resp_preview}...\"")

    # Core NATS subscribe catches both JetStream and core NATS publishes
    await nc.subscribe("chat.output", cb=output_handler)

    print(f"\nStarting {iterations} pulses (5s spacing)...\n")

    for i in range(iterations):
        send_time = time.time()
        pulse_send_times[i] = send_time
        current_pulse = {
            "text": "Hello, can you see what I am doing right now?",
            "metadata": {
                "benchmark_id": "bench_pulse",
                "pulse_num": i,
                "start_time": send_time
            }
        }
        
        await js.publish("chat.input", json.dumps(current_pulse).encode())
        await asyncio.sleep(5)  # Allow time for LLM inference + cognitive pipeline

    # Extra wait for any trailing responses
    print("\n⏳ Waiting for trailing responses...")
    await asyncio.sleep(10)

    print("\n✅ Benchmarking complete. Finalizing statistics...\n")

    def compute_stats(data, label):
        if not data:
            print(f"  {label}: No data captured")
            return None
        avg = statistics.mean(data)
        sd = sorted(data)
        p50 = statistics.median(data)
        p95 = sd[int(len(sd) * 0.95)] if len(sd) > 1 else sd[-1]
        p99 = sd[int(len(sd) * 0.99)] if len(sd) > 1 else sd[-1]
        jitter = statistics.stdev(data) if len(data) > 1 else 0.0
        mn = min(data)
        mx = max(data)
        print(f"  {label}:")
        print(f"    Samples:  {len(data)}/{iterations}")
        print(f"    Mean:     {avg:.2f} ms")
        print(f"    p50:      {p50:.2f} ms")
        print(f"    p95:      {p95:.2f} ms")
        print(f"    p99:      {p99:.2f} ms")
        print(f"    Min:      {mn:.2f} ms")
        print(f"    Max:      {mx:.2f} ms")
        print(f"    Jitter:   {jitter:.2f} ms")
        return {
            "samples": len(data),
            "mean": round(avg, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "min": round(mn, 2),
            "max": round(mx, 2),
            "jitter": round(jitter, 2),
            "raw": [round(r, 2) for r in data]
        }

    print("📈 --- COGNITIVE BENCHMARK RESULTS ---")
    print("-" * 50)
    
    e2e_stats = compute_stats(e2e_results, "End-to-End Latency (Thought)")
    print()
    ttft_stats = compute_stats(ttft_results, "Time-to-First-Token (TTFT)")
    print("-" * 50)

    # Save results
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    results_data = {
        "timestamp": datetime.now().isoformat(),
        "iterations": iterations,
        "e2e": e2e_stats,
        "ttft": ttft_stats,
    }
    with open(out_path, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n💾 Results saved to: {out_path}")

    await nc.close()

if __name__ == "__main__":
    import sys
    iters = 50
    for idx, arg in enumerate(sys.argv):
        if arg in ("--iterations", "-i") and idx + 1 < len(sys.argv):
            try:
                iters = int(sys.argv[idx + 1])
            except ValueError:
                print(f"⚠️ Invalid iterations value, defaulting to 50")
    asyncio.run(run_benchmark(iterations=iters))
