"""
Cognitive Service — The Orchestrator for the Cognitive Loop.

Pipeline (psychological_layer.md System Principle):
    Signal → Appraisal → State → Intent → Expression → Reappraisal → Memory
             ↑                                                         │
             └─────────────────────────────────────────────────────────┘
"""

import logging
import time
from typing import Dict, Any, AsyncGenerator

from .perception import PerceptionService
from .appraisal import AppraisalEngine, AppraisalVector
from ..state import StateService
from .decision import DecisionService
from .action import ActionService
from .learning import ReflectionService
from .identity import IdentityManager
from .pipeline import CognitivePipeline

logger = logging.getLogger(__name__)


class CognitiveService:
    """
    The Orchestrator for the Cognitive Loop.
    Integrates BDI logic, State dynamics, Appraisal, and Identity enforcement.
    """

    def __init__(
        self,
        llm_service,
        memory_store,
        graph_db,
        identity_store=None,
        base_path=None,
    ):
        self.identity = IdentityManager(base_path=base_path)
        self.identity_store = identity_store
        self.perception = PerceptionService(llm_service=llm_service)
        self.appraisal = AppraisalEngine()  # §1: OCC/Lazarus/EMA
        self.state = StateService(graph_store=graph_db)
        self.decision = DecisionService(
            llm_service=llm_service, memory_store=memory_store
        )
        self.action = ActionService(llm_service=llm_service, memory_store=memory_store)
        self.learning = ReflectionService(
            llm_service=llm_service,
            graph_store=graph_db,
            pg_vector=memory_store,
            identity_manager=self.identity,
        )
        self.pipeline = CognitivePipeline(
            perception=self.perception,
            appraisal=self.appraisal,
            state=self.state,
            decision=self.decision,
            action=self.action,
            learning=self.learning,
            identity=self.identity,
            llm_service=llm_service,
        )
        self.action.publish_cb = self.publish
        self.surfaced_memories = []
        self.agent = None  # NATS Mesh connection
        self._last_appraisal: AppraisalVector = None  # Cache for downstream consumers
        self.subject_metrics = {
            "system.tick": {"count": 0, "latency_total_ms": 0.0, "latency_samples": 0},
            "memory.surfaced": {
                "count": 0,
                "latency_total_ms": 0.0,
                "latency_samples": 0,
            },
            "audio.stop": {"count": 0, "latency_total_ms": 0.0, "latency_samples": 0},
            "audio.resume": {"count": 0, "latency_total_ms": 0.0, "latency_samples": 0},
        }
        self.last_reflection_task = None

    async def publish(self, subject: str, data: Dict[str, Any]):
        if self.agent:
            await self.agent.publish(subject, data)

    async def initialize(self, agent: Any = None):
        """Load identity and hydrate states. Subscribes to Mesh heartbeats."""
        if self.identity_store:
            await self.identity.hydrate_from_config_store(self.identity_store)
        await self.state.hydrate_state()

        # Initialize appraisal engine with identity boundaries
        boundaries = self.identity.personality.get("boundaries", [])
        self.appraisal = AppraisalEngine(identity_core_values=boundaries)

        # Subscribe to Mesh Channels
        if agent:
            self.agent = agent
            await agent.subscribe(
                "system.tick",
                self._on_system_tick,
                durable=f"{agent.name}_system_tick_live",
                deliver_policy="new",
            )
            await agent.subscribe(
                "memory.surfaced",
                self._on_memory_surfaced,
                durable=f"{agent.name}_memory_surfaced_live",
                deliver_policy="new",
            )
            await agent.subscribe(
                "audio.perception",
                self._on_audio_perception,
                durable=f"{agent.name}_audio_perception_live",
                deliver_policy="new",
            )

        logger.info("[CognitiveService] Hardened Identity Mesh Fully Initialized.")

    async def _on_system_tick(self, data: Dict[str, Any]):
        """Mesh-driven idle evolution."""
        self._record_subject_metric("system.tick", data)
        await self.state.handle_system_tick(data)

    async def _on_audio_perception(self, data: Dict[str, Any]):
        """Sensory Intelligence: Handle emotional & event cues from SenseVoice."""
        perception_meta = data.get("metadata", {})
        perception_meta.setdefault("confidence", data.get("confidence", 0.0))
        speculative_intent = data.get("speculative_intent")
        if speculative_intent:
            self.state.last_speculative_intent = speculative_intent
        elif data.get("intent"):
            self.state.last_speculative_intent = {
                "name": data.get("intent"),
                "keywords": data.get("keywords", []),
                "confidence": data.get("confidence", 0.0),
                "text": data.get("text", ""),
                "timestamp": data.get("timestamp", time.time()),
            }
        await self.state.apply_sensory_perception(perception_meta)

    async def _on_memory_surfaced(self, data: Dict[str, Any]):
        """Proactive memory recall (Active influence)."""
        self._record_subject_metric("memory.surfaced", data)
        memory_text = data.get("content", "")
        if memory_text:
            self.surfaced_memories.append(
                {
                    "content": memory_text,
                    "timestamp": data.get("timestamp", 0),
                    "relevance": data.get("relevance", 1.0),
                }
            )
            self.surfaced_memories = self.surfaced_memories[-5:]
            logger.debug(
                f"[Cognitive] Active Memory Influence: Surfaced '{memory_text[:30]}...'"
            )

    async def process_event(
        self, raw_event: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Mesh-aware wrapper for the pure CognitivePipeline.
        Handles transport side-effects like NATS signaling and reflection triggers.
        """
        event_metadata = raw_event.get("metadata", {})
        latency_metadata = (
            event_metadata.get("latency_metadata")
            if isinstance(event_metadata, dict)
            else None
        )

        async for output in self.pipeline.execute(
            raw_event, surfaced_memories=self.surfaced_memories
        ):
            if output["type"] == "mesh_signal":
                subject = output["subject"]
                data = output["data"]

                if self.agent:
                    publish_started = time.perf_counter()
                    await self.agent.publish(subject, data)

                    self._record_subject_metric(
                        subject,
                        {"latency_metadata": latency_metadata},
                        local_latency_ms=(time.perf_counter() - publish_started) * 1000,
                    )
                yield output

            elif output["type"] == "appraisal":
                self._last_appraisal = output["data"]
                yield output

            elif output["type"] == "reflection_needed":
                episodes = output["data"]
                self.last_reflection_task = await self.learning.trigger_reflection(
                    episodes
                )
                yield output

            else:
                # content, error, done, etc.
                yield output

    async def get_current_emotion(self) -> str:
        return self.state.get_emotion_label()

    async def generate_proactive_response(
        self, thought_prompt: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Phase 1: Proactive Engagement.
        Generates a spontaneous message grounded in real identity, state, and memory.
        If thought_prompt is provided by the SubconsciousEngine, it acts as the seed.
        """
        state_directive = self.state.get_behavioral_directive()
        state_snapshot = self.state.get_context_snapshot()
        identity_prompt = self.identity.get_persona_prompt(state_directive)
        relationship = self.identity.history.get("relationship", "Friend")
        energy = self.state.current_state.energy
        mood_label = self.state.get_emotion_label()

        memory_context = ""
        if self.surfaced_memories:
            memory_context = "\nRECENT SHARED MEMORIES:\n" + "\n".join(
                [f"- {m['content']}" for m in self.surfaced_memories[-3:]]
            )

        thought_context = (
            f'Your subconscious thought: "{thought_prompt}"'
            if thought_prompt
            else "You feel an urge to reach out."
        )

        proactive_instruction = f"""
        {identity_prompt}

        SITUATION: The user has been away for a while. {thought_context}
        Your current emotional state: {mood_label}
        Your energy level: {energy:.2f}
        Your relationship with the user: {relationship}
        {memory_context}

        TASK: Generate a single, natural, spontaneous message to the user based on your subconscious thought.
        This should feel like a real friend checking in — not a notification or reminder.
        Keep it brief (1-3 sentences max). Match your tone to your current mood and energy.
        If you have shared memories, you may reference them naturally.
        Do NOT ask "How can I help you?" — you are a friend, not an assistant.

        Examples of natural check-ins:
        - "Hey, been a while! What have you been up to?"
        - "I was just thinking about that thing you mentioned earlier..."
        - "You okay? Haven't heard from you in a bit."

        Respond with ONLY the message. No quotes, no labels, no preamble.
        """.strip()

        from .decision import ActionPlan

        plan = ActionPlan(
            action_type="RESPOND_CHAT",
            goal="INITIATE",
            payload={
                "message": "[PROACTIVE_TRIGGER]",
                "identity_prompt": proactive_instruction,
                "emotion_state": mood_label,
                "surfaced_memories": self.surfaced_memories[-3:]
                if self.surfaced_memories
                else [],
                # Tier-5 Endocrine: Inject hormonal state
                "cortisol": state_snapshot.get("cortisol", 0.5),
                "dopamine": state_snapshot.get("dopamine", 0.0),
            },
            priority=0,
        )

        full_response = ""
        async for chunk in self.action.execute(plan):
            if chunk["type"] == "content":
                full_response += chunk["data"]
            yield chunk

        self.state.mark_proactive_attempt()

        if full_response:
            episode = {
                "id": f"proactive-{time.time()}",
                "event": "[Agent initiated contact]",
                "context": state_directive,
                "emotion_vector": {
                    "V": self.state.current_state.valence,
                    "Ar": self.state.current_state.arousal,
                    "D": self.state.current_state.dominance,
                },
                "content": "[Agent initiated contact]",
                "intent": "CHAT",
                "state": state_snapshot,
                "response": full_response,
            }
            self.last_reflection_task = await self.learning.trigger_reflection(
                [episode]
            )

        logger.info(
            "[Cognitive] Proactive generation complete. Response length: %d",
            len(full_response),
        )

    def _record_subject_metric(
        self,
        subject: str,
        data: Dict[str, Any],
        local_latency_ms: float = None,
    ):
        metric = self.subject_metrics.get(subject)
        if metric is None:
            return

        metric["count"] += 1

        metadata = data.get("latency_metadata") if isinstance(data, dict) else None
        if isinstance(metadata, dict) and metadata.get("start_time") is not None:
            try:
                latency_ms = max(
                    0.0, (time.time() - float(metadata["start_time"])) * 1000
                )
                metric["latency_total_ms"] += latency_ms
                metric["latency_samples"] += 1
            except (TypeError, ValueError):
                pass

        if local_latency_ms is not None:
            metric["latency_total_ms"] += local_latency_ms
            metric["latency_samples"] += 1

        if metric["count"] == 1 or metric["count"] % 20 == 0:
            avg_latency = 0.0
            if metric["latency_samples"] > 0:
                avg_latency = metric["latency_total_ms"] / metric["latency_samples"]
            logger.info(
                "[CognitiveMetrics] subject=%s count=%s avg_latency_ms=%.2f",
                subject,
                metric["count"],
                avg_latency,
            )
