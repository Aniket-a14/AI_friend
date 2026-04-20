import asyncio
import logging
import time
from typing import Dict, Any
from .base import BaseAgent
from ..state import ConversationHistoryStore, MemoryStore, GraphDB

logger = logging.getLogger("surfacing_agent")

class SurfacingAgent(BaseAgent):
    """
    Active Memory Influence Agent.
    Asynchronously evaluates long-term memory and 'surfaces' relevant context 
    as mesh events for current cognition.
    """
    def __init__(self, memory_store=None, graph_db=None, conversation_store=None):
        super().__init__(name="surfacing_agent")
        self.memory = memory_store
        self.graph = graph_db
        self.conversation_store = conversation_store
        self.last_context = ""
        self.surfacing_cooldown = 30 # Seconds between surfacing events
        self.surface_novelty_window = 300
        self.last_surfaced_time = 0
        self.recently_surfaced = {}

    async def start(self):
        await self.connect()
        # Subscribe to chat inputs to stay sync'd with user context
        await self.subscribe("chat.input", self._on_chat_input)
        # Periodic 'background sweep' on system tick
        await self.subscribe("system.tick", self._on_system_tick)
        logger.info(f"🧠 {self.name} Online | Memory Surfacing Active.")

    async def _on_chat_input(self, data: Dict[str, Any], metadata: dict = None):
        """Update recent context tracking."""
        self.last_context = data.get("text", "")
        # Trigger immediate surfacing check if it's been a while
        if time.time() - self.last_surfaced_time > 10:
             asyncio.create_task(self._surface_relevant_memories())

    async def _on_system_tick(self, data: Dict[str, Any]):
        """Periodic background sweep for memory relevance."""
        # Only surface if we haven't recently or if context is fresh
        if time.time() - self.last_surfaced_time > self.surfacing_cooldown:
             await self._surface_relevant_memories()

    async def _surface_relevant_memories(self):
        """
        The Core Surfacing Logic:
        1. Query Vector store for contextual similarity.
        2. Query Neo4j for relationship milestones.
        3. Publish 'memory.surfaced' event.
        """
        if not self.last_context or not self.memory:
            return
            
        try:
            now = time.time()
            self._prune_recently_surfaced(now)

            # 1. Vector Search for similarity
            memories = await self.memory.search_memories(
                self.last_context,
                limit=3,
                refresh_on_recall=False,
                exclude_contents=list(self.recently_surfaced.keys()),
            )
            
            # 2. Ranking & Filtering (Simulated ranking here)
            # In a full version, we'd use emotional_weight and recency.
            for mem in memories:
                content = mem.get("content")
                if content and not self._was_recently_surfaced(content, now):
                    # 3. Publish to Mesh
                    await self.publish("memory.surfaced", {
                        "content": content,
                        "timestamp": now,
                        "relevance": mem.get("score", 0.7),
                        "source": "vector_long_term"
                    })
                    self.last_surfaced_time = now
                    self.recently_surfaced[content] = now
                    logger.debug(f"[Surfacing] Emerged memory: {content[:40]}...")
                    # Surface only one at a time for focus
                    break
                    
        except Exception as e:
            logger.error(f"[Surfacing] Error in background sweep: {e}")

    def _prune_recently_surfaced(self, now: float):
        stale = [
            content
            for content, surfaced_at in self.recently_surfaced.items()
            if (now - surfaced_at) >= self.surface_novelty_window
        ]
        for content in stale:
            self.recently_surfaced.pop(content, None)

    def _was_recently_surfaced(self, content: str, now: float) -> bool:
        surfaced_at = self.recently_surfaced.get(content)
        if surfaced_at is None:
            return False
        return (now - surfaced_at) < self.surface_novelty_window

    async def stop(self):
        if self.graph:
            try:
                await self.graph.close()
            except Exception as e:
                logger.warning(f"[Surfacing] GraphDB close warning: {e}")

        if self.conversation_store:
            try:
                await self.conversation_store.close()
            except Exception as e:
                logger.warning(f"[Surfacing] Conversation store close warning: {e}")

        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")

async def main():
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()

    memory_store = MemoryStore(pool=conversation_store.pool)
    graph_db = GraphDB()

    agent = SurfacingAgent(
        memory_store=memory_store,
        graph_db=graph_db,
        conversation_store=conversation_store,
    )

    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        await agent.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
