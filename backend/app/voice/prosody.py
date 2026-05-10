"""
Voice Prosody Mapping — CVS-1.0

Maps Valence-Arousal-Dominance (VAD) vectors from the cognitive layer
to physical speech synthesis parameters (rate, pitch, volume).
Based on Scherer's Vocal Expression predictions.
"""

import re
from typing import Dict, List


def vad_to_prosody(affect: Dict[str, float]) -> Dict[str, float]:
    """
    Maps Valence, Arousal, Dominance (VAD) to SoVITS inference parameters.
    Follows Scherer's Vocal Expression predictions (Psychological Layer V2.1).
    """
    v = affect.get("valence", 0.5)
    a = affect.get("arousal", 0.5)
    d = affect.get("dominance", 0.5)

    # 1. Speed (Arousal based) — High arousal = faster speech
    rate = 1.0 + (a - 0.5) * 0.8  # Range [0.6, 1.4]

    # 2. Pitch (Valence and Arousal based)
    pitch = 1.0 + (a - 0.5) * 0.5 + (v - 0.5) * 0.2

    # 3. Volume (Dominance based)
    volume = 0.5 + d * 0.5

    return {
        "rate": round(rate, 2),
        "pitch": round(pitch, 2),
        "volume": round(volume, 2),
        "pause_bias": 1.0 - a,  # High arousal = shorter pauses
    }


def has_temporal_marker(text: str) -> bool:
    """Check if text contains <pause=Nms> or <hesitate> control markers."""
    return bool(re.search(r"(<pause=\d+ms>|<hesitate>)", text))


def force_split(text: str, max_words: int = 8) -> List[str]:
    """Split long text into max_words-sized chunks for synthesis."""
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]
