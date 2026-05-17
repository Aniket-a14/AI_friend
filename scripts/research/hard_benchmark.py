import asyncio
import json
import time
import nats
import os
import statistics
from datetime import datetime

# Sovereign Mesh: Architectural Performance Benchmarker
# Use this to generate the "Results" section for your research paper.
# Measures: Cognitive Response Latency, Throughput Stability, and Jitter.

async def run_benchmark(iterations=20):
    print(f"\n🚀 --- Sovereign Mesh Hard Benchmark (Tier-4/5) ---")
    print(f"Iterations: {iterations} | Target: p99 Latency & Multi-token Throughput")
    
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    try:
        nc = await nats.connect(nats_url)
    except Exception as e:
        print(f"❌ Failed to connect to NATS at {nats_url}: {e}")
        print("💡 Please ensure your NATS mesh Docker container is active: docker compose up -d")
        return
        
    results = []
    
    # Test Payload: Standard conversation pulse
    test_pulse = {
        "text": "Hello, can you see what I am doing right now?",
        "metadata": {
            "benchmark_id": "bench_pulse",
            "start_time": 0
        }
    }

    async def output_handler(msg):
        nonlocal results
        now = time.time()
        data = json.loads(msg.data.decode())
        
        metadata = data.get("metadata", {})
        if metadata.get("benchmark_id") == "bench_pulse":
            start_time = metadata.get("start_time", 0)
            if start_time > 0:
                latency = (now - start_time) * 1000
                results.append(latency)
                print(f"✅ Pulse {len(results)}: Thought={latency:.0f}ms")

    # Subscribe purely to Cognitive Output (Full thought)
    await nc.subscribe("chat.output", cb=output_handler)

    print(f"Starting {iterations} pulses...")

    for i in range(iterations):
        current_pulse = test_pulse.copy()
        current_pulse["metadata"] = {
            "benchmark_id": "bench_pulse",
            "pulse_num": i,
            "start_time": time.time()
        }
        
        await nc.publish("chat.input", json.dumps(current_pulse).encode())
        await asyncio.sleep(2.5) # Dynamic sleep for response resolution

    print("\n✅ Benchmarking complete. Finalizing statistics...")

    if results:
        avg_thought = statistics.mean(results)
        sorted_res = sorted(results)
        p50 = statistics.median(results)
        p95 = sorted_res[int(len(sorted_res) * 0.95)] if len(sorted_res) > 0 else 0
        p99 = sorted_res[int(len(sorted_res) * 0.99)] if len(sorted_res) > 0 else 0
        jitter = statistics.stdev(results) if len(results) > 1 else 0.0

        print(f"\n📈 --- COGNITIVE RESULTS FOR PAPER ---")
        print(f"Cognitive Latency (Thought):   {avg_thought:.2f} ms")
        print("-" * 45)
        print(f"p99 Stability (Thought):       {p99:.2f} ms")
        print("-" * 45)
        
        # Save to file for easy copy-paste
        out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
        with open(out_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "avg": avg_thought,
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "jitter": jitter,
                "raw_data_thought": results
            }, f, indent=2)
        print(f"💾 Raw results saved to: {out_path}")
            
    else:
        print("❌ No results captured. Is the Brain Agent running in Docker?")

    await nc.close()

if __name__ == "__main__":
    asyncio.run(run_benchmark())
