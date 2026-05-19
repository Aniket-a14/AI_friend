import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.cognitive.core import CognitiveService
from app.llm.ollama_client import OllamaClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_loop")


async def test_cognitive_loop():
    logger.info("🚀 Starting Cognitive Loop Verification...")

    # 1. Setup Mock/Local Dependencies
    # In a real test, we'd use a test DB. Here we use the local dev ones.
    ollama = OllamaClient(base_url="http://localhost:11434")

    # Note: MemoryStore and GraphDB usually need connections.
    # For this unit test, we'll see if they initialize.
    memory = None
    graph = None

    try:
        core = CognitiveService(llm_service=ollama, memory_store=memory, graph_db=graph)

        await core.initialize()

        # 2. Simulate a User Message
        logger.info("--- Phase 1: Chat Input ---")
        raw_event = {
            "id": "test-123",
            "type": "USER_MESSAGE",
            "content": "Hello! Can you remember that my favorite color is Cyan?",
            "metadata": {},
        }

        async for output in core.process_event(raw_event):
            if output["type"] == "content":
                print(output["data"], end="", flush=True)
            elif output["type"] == "done":
                print("\n[Loop Finished]")

        # 3. Simulate a System Tick (Reflection Trigger)
        logger.info("\n--- Phase 2: System Tick (Reflection) ---")
        tick_event = {
            "id": "tick-999",
            "type": "SYSTEM_TICK",
            "content": "Idle",
            "metadata": {},
        }

        async for output in core.process_event(tick_event):
            pass

        logger.info("✅ Core Cognitive Loop Logic Verified!")

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_cognitive_loop())
