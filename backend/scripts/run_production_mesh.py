"""
Unified Runtime Mesh Runner.
Starts BrainAgent and TransportAgent concurrently with coordinated shutdown.

STT and Voice are Rust binaries (crates/stt-agent, crates/voice-agent),
run as their own systemd units (ai-friend-stt.service, ai-friend-voice.service)
-- see .agents/CONTEXT.md's 2026-08-31 entries for why they're separate
processes rather than folded in here.
"""

import asyncio
import logging
import os
import sys

# Ensure backend root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.base import install_shutdown_signal_handlers
from app.agents.brain_agent import BrainAgent
from app.agents.transport_agent import TransportAgent
from app.config import Config
from app.logging_config import setup_logging
from app.runtime_bootstrap import bootstrap_runtime
from app.state import ConversationHistoryStore, GraphDB, MemoryStore

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
    transport_agent = TransportAgent(
        nats_url=Config.NATS_URL,
        lk_url="ws://127.0.0.1:7880",
        lk_api_key=Config.LIVEKIT_API_KEY,
        lk_api_secret=Config.LIVEKIT_API_SECRET,
    )

    # 3. Start Agents Concurrently
    logger.info("📡 Connecting Agents to NATS & WebRTC SFU concurrently...")
    await asyncio.gather(
        brain_agent.start(),
        transport_agent.start(),
    )
    logger.info("✨ BRAIN + TRANSPORT ONLINE (STT/Voice run as separate Rust services).")

    shutdown_trigger = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_trigger)
    await shutdown_trigger.wait()

    logger.info("🛑 Shutting down AI Friend Runtime Mesh...")
    await asyncio.gather(
        transport_agent.stop(),
        brain_agent.stop(),
    )
    logger.info("👋 Mesh cleanly stopped.")


if __name__ == "__main__":
    asyncio.run(main())
