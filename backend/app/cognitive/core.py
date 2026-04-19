import logging
import time
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
        graph_db,
        identity_store=None,
    ):
        self.identity = IdentityManager()
        self.identity_store = identity_store
        self.perception = PerceptionService(llm_service=llm_service)
        self.state = StateService(graph_store=graph_db)
        self.decision = DecisionService(llm_service=llm_service, memory_store=memory_store)
        self.action = ActionService(llm_service=llm_service, memory_store=memory_store)
        self.learning = ReflectionService(
            llm_service=llm_service, 
            graph_store=graph_db, 
            pg_vector=memory_store,
            identity_manager=self.identity
        )
        self.surfaced_memories = [] # Buffer for active memory influence
        self.agent = None # NATS Mesh connection

    async def initialize(self, agent: Any = None):
        """Load identity and hydrate states. Subscribes to Mesh heartbeats."""
        if self.identity_store:
            await self.identity.hydrate_from_config_store(self.identity_store)
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
        raw_event_type = raw_event.get("event_type") or raw_event.get("type")
        if raw_event_type == "USER_MESSAGE" and not raw_event.get("is_partial"):
            final_text = raw_event.get("content", "")
            speculative_intent = self.state.last_speculative_intent
            if speculative_intent:
                confirmed = self.decision.is_speculative_stop_confirmed(
                    final_text,
                    speculative_intent.get("keywords"),
                )
                self.state.last_speculative_intent = None
                if not confirmed:
                    # REJECTED: False positive. Resume playback immediately.
                    logger.info("[Cognitive] Interruption REJECTED. Resuming playback...")
                    
                    # DIRECT MESH SIGNAL: Resume bypasses the cognitive generator
                    if self.agent:
                        await self.agent.publish("audio.resume", {
                            "reason": "conflict_rejected",
                            "perception_text": speculative_intent.get("text", ""),
                            "utterance_id": speculative_intent.get("utterance_id"),
                        })
                    
                    yield {"type": "mesh_signal", "data": "audio.resume"}
                else:
                    logger.info("[Cognitive] Interruption CONFIRMED. Stopping playback.")
                    if self.agent:
                        await self.agent.publish("audio.stop", {
                            "interrupt": True,
                            "speculative": False,
                            "reason": "confirmed_command",
                            "command_text": final_text,
                            "keywords": speculative_intent.get("keywords", []),
                            "utterance_id": speculative_intent.get("utterance_id"),
                            "turn_id": raw_event.get("metadata", {}).get("turn_id"),
                        })
                    yield {"type": "mesh_signal", "data": "audio.stop"}
                    return

        # 2. Sequential Perception
        event = await self.perception.perceive(raw_event)
        
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
