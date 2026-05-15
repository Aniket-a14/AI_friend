import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SubconsciousEngine:
    """
    Pure Logic Engine for Tier-5 Subconscious Thoughts.
    Decoupled from NATS and State Persistence.
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    async def evaluate_and_think(
        self, 
        state_snapshot: Dict[str, Any],
        proactive_eligible: bool
    ) -> Optional[str]:
        """
        Evaluates conditions and generates a thought string if eligible.
        """
        if not proactive_eligible:
            return None

        emotion = state_snapshot.get("emotion", "neutral")
        energy = state_snapshot.get("energy", 0.5)

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
                return None

            return thought

        except Exception as e:
            logger.error(f"[SubconsciousEngine] Thought generation failed: {e}")
            return None
