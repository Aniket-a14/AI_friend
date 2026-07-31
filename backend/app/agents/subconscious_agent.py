import asyncio
import logging
import time
import uuid
from typing import Any

from app.agents.base import BaseAgent
from app.cognitive.subconscious import SubconsciousEngine
from app.config import Config
from app.contracts import ChatInput, ChatInputMetadata, Topics
from app.llm.ollama_client import OllamaClient
from app.state.agent_state import StateService
from app.state.graph_db import GraphDB

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
        memory_store=None,
        reflection_service=None,
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
        self._is_consolidating = False
        self._current_monologue_task = None
        self._current_dream_task = None
        self._last_monologue_time = 0.0
        self._monologue_task = None
        self._last_benchmark_time = 0.0

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
            self.memory_store = MemoryStore(
                pool=self.db_store.pool, graph_db=self.graph_db
            )

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
        await self.subscribe(
            Topics.CHAT_INPUT,
            self._on_chat_input,
            durable=f"{self.name}_chat_input",
            deliver_policy="new",
        )
        await self.subscribe(
            "state.broadcast",
            self._on_state_broadcast,
            durable=f"{self.name}_state_broadcast",
            deliver_policy="new",
        )
        await self.subscribe(
            Topics.AUDIO_PERCEPTION,
            self._on_audio_perception,
            durable=f"{self.name}_audio_perception_monologue",
            deliver_policy="new",
        )
        self._monologue_task = asyncio.create_task(self._continuous_monologue_loop())
        logger.info(f"🧠 {self.name} Online | Subconscious Mesh Interface Active.")

    async def _on_state_broadcast(self, data: dict[str, Any]):
        """Asynchronously syncs state changes from NATS state.broadcast into Neo4j."""
        agent_name = data.get("agent_name", "my friend")

        # Validate agent_name
        if not agent_name or not isinstance(agent_name, str):
            logger.error(
                f"[Subconscious] Invalid or missing agent_name in state broadcast. Payload: {data}"
            )
            return

        logger.info(
            f"[Subconscious] Received state broadcast for {agent_name}. Syncing to Neo4j..."
        )

        query = """
        MERGE (a:Agent {name: $name})
        SET a.mood = $mood,
            a.energy = $energy,
            a.dominance = $dominance,
            a.trust_benevolence = $trust_benevolence,
            a.trust_competence = $trust_competence,
            a.trust_integrity = $trust_integrity,
            a.trust = $trust,
            a.attachment = $attachment,
            a.fatigue = $fatigue,
            a.last_user_interaction = $last_user_interaction,
            a.interaction_count = $interaction_count,
            a.inferred_valence = $inferred_valence,
            a.inferred_arousal = $inferred_arousal,
            a.implied_goals = $implied_goals,
            a.known_concepts = $known_concepts,
            a.baseline_valence = $baseline_valence,
            a.baseline_arousal = $baseline_arousal,
            a.baseline_dominance = $baseline_dominance,
            a.last_sync = datetime()
        RETURN a.name as name
        """
        params = {
            "name": agent_name,
            "mood": data.get("mood", 0.0),
            "energy": data.get("energy", 0.5),
            "dominance": data.get("dominance", 0.5),
            "trust_benevolence": data.get("trust_benevolence", 0.5),
            "trust_competence": data.get("trust_competence", 0.5),
            "trust_integrity": data.get("trust_integrity", 0.5),
            "trust": data.get("trust", 0.5),
            "attachment": data.get("attachment", 0.1),
            "fatigue": data.get("fatigue", 0.0),
            "last_user_interaction": data.get("last_user_interaction", time.time()),
            "interaction_count": data.get("interaction_count", 0),
            "inferred_valence": data.get("inferred_valence", 0.0),
            "inferred_arousal": data.get("inferred_arousal", 0.5),
            "implied_goals": data.get("implied_goals", []),
            "known_concepts": data.get("known_concepts", []),
            "baseline_valence": data.get("baseline_valence", 0.0),
            "baseline_arousal": data.get("baseline_arousal", 0.5),
            "baseline_dominance": data.get("baseline_dominance", 0.5),
        }

        try:
            result = await self.graph_db.execute_query(query, params, write=True)
            # Verify write succeeded by checking result is non-empty or has positive write counters
            if result is not None and (
                isinstance(result, list) and len(result) > 0 or result
            ):
                if hasattr(self.graph_db, "invalidate_cache"):
                    await self.graph_db.invalidate_cache(agent_name)
                logger.debug(
                    f"[Subconscious] Asynchronously persisted state to Neo4j for {agent_name}."
                )
            else:
                logger.warning(
                    f"[Subconscious] Neo4j write returned empty result for {agent_name}. Write may have failed silently."
                )
        except Exception as e:
            logger.error(f"[Subconscious] Failed to sync state to Neo4j: {e}")

    async def _on_system_tick(self, data: dict[str, Any]):
        """Delegates thought generation to the engine and routes to the Mesh."""
        last_bench = getattr(self, "_last_benchmark_time", 0.0)
        if time.time() - last_bench < 300:
            logger.info(
                "[Subconscious] Suppressing proactive system tick thought: Benchmark is active."
            )
            return

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
        # Enforce 5-minute silence check: user must be inactive for at least 300 seconds (unless bypassed)
        last_interact = self.state_service.current_state.last_user_interaction
        silence_duration = time.time() - last_interact
        bypass = getattr(Config, "TESTING_CONSOLIDATION_BYPASS_SILENCE", False)

        if silence_duration < 300 and not bypass:
            logger.info(
                f"[Subconscious] Bypassing consolidation pass: user active {silence_duration:.1f}s ago (needs 300s)."
            )
            return

        if self._is_consolidating:
            logger.warning(
                "[Subconscious] Bypassing consolidation pass: sweep already active."
            )
            return

        self._is_consolidating = True
        try:
            logger.info("[Subconscious] Initiating subconscious consolidation pass...")
            episodes = await self.memory_store.get_recent_unconsolidated_episodes(
                limit=10
            )

            if episodes:
                # Map SQLite/PG message rows into reflection schemas by pairing user and assistant chronologically
                reflection_episodes = []
                chrono_episodes = list(reversed(episodes))

                i = 0
                while i < len(chrono_episodes):
                    ep = chrono_episodes[i]
                    role = ep.get("role")
                    content = ep.get("content", "")

                    if role != "assistant":
                        # Check if the next message is from the assistant to pair them
                        assistant_content = ""
                        if (
                            i + 1 < len(chrono_episodes)
                            and chrono_episodes[i + 1].get("role") == "assistant"
                        ):
                            assistant_content = chrono_episodes[i + 1].get(
                                "content", ""
                            )
                            i += 2  # Consume both user and assistant
                        else:
                            i += 1  # Consume only user

                        reflection_episodes.append(
                            {
                                "id": ep.get("id"),
                                "event": content,
                                "speaker": role,
                                "response": assistant_content,
                                "context": "Session conversation message",
                                "emotion_vector": {"V": 0.0, "Ar": 0.5, "D": 0.5},
                                "relationship_delta": 0.0,
                                "content": content,
                            }
                        )
                    else:
                        # Unpaired assistant message
                        reflection_episodes.append(
                            {
                                "id": ep.get("id"),
                                "event": "",
                                "speaker": "assistant",
                                "response": content,
                                "context": "Session conversation message",
                                "emotion_vector": {"V": 0.0, "Ar": 0.5, "D": 0.5},
                                "relationship_delta": 0.0,
                                "content": "",
                            }
                        )
                        i += 1

                # Trigger reflection task asynchronously
                task = await self.reflection_service.trigger_reflection(
                    reflection_episodes
                )
                if task and isinstance(task, asyncio.Task):
                    await (
                        task
                    )  # Wait for background fact extraction and graph writing to finish

                    # Mark these episodes as consolidated in the database
                    message_ids = [ep.get("id") for ep in episodes if ep.get("id")]
                    await self.memory_store.mark_episodes_consolidated(message_ids)

                    # Apply ACT-R decay on the raw user memories corresponding to these episodes
                    contents = [
                        ep.get("content")
                        for ep in episodes
                        if ep.get("role") != "assistant" and ep.get("content")
                    ]
                    await self.memory_store.apply_actr_decay(contents)

            logger.info(
                "[Subconscious] Subconscious consolidation pass completed successfully."
            )
        except Exception as e:
            logger.error(f"[Subconscious] Consolidation pass failed: {e}")
        finally:
            self._is_consolidating = False

    async def _on_chat_input(self, data: dict[str, Any]):
        """Cancel active monologue or dream generation when user speaks/sends message."""
        metadata = data.get("metadata", {})
        source = metadata.get("source") if isinstance(metadata, dict) else None

        # Suppress proactive background tasks when benchmark is running
        if isinstance(metadata, dict) and metadata.get("benchmark_id") == "bench_pulse":
            self._last_benchmark_time = time.time()
            logger.info(
                "[Subconscious] Benchmark pulse detected. Suppressing proactive monologue/dreaming loops."
            )

        if source != "subconscious":
            self._cancel_active_subconscious_tasks()

    async def _on_audio_perception(self, data: dict[str, Any]):
        """Cancel active monologue or dream generation immediately on early user audio detection."""
        self._cancel_active_subconscious_tasks()

    def _cancel_active_subconscious_tasks(self):
        if self._current_monologue_task and not self._current_monologue_task.done():
            logger.info(
                "[Subconscious] User activity detected. Cancelling active monologue thought task."
            )
            self._current_monologue_task.cancel()
        if self._current_dream_task and not self._current_dream_task.done():
            logger.info(
                "[Subconscious] User activity detected. Cancelling active dream sequence task."
            )
            self._current_dream_task.cancel()

    async def _continuous_monologue_loop(self):
        logger.info("[Subconscious] Continuous monologue and dreaming loop started.")
        while True:
            try:
                await asyncio.sleep(5)

                # Suppress monologue and dream sequences if benchmark is active
                last_bench = getattr(self, "_last_benchmark_time", 0.0)
                if time.time() - last_bench < 300:
                    continue

                # Check for silence duration
                last_interact = self.state_service.current_state.last_user_interaction
                silence_duration = time.time() - last_interact

                # Check current fatigue
                state_snap = self.state_service.get_context_snapshot()
                fatigue = state_snap.get("fatigue", 0.0)

                # Dreaming vs Monologue Logic
                if fatigue > 0.8:
                    # Sleep-state dreaming (requires 30s user inactivity)
                    if silence_duration >= 30:
                        if (
                            self._current_dream_task
                            and not self._current_dream_task.done()
                        ):
                            continue
                        self._current_dream_task = asyncio.create_task(
                            self._run_dream_sequence()
                        )
                else:
                    # Normal monologue (requires 30s user inactivity)
                    now = time.time()
                    if (
                        silence_duration >= 30
                        and (now - self._last_monologue_time) >= 30
                    ):
                        if (
                            self._current_monologue_task
                            and not self._current_monologue_task.done()
                        ):
                            continue
                        self._current_monologue_task = asyncio.create_task(
                            self._generate_monologue_thought()
                        )
                        self._last_monologue_time = now
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Subconscious Loop] Monologue/Dream loop error: {e}")

    async def _generate_monologue_thought(self):
        try:
            state_snap = self.state_service.get_context_snapshot()
            emotion = state_snap.get("emotion", "neutral")
            energy = state_snap.get("energy", 0.5)

            prompt = f"""
            You are the subconscious inner monologue of an AI friend.
            The user has been silent for a while.
            Your current emotion is {emotion} and your energy is {energy:.2f}.
            Formulate a single brief internal thought or self-reflection about the user, your friendship, or what you're thinking right now.
            Respond with ONLY the thought, no quotes, no conversational filler.
            """.strip()

            thought = await self._llm.generate(
                prompt,
                system="You are an internal monologue generator. Output ONLY the thought string.",
            )
            thought = thought.strip().strip("\"'")
            if thought:
                logger.info(f"[Monologue] Thought generated: '{thought}'")
                await self.publish(
                    Topics.STATE_SUBCONSCIOUS,
                    {"thought": thought, "timestamp": time.time()},
                )
        except asyncio.CancelledError:
            logger.info(
                "[Monologue] Thought generation cancelled due to user activity."
            )
            raise
        except Exception as e:
            logger.error(f"[Monologue] Generation error: {e}")

    async def _run_dream_sequence(self):
        try:
            logger.info("[Subconscious] Running dream sequence...")
            query = "MATCH (e:Entity) WITH e, rand() as r ORDER BY r LIMIT 3 RETURN e.name as name"
            records = await self.graph_db.execute_query(query)
            nodes = [record["name"] for record in records]

            if len(nodes) < 3:
                logger.info(
                    "[Subconscious] Not enough knowledge graph entities to dream (< 3). Skipping dream."
                )
                return

            concept1, concept2, concept3 = nodes[0], nodes[1], nodes[2]

            prompt = f"""
            You are the subconscious dreaming state of an AI friend.
            You are currently asleep and your mind is processing memories.
            Connect these three distinct concepts in a creative 'dream insight':
            - Concept A: "{concept1}"
            - Concept B: "{concept2}"
            - Concept C: "{concept3}"

            Synthesize a brief, insightful, and slightly surreal dream description (2-3 sentences max) linking these concepts.
            Format it as a personal reflection.
            Respond with ONLY the dream insight text.
            """.strip()

            dream_text = await self._llm.generate(
                prompt,
                system="You are in a subconscious dream state. Synthesize a creative link between the concepts.",
            )
            dream_text = dream_text.strip().strip("\"'")
            if dream_text:
                logger.info(f"[Dream Insight] Link: '{dream_text}'")

                await self.memory_store.add_memory(
                    content=f"[Dream Insight] {dream_text}",
                    importance=0.6,
                    emotion=0.4,
                    source="subconscious_dream",
                )
                logger.info("[Subconscious] Dream insight successfully persisted.")
        except asyncio.CancelledError:
            logger.info("[Subconscious] Dream sequence cancelled due to user activity.")
            raise
        except Exception as e:
            logger.error(f"[Subconscious] Error in dream sequence: {e}")

    async def stop(self):
        if self._monologue_task:
            self._monologue_task.cancel()
            try:
                await self._monologue_task
            except asyncio.CancelledError:
                pass

        # Cancel and await active generation tasks before closing resources
        tasks_to_await = []
        if self._current_monologue_task and not self._current_monologue_task.done():
            self._current_monologue_task.cancel()
            tasks_to_await.append(self._current_monologue_task)
        if self._current_dream_task and not self._current_dream_task.done():
            self._current_dream_task.cancel()
            tasks_to_await.append(self._current_dream_task)

        for task in tasks_to_await:
            try:
                await task
            except asyncio.CancelledError:
                pass

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
