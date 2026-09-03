"""Phase 5C (§14 MODIFY, PLAN §5C): reviewable/rollbackable reflection proposals.

`ReflectionService._consolidate_persona` used to apply every persona
suggestion straight to `IdentityManager` (auto-apply). When
`Config.LEARNING_REVIEW_REQUIRED` is True, suggestions land in this queue
instead and wait for an explicit `approve()`/`reject()` call.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .identity import IdentityManager


class LearningProposal(BaseModel):
    """A pending persona-evolution suggestion, not yet applied."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "reflection"
    suggestions: dict[str, Any]
    speaker: str | None = None
    # Phase 2C fields, reused: set when the suggestion conflicts with an
    # existing confirmed memory found via MemoryStore.find_contradiction.
    record_type: str = "reflection_proposal"
    contradicts_id: str | None = None

    @property
    def is_contradiction(self) -> bool:
        return self.contradicts_id is not None


class LearningReviewQueue:
    """In-memory pending-proposal queue -- one per running agent process."""

    def __init__(self) -> None:
        self._pending: list[LearningProposal] = []

    def submit(
        self,
        suggestions: dict[str, Any],
        source: str = "reflection",
        speaker: str | None = None,
        contradicts_id: str | None = None,
    ) -> LearningProposal:
        proposal = LearningProposal(
            suggestions=suggestions,
            source=source,
            speaker=speaker,
            contradicts_id=contradicts_id,
        )
        self._pending.append(proposal)
        return proposal

    def pending(self) -> list[LearningProposal]:
        return list(self._pending)

    def contradictions(self) -> list[LearningProposal]:
        return [p for p in self._pending if p.is_contradiction]

    def _pop(self, proposal_id: str) -> LearningProposal | None:
        for i, p in enumerate(self._pending):
            if p.id == proposal_id:
                return self._pending.pop(i)
        return None

    async def approve(
        self, proposal_id: str, identity_manager: IdentityManager
    ) -> LearningProposal | None:
        """Apply a reviewed proposal via the identity manager's own evolution path."""
        proposal = self._pop(proposal_id)
        if proposal is None:
            return None
        # Stamped before evolve_persona() so its own save()/persist_to_config_store() carries it.
        identity_manager.history["evolved_learnings"] = (
            f"{proposal.created_at}: {proposal.suggestions}"
        )
        await identity_manager.evolve_persona(proposal.suggestions)
        return proposal

    def reject(self, proposal_id: str) -> LearningProposal | None:
        return self._pop(proposal_id)
