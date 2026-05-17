import asyncio
import logging
import uuid
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.llm.ollama_client import OllamaClient
from app.state.graph_db import GraphDB
from app.state.agent_state import StateService
from app.config import Config
from app.contracts import Topics, ChatInput, ChatInputMetadata
from app.cognitive.subconscious import SubconsciousEngine

logger = logging.getLogger(__name__)


class SubconsciousAgent(BaseAgent):
    """
    Tier-5 Subconscious Agent.
    NATS wrapper for the SubconsciousEngine.
    """

    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB = None,
        state_service: StateService = None,
    ):
        super().__init__(name="subconscious_agent")
        self._llm = OllamaClient(base_url=ollama_url, model=Config.LLM_CHAT_MODEL)
        self.state_service = state_service or StateService(graph_store=graph_db or GraphDB())
        self.engine = SubconsciousEngine(llm_client=self._llm)

    @property
    def llm(self):
        return self._llm

    @llm.setter
    def llm(self, value):
        self._llm = value
        if hasattr(self, "engine"):
            self.engine.llm = value

    async def start(self):
        await self.connect()
        await self.subscribe(
            Topics.SYSTEM_TICK,
            self._on_system_tick,
            durable=f"{self.name}_system_tick",
            deliver_policy="new",
        )
        logger.info(f"🧠 {self.name} Online | Subconscious Mesh Interface Active.")

    async def _on_system_tick(self, data: Dict[str, Any]):
        """Delegates thought generation to the engine and routes to the Mesh."""
        state_snap = self.state_service.get_context_snapshot()
        eligible = self.state_service.check_proactive_eligibility()

        thought = await self.engine.evaluate_and_think(state_snap, eligible)
        
        if thought:
            logger.info(f"[Subconscious] Thought generated: '{thought}'")
            
            msg = ChatInput(
                text=thought,
                utterance_id=str(uuid.uuid4()),
                metadata=ChatInputMetadata(source="subconscious", confidence=1.0),
            )

            await self.publish(Topics.CHAT_INPUT, msg.model_dump())
            self.state_service.mark_proactive_attempt()

    async def stop(self):
        await self.llm.close()
        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")


async def main():
    agent = SubconsciousAgent()
    await agent.start()
    try:
        shutdown_trigger = asyncio.Event()
        await shutdown_trigger.wait()
    except asyncio.CancelledError:
        await agent.stop()


if __name__ == "__main__":
    from app.logging_config import setup_logging
    setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))
    asyncio.run(main())
