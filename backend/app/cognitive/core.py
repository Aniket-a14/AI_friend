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

    async def initialize(self):
        """Load identity and hydrate states."""
        await self.state.hydrate_state()
        logger.info("[CognitiveService] BDI Mesh Fully Initialized.")

    async def process_event(self, raw_event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        The Master Cognitive Loop:
        1. Perceive: Raw -> Structured Event
        2. State Update: Dynamic evolution
        3. Decide: Plan based on Goal
        4. Execute: Generate and Validate
        5. Learn: Consolidation
        """
        # 1. & 2. Concurrent Perception and State Retrieval
        # While perception classifies intent, we can simultaneously fetch current state.
        perception_task = asyncio.create_task(self.perception.perceive(raw_event))
        state_task = asyncio.create_task(self.state.hydrate_state()) # Ensure fresh state from Neo4j
        
        event, _ = await asyncio.gather(perception_task, state_task)
        
        # 3. Decision (BT Based)
        state_snapshot = self.state.get_context_snapshot()
        plan = await self.decision.decide(event, state_snapshot)
        
        # 4. Action Execution with Identity Validation
        # We pass the IdentityManager to ActionService or handle it here.
        # For 'drift-at-source', we inject identity prompt.
        plan.payload["identity_prompt"] = self.identity.get_persona_prompt()
        
        full_response = ""
        async for chunk in self.action.execute(plan):
            if chunk["type"] == "content":
                full_response += chunk["data"]
            yield chunk
            
        # 5. Validation Check
        if full_response:
            is_valid, reason = await self.identity.validate_response(full_response, plan.goal)
            if not is_valid:
                logger.warning(f"[Identity] Validation failed: {reason}. Triggering self-correction...")
                # In a more advanced loop, we would re-run generation with the reason.
        
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
