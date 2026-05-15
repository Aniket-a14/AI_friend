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
    reflex_results = []
    
    # Test Payload: Standard conversation pulse
    test_pulse = {
        "text": "Hello, can you see what I am doing right now?",
        "metadata": {
            "benchmark_id": "bench_pulse",
            "start_time": 0
        }
    }

    async def reflex_handler(msg):
        nonlocal reflex_results
        now = time.time()
        data = json.loads(msg.data.decode())
        
        metadata = data.get("metadata", {})
        if metadata.get("benchmark_id") == "bench_pulse":
            start_time = metadata.get("start_time", 0)
            if start_time > 0:
                latency = (now - start_time) * 1000
                reflex_results.append(latency)

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
                print(f"✅ Pulse {len(results)}: Thought={latency:.0f}ms | Reflex={reflex_results[-1] if reflex_results else 0:.0f}ms")

    # Subscribe to Reflex (First sound) and Output (Full thought)
    await nc.subscribe("voice.segment", cb=reflex_handler)
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
        await asyncio.sleep(2.5) # Increased for stability

    print("\n✅ Benchmarking complete. Finalizing statistics...")

    if results:
        avg_thought = statistics.mean(results)
        avg_reflex = statistics.mean(reflex_results) if reflex_results else 0
        p99_thought = sorted(results)[int(len(results) * 0.99)]

        print(f"\n📈 --- HUMAN-FIDELITY RESULTS FOR PAPER ---")
        print(f"Reflex Latency (First Sound):  {avg_reflex:.2f} ms")
        print(f"Cognitive Latency (Thought):   {avg_thought:.2f} ms")
        print(f"Human-Likeness Gap:            {avg_thought - avg_reflex:.2f} ms")
        print("-" * 45)
        print(f"p99 Stability (Thought):       {p99_thought:.2f} ms")
        print("-" * 45)
        
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
