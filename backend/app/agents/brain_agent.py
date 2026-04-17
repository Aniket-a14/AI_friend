import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

from .base import BaseAgent
from ..llm.ollama_client import OllamaClient
from ..knowledge.graph_db import GraphDB
from ..memory_store import MemoryStore
from ..conversation_history_store import ConversationHistoryStore
from ..config import Config
from ..cognitive import CognitiveService

logger = logging.getLogger(__name__)

class BrainAgent(BaseAgent):
    """
    The Brain Agent - The Orchestrator of Identity and Goal-Driven Reasoning.
    Processes user input through a BDI Cognitive Loop and maintains a persistent identity.
    """
    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB = None,
        memory_store: MemoryStore = None,
        conversation_store: ConversationHistoryStore = None,
    ):
        super().__init__(name="brain_agent")
        self.ollama = OllamaClient(base_url=ollama_url)
        self.graph_db = graph_db
        self.memory_store = memory_store
        self.conversation_store = conversation_store
        
        # Initialize the Functional Core
        self.cognitive_core = CognitiveService(
            llm_service=self.ollama,
            memory_store=memory_store,
            graph_db=graph_db
        )

        self.last_interaction_time = datetime.now()
        self.last_visual_context = "No visual data available."

    async def start(self):
        """Initialize the Cognitive Core and start the Identity Autonomy Loop."""
        await self.cognitive_core.initialize()

        if self.conversation_store:
            await self.conversation_store.initialize()
            await self.conversation_store.start_session()

        await self.connect()

        # Subscribe to I/O streams
        await self.subscribe("chat.input", self._on_chat_input)
        await self.subscribe("vision.frames", self._on_vision_frame, deliver_policy="last")
        
        # Start Autonomy Loop (Idle Reflection & State Evolution)
        asyncio.create_task(self._autonomy_loop())

        logger.info(f"🧠 {self.name} is online. Identity Simulator Active.")

    async def _on_vision_frame(self, data: Dict[str, Any]):
        """Update visual context buffer."""
        source = data.get("source", "unknown")
        self.last_visual_context = f"I am seeing the user's {source}."

    async def _on_chat_input(self, message: Dict[str, Any]):
        """Primary Cognitive Lifecycle trigger."""
        now = datetime.now()
        self.last_interaction_time = now
        
        user_text = message.get("text", "")
        if not user_text:
            return

        raw_event = {
            "id": str(uuid.uuid4()),
            "type": "USER_MESSAGE",
            "content": user_text,
            "metadata": {"visuals": self.last_visual_context}
        }

        # History logging
        if self.conversation_store:
            asyncio.create_task(self.conversation_store.log_message("user", user_text))

        await self.set_state("thinking")
        
        # PROCESS: Push through Cognitive Loop
        full_response = ""
        sentence_buffer = ""
        try:
            async for output in self.cognitive_core.process_event(raw_event):
                if output["type"] == "content":
                    await self.set_state("speaking")
                    chunk = output["data"]
                    full_response += chunk
                    sentence_buffer += chunk
                    
                    # If sentence is complete, publish to trigger TTS early
                    if any(p in chunk for p in [".", "?", "!"]):
                        await self.publish("chat.output", {
                            "content": sentence_buffer.strip(), 
                            "done": False,
                            "state": self.cognitive_core.state.get_context_snapshot()
                        })
                        sentence_buffer = ""
                
                elif output["type"] == "done":
                    # Send any remaining text and then final signal
                    if sentence_buffer.strip():
                        await self.publish("chat.output", {
                            "content": sentence_buffer.strip(),
                            "done": False,
                            "state": self.cognitive_core.state.get_context_snapshot()
                        })
                    
                    state = self.cognitive_core.state.get_context_snapshot()
                    await self.publish("chat.output", {
                        "content": "", 
                        "done": True, 
                        "full_response": full_response,
                        "state": state,
                        "emotion": state.get("emotion", "neutral")
                    })

        except Exception as e:
            logger.error(f"Cognitive Loop error: {e}")
            await self.publish("chat.output", {"chunk": "I encountered an internal error.", "done": True})

        if self.conversation_store and full_response:
            asyncio.create_task(self.conversation_store.log_message("assistant", full_response))

        await self.set_state("idle")

    async def _autonomy_loop(self):
        """Heartbeat of the Identity."""
        SILENCE_TICK_SECONDS = 60.0
        while True:
            await asyncio.sleep(SILENCE_TICK_SECONDS)
            now = datetime.now()
            idle_seconds = (now - self.last_interaction_time).total_seconds()
            await self.cognitive_core.state.evolve_idle(dt_hours=idle_seconds / 3600.0)
            
            if idle_seconds > 300.0:
                logger.info("[Brain] Triggering background reflection loop.")
                raw_event = {
                    "id": str(uuid.uuid4()),
                    "type": "SYSTEM_TICK",
                    "content": "Deep reflection requested.",
                    "metadata": {}
                }
                async for _ in self.cognitive_core.process_event(raw_event):
                    pass

    async def stop(self):
        await super().stop()
        logger.info(f"🧠 {self.name} offline.")

async def main():
    agent = BrainAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
