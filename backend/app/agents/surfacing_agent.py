import asyncio
import logging
import time
from typing import Dict, Any, Optional
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
        self.min_sweep_interval = 5  # Avoid high-frequency vector sweeps when no memory is surfaced.
        self.surface_novelty_window = 300
        self.last_surfaced_time = 0
        self.last_sweep_attempt = 0
        self.recently_surfaced = {}
        self._sweep_task: Optional[asyncio.Task] = None
        self.subject_metrics = {
            "system.tick": {"count": 0, "latency_total_ms": 0.0, "latency_samples": 0},
            "memory.surfaced": {"count": 0, "latency_total_ms": 0.0, "latency_samples": 0},
        }

    async def start(self):
        await self.connect()
        # Subscribe to chat inputs to stay sync'd with user context
        await self.subscribe(
            "chat.input",
            self._on_chat_input,
            durable=f"{self.name}_chat_input_live",
            deliver_policy="new",
        )
        # Periodic 'background sweep' on system tick
        await self.subscribe(
            "system.tick",
            self._on_system_tick,
            durable=f"{self.name}_system_tick_live",
            deliver_policy="new",
        )
        logger.info(f"🧠 {self.name} Online | Memory Surfacing Active.")

    async def _on_chat_input(self, data: Dict[str, Any], metadata: dict = None):
        """Update recent context tracking."""
        self.last_context = data.get("text", "")
        # Trigger immediate surfacing check if it's been a while
        if time.time() - self.last_surfaced_time > 10:
             source_meta = metadata or data.get("latency_metadata")
             self._schedule_sweep(source_metadata=source_meta)

    async def _on_system_tick(self, data: Dict[str, Any]):
        """Periodic background sweep for memory relevance."""
        self._record_surfacing_metric("system.tick", metadata=data.get("latency_metadata"))
        # Only surface if we haven't recently or if context is fresh
        if time.time() - self.last_surfaced_time > self.surfacing_cooldown:
             await self._run_sweep_now(source_metadata=data.get("latency_metadata"))

    async def _run_sweep_now(self, source_metadata: Optional[Dict[str, Any]] = None):
        """Run a sweep inline (used by low-frequency control channels like system.tick)."""
        now = time.time()
        if self._sweep_task is not None and not self._sweep_task.done():
            return
        if (now - self.last_sweep_attempt) < self.min_sweep_interval:
            return

        self.last_sweep_attempt = now
        self._sweep_task = asyncio.create_task(
            self._surface_relevant_memories(source_metadata=source_metadata)
        )
        await self._sweep_task

    def _schedule_sweep(self, source_metadata: Optional[Dict[str, Any]] = None):
        """Run at most one surfacing sweep at a time and throttle retry storms."""
        now = time.time()
        if self._sweep_task is not None and not self._sweep_task.done():
            return
        if (now - self.last_sweep_attempt) < self.min_sweep_interval:
            return

        self.last_sweep_attempt = now
        self._sweep_task = asyncio.create_task(
            self._surface_relevant_memories(source_metadata=source_metadata)
        )

    async def _surface_relevant_memories(self, source_metadata: Optional[Dict[str, Any]] = None):
        """
        The Core Surfacing Logic:
        1. Query Vector store for contextual similarity.
        2. Query Neo4j for relationship milestones.
        3. Publish 'memory.surfaced' event.
        """
        if not self.last_context or not self.memory:
            return
            
        try:
            sweep_started = time.perf_counter()
            now = time.time()
            self._prune_recently_surfaced(now)

            # 1. Vector Search for similarity
            search_started = time.perf_counter()
            memories = await self.memory.search_memories(
                self.last_context,
                limit=3,
                refresh_on_recall=False,
                exclude_contents=list(self.recently_surfaced.keys()),
            )
            search_ms = (time.perf_counter() - search_started) * 1000
            
            # 2. Ranking & Filtering (Simulated ranking here)
            # In a full version, we'd use emotional_weight and recency.
            for mem in memories:
                content = mem.get("content")
                if content and not self._was_recently_surfaced(content, now):
                    # 3. Publish to Mesh
                    publish_started = time.perf_counter()
                    await self.publish("memory.surfaced", {
                        "content": content,
                        "timestamp": now,
                        "relevance": mem.get("score", 0.7),
                        "source": "vector_long_term"
                    }, metadata=source_metadata)
                    publish_ms = (time.perf_counter() - publish_started) * 1000

                    self.last_surfaced_time = now
                    self.recently_surfaced[content] = now
                    self._record_surfacing_metric("memory.surfaced", metadata=source_metadata)
                    logger.info(
                        "[SurfacingMetrics] surfaced=1 search_ms=%.2f publish_ms=%.2f total_ms=%.2f",
                        search_ms,
                        publish_ms,
                        (time.perf_counter() - sweep_started) * 1000,
                    )
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

    def _record_surfacing_metric(self, subject: str, metadata: Optional[Dict[str, Any]] = None):
        metric = self.subject_metrics.get(subject)
        if metric is None:
            return

        metric["count"] += 1

        if isinstance(metadata, dict) and metadata.get("start_time") is not None:
            try:
                latency_ms = max(0.0, (time.time() - float(metadata["start_time"])) * 1000)
                metric["latency_total_ms"] += latency_ms
                metric["latency_samples"] += 1
            except (TypeError, ValueError):
                pass

        if metric["count"] == 1 or metric["count"] % 20 == 0:
            avg_latency = 0.0
            if metric["latency_samples"] > 0:
                avg_latency = metric["latency_total_ms"] / metric["latency_samples"]
            logger.info(
                "[SurfacingMetrics] subject=%s count=%s avg_latency_ms=%.2f",
                subject,
                metric["count"],
                avg_latency,
            )

    async def stop(self):
        if self._sweep_task and not self._sweep_task.done():
            self._sweep_task.cancel()

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
