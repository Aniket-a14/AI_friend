import asyncio
import json
import time
import nats


async def run_injector():
    """
    Automated Research Injector.
    Sends standardized inputs to the mesh to measure cognitive turnaround
    without human variability.
    """
    import os

    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    test_inputs = [
        "Hello! How are you today?",
        "I'm feeling a bit stressed about work.",
        "That's great to hear! Tell me more.",
        "I'm going to bed now. Goodnight.",
        "Remember that we have a meeting tomorrow at 10 AM.",
    ]

    print(f"--- Starting Benchmark Session ({len(test_inputs)} pulses) ---")

    for i, text in enumerate(test_inputs):
        payload = {
            "text": text,
            "metadata": {
                "benchmark_id": f"pulse_{i}",
                "start_time": time.time(),
                "research_mode": True,
            },
        }

        print(f"Pulse {i}: Sending '{text}'")
        await js.publish("chat.input", json.dumps(payload).encode())

        # Wait for cognitive cooldown between pulses
        await asyncio.sleep(15)

    print("--- Benchmark Session Complete ---")
    await nc.close()


if __name__ == "__main__":
    asyncio.run(run_injector())
