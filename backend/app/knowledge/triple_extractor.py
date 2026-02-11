import logging
import json
import re
from typing import List, Tuple
from .graph_db import GraphDB

logger = logging.getLogger(__name__)

class TripleExtractor:
    """
    Service to extract (Subject, Relation, Object) triples from text.
    In v3.0, this uses an LLM to parse conversation semantics.
    """
    def __init__(self, llm_service=None, graph_db: GraphDB = None):
        self.llm_service = llm_service  # This would be an instance of LLMService
        self.graph_db = graph_db

    async def extract_and_store(self, text: str, user_id: str = "User"):
        """
        Parses text, finds facts, and merges them into the Graph.
        """
        prompt = f"""
        Extract key factual relationships from the following text as (Subject, Relation, Object) triples.
        The Subject should usually be "{user_id}" or a person/entity mentioned.
        Return ONLY a JSON list of lists.
        Text: "{text}"
        Example Output: [["{user_id}", "LIVES_IN", "Berlin"], ["{user_id}", "HAS_BROTHER", "Rahul"]]
        """
        
        try:
            # For now, we'll use a fallback or the provided LLM service
            if self.llm_service:
                response = await self.llm_service.generate_response_stream(prompt)
                # Note: This is simplified. In a real scenario, we'd use a non-streaming 
                # call or collect the stream.
                triples = self._parse_json_from_text(response)
            else:
                # Mock extraction for bootstrap
                triples = []
                if "live in" in text.lower():
                    match = re.search(r"live in (\w+)", text, re.I)
                    if match: triples.append([user_id, "LIVES_IN", match.group(1)])

            if triples and self.graph_db:
                for sub, rel, obj in triples:
                    await self.graph_db.create_relationship(sub, rel, obj)
            
            return triples
        except Exception as e:
            logger.error(f"Triple extraction failed: {e}")
            return []

    def _parse_json_from_text(self, text: str) -> List[List[str]]:
        try:
            # Find the first [ and last ]
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return []
        except:
            return []
