import asyncio
import logging
from typing import Dict, Any, AsyncGenerator

from .perception import PerceptionService
from .state import StateService
from .decision import DecisionService
from .action import ActionService
from .learning import ReflectionService
from .identity import IdentityManager

logger = logging.getLogger(__name__)

class CognitiveService:
    """
    The Orchestrator for the Cognitive Loop.
    Integrates BDI logic, State dynamics, and Identity enforcement.
    """
    def __init__(
        self,
        llm_service,
        memory_store,
        graph_db
    ):
        self.perception = PerceptionService(llm_service=llm_service)
        self.state = StateService(graph_store=graph_db)
        self.decision = DecisionService(llm_service=llm_service, memory_store=memory_store)
        self.action = ActionService(llm_service=llm_service, memory_store=memory_store)
        self.learning = ReflectionService(
            llm_service=llm_service, 
            graph_store=graph_db, 
            pg_vector=memory_store
        )
        self.identity = IdentityManager()
        self.surfaced_memories = [] # Buffer for active memory influence
        self.agent = None # NATS Mesh connection

    async def initialize(self, agent: Any = None):
        """Load identity and hydrate states. Subscribes to Mesh heartbeats."""
        await self.state.hydrate_state()
        
        # Subscribe to Mesh Channels
        if agent:
             self.agent = agent
             await agent.subscribe("system.tick", self._on_system_tick)
             await agent.subscribe("memory.surfaced", self._on_memory_surfaced)
             await agent.subscribe("audio.perception", self._on_audio_perception)
             
        logger.info("[CognitiveService] Hardened Identity Mesh Fully Initialized.")

    async def _on_system_tick(self, data: Dict[str, Any]):
        """Mesh-driven idle evolution."""
        await self.state.handle_system_tick(data)

    async def _on_audio_perception(self, data: Dict[str, Any]):
        """
        Sensory Intelligence: Handle emotional & event cues from SenseVoice.
        """
        perception_meta = data.get("metadata", {})
        # Store last speculative intent for arbitration
        self.state.last_speculative_intent = data.get("intent")
        await self.state.apply_sensory_perception(perception_meta)

    async def _on_memory_surfaced(self, data: Dict[str, Any]):
        """Proactive memory recall (Active influence)."""
        memory_text = data.get("content", "")
        if memory_text:
            self.surfaced_memories.append({
                "content": memory_text,
                "timestamp": data.get("timestamp", 0),
                "relevance": data.get("relevance", 1.0)
            })
            # Keep only last 5 surfaced memories
            self.surfaced_memories = self.surfaced_memories[-5:]
            logger.debug(f"[Cognitive] Active Memory Influence: Surfaced '{memory_text[:30]}...'")

    async def process_event(self, raw_event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        The Master Cognitive Loop:
        Refined for Solid State Social Mesh Arbitration.
        """
        # 1. Conflict Resolution (Turn-Taking Stability)
        # If we just received a final transcript, check if it contradicts a recent speculative stop.
        if raw_event.get("event_type") == "USER_MESSAGE" and not raw_event.get("is_partial"):
            final_text = raw_event.get("content", "")
            if self.state.last_speculative_intent:
                confirmed = self.decision.is_speculative_stop_confirmed(final_text)
                if not confirmed:
                    # REJECTED: False positive. Resume playback immediately.
                    logger.info("[Cognitive] Interruption REJECTED. Resuming playback...")
                    
                    # DIRECT MESH SIGNAL: Resume bypasses the cognitive generator
                    if self.agent:
                        await self.agent.publish("audio.resume", {"reason": "conflict_rejected"})
                    
                    self.state.last_speculative_intent = None
                    yield {"type": "mesh_signal", "data": "audio.resume"}

        # 2. Sequential Perception and State Retrieval
        perception_task = asyncio.create_task(self.perception.perceive(raw_event))
        state_task = asyncio.create_task(self.state.hydrate_state())
 # Ensure fresh state from Neo4j
        
        event, _ = await asyncio.gather(perception_task, state_task)
        
        # 3. Decision (BT Based)
        state_snapshot = self.state.get_context_snapshot()
        state_directive = self.state.get_behavioral_directive()
        
        # Add surfaced memories to event context for 'Active Influence'
        if self.surfaced_memories:
            event.metadata["surfaced_memories"] = self.surfaced_memories
            
        plan = await self.decision.decide(event, state_snapshot)
        
        # 4. Action Execution with Identity Validation
        # Condition behavior on Evolving State + Immutable Core
        plan.payload["identity_prompt"] = self.identity.get_persona_prompt(state_directive)
        
        full_response = ""
        async for chunk in self.action.execute(plan):
            if chunk["type"] == "content":
                full_response += chunk["data"]
            yield chunk
            
        # 5. Validation Check & Self-Correction
        if full_response:
            is_valid, reason = await self.identity.validate_response(full_response, plan.goal)
            if not is_valid:
                logger.warning(f"[Identity] Validation failed: {reason}. SELF-CORRECTION TRIGGERED.")
                # PRODUCTION LOGIC: Automated Self-Correction
                # We append the reason and re-generate once.
                plan.payload["identity_prompt"] += f"\n\nCRITICAL FIX: Your previous response was rejected for: {reason}. Correct this immediately."
                
                full_response = ""
                async for chunk in self.action.execute(plan):
                    if chunk["type"] == "content":
                        full_response += chunk["data"]
                    yield chunk
        
        # 6. Learning
        if event.intent in ["CHAT", "REMEMBER"]:
             episode = {
                 "id": event.event_id,
                 "content": event.raw_content,
                 "intent": event.intent,
                 "state": state_snapshot,
                 "response": full_response
             }
             await self.learning.trigger_reflection([episode])

    async def get_current_emotion(self) -> str:
        return self.state.get_emotion_label()
