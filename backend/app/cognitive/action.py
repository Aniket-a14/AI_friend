import logging
from typing import Dict, Any, AsyncGenerator
from .decision import ActionPlan

logger = logging.getLogger(__name__)

class ActionService:
    """
    The Action Layer.
    Executes the Decision Plan by generating responses or performing system tasks.
    Enforces the Identity Protocol in LLM generations.
    """
    def __init__(self, llm_service=None, memory_store=None):
        self.llm = llm_service
        self.memory = memory_store

    async def execute(self, plan: ActionPlan) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the plan and yields output chunks.
        """
        logger.info(f"[Action] Executing Decision: {plan.action_type} for Goal: {plan.goal}")
        
        if plan.action_type == "RESPOND_CHAT":
            # 1. Prepare Identity-Aware Prompt
            msg = plan.payload.get("message", "")
            identity_prompt = plan.payload.get("identity_prompt", "You are my friend.")
            emotion = plan.payload.get("emotion_state", "neutral")
            
            model = plan.payload.get("model")
            
            # Construct the final prompt with structural guidance
            full_prompt = f"""
            {identity_prompt}
            
            Current Context: 
            - Goal: {plan.goal}
            - Current Emotion: {emotion}
            
            Guidelines:
            - Maintain your identity rules at all times.
            - Wrap your response in <emotion type='...'>...</emotion> tags.
            
            User: {msg}
            Assistant: """.strip()
            
            try:
                # 2. Stream Generation
                async for chunk in self.llm.generate_stream(full_prompt, model=model):
                    yield {"type": "content", "data": chunk}
                yield {"type": "done", "data": "finished"}
                
            except Exception as e:
                logger.error(f"[Action] LLM Execution failed: {e}")
                yield {"type": "error", "data": str(e)}
                yield {"type": "done", "data": ""}
             
        elif plan.action_type == "STORE_MEMORY":
             content = plan.payload.get("content", "")
             # Using the new intelligent MemoryStore
             if self.memory:
                 await self.memory.add_memory(
                     content=content,
                     importance=0.7, # High importance for explicit 'remember' commands
                     emotion=0.2,
                     source='user'
                 )
             yield {"type": "system", "data": "Memory securely consolidated."}
             yield {"type": "done", "data": ""}
             
        elif plan.action_type == "BACKGROUND_CONSOLIDATION":
             # Already triggered by CognitiveService
             yield {"type": "done", "data": ""}
             
        else:
             logger.warning(f"[Action] Unrecognized action: {plan.action_type}")
             yield {"type": "error", "data": "Unknown operation."}
             yield {"type": "done", "data": ""}
