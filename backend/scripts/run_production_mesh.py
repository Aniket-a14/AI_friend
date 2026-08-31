"""
Unified Runtime Mesh Runner.
Starts BrainAgent, VoiceAgent, STTAgent, and TransportAgent concurrently with coordinated shutdown.
"""

import asyncio
import logging
import os
import sys

# Ensure backend root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Config
from app.logging_config import setup_logging
from app.runtime_bootstrap import bootstrap_runtime
from app.state import ConversationHistoryStore, GraphDB, MemoryStore
from app.agents.brain_agent import BrainAgent
from app.agents.stt_agent import STTAgent
from app.agents.transport_agent import TransportAgent
from app.agents.voice_agent import VoiceAgent
from app.agents.base import install_shutdown_signal_handlers

setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))
logger = logging.getLogger("production_mesh")


async def main():
    logger.info("🚀 Starting AI Friend Production Runtime Mesh...")

    if Config.RUNTIME_AUTO_BOOTSTRAP:
        logger.info("[Mesh] Running runtime bootstrap checks...")
        try:
            await bootstrap_runtime()
        except Exception as e:
            logger.warning(f"[Mesh] Bootstrap non-fatal notice: {e}")

    # 1. State Stores
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()

    graph_db = GraphDB()
    await graph_db.initialize()

    memory_store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)

    # 2. Instantiate Coordinated Agents
    brain_agent = BrainAgent(
        ollama_url=Config.OLLAMA_URL,
        graph_db=graph_db,
        memory_store=memory_store,
        conversation_store=conversation_store,
    )
    stt_agent = STTAgent(
        model_size=getattr(Config, "STT_MODEL_SIZE", "base"),
        nats_url=Config.NATS_URL,
    )
    voice_agent = VoiceAgent(
        nats_url=Config.NATS_URL,
        sovits_url="http://127.0.0.1:9871/tts",
    )
    transport_agent = TransportAgent(
        nats_url=Config.NATS_URL,
        lk_url="ws://127.0.0.1:7880",
        lk_api_key=Config.LIVEKIT_API_KEY,
        lk_api_secret=Config.LIVEKIT_API_SECRET,
    )

    # 3. Start All Agents Concurrently
    logger.info("📡 Connecting Agents to NATS & WebRTC SFU concurrently...")
    await asyncio.gather(
        brain_agent.start(),
        stt_agent.start(),
        voice_agent.start(),
        transport_agent.start(),
    )
    logger.info("✨ ALL AGENTS (BRAIN, STT, VOICE, TRANSPORT) ONLINE AND LISTENING!")

    shutdown_trigger = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_trigger)
    await shutdown_trigger.wait()

    logger.info("🛑 Shutting down AI Friend Runtime Mesh...")
    await asyncio.gather(
        transport_agent.stop(),
        voice_agent.stop(),
        stt_agent.stop(),
        brain_agent.stop(),
    )
    logger.info("👋 Mesh cleanly stopped.")


if __name__ == "__main__":
    asyncio.run(main())
