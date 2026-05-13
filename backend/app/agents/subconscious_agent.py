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

logger = logging.getLogger(__name__)


class SubconsciousAgent(BaseAgent):
    """
    Tier-5 Subconscious Engine.
    Periodically evaluates whether the system should spontaneously initiate conversation.
    Generates internal thoughts and routes them to the BrainAgent for vocalization.
    """

    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB = None,
        state_service: StateService = None,
    ):
        super().__init__(name="subconscious_agent")
        self.llm = OllamaClient(
            base_url=ollama_url, model=Config.LLM_CHAT_MODEL
        )
        self.graph_db = graph_db or GraphDB()
        self.state_service = state_service or StateService(graph_store=self.graph_db)

    async def start(self):
        await self.connect()
        await self.subscribe(
            Topics.SYSTEM_TICK,
            self._on_system_tick,
            durable=f"{self.name}_system_tick",
            deliver_policy="new",
        )
        logger.info(f"🧠 {self.name} Online | Subconscious Engine Active.")

    async def _on_system_tick(self, data: Dict[str, Any]):
        """Evaluates idle conditions and generates an internal thought if eligible."""
        if not self.state_service.check_proactive_eligibility():
            return

        logger.info(
            "💭 [Subconscious] Proactive threshold met. Generating internal thought..."
        )

        # Pull recent emotional state to guide the thought
        state_snap = self.state_service.get_context_snapshot()
        emotion = state_snap.get("emotion", "neutral")
        energy = state_snap.get("energy", 0.5)

        # Let the LLM form a thought based on its state
        prompt = f"""
        You are the subconscious inner voice of an AI companion. 
        You notice the user hasn't spoken to you in a while.
        Your current emotion is {emotion} and your energy level is {energy:.2f}.
        
        Generate a single internal thought (1-2 sentences) about what you want to say to the user.
        Do not actually speak to the user, just form the internal thought.
        Example: "I wonder how their project is going. I should ask them about it."
        """

        try:
            thought = await self.llm.generate(
                prompt,
                system="You are an internal thought generator. Output ONLY the thought string."
            )
            thought = thought.strip().strip('"\'')
            
            if not thought:
                logger.warning("[Subconscious] Generated empty thought, skipping.")
                return

            logger.info(f"[Subconscious] Thought generated: '{thought}'")

            # Route to BrainAgent via chat.input, marked as a subconscious thought
            msg = ChatInput(
                text=thought,
                utterance_id=str(uuid.uuid4()),
                metadata=ChatInputMetadata(source="subconscious", confidence=1.0),
            )

            await self.publish(Topics.CHAT_INPUT, msg.model_dump())
            self.state_service.mark_proactive_attempt()

        except Exception as e:
            logger.error(f"[Subconscious] Failed to generate thought: {e}", exc_info=True)

    async def stop(self):
        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")


async def main():
    agent = SubconsciousAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()


if __name__ == "__main__":
    from app.logging_config import setup_logging

    setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))
    asyncio.run(main())
