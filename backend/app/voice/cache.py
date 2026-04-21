import logging
from collections import deque
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class AudioCache:
    """
    Multidimensional Stylistic Cache.
    Key: (text, emotion_hash, rate).
    Supports Near-Neighbor Reuse.
    """
    def __init__(self, max_size=200):
        self.cache = {}
        self.order = deque()
        self.max_size = max_size

    def _get_key(self, text: str, rate: float, pitch: float) -> Tuple[str, float, float]:
        # Normalize text for robustness
        norm_text = "".join(e for e in text.lower() if e.isalnum() or e.isspace()).strip()
        return (norm_text, round(rate, 2), round(pitch, 2))

    def get(self, text: str, rate: float, pitch: float) -> Optional[bytes]:
        key = self._get_key(text, rate, pitch)
        if key in self.cache:
            self.order.remove(key)
            self.order.append(key)
            return self.cache[key]
        
        # Stylistic Near-Neighbor Match (V2.6)
        norm_text = key[0]
        for c_key in self.cache:
            if c_key[0] == norm_text:
                if abs(c_key[1] - rate) < 0.1 and abs(c_key[2] - pitch) < 0.1:
                    logger.info(f"🎯 Cache Near-Neighbor Hit: {text} (Rate: {c_key[1]}, Pitch: {c_key[2]})")
                    return self.cache[c_key]
        return None

    def set(self, text: str, rate: float, pitch: float, audio: bytes):
        key = self._get_key(text, rate, pitch)
        if key in self.cache:
            self.order.remove(key)
        elif len(self.cache) >= self.max_size:
            oldest = self.order.popleft()
            del self.cache[oldest]
        
        self.cache[key] = audio
        self.order.append(key)
