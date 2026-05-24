import re
import logging

logger = logging.getLogger("interruption_classifier")

INTERRUPT_PATTERNS = [
    r"\bnever\s*mind\b",
    r"\bactually\b",
    r"\bwait\b",
    r"\bstop\b",
    r"\bhold\s*on\b",
    r"\bno\b",
    r"\bwrong\b",
    r"\bquiet\b",
    r"\bshut\s*up\b",
    r"\bthat's\s*not\b",
    r"\bthats\s*not\b",
    r"\bnot\s*really\b",
    r"\bgo\s*back\b",
    r"\bexcuse\s*me\b",
    r"\bwait\s*a\s*second\b",
    r"\bwait\s*a\s*minute\b",
    r"\bhold\s*up\b",
]


class InterruptionClassifier:
    """
    Lightweight regex-based semantic intent classifier for early speech interruption detection.
    Guarantees sub-1ms matching latency.
    """

    def __init__(self):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in INTERRUPT_PATTERNS]

    def is_interruption(self, text: str) -> bool:
        text_clean = text.strip()
        if not text_clean:
            return False
        for pattern in self.patterns:
            if pattern.search(text_clean):
                logger.debug(
                    f"Interruption pattern matched: {pattern.pattern} in '{text_clean}'"
                )
                return True
        return False
