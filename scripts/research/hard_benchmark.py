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
    nc = await nats.connect(nats_url)
    
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
                print(f"✅ Pulse {len(results)}: {latency:.2f}ms (RTT-aware)")

    # Subscribe to the final cognitive output (The moment the Brain decides)
    await nc.subscribe("chat.output", cb=output_handler)

    print(f"Starting {iterations} pulses...")

    for i in range(iterations):
        pulse_id = f"pulse_{i}"
        current_pulse = test_pulse.copy()
        current_pulse["metadata"] = {
            "benchmark_id": "bench_pulse",
            "pulse_num": i,
            "start_time": time.time()
        }
        
        # Publish to the mesh
        await nc.publish("chat.input", json.dumps(current_pulse).encode())
        
        # Wait for the mesh to process before next pulse
        # This simulates high-frequency natural interaction
        await asyncio.sleep(1.5) 
        print(f"[{i+1}/{iterations}] Pulse injected...", end='\r')

    print("\n✅ Benchmarking complete. Finalizing statistics...")

    if results:
        p50 = statistics.median(results)
        p95 = sorted(results)[int(len(results) * 0.95)]
        p99 = sorted(results)[int(len(results) * 0.99)]
        avg = statistics.mean(results)
        jitter = statistics.stdev(results) if len(results) > 1 else 0

        print(f"\n📈 --- QUANTIFIABLE RESULTS FOR PAPER ---")
        print(f"Subject: Cognitive Turnaround (STT -> Brain Decision)")
        print("-" * 45)
        print(f"Average Latency: {avg:.2f} ms")
        print(f"p50 (Median):    {p50:.2f} ms")
        print(f"p95 (Burst):     {p95:.2f} ms")
        print(f"p99 (Worst Case):{p99:.2f} ms")
        print(f"Jitter (StdDev): {jitter:.2f} ms")
        print("-" * 45)
        print(f"Throughput:      {1000/avg:.2f} cognitive-turns/sec (theoretical)")
        
        # Save to file for easy copy-paste
        with open("benchmark_results.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "avg": avg,
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "jitter": jitter,
                "raw_data": results
            }, f, indent=2)
            
    else:
        print("❌ No results captured. Is the Brain Agent running in Docker?")

    await nc.close()

if __name__ == "__main__":
    asyncio.run(run_benchmark())
