import logging
import asyncio
import json
import re
import time
from typing import List, Dict, Any
from .identity import IdentityManager
from ..config import Config
from ..state.graph_db import GraphDB

logger = logging.getLogger("reflection")


class ReflectionService:
    """
    CVS-1.0 Solid State Learning Layer.
    Implements Fact Resolution, Confidence Gating, and Adaptive Persona Evolution.
    """

    def __init__(
        self, llm_service=None, graph_store=None, pg_vector=None, identity_manager=None
    ):
        self.llm = llm_service
        self.graph = graph_store
        self.vector = pg_vector
        self.identity = identity_manager or IdentityManager()
        self.is_reflecting = False
        self.last_reflection_started_at = 0.0

        # CVS-1.0: Explicit completion signaling for deterministic mesh verification
        self.reflection_done = asyncio.Event()
        self.reflection_done.set()

    async def trigger_reflection(self, recent_episodes: List[Dict[str, Any]]):
        """Non-blocking trigger for background learning."""
        if not getattr(Config, "REFLECTION_ENABLED", True):
            return

        if self.is_reflecting or not recent_episodes:
            # CVS-1.0: Always return awaitable to support deterministic testing
            f = asyncio.Future()
            f.set_result(None)
            return f

        min_interval = max(
            0.0, float(getattr(Config, "REFLECTION_MIN_INTERVAL_SECONDS", 0.0))
        )
        now = time.monotonic()
        if (
            min_interval > 0.0
            and (now - self.last_reflection_started_at) < min_interval
        ):
            f = asyncio.Future()
            f.set_result(None)
            return f

        self.last_reflection_started_at = now

        # CVS-1.0: Signal started
        self.reflection_done.clear()

        logger.info(
            f"[Reflection] Starting semantic consolidation logic for {len(recent_episodes)} events."
        )
        return asyncio.create_task(self._consolidate(recent_episodes))

    async def _consolidate(self, episodes: List[Dict[str, Any]]):
        """
        Background Solid State Consolidation (§7):
        1. Fact Resolution (Deduplication & Gating)
        2. Persona Evolution (Locked Logic)

        Episodes now use the enriched schema (§6.1 — Tulving + Amory):
        {id, event, context, emotion_vector, appraisal, relationship_delta, response}
        """
        self.is_reflecting = True
        try:
            # Build enriched summary from episodic schema
            summary_parts = []
            for e in episodes:
                emotion_vec = e.get("emotion_vector", {})
                V = emotion_vec.get("V", 0.0)
                Ar = emotion_vec.get("Ar", 0.5)
                D = emotion_vec.get("D", 0.5)
                ctx = e.get("context", "")
                ri = e.get("relationship_delta", 0.0)
                summary_parts.append(
                    f"Context: {ctx}\n"
                    f"User: {e.get('content', e.get('event', ''))}\n"
                    f"AI: {e.get('response', '')}\n"
                    f"[Emotion V={V:.2f} Ar={Ar:.2f} D={D:.2f} | RelDelta={ri:.2f}]"
                )
            summary_text = "\n---\n".join(summary_parts)

            # --- PART 1: Fact Resolution (Neo4j) ---
            fact_prompt = f"""
            Extract new entities, relationships, and "Theory of Mind" observations from these interactions.
            Interactions:
            {summary_text}

            Focus on:
            1. People, Preferences, and Facts about the User.
            2. THEORY OF MIND: Observations about the User's mental/physical state (e.g., "User seems stressed", "User is tired from work").

            REQUIREMENT: Provide a confidence score (0.0 - 1.0), the appropriate category (one of: social, vocational, somatic, spiritual, crisis, milestone), and a brief reasoning for each fact.
            Output JSON List ONLY: [{{"subject", "subject_type", "relation", "object", "object_type", "category", "confidence", "reason"}}]
            """

            try:
                fact_res = await self.llm.generate(
                    fact_prompt,
                    model=Config.LLM_REFLECTION_MODEL,
                    options_override={"num_predict": 256},
                )
                facts = self._extract_json(fact_res)

                # CVS-1.0: Defensive parsing for LLM output variability
                if isinstance(facts, dict):
                    facts = [facts]
                elif not isinstance(facts, list):
                    facts = []

                for f in facts:
                    if not isinstance(f, dict):
                        continue

                    # 1. CONFIDENCE GATING: Only store facts with > 0.8 certainty
                    confidence = f.get("confidence", 0.0)
                    if confidence < 0.8:
                        logger.debug(
                            f"Fact REJECTED (Low Confidence: {confidence}): {f.get('subject')} - {f.get('relation')}"
                        )
                        continue

                    # 2. FACT RESOLUTION: Check for existing duplication in GraphDB
                    subject = f.get("subject")
                    object_val = f.get("object")
                    relation = f.get("relation")
                    subject_type = f.get("subject_type", "Entity")
                    object_type = f.get("object_type", "Entity")
                    category = f.get("category", "social").lower()

                    if not subject or not object_val or not relation:
                        continue

                    # Neo4j must NOT have distractors
                    if category == "distractor":
                        logger.debug(
                            "Fact REJECTED (Distractors are excluded from Neo4j)"
                        )
                        continue

                    if category not in [
                        "social",
                        "vocational",
                        "somatic",
                        "spiritual",
                        "crisis",
                        "milestone",
                    ]:
                        category = "social"

                    try:
                        rel_type = GraphDB._safe_relation(relation)
                        GraphDB._safe_label(subject_type)
                        GraphDB._safe_label(object_type)
                        GraphDB._safe_label(category.capitalize())
                    except ValueError:
                        logger.warning(
                            "Skipping unsafe graph fact from reflection: %r", f
                        )
                        continue

                    # Search if this relationship already exists with high weight
                    query = f"""
                    MATCH (s)-[r:{rel_type}]->(t)
                    WHERE s.name = $s_name AND t.name = $t_name
                    RETURN r
                    """
                    existing = await self.graph.execute_query(
                        query, {"s_name": subject, "t_name": object_val}
                    )

                    if existing:
                        logger.debug(
                            f"Fact RESOLVED: Relationship already exists between {subject} and {object_val}."
                        )
                        # Optionally nudge the weight instead of creating new
                        continue

                    # Actual Storage
                    await self.graph.create_triplet(
                        subject,
                        rel_type,
                        object_val,
                        properties={
                            "confidence": confidence,
                            "extracted_at": str(time.time()),
                            "category": category,
                        },
                        subject_label=subject_type,
                        target_label=object_type,
                    )
            except Exception as e:
                logger.error(f"Fact consolidation failure: {e}")

            # --- PART 2: Persona Evolution ---
            # Identical pattern for Persona stability
            identity_prompt = f"""
            Determine if {self.identity.personality.get("name")}'s personality or relationship should evolve.
            Interactions:
            {summary_text}
            Current Role: {self.identity.history.get("relationship")}

            Output JSON ONLY: {{"new_traits": ["..."], "relationship": "...", "confidence": 0.0}}
            """
            try:
                ident_res = await self.llm.generate(
                    identity_prompt,
                    model=Config.LLM_REFLECTION_MODEL,
                    options_override={"num_predict": 256},
                )
                suggestions = self._extract_json(ident_res)

                # CVS-1.0: Defensive parsing for identity suggestions (Ensures .get() availability)
                if isinstance(suggestions, list) and len(suggestions) > 0:
                    suggestions = suggestions[0]
                elif not isinstance(suggestions, dict):
                    suggestions = {}

                if suggestions and suggestions.get("confidence", 0.0) >= 0.8:
                    await self.identity.evolve_persona(suggestions)
                else:
                    logger.debug(
                        "Persona evolution REJECTED: Low confidence or no growth detected."
                    )
            except Exception as e:
                logger.error(f"Identity evolution failure: {e}")

            # --- PART 3: Long-Term Episodic Memory Consolidation ---
            try:
                # Calculate composite affective vectors
                total_valence = 0.0
                total_arousal = 0.0
                total_dominance = 0.0
                count = len(episodes)
                for e in episodes:
                    emotion_vec = e.get("emotion_vector", {})
                    total_valence += emotion_vec.get("V", 0.0)
                    total_arousal += emotion_vec.get("Ar", 0.5)
                    total_dominance += emotion_vec.get("D", 0.5)

                avg_valence = total_valence / count if count > 0 else 0.0
                avg_arousal = total_arousal / count if count > 0 else 0.5
                avg_dominance = total_dominance / count if count > 0 else 0.5

                consolidation_prompt = f"""
                Consolidate the following recent interaction episodes into a single, cohesive episodic memory summary.
                This summary should capture the essence of what was discussed, the emotional tone of both the user and the AI, and any key takeaways or relationship progression.
                Interactions:
                {summary_text}

                Format: A brief, single-paragraph narrative from the AI's perspective (e.g. "We discussed...").
                """

                consolidation_res = await self.llm.generate(
                    consolidation_prompt,
                    model=Config.LLM_REFLECTION_MODEL,
                    options_override={"num_predict": 256},
                )
                consolidated_summary = consolidation_res.strip()
                if "<think>" in consolidated_summary:
                    consolidated_summary = consolidated_summary.split("</think>")[
                        -1
                    ].strip()

                if consolidated_summary and self.vector:
                    await self.vector.add_memory(
                        content=consolidated_summary,
                        raw_content=summary_text,
                        wing="personal",
                        importance=0.6,
                        emotion=avg_arousal,
                        valence=avg_valence,
                        source="subconscious_consolidation",
                        metadata={
                            "composite_valence": avg_valence,
                            "composite_arousal": avg_arousal,
                            "composite_dominance": avg_dominance,
                            "episode_count": len(episodes),
                        },
                    )
                    logger.info(
                        "[Reflection] Long-term episodic memory successfully consolidated and stored."
                    )
            except Exception as e:
                logger.error(f"Episodic memory consolidation failure: {e}")

            logger.info("[Reflection] Semantic Mesh Consolidation Complete.")

        except Exception as e:
            logger.error(f"[Reflection] Critical Consolidation Failure: {e}")
        finally:
            self.is_reflecting = False
            self.reflection_done.set()  # Unblock waiters

    def _extract_json(self, text: str) -> Any:
        try:
            if "<think>" in text:  # Handle deep reasoning prefixes
                text = text.split("</think>")[-1].strip()

            match = re.search(r"\[.*\]|\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return [] if "[" in text else {}
        except Exception as e:
            logger.error(f"JSON extraction failed: {e}")
            return []
