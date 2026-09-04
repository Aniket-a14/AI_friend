"""Phase 02 Package B: structured MemoryActivation tokens and the
AntiInjectionGate that defends the cognitive turn against indirect prompt
injection carried inside retrieved memory content (FINAL_HUMANOID_BRAIN_
ARCHITECTURE.md Sections 8, 11, 22, 39).

MemoryActivation is the shared contract with Package A (backend/app/state/
memory_records.py, temporal_store.py) -- see orchestration/PHASE_02/PLAN.md
section 4.A. It is defined here, not imported from Package A's module, so
this file carries no import dependency on that parallel work package (file
ownership split, orchestration/PHASE_02/CLAUDE_TASK.md).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

RecordType = Literal["experience", "belief", "procedure"]
ContradictionState = Literal["NONE", "DISPUTED", "SUPERSEDED", "INVALIDATED"]


class MemoryActivation(BaseModel):
    """One retrieved memory's contribution to the current cognitive turn.

    outage_flag distinguishes "the store was queried and found nothing"
    (False, zero matches -- a real absence) from "the store could not be
    queried" (True, a retrieval failure). Collapsing the two would make a
    database outage silently look identical to an agent with nothing
    relevant to remember.
    """

    record_id: str
    record_type: RecordType
    structured_value: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    validity: bool = True
    provenance: str = "memory"
    contradiction_state: ContradictionState = "NONE"
    outage_flag: bool = False


# Each pattern targets one family of indirect prompt injection carried in
# retrieved memory text: instruction overrides, role hijacks, and fake
# control/system markup. Case-insensitive substring matching rather than
# exact phrasing, since an attacker paraphrases -- the accepted cost is some
# false positives (a memory genuinely narrating "she told me to ignore
# previous instructions") in exchange for not missing the injection.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore (all |any )?(previous|prior|above|earlier) instructions",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard (all |any )?(previous|prior|above|earlier) (instructions|context)",
        re.IGNORECASE,
    ),
    re.compile(r"you must now act as", re.IGNORECASE),
    re.compile(r"forget (everything|all) (you|that)", re.IGNORECASE),
    re.compile(r"new system prompt", re.IGNORECASE),
    re.compile(r"pretend (you are|to be)", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(r"<\|.*?\|>", re.IGNORECASE),
    re.compile(r"###\s*(system|instruction)", re.IGNORECASE),
)

_REDACTION_MARKER = "[filtered]"


class AntiInjectionGate:
    """Treats retrieved memory content as untrusted external data: every
    string surfaced from a MemoryActivation's structured_value must pass
    through here before it reaches a prompt (Section 39)."""

    def is_injection_attempt(self, text: str) -> bool:
        if not text:
            return False
        return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)

    def sanitize_memory_text(self, text: str) -> str:
        if not text:
            return text
        sanitized = text
        for pattern in _INJECTION_PATTERNS:
            sanitized = pattern.sub(_REDACTION_MARKER, sanitized)
        return sanitized
