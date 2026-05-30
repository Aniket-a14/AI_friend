from typing import List, Dict, Any
from ..contracts import ChatOutput, ChatOutputAffect


class SpeechCoordinator:
    """
    Coordinates text-to-speech chunking and prosody mapping.
    Maps emotional state to speaking rate, intensity, and pause bias.
    """

    def __init__(self, segmenter, formation_buffer_ms: float = 0.030):
        self.segmenter = segmenter
        self.formation_buffer_ms = formation_buffer_ms

    def map_affect_to_prosody(self, state_snap: Dict[str, Any]) -> Dict[str, float]:
        """§5.1: Continuous PAD-to-prosody formulas."""
        V = state_snap.get("valence", state_snap.get("mood", 0.0))
        Ar = state_snap.get("arousal", state_snap.get("energy", 0.5))
        F = state_snap.get("fatigue", 0.0)

        # Continuous formulas from CVS-3.5 Roadmap:
        # Sr = 1.0 + (0.20 * arousal) - (0.10 * valence) - (0.25 * fatigue)
        speaking_rate = max(0.6, min(1.8, 1.0 + (0.20 * Ar) - (0.10 * V) - (0.25 * F)))
        confidence = 0.9  # Baseline
        intensity = abs(V) * Ar
        # pause_bias = 1.0 - arousal
        pause_bias = max(0.0, min(1.0, 1.0 - Ar))

        return {
            "speaking_rate": round(speaking_rate, 3),
            "intensity": round(intensity, 3),
            "pause_bias": round(pause_bias, 3),
            "confidence": confidence,
        }

    def create_chunk_payload(
        self,
        words: List[str] = None,
        state_snap: Dict[str, Any] = None,
        turn_id: str = None,
        done: bool = False,
        full_response: str = None,
        generation_error: str = None,
        proactive: bool = False,
        user_distance: float = None,
    ) -> ChatOutput:
        text = " ".join(words).strip() if words else None
        prosody = self.map_affect_to_prosody(state_snap or {})

        return ChatOutput(
            content=text,
            done=done,
            turn_id=turn_id,
            confidence=prosody["confidence"],
            intensity=prosody["intensity"],
            speaking_rate=prosody["speaking_rate"],
            pause_bias=prosody["pause_bias"],
            full_response=full_response,
            generation_error=generation_error,
            proactive=proactive,
            affect=ChatOutputAffect(
                valence=state_snap.get("valence", state_snap.get("mood", 0.0))
                if state_snap
                else 0.0,
                arousal=state_snap.get("arousal", state_snap.get("energy", 0.5))
                if state_snap
                else 0.5,
                dominance=state_snap.get("dominance", 0.5) if state_snap else 0.5,
                trust=state_snap.get("trust", 0.5) if state_snap else 0.5,
                attachment=state_snap.get("attachment", 0.1) if state_snap else 0.1,
                emotion=state_snap.get("emotion", "neutral")
                if state_snap
                else "neutral",
                fatigue=state_snap.get("fatigue", 0.0) if state_snap else 0.0,
                user_distance=user_distance,
            ),
        )
