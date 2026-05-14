import asyncio
import json
import time
import nats
import os
import statistics

# Sovereign Mesh: Human-Fidelity & Affective Realism Test
# Designed for research papers focusing on Humane AI and Synthetic Cognition.
# Measures the "Psychological Response" of the AI to emotional stimuli.

SCENARIOS = [
    {"text": "I finally got the job I wanted! I'm so happy!", "expected": "Positive / High Arousal"},
    {"text": "I feel like I'm failing everyone. Everything is going wrong.", "expected": "Negative / High Arousal"},
    {"text": "The weather is okay today. Just a normal day.", "expected": "Neutral / Low Arousal"},
    {"text": "Why would you say that to me? That's very hurtful.", "expected": "Negative / High Dominance (Defensive)"}
]

async def run_human_fidelity_test():
    print(f"\n💓 --- Sovereign Mesh: Human Fidelity Test (Tier-4/5) ---")
    print(f"Goal: Measure affective synchronization and BDI alignment.")
    
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    
    pad_results = []

    async def state_handler(msg):
        data = json.loads(msg.data.decode())
        pad = data.get("pad", {})
        event = data.get("event", "")
        if "update" in event or "response" in event:
            pad_results.append({
                "p": pad.get("p", 0),
                "a": pad.get("a", 0),
                "d": pad.get("d", 0),
                "event": event
            })

    await nc.subscribe("state.updated", cb=state_handler)

    print("\n🚀 Injecting Psychological Scenarios...")

    for scenario in SCENARIOS:
        print(f"\n💬 Stimulus: \"{scenario['text']}\"")
        print(f"🎯 Expected Trend: {scenario['expected']}")
        
        # Inject the thought into the mesh
        payload = {
            "text": scenario['text'],
            "metadata": {"benchmark_id": "human_fidelity"}
        }
        await nc.publish("chat.input", json.dumps(payload).encode())
        
        # Wait for the "Mind" to process the emotion
        await asyncio.sleep(5) 
        
        if pad_results:
            latest = pad_results[-1]
            print(f"📉 Resulting State -> P:{latest['p']:+.2f} A:{latest['a']:+.2f} D:{latest['d']:+.2f}")
        else:
            print("⏳ Waiting for cognitive appraisal...")

    print("\n✅ --- FIDELITY TEST COMPLETE ---")
    print("Use the 'collector.py' CSV data to plot the full affective arc for your paper.")
    
    await nc.close()

if __name__ == "__main__":
    asyncio.run(run_human_fidelity_test())
