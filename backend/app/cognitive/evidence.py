"""Evidence (§15 item 1): a typed unit of "what the agent currently knows
this from," carrying modality, confidence, and provenance alongside content.

Today's `brain_agent.last_visual_context` is a plain string overwritten on
every vision event -- once a VLM description arrives, there is no way to
distinguish "just observed, high confidence" from "last seen a while ago,
maybe stale," and `action.py::_build_visual_context` has no basis to render
that distinction even if it wanted to. `Evidence` is additive: it exists
alongside the string context, not instead of it, so nothing that already
reads `last_visual_context` breaks.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Modality = Literal["vision", "audio", "text", "memory"]


class Evidence(BaseModel):
    """One piece of grounding for a cognitive turn: what was perceived or
    recalled, where it came from, and how much to trust it."""

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    source: str
    modality: Modality
    timestamp: float = Field(default_factory=time.time)
    confidence: float = 1.0
    provenance: str = ""
    # Wall-clock time after which this evidence should no longer be treated
    # as current (e.g. a visual observation going stale). None means it
    # doesn't expire on its own -- the caller decides staleness some other
    # way (e.g. comparing against `timestamp` directly, as the visual
    # context renderer does).
    expiry: float | None = None

    def is_expired(self, now: float | None = None) -> bool:
        if self.expiry is None:
            return False
        return (now if now is not None else time.time()) >= self.expiry

    @classmethod
    def from_surfaced_memory(cls, mem: Any) -> Evidence:
        """Adapt a `contracts.SurfacedMemory` into `Evidence`. Takes `Any`
        rather than importing `SurfacedMemory` to avoid a
        `cognitive` -> `contracts` -> ... import cycle risk; the attributes
        read here (`content`, `score`, `created_at`, `metadata`) are exactly
        `SurfacedMemory`'s own fields."""
        created_at = getattr(mem, "created_at", None)
        timestamp = time.time()
        if created_at:
            try:
                timestamp = time.mktime(time.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S"))
            except (ValueError, TypeError):
                pass
        score = getattr(mem, "score", 1.0) or 0.0
        metadata = getattr(mem, "metadata", None) or {}
        return cls(
            content=getattr(mem, "content", ""),
            source=str(metadata.get("provenance", "memory_store")),
            modality="memory",
            timestamp=timestamp,
            confidence=max(0.0, min(1.0, score)),
            provenance="memory_store",
        )
