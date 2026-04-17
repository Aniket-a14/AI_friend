import asyncio
import time
import nats
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    start_time = time.time()
    
    first_token_time = None
    first_audio_time = None

    async def chat_handler(msg):
        nonlocal first_token_time
        data = json.loads(msg.data.decode())
        if first_token_time is None and data.get("content"):
            first_token_time = time.time()
            logger.info(f"✨ First Token received in {(first_token_time - start_time)*1000:.2f}ms")

    async def audio_handler(msg):
        nonlocal first_audio_time
        data = json.loads(msg.data.decode())
        if first_audio_time is None and data.get("audio"):
            first_audio_time = time.time()
            logger.info(f"🔊 First Audio Chunk received in {(first_audio_time - start_time)*1000:.2f}ms")

    # Subscribe to outputs
    await js.subscribe("chat.output", cb=chat_handler, deliver_policy="new")
    await js.subscribe("audio.stream", cb=audio_handler, deliver_policy="new")

    # Send input
    logger.info("🚀 Sending benchmark request: 'Hi'")
    payload = {
        "text": "Hi",
        "latency_metadata": {
            "start_time": start_time,
            "hops": []
        }
    }
    await js.publish("chat.input", json.dumps(payload).encode())

    # Wait for results
    timeout = 30.0
    end_wait = time.time() + timeout
    while (first_audio_time is None) and time.time() < end_wait:
        await asyncio.sleep(0.1)

    if first_audio_time:
        total_latency = (first_audio_time - start_time) * 1000
        logger.info(f"✅ BENCHMARK COMPLETE | Total Latency: {total_latency:.2f}ms")
    else:
        logger.error("❌ Benchmark timed out.")

    await nc.close()

if __name__ == "__main__":
    asyncio.run(main())
