import logging

logger = logging.getLogger(__name__)


class HybridSegmenter:
    """
    AI Friend Semantic Chunking Logic.
    Uses punctuation cues and target chunk sizes to find natural speech boundaries.
    """

    def __init__(self, target_size: int = 8):
        self.target_size = target_size

    def score_split_point(self, word: str, chunk_len: int) -> float:
        """
        Calculates the probability [0, 1] that a word is a good segment boundary.
        §4.1: Goldman-Eisler — Linguistic juncture markers.
        """
        score = 0.0
        # Punctuation is the strongest cue
        if word:
            # Inline character checks to completely avoid generator allocation overhead
            if "." in word or "?" in word or "!" in word:
                score += 0.8
            elif "," in word or ":" in word or ";" in word:
                score += 0.4

        # Length-based pressure
        if chunk_len >= self.target_size:
            score += 0.3

        # Extreme length override
        if chunk_len > 12:
            score = 1.0

        return score
