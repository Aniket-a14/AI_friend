import logging
import asyncio
import json
import re
from typing import List, Dict, Any
from .identity import IdentityManager

logger = logging.getLogger(__name__)

class ReflectionService:
    """
    The Learning / Consolidation Layer (Background Reflection).
    Uses the LLM to synthesize facts for Neo4j and evolve the Persona.
    """
    def __init__(self, llm_service=None, graph_store=None, pg_vector=None):
        self.llm = llm_service
        self.graph = graph_store
        self.vector = pg_vector
        self.identity = IdentityManager()
        self.is_reflecting = False

    async def trigger_reflection(self, recent_episodes: List[Dict[str, Any]]):
        """Non-blocking trigger for background learning."""
        if self.is_reflecting or not recent_episodes:
            return
            
        logger.info(f"[Reflection] Starting consolidation logic for {len(recent_episodes)} events.")
        asyncio.create_task(self._consolidate(recent_episodes))

    async def _consolidate(self, episodes: List[Dict[str, Any]]):
        """
        The background process:
        1. Fact Extraction (Neo4j)
        2. Identity Evolution (JSON)
        """
        self.is_reflecting = True
        try:
            summary_text = "\n".join([f"User: {e.get('content')}\nAI: {e.get('response', '')}" for e in episodes])
            
            # --- PART 1: Fact Synthesis (Neo4j) ---
            fact_prompt = f"""
            Extract new entities and relationships from these interactions.
            Interactions:
            {summary_text}
            
            Focus on: People, Preferences, Events, and Facts about the User.
            Output JSON List ONLY: [{{"subject", "relation", "object", "type"}}]
            """
            try:
                fact_res = await self.llm.generate(fact_prompt)
                facts = self._extract_json(fact_res)
                for f in facts:
                    if "subject" in f and "object" in f:
                        await self.graph.create_relationship(
                            f["subject"], f.get("type", "Entity"), f["relation"], f["object"], "Entity"
                        )
            except Exception as e:
                logger.error(f"Fact extraction failed: {e}")

            # --- PART 2: Identity Evolution (JSON Persona) ---
            identity_prompt = f"""
            Analyze these interactions to see if {self.identity.personality.get('name')}'s personality or relationship should evolve.
            Interactions:
            {summary_text}
            
            Current Role: {self.identity.history.get('relationship')}
            
            Should we add a core trait? Should we update the relationship status?
            Output JSON ONLY: {{"new_traits": ["..."], "relationship": "...", "new_memory": "..."}}
            """
            try:
                ident_res = await self.llm.generate(identity_prompt)
                suggestions = self._extract_json(ident_res)
                if suggestions:
                    await self.identity.evolve_persona(suggestions)
            except Exception as e:
                logger.error(f"Identity evolution failed: {e}")

            logger.info("[Reflection] Background consolidation and persona evolution complete.")
            
        except Exception as e:
            logger.error(f"[Reflection] Consolidation failed: {e}")
        finally:
            self.is_reflecting = False

    def _extract_json(self, text: str) -> Any:
        try:
            # Handle DeepSeek thoughts
            if "<think>" in text:
                text = text.split("</think>")[-1].strip()
            
            match = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return [] if "[" in text else {}
        except Exception as e:
            logger.error(f"JSON extraction failed: {e}")
            return []
