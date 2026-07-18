import logging
import json
import re
from typing import List
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
                if hasattr(response, "__aiter__"):
                    response = "".join([chunk async for chunk in response])
                triples = self._parse_json_from_text(response)
            else:
                # Mock extraction for bootstrap
                triples = []
                if "live in" in text.lower():
                    match = re.search(r"live in (\w+)", text, re.I)
                    if match:
                        triples.append([user_id, "LIVES_IN", match.group(1)])

            if triples and self.graph_db:
                for triple in triples:
                    if len(triple) != 3:
                        continue
                    sub, rel, obj = triple
                    await self.graph_db.create_triplet(
                        sub,
                        rel,
                        obj,
                        {"source": "triple_extractor"},
                    )

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
        except Exception:
            return []
