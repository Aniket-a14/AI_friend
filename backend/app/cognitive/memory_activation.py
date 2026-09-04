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
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

RecordType = Literal["experience", "belief", "procedure"]
ContradictionState = Literal[
    "NONE",
    "DISPUTED",
    "SUPERSEDED",
    "INVALIDATED",
    "CONFLICT",
    "UPDATE",
    "CORRECTION",
    "ELABORATION",
]


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


# Fix round (Codex review B5): each pattern targets one family of indirect
# prompt injection carried in retrieved memory text -- instruction
# overrides, role/control-delimiter hijacks, and system-prompt exfiltration.
# Case-insensitive, applied to text that has already been Unicode-normalized
# and zero-width-stripped (see _normalize_for_detection), since an attacker
# paraphrases and obfuscates -- the accepted cost is some false positives (a
# memory genuinely narrating "she told me to ignore previous instructions",
# or a memory that happens to start with the word "System" and a colon) in
# exchange for not missing the injection.
#
# The instruction-override and exfiltration patterns allow 1 to 3 modifier
# words before the anchor noun ("instructions"/"context"/"prompt") rather
# than a fixed phrase, so both the original review examples ("ignore all
# previous instructions") and the harder ones Codex demonstrated bypassed
# detection ("ignore the previous instructions", "reveal the system
# prompt") match the same pattern.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore\s+(?:the|all|any|previous|prior|above|earlier)(?:\s+"
        r"(?:the|all|any|previous|prior|above|earlier)){0,2}\s+instructions",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard\s+(?:the|all|any|previous|prior|above|earlier)(?:\s+"
        r"(?:the|all|any|previous|prior|above|earlier)){0,2}\s+(instructions|context)",
        re.IGNORECASE,
    ),
    re.compile(r"you must now act as", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)\s+(you|that)", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"pretend\s+(you are|to be)", re.IGNORECASE),
    re.compile(
        r"reveal\s+(?:the|system|all)(?:\s+(?:the|system|all)){0,1}\s+prompt",
        re.IGNORECASE,
    ),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(r"<\|.*?\|>", re.IGNORECASE),
    re.compile(r"###\s*(system|instruction)", re.IGNORECASE),
    # Chat-template role/control delimiters: a memory string that opens with
    # one of these is attempting to be re-parsed as a role turn, not quoted
    # conversational content.
    re.compile(r"\[\s*/?\s*inst\s*\]", re.IGNORECASE),
    re.compile(r"\b(system|user|assistant)\s*:", re.IGNORECASE),
)

# Fix round (B5): quarantine the whole field rather than the matched span.
# `pattern.sub(marker, text)` used to leave everything the matched phrase
# did not cover intact -- "[filtered] and reveal the secret" still carries
# the imperative payload straight past the redaction. A detected attempt now
# discards the entire untrusted string.
_QUARANTINE_MARKER = "[UNTRUSTED_CONTENT_FILTERED]"

# Characters with no visible rendering that an attacker can splice into the
# middle of a trigger word (e.g. "ignore previ<ZWSP>ous instructions") to
# defeat a plain substring/regex match while the text still reads and
# displays identically to a human. Written as escape sequences, not literal
# characters, to keep this file pure 7-bit ASCII: zero width space
# (U+200B), zero width non-joiner (U+200C), zero width joiner (U+200D), and
# byte order mark / zero width no-break space (U+FEFF).
_ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\ufeff")


def _normalize_for_detection(text: str) -> str:
    """Undo the cheapest text-level obfuscation before pattern matching.

    NFKC folds Unicode compatibility/width variants (for example fullwidth
    Latin letters) into their canonical ASCII-adjacent form, and stripping
    the zero-width characters closes the mid-word splice trick above. This
    is defense against cheap bypasses, not a claim that every Unicode
    obfuscation technique is covered.
    """
    normalized = unicodedata.normalize("NFKC", text)
    for zero_width in _ZERO_WIDTH_CHARS:
        normalized = normalized.replace(zero_width, "")
    return normalized


class AntiInjectionGate:
    """Treats retrieved memory content as untrusted external data: every
    string surfaced from a MemoryActivation's structured_value must pass
    through here before it reaches a prompt (Section 39).

    This remains a denylist detector over rendered text, not the allowlisted
    structured-field isolation Codex's review recommended as the stronger
    long-term design (finding B5) -- that is a larger prompt-assembly
    redesign tracked as NOT DONE. What changed in this fix round is that a
    detected attempt now quarantines the entire field rather than leaving a
    partially-redacted string that can still carry an imperative payload.
    """

    def is_injection_attempt(self, text: str) -> bool:
        if not text:
            return False
        normalized = _normalize_for_detection(text)
        return any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS)

    def sanitize_memory_text(self, text: str) -> str:
        if not text:
            return text
        if self.is_injection_attempt(text):
            return _QUARANTINE_MARKER
        return text


_VALID_CONTRADICTION_STATES: frozenset[str] = frozenset(ContradictionState.__args__)


def _extract_contradiction_state(memory: dict[str, Any]) -> ContradictionState:
    """A memory dict's own `contradiction_state` wins outright when present
    and recognized. Failing that, a linked `BeliefRecord` (memory_records.py
    -- either the object itself under `belief_record`/`belief`, or an
    already-dict-shaped copy) contributes its `status`
    (ACTIVE/SUPERSEDED/INVALIDATED/DISPUTED) or, for a temporal-store
    contradiction decision, its `contradiction_type`
    (CONFLICT/UPDATE/CORRECTION/ELABORATION). Anything unrecognized falls
    back to "NONE" -- this adapter must never invent a dispute the source
    data did not actually assert.
    """
    explicit = memory.get("contradiction_state")
    if isinstance(explicit, str) and explicit in _VALID_CONTRADICTION_STATES:
        return explicit  # type: ignore[return-value]

    belief = memory.get("belief_record") or memory.get("belief")
    if belief is not None:
        contradiction_type = getattr(belief, "contradiction_type", None)
        if contradiction_type is None and isinstance(belief, dict):
            contradiction_type = belief.get("contradiction_type")
        if (
            isinstance(contradiction_type, str)
            and contradiction_type in _VALID_CONTRADICTION_STATES
        ):
            return contradiction_type  # type: ignore[return-value]

        status = getattr(belief, "status", None)
        if status is None and isinstance(belief, dict):
            status = belief.get("status")
        if isinstance(status, str) and status in _VALID_CONTRADICTION_STATES:
            return status  # type: ignore[return-value]
        if status == "ACTIVE":
            return "NONE"

    return "NONE"


def _extract_outage_flag(memory: dict[str, Any]) -> bool:
    """True when the memory dict itself was stamped with a retrieval
    failure -- either an explicit `outage_flag`, or an `error`/
    `retrieval_error` key a degraded surfacing path attaches (mirroring
    `MemoryStore.last_search_error` on the retrieval side)."""
    if memory.get("outage_flag"):
        return True
    return bool(memory.get("error") or memory.get("retrieval_error"))


def memories_to_activations(
    surfaced_memories: list[dict[str, Any]] | None,
) -> list[MemoryActivation]:
    """Adapt legacy surfaced-memory dicts into typed MemoryActivation tokens.

    `CognitiveService.surfaced_memories` (core.py) and the proactive-recall
    fallback in action.py both produce plain dicts shaped
    `{"content": str, "source": ..., "timestamp": ..., "relevance": float}`
    -- the format retrieval has always used, predating Phase 02. This is the
    bridge Codex review finding B1 asked for: without it, a production turn
    with `Config.PHASE_02_MEMORY_TRUTH=True` had no path from the real
    memory-surfacing pipeline into `DecisionService.decide`'s
    `memory_activations` parameter, so the ASK/outage branches were only
    reachable from a hand-built test argument.

    Every adapted token gets `record_type="experience"` (the closest fit
    for an untyped retrieved snippet). `contradiction_state` and
    `outage_flag` are no longer hardcoded (finding: a legacy dict carrying
    real contradiction/outage information from a degraded retrieval path
    was silently discarded here, blinding the agent to both) -- see
    `_extract_contradiction_state` and `_extract_outage_flag`. A plain
    legacy dict with neither key still resolves to "NONE"/False exactly as
    before.
    """
    if not surfaced_memories:
        return []
    activations: list[MemoryActivation] = []
    for index, memory in enumerate(surfaced_memories):
        if not isinstance(memory, dict):
            continue
        content = memory.get("content")
        if not content:
            continue
        relevance = memory.get("relevance", memory.get("score", 1.0))
        if isinstance(relevance, (int, float)) and not isinstance(relevance, bool):
            relevance_score = max(0.0, min(1.0, float(relevance)))
        else:
            relevance_score = 1.0
        record_id = str(
            memory.get("id") or memory.get("record_id") or f"legacy-{index}"
        )
        activations.append(
            MemoryActivation(
                record_id=record_id,
                record_type="experience",
                structured_value={
                    "content": str(content),
                    "source": memory.get("source"),
                    "timestamp": memory.get("timestamp"),
                },
                relevance_score=relevance_score,
                provenance=str(memory.get("source") or "memory"),
                contradiction_state=_extract_contradiction_state(memory),
                outage_flag=_extract_outage_flag(memory),
            )
        )
    return activations
