import asyncio
import json
import time
import nats

async def run_monitor():
    """
    Mesh Latency Monitor.
    Subscribes to input and output subjects to calculate precise cognitive turnaround.
    """
    print("📡 Mesh Latency Monitor online...")
    nc = await nats.connect("nats://localhost:4222")
    
    start_times = {}

    async def input_handler(msg):
        data = json.loads(msg.data.decode())
        if "metadata" in data and "start_time" in data["metadata"]:
            benchmark_id = data["metadata"].get("benchmark_id", "default")
            start_times[benchmark_id] = data["metadata"]["start_time"]
            print(f"TRACKING: {benchmark_id}")

    async def output_handler(msg):
        data = json.loads(msg.data.decode())
        now = time.time()
        
        # Try to find matching benchmark_id in metadata
        metadata = data.get("metadata", {})
        benchmark_id = metadata.get("benchmark_id", "default")
        
        if benchmark_id in start_times:
            latency_ms = (now - start_times[benchmark_id]) * 1000
            print(f"✅ TURNAROUND COMPLETE | ID: {benchmark_id} | Latency: {latency_ms:.2f}ms")
            del start_times[benchmark_id]

    await nc.subscribe("chat.input", cb=input_handler)
    await nc.subscribe("chat.output", cb=output_handler)
    
    print("Listening for signal pulses... (Ctrl+C to stop)")
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(run_monitor())
