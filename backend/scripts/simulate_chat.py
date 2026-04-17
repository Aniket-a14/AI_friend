import asyncio
import nats
import json
import time

async def main():
    try:
        # Connect to NATS on localhost (bridged to Docker)
        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()
        
        print("🚀 Connected to NATS mesh. Simulating user input...")
        
        # 1. Listen for Brain's response
        sub = await js.subscribe("chat.output")
        
        # 2. Publish a message to the Brain
        test_msg = {
            "text": "Hello, my friend! Are you there? Tell me a short joke.",
            "source": "terminal_test",
            "timestamp": time.time()
        }
        
        await js.publish("chat.input", json.dumps(test_msg).encode())
        print(f"SENT: {test_msg['text']}")
        print("Waiting for Brain to process...")

        # 3. Wait for real-time response chunks
        print("\n🧠 BRAIN RESPONSE: ", end="", flush=True)
        while True:
            try:
                msg = await sub.next_msg(timeout=30.0)
                response = json.loads(msg.data.decode())
                
                if not response.get("done"):
                    chunk = response.get("chunk", "")
                    print(chunk, end="", flush=True)
                else:
                    print("\n\n✅ BRAIN FINISHED.")
                    await msg.ack()
                    break
                await msg.ack()
            except asyncio.TimeoutError:
                print("\n❌ Timeout: No response from Brain Agent within 30 seconds.")
                break
            
        await nc.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
