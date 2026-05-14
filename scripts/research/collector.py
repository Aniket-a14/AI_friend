import asyncio
import csv
import time
import json
import nats
import os
from datetime import datetime

# Research-grade Event-Driven State Collector (CVS-1.0)
# Listens to NATS broadcasts for the current PAD state of the agent 
# and logs it to a CSV for high-fidelity research trajectories.

LOG_FILE = "research_pad_trajectory.csv"

async def run_collector():
    """
    Research State Collector.
    Uses NATS state.updated broadcasts to log PAD trajectories.
    """
    print(f"\n📊 [Sovereign Mesh] State Collector starting... logging to {LOG_FILE}")
    
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)

    # Initialize CSV with high-fidelity headers
    # PAD (Pleasure, Arousal, Dominance)
    with open(LOG_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "elapsed_sec", "pleasure", "arousal", "dominance", "event_type"])

    print(f"Connected to NATS at {nats_url}")
    print("Listening for Real-time State Updates... (Ctrl+C to stop)\n")
    
    start_time = time.time()

    async def state_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            pad = data.get("pad", {})
            p = pad.get("p", 0.0)
            a = pad.get("a", 0.0)
            d = pad.get("d", 0.0)
            event = data.get("event", "decay")
            
            elapsed = time.time() - start_time
            
            row = [
                datetime.now().isoformat(),
                round(elapsed, 3),
                p, a, d,
                event
            ]
            
            with open(LOG_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            # Print state to console
            print(f"💓 [State] P:{p:+.2f} A:{a:+.2f} D:{d:+.2f} | {event[:15]}")
        except Exception as e:
            print(f"Error parsing state: {e}")

    # Subscribe to state updates (Super-Wildcard routing)
    await nc.subscribe("state.updated", cb=state_handler)
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping collector...")
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(run_collector())
