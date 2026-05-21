import asyncio
import csv
import time
import json
import nats
import os
from datetime import datetime

# Research-grade Event-Driven State Collector (CVS-3.0)
# Listens to NATS broadcasts for the current PAD state of the agent
# and logs it to a CSV for high-fidelity research trajectories.

LOG_FILE = "research_pad_trajectory.csv"


async def run_collector():
    """
    Research State Collector.
    Uses NATS state.update broadcasts to log PAD trajectories.
    """
    print(f"\n📊 [Sovereign Mesh] State Collector starting... logging to {LOG_FILE}")

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    # Initialize CSV with high-fidelity headers
    with open(LOG_FILE, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "elapsed_sec",
                "pleasure",
                "arousal",
                "dominance",
                "trust",
                "cortisol",
                "dopamine",
                "fatigue",
                "inferred_valence",
                "inferred_arousal",
                "snr",
                "wing",
                "tags",
                "emotion",
            ]
        )

    print(f"Connected to NATS at {nats_url}")
    print("Listening for Real-time State Updates... (Ctrl+C to stop)\n")

    start_time = time.time()

    # Track latest auxiliary signals
    latest_snr = 0.0
    latest_wing = "none"
    latest_tags = []

    async def perception_handler(msg):
        nonlocal latest_snr
        data = json.loads(msg.data.decode())
        latest_snr = data.get("snr", 0.0)

    async def memory_handler(msg):
        nonlocal latest_wing
        data = json.loads(msg.data.decode())
        memories = data.get("memories", [])
        if memories:
            latest_wing = memories[0].get("scope", {}).get("wing", "none")

    async def output_handler(msg):
        nonlocal latest_tags
        data = json.loads(msg.data.decode())
        latest_tags = data.get("paralinguistic_tags", [])

    async def state_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            # CVS-3.0 uses direct fields: mood (P), energy (A), dominance (D)
            p = data.get("mood", 0.0)
            a = data.get("energy", 0.5)
            d = data.get("dominance", 0.5)
            trust = data.get("trust", 0.5)
            cortisol = data.get("cortisol", 0.0)
            dopamine = data.get("dopamine", 0.0)
            fatigue = data.get("fatigue", 0.0)

            # Theory of Mind user mental model
            user_mental_model = data.get("user_mental_model") or {}
            inferred_valence = user_mental_model.get("inferred_valence", 0.0)
            inferred_arousal = user_mental_model.get("inferred_arousal", 0.5)

            emotion = data.get("emotion", "neutral")

            elapsed = time.time() - start_time

            row = [
                datetime.now().isoformat(),
                round(elapsed, 3),
                p,
                a,
                d,
                trust,
                cortisol,
                dopamine,
                fatigue,
                inferred_valence,
                inferred_arousal,
                round(latest_snr, 2),
                latest_wing,
                "|".join(latest_tags),
                emotion,
            ]

            with open(LOG_FILE, mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            print(
                f"💓 [State] P:{p:+.2f} A:{a:+.2f} D:{d:+.2f} | T:{trust:.2f} | C:{cortisol:.2f} DP:{dopamine:.2f} F:{fatigue:.2f} | ToM V:{inferred_valence:+.2f} A:{inferred_arousal:.2f} | {emotion}"
            )
        except Exception as e:
            print(f"Error parsing state: {e}")

    # Subscribe to the full signal bouquet
    await nc.subscribe("state.update", cb=state_handler)
    await nc.subscribe("audio.perception", cb=perception_handler)
    await nc.subscribe("memory.surfaced", cb=memory_handler)
    await nc.subscribe("chat.output", cb=output_handler)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping collector...")
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(run_collector())
