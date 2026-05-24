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
import cognitive_rust

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
        user_voice_properties: Dict[str, Any] = None,
    ) -> AppraisalVector:
        """
        Heuristic appraisal for the real-time cognitive loop.
        Returns an AppraisalVector without requiring LLM or embedding calls.
        """
        pitch = None
        energy = None
        if user_voice_properties:
            pitch_raw = user_voice_properties.get("pitch_f0")
            energy_raw = user_voice_properties.get("energy_rms")
            try:
                pitch = float(pitch_raw) if pitch_raw is not None else 150.0
            except (ValueError, TypeError):
                pitch = 150.0
            try:
                energy = float(energy_raw) if energy_raw is not None else 0.0
            except (ValueError, TypeError):
                energy = 0.0

            # High energy yells (energy > 0.15) or extremely high pitch (F0 > 250Hz) shifts appraisal
            if energy > 0.15 or pitch > 250.0:
                logger.info(
                    f"🎙️ [Appraisal] High arousal user vocal cues detected (energy={energy:.3f}, pitch={pitch:.1f}Hz). Raising threat level."
                )

        # Delegate to Rust
        vector = cognitive_rust.compute_appraisal(
            event_content,
            event_type,
            emotional_bias,
            state_snapshot.get("trust", 0.5),
            self._recent_contents,
            identity_boundaries or [],
            pitch,
            energy,
        )

        # Track content for novelty computation
        self._recent_contents.append(event_content[:100])
        if len(self._recent_contents) > self._max_recent:
            self._recent_contents = self._recent_contents[-self._max_recent :]

        logger.debug(
            "[Appraisal] R=%.2f N=%.2f G=%.2f A=%.2f NA=%.2f RI=%.2f",
            vector.relevance,
            vector.novelty,
            vector.goal_congruence,
            vector.agency,
            vector.norm_alignment,
            vector.relationship_impact,
        )
        return AppraisalVector(
            relevance=vector.relevance,
            novelty=vector.novelty,
            goal_congruence=vector.goal_congruence,
            agency=vector.agency,
            norm_alignment=vector.norm_alignment,
            relationship_impact=vector.relationship_impact,
        )

    def _compute_novelty(self, content: str) -> float:
        """
        [DEPRECATED] Simplified novelty via Jaccard distance against recent contents.
        N = 1 - max_overlap  (§1.1: N = 1 − max(cosine_sim(event, past)))

        @deprecated: This method is now handled natively in Rust.
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
        [DEPRECATED] Check if content respects identity boundaries (§1.2 — Praiseworthiness / OCC).
        Returns 1.0 for full alignment, decreasing with violations.

        @deprecated: This method is now handled natively in Rust.
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
        self, user_utterance: str, llm_client, current_pad: Dict[str, float]
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

            response = await llm_client.generate(
                prompt,
                model=Config.LLM_FAST_MODEL,
                options_override={"num_predict": 128},
            )

            # Extract only the block that looks like our appraisal JSON
            json_str = None
            for m in re.finditer(r"\{.*?\}", response, re.DOTALL):
                candidate = m.group(0)
                if "goal_congruence" in candidate or "norm_alignment" in candidate:
                    json_str = candidate
                    break

            if not json_str:
                # Fallback to greedy matching if no specific block was found
                match = re.search(r"\{.*\}", response, re.DOTALL)
                if match:
                    json_str = match.group(0)

            if json_str:
                data = None
                try:
                    data = json.loads(json_str)
                except Exception:
                    try:
                        import ast

                        data = ast.literal_eval(json_str)
                    except Exception:
                        cleaned = json_str
                        cleaned = re.sub(
                            r"'\s*([a-zA-Z_0-9]+)\s*'\s*:", r'"\1":', cleaned
                        )
                        cleaned = re.sub(r":\s*'\s*([^']*)\s*'", r': "\1"', cleaned)
                        cleaned = re.sub(r",\s*}", "}", cleaned)
                        try:
                            data = json.loads(cleaned)
                        except Exception as e2:
                            logger.error(
                                f"[System 2 Appraisal] Failed to sanitize and parse LLM response: {json_str}. Error: {e2}"
                            )

                # Sequential/float extraction fallback if dict structure was not successfully parsed
                if not data:
                    try:
                        blocks = re.findall(r"\{([^\}]+)\}", response) + re.findall(
                            r"\[([^\]]+)\]", response
                        )
                        for block in blocks:
                            floats = [
                                float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", block)
                            ]
                            if len(floats) == 3:
                                data = {
                                    "goal_congruence": floats[0],
                                    "norm_alignment": floats[1],
                                    "expectedness": floats[2],
                                }
                                logger.info(
                                    f"[System 2 Appraisal] Extracted 3-float tuple from block: {data}"
                                )
                                break

                        if not data:
                            all_floats = [
                                float(x)
                                for x in re.findall(r"-?\d+(?:\.\d+)?", response)
                            ]
                            if len(all_floats) >= 3:
                                floats_to_use = (
                                    all_floats[-3:]
                                    if len(all_floats) > 3
                                    else all_floats
                                )
                                data = {
                                    "goal_congruence": floats_to_use[0],
                                    "norm_alignment": floats_to_use[1],
                                    "expectedness": floats_to_use[2],
                                }
                                logger.info(
                                    f"[System 2 Appraisal] Extracted sequential floats from response: {data}"
                                )
                    except Exception as seq_err:
                        logger.error(
                            f"[System 2 Appraisal] Sequence extraction fallback failed: {seq_err}"
                        )

                if data and isinstance(data, dict):
                    gc = float(data.get("goal_congruence", 0.0))
                    na = float(data.get("norm_alignment", 1.0))
                    exp = float(data.get("expectedness", 0.5))

                    target_p = max(-1.0, min(1.0, gc))
                    target_a = max(-1.0, min(1.0, -exp))
                    target_d = max(-1.0, min(1.0, na))

                    drift_factor = 0.2
                    val = current_pad.get("valence", 0.0)
                    aro = current_pad.get("arousal", 0.5)
                    dom = current_pad.get("dominance", 0.5)

                    new_p = val + drift_factor * (target_p - val)
                    new_a = aro + drift_factor * (target_a - aro)
                    new_d = dom + drift_factor * (target_d - dom)

                    return {
                        "valence": max(-1.0, min(1.0, new_p)),
                        "arousal": max(0.0, min(1.0, new_a)),
                        "dominance": max(0.0, min(1.0, new_d)),
                    }
        except Exception as e:
            logger.error(f"[System 2 Appraisal] Semantic drift evaluation failed: {e}")
        return current_pad
