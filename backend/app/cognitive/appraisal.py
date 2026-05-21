"""
Appraisal Engine — OCC/Lazarus/EMA (psychological_layer.md §1).

Computes the 6-variable appraisal vector on every user event.
Uses heuristic computation on the hot path; the ReappraisalEngine
refines weights in the background.

Sources:
  - OCC (Ortony, Clore & Collins, 1988) for emotion categorization
  - Lazarus (1991) for primary/secondary appraisal
  - EMA (Gratch & Marsella, 2004) for computational implementation
"""

import logging
import json
import re
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppraisalVector:
    """
    6-variable appraisal vector (§1.3).

    Primary appraisal (Lazarus):
        R  — Relevance          [0, 1]
        N  — Novelty            [0, 1]
        G  — Goal Congruence    [-1, 1]

    Secondary appraisal (Lazarus/OCC/EMA):
        A  — Agency             [0, 1]
        NA — Norm Alignment     [0, 1]
        RI — Relationship Impact [-1, 1]  (our extension)
    """

    relevance: float = 0.5
    novelty: float = 0.3
    goal_congruence: float = 0.0
    agency: float = 0.5
    norm_alignment: float = 1.0
    relationship_impact: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


class AppraisalEngine:
    """
    Computes appraisal vectors from cognitive events.

    Uses heuristic computation on the hot path to avoid LLM latency.
    R and N use lightweight text similarity; G, A, NA, RI are derived
    from available state signals (acoustic perception, identity boundaries).
    """

    def __init__(self, identity_core_values: List[str] = None):
        self.identity_values = identity_core_values or []
        self._recent_contents: List[str] = []
        self._max_recent = 20

    def appraise(
        self,
        event_content: str,
        event_type: str,
        emotional_bias: float,
        state_snapshot: Dict[str, Any],
        identity_boundaries: List[str] = None,
    ) -> AppraisalVector:
        """
        Heuristic appraisal for the real-time cognitive loop.
        Returns an AppraisalVector without requiring LLM or embedding calls.
        """
        # --- Primary Appraisal (§1.1) ---

        # R — Relevance: User messages are always relevant
        if event_type == "USER_MESSAGE":
            relevance = 1.0
        elif event_type == "SYSTEM_TICK":
            relevance = 0.1
        else:
            relevance = 0.5

        # N — Novelty: Word-overlap similarity against recent messages
        novelty = self._compute_novelty(event_content)

        # G — Goal Congruence: Positive emotional bias → congruent with social goals
        goal_congruence = max(-1.0, min(1.0, emotional_bias))

        # --- Secondary Appraisal (§1.2) ---

        # A — Agency: Can the agent do something about this?
        if event_type == "USER_MESSAGE":
            agency = 0.8  # Agent can respond
        else:
            agency = 0.3  # Limited control over system events

        # NA — Norm Alignment: Check content against identity boundaries
        norm_alignment = self._check_norm_alignment(
            event_content, identity_boundaries or []
        )

        # RI — Relationship Impact: Emotional tone → trust direction
        trust = state_snapshot.get("trust", 0.5)
        ri = emotional_bias * 0.5
        if trust < 0.3:
            ri *= 0.5  # Low trust dampens positive impact

        # Track content for novelty computation
        self._recent_contents.append(event_content[:100])
        if len(self._recent_contents) > self._max_recent:
            self._recent_contents = self._recent_contents[-self._max_recent :]

        vector = AppraisalVector(
            relevance=relevance,
            novelty=novelty,
            goal_congruence=goal_congruence,
            agency=agency,
            norm_alignment=norm_alignment,
            relationship_impact=ri,
        )

        logger.debug(
            "[Appraisal] R=%.2f N=%.2f G=%.2f A=%.2f NA=%.2f RI=%.2f",
            vector.relevance,
            vector.novelty,
            vector.goal_congruence,
            vector.agency,
            vector.norm_alignment,
            vector.relationship_impact,
        )
        return vector

    def _compute_novelty(self, content: str) -> float:
        """
        Simplified novelty via Jaccard distance against recent contents.
        N = 1 - max_overlap  (§1.1: N = 1 − max(cosine_sim(event, past)))
        """
        if not self._recent_contents:
            return 0.8  # First message is inherently novel

        content_words = set(content.lower().split())
        if not content_words:
            return 0.5

        max_overlap = 0.0
        for recent in self._recent_contents:
            recent_words = set(recent.lower().split())
            if not recent_words:
                continue
            intersection = content_words & recent_words
            union = content_words | recent_words
            overlap = len(intersection) / len(union) if union else 0.0
            max_overlap = max(max_overlap, overlap)

        return max(0.0, min(1.0, 1.0 - max_overlap))

    def _check_norm_alignment(self, content: str, boundaries: List[str]) -> float:
        """
        Check if content respects identity boundaries (§1.2 — Praiseworthiness / OCC).
        Returns 1.0 for full alignment, decreasing with violations.
        """
        if not boundaries:
            return 1.0

        content_lower = content.lower()
        violations = 0
        skip_words = {"not", "no", "don't", "never", "without", "isn't"}

        for boundary in boundaries:
            boundary_keywords = [
                w for w in boundary.lower().split() if w not in skip_words
            ]
            for kw in boundary_keywords:
                if len(kw) > 3 and kw in content_lower:
                    violations += 1

        if violations == 0:
            return 1.0
        return max(0.0, 1.0 - (violations * 0.2))

    async def appraise_semantic_drift(
        self,
        user_utterance: str,
        llm_client,
        current_pad: Dict[str, float]
    ) -> Dict[str, float]:
        """
        System 2 deliberative appraisal using LLM.
        Drifts target mood via primary/secondary appraisal analysis.
        """
        prompt = f"""
        Analyze the user's statement for deep appraisal dimensions:
        User statement: "{user_utterance}"
        
        Evaluate on a scale of -1.0 to 1.0:
        1. goal_congruence (Is this statement matching the friendly, helpful social goals? Positive if friendly, negative if hostile)
        2. norm_alignment (Does this align with social norms? 1.0 if perfectly polite, lower if offensive/toxic)
        3. expectedness (How expected is this statement? 1.0 if very standard, -1.0 if surprising)
        
        Output JSON ONLY:
        {{
          "goal_congruence": 0.0,
          "norm_alignment": 1.0,
          "expectedness": 0.5
        }}
        """.strip()
        
        try:
            from ..config import Config
            response = await llm_client.generate(prompt, model=Config.LLM_FAST_MODEL)
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                gc = float(data.get("goal_congruence", 0.0))
                na = float(data.get("norm_alignment", 1.0))
                exp = float(data.get("expectedness", 0.5))
                
                target_p = max(-1.0, min(1.0, gc))
                target_a = max(-1.0, min(1.0, 1.0 - abs(exp)))
                target_d = max(-1.0, min(1.0, na))
                
                drift_factor = 0.2
                new_p = current_pad.get("valence", 0.0) + drift_factor * (target_p - current_pad.get("valence", 0.0))
                new_a = current_pad.get("arousal", 0.5) + drift_factor * (target_a - current_pad.get("arousal", 0.5))
                new_d = current_pad.get("dominance", 0.5) + drift_factor * (target_d - current_pad.get("dominance", 0.5))
                
                return {
                    "valence": max(-1.0, min(1.0, new_p)),
                    "arousal": max(0.0, min(1.0, new_a)),
                    "dominance": max(0.0, min(1.0, new_d))
                }
        except Exception as e:
            logger.error(f"[System 2 Appraisal] Semantic drift evaluation failed: {e}")
        return current_pad
