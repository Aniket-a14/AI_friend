import asyncio
import json
import time
import nats
import os


async def run_monitor():
    """
    Mesh Latency Monitor (CVS-3.0 Multimodal).
    Subscribes to input, output, and perceptual subjects to calculate precise
    cognitive turnaround and multimodal jitter.
    """
    print("\n📡 Sovereign Mesh Research Monitor (Tier-4/5) online...")
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    start_times = {}

    print(f"Connected to NATS at {nats_url}")
    print("Tracking: Audio, Vision, and Speculative Intent.\n")

    async def input_handler(msg):
        data = json.loads(msg.data.decode())
        # Track start time from the mesh metadata
        metadata = data.get("metadata", {})
        benchmark_id = metadata.get("benchmark_id", "user_input")
        start_times[benchmark_id] = time.time()
        print(f"📥 [Input] Received: {benchmark_id}")

    async def output_handler(msg):
        data = json.loads(msg.data.decode())
        now = time.time()

        metadata = data.get("metadata", {})
        benchmark_id = metadata.get("benchmark_id", "user_input")

        if benchmark_id in start_times:
            latency_ms = (now - start_times[benchmark_id]) * 1000
            print(
                f"✅ [Result] TURNAROUND COMPLETE | ID: {benchmark_id} | Latency: {latency_ms:.2f}ms"
            )
            del start_times[benchmark_id]

    async def perception_handler(msg):
        """Track speculative STT latency (The 'Reflex' time)"""
        time.time()
        print(
            f"⚡ [Reflex] Speculative Intent Detected: {msg.subject} (High Frequency)"
        )

    async def vision_handler(msg):
        """Track Multimodal Vision descriptions"""
        data = json.loads(msg.data.decode())
        desc = data.get("description", "")
        print(f"👁️ [Vision] Description received ({len(desc)} chars): {desc[:60]}...")

    # Subscribe to subjects using the new Super-Wildcard routing
    await nc.subscribe("chat.input", cb=input_handler)
    await nc.subscribe("chat.output", cb=output_handler)
    await nc.subscribe("audio.perception", cb=perception_handler)
    await nc.subscribe("vision.description", cb=vision_handler)

    print("Listening for signal pulses... (Ctrl+C to stop)")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(run_monitor())
