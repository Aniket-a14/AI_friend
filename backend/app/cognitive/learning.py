import logging
import asyncio
import json
import re
from typing import List, Dict, Any
from .identity import IdentityManager

logger = logging.getLogger("reflection")

class ReflectionService:
    """
    CVS-1.0 Solid State Learning Layer.
    Implements Fact Resolution, Confidence Gating, and Adaptive Persona Evolution.
    """
    def __init__(self, llm_service=None, graph_store=None, pg_vector=None, identity_manager=None):
        self.llm = llm_service
        self.graph = graph_store
        self.vector = pg_vector
        self.identity = identity_manager or IdentityManager()
        self.is_reflecting = False

    async def trigger_reflection(self, recent_episodes: List[Dict[str, Any]]):
        """Non-blocking trigger for background learning."""
        if self.is_reflecting or not recent_episodes:
            return
            
        logger.info(f"[Reflection] Starting semantic consolidation logic for {len(recent_episodes)} events.")
        asyncio.create_task(self._consolidate(recent_episodes))

    async def _consolidate(self, episodes: List[Dict[str, Any]]):
        """
        Background Solid State Consolidation:
        1. Fact Resolution (Deduplication & Gating)
        2. Persona Evolution (Locked Logic)
        """
        self.is_reflecting = True
        try:
            summary_text = "\n".join([f"User: {e.get('content')}\nAI: {e.get('response', '')}" for e in episodes])
            
            # --- PART 1: Fact Resolution (Neo4j) ---
            fact_prompt = f"""
            Extract new entities and relationships from these interactions.
            Interactions:
            {summary_text}
            
            Focus on: People, Preferences, Events, and Facts about the User.
            REQUIREMENT: Provide a confidence score (0.0 - 1.0) and a brief reasoning for each fact.
            Output JSON List ONLY: [{{"subject", "relation", "object", "type", "confidence", "reason"}}]
            """
            
            try:
                fact_res = await self.llm.generate(fact_prompt, model="qwen2.5:7b")
                facts = self._extract_json(fact_res)
                
                for f in facts:
                    # 1. CONFIDENCE GATING: Only store facts with > 0.8 certainty
                    confidence = f.get("confidence", 0.0)
                    if confidence < 0.8:
                        logger.debug(f"Fact REJECTED (Low Confidence: {confidence}): {f.get('subject')} - {f.get('relation')}")
                        continue
                    
                    # 2. FACT RESOLUTION: Check for existing duplication in GraphDB
                    subject = f.get("subject")
                    object_val = f.get("object")
                    relation = f.get("relation")
                    
                    if not subject or not object_val:
                        continue

                    # Search if this relationship already exists with high weight
                    query = f"""
                    MATCH (s)-[r:{relation.upper().replace(' ', '_')}]->(t)
                    WHERE s.name = $s_name AND t.name = $t_name
                    RETURN r
                    """
                    existing = await self.graph.execute_query(query, {"s_name": subject, "t_name": object_val})
                    
                    if existing:
                        logger.debug(f"Fact RESOLVED: Relationship already exists between {subject} and {object_val}.")
                        # Optionally nudge the weight instead of creating new
                        continue
                    
                    # Actual Storage
                    await self.graph.create_relationship(
                        subject, f.get("type", "Entity"), f["relation"], object_val, "Entity",
                        properties={"confidence": confidence, "extracted_at": str(asyncio.get_event_loop().time())}
                    )
            except Exception as e:
                logger.error(f"Fact consolidation failure: {e}")

            # --- PART 2: Persona Evolution ---
            # Identical pattern for Persona stability
            identity_prompt = f"""
            Determine if {self.identity.personality.get('name')}'s personality or relationship should evolve.
            Interactions:
            {summary_text}
            Current Role: {self.identity.history.get('relationship')}
            
            Output JSON ONLY: {{"new_traits": ["..."], "relationship": "...", "confidence": 0.0}}
            """
            try:
                ident_res = await self.llm.generate(identity_prompt)
                suggestions = self._extract_json(ident_res)
                if suggestions and suggestions.get("confidence", 0.0) >= 0.8:
                    await self.identity.evolve_persona(suggestions)
                else:
                    logger.debug("Persona evolution REJECTED: Low confidence or no growth detected.")
            except Exception as e:
                logger.error(f"Identity evolution failure: {e}")

            logger.info("[Reflection] Semantic Mesh Consolidation Complete.")
            
        except Exception as e:
            logger.error(f"[Reflection] Critical Consolidation Failure: {e}")
        finally:
            self.is_reflecting = False

    def _extract_json(self, text: str) -> Any:
        try:
            if "<think>" in text: # Handle deep reasoning prefixes
                text = text.split("</think>")[-1].strip()
            
            match = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return [] if "[" in text else {}
        except Exception as e:
            logger.error(f"JSON extraction failed: {e}")
            return []
