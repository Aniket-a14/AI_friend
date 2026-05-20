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
    {"text": "I finally got the job I wanted! I'm so happy!", "expected_tag": "[laughs]", "trend": "Positive / High Arousal"},
    {"text": "I feel like I'm failing everyone. Everything is going wrong.", "expected_tag": "[sighs]", "trend": "Negative / High Arousal"},
    {"text": "The weather is okay today. Just a normal day.", "expected_tag": None, "trend": "Neutral / Low Arousal"},
    {"text": "You are my best friend, I trust you completely.", "expected_tag": None, "trend": "High Trust / Personal Wing"}
]

async def run_human_fidelity_test():
    print(f"\n💓 --- Sovereign Mesh: Human Fidelity Test (Tier-5) ---")
    print(f"Goal: Measure affective synchronization, Paralinguistic Alignment, and Memory Saliency.")
    
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    js = nc.jetstream()
    
    pad_results = []
    captured_tags = []
    captured_wings = []

    async def state_handler(msg):
        data = json.loads(msg.data.decode())
        pad = {
            "P": data.get("mood", 0.0),
            "A": data.get("energy", 0.5),
            "D": data.get("dominance", 0.5)
        }
        pad_results.append(pad)

    async def output_handler(msg):
        data = json.loads(msg.data.decode())
        tags = data.get("paralinguistic_tags", [])
        captured_tags.extend(tags)

    async def memory_handler(msg):
        data = json.loads(msg.data.decode())
        # The new hierarchical contract uses 'scope.wing'
        memories = data.get("memories", [])
        for m in memories:
            wing = m.get("scope", {}).get("wing", "unknown")
            captured_wings.append(wing)

    await nc.subscribe("state.update", cb=state_handler)
    await nc.subscribe("chat.output", cb=output_handler)
    await nc.subscribe("memory.surfaced", cb=memory_handler)

    print("\n🚀 Injecting Psychological Scenarios...")

    for scenario in SCENARIOS:
        print(f"\n💬 Stimulus: \"{scenario['text']}\"")
        captured_tags.clear()
        captured_wings.clear()
        
        await js.publish("chat.input", json.dumps({
            "text": scenario['text'],
            "metadata": {"benchmark_id": "human_fidelity"}
        }).encode())
        
        await asyncio.sleep(8)  # Allow time for full cognitive pipeline + LLM
        
        print(f"📈 Trend: {scenario['trend']}")
        print(f"🎭 Tags Detected:  {captured_tags if captured_tags else 'None'}")
        print(f"🧠 Wings Triggered: {list(set(captured_wings)) if captured_wings else 'No Recall'}")
        
        if scenario['expected_tag'] and scenario['expected_tag'] in captured_tags:
            print("✅ Paralinguistic Alignment: MATCH")
        elif scenario['expected_tag']:
            print("⚠️ Paralinguistic Alignment: MISMATCH")

    print("\n✅ --- HUMAN FIDELITY TEST COMPLETE ---")
    print("Use the 'collector.py' CSV data to plot the full affective arc for your paper.")
    
    await nc.close()

if __name__ == "__main__":
    asyncio.run(run_human_fidelity_test())
