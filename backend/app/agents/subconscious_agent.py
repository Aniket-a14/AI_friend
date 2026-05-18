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
    NATS wrapper for the SubconsciousEngine and solid-state memory consolidation.
    """

    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB = None,
        state_service: StateService = None,
        memory_store = None,
        reflection_service = None,
    ):
        super().__init__(name="subconscious_agent")
        self._llm = OllamaClient(base_url=ollama_url, model=Config.LLM_CHAT_MODEL)
        self.graph_db = graph_db or GraphDB()
        self.state_service = state_service or StateService(graph_store=self.graph_db)
        self.engine = SubconsciousEngine(llm_client=self._llm)
        self.memory_store = memory_store
        self._owns_memory_store = memory_store is None
        self._owns_db_store = memory_store is None
        self.reflection_service = reflection_service
        self.db_store = None

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

        # Initialize SQLite/Postgres DB pool and MemoryStore if not provided
        if not self.memory_store:
            from app.state.conversation_store import ConversationHistoryStore
            from app.state.memory_store import MemoryStore
            
            self.db_store = ConversationHistoryStore()
            await self.db_store.initialize()
            self.memory_store = MemoryStore(pool=self.db_store.pool)
            
        if not self.reflection_service:
            from app.cognitive.learning import ReflectionService
            self.reflection_service = ReflectionService(
                llm_service=self._llm,
                graph_store=self.graph_db,
                pg_vector=self.memory_store,
            )

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

        # Subconscious Memory Consolidation (ACT-R & Fact Triplet Crystallization)
        try:
            logger.info("[Subconscious] Initiating subconscious consolidation pass...")
            episodes = await self.memory_store.get_recent_unconsolidated_episodes(limit=10)
            
            if episodes:
                # Map SQLite/PG message rows into reflection schemas
                reflection_episodes = []
                for ep in episodes:
                    reflection_episodes.append({
                        "id": ep.get("id"),
                        "event": ep.get("content") if ep.get("role") == "user" else "",
                        "response": ep.get("content") if ep.get("role") == "assistant" else "",
                        "context": "Session conversation message",
                        "emotion_vector": {"V": 0.0, "Ar": 0.5, "D": 0.5},
                        "relationship_delta": 0.0,
                        "content": ep.get("content") if ep.get("role") == "user" else ""
                    })
                
                # Trigger reflection task asynchronously
                task = await self.reflection_service.trigger_reflection(reflection_episodes)
                if task and isinstance(task, asyncio.Task):
                    await task  # Wait for background fact extraction and graph writing to finish
                    
                    # Mark these episodes as consolidated in the database
                    message_ids = [ep.get("id") for ep in episodes if ep.get("id")]
                    await self.memory_store.mark_episodes_consolidated(message_ids)
                    
                    # Apply ACT-R decay on the raw user memories corresponding to these episodes
                    contents = [ep.get("content") for ep in episodes if ep.get("role") == "user" and ep.get("content")]
                    await self.memory_store.apply_actr_decay(contents)
                    
            logger.info("[Subconscious] Subconscious consolidation pass completed successfully.")
        except Exception as e:
            logger.error(f"[Subconscious] Consolidation pass failed: {e}")

    async def stop(self):
        await self.llm.close()
        if self.db_store and self._owns_db_store:
            await self.db_store.close()
        if self.memory_store and self._owns_memory_store:
            await self.memory_store.close()
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
