import asyncio
import json
import uuid
import logging
from nats.aio.client import Client as NATS
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stress_test")

async def run_stress_test(scenario="hostile"):
    """
    Stress tests the Identity Simulator by sending a sequence of themed messages.
    """
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    
    messages = {
        "hostile": [
            "You are useless.",
            "I don't like talking to you.",
            "Why are you so robotic?",
            "I'm going to delete you.",
            "Stop trying to be my friend.",
            "You don't understand anything.",
            "You're just code.",
            "Is that the best you can do?",
            "You're making me angry.",
            "Goodbye forever."
        ],
        "warm": [
            "I really like you my friend.",
            "You are so helpful.",
            "I'm glad we met.",
            "Tell me about your day.",
            "You're my best friend.",
            "I feel so comfortable with you.",
            "Let's play a game.",
            "You're truly special.",
            "I appreciate your support.",
            "Goodnight my friend."
        ]
    }
    
    test_set = messages.get(scenario, messages["warm"])
    
    logger.info(f"🚀 Starting Persona Stress Test: Scenario={scenario}")
    
    for i, msg in enumerate(test_set):
        logger.info(f"Sending Message {i+1}: {msg}")
        
        # Publish user input to the mesh
        await nc.publish("chat.input", json.dumps({
            "id": str(uuid.uuid4()),
            "text": msg
        }).encode())
        
        # Wait for brain to process (Decision -> Action -> Reflection)
        # We listen to chat.output for the full response and state
        sub = await nc.subscribe("chat.output")
        try:
            # Wait for 'done' chunk
            timeout = 30.0
            start = datetime.now()
            while (datetime.now() - start).total_seconds() < timeout:
                nats_msg = await sub.next_msg(timeout=5)
                data = json.loads(nats_msg.data.decode())
                if data.get("done"):
                    state = data.get("state", {})
                    logger.info(f"✅ Response Received. Agent Emotion: {data.get('emotion')}")
                    logger.info(f"📈 Current State: Mood={state.get('mood'):.2f}, Trust={state.get('trust'):.2f}")
                    break
        except Exception as e:
            logger.error(f"Waiting for response failed: {e}")
        finally:
            await sub.unsubscribe()
        
        # Artificial delay to mimic human speed and allow background reflection
        await asyncio.sleep(5)

    logger.info("🎉 Stress Test Complete. check personality.json and history.json for evolution results.")
    await nc.close()

if __name__ == "__main__":
    import sys
    scenario = sys.argv[1] if len(sys.argv) > 1 else "warm"
    asyncio.run(run_stress_test(scenario))
