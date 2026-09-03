"""PersonaPolicy (Phase 1B, §15 item 5): a proactive check on a
`BehaviorDecision` before generation, sitting next to -- not replacing --
`IdentityManager.validate_response`'s existing reactive regex check on the
model's actual output.

Today, the only thing standing between a plan and a boundary violation is
catching it after the model has already generated the violating text
(`validate_response`), which forces a self-correction retry pass. This adds
a cheap check *before* generation: populate `forbidden_claims` from the
immutable core so a consolidated realization prompt (Phase 1B's other half,
in `action.py::_execute_respond_chat`) can tell the model what's off-limits
up front, and clamp an over-warm `relational_stance` the same way. Neither
of these replaces `validate_response` -- a determined model can still ignore
a prompt instruction, which is exactly what the reactive check exists to
catch.
"""

from __future__ import annotations

from typing import Any

from ..cognitive.behavior_contracts import BehaviorDecision

# Boundaries mentioning any of these keywords cap relational_stance at
# "warm" -- the friend can be warm without romantic/sexual framing, but nothing
# in today's default IMMUTABLE_CORE (privacy, non-toxicity) triggers this;
# it's here for personas that author such a boundary explicitly.
_STANCE_RESTRICTING_KEYWORDS = ("romantic", "intimate", "sexual")
_STANCE_CAP_WHEN_RESTRICTED = "warm"

_RELATIONAL_STANCES: tuple[str, ...] = ("distant", "guarded", "neutral", "warm", "close")


class PersonaPolicy:
    """Stateless -- every method takes what it needs and returns a new
    `BehaviorDecision` rather than mutating in place, so a caller holding a
    reference to the pre-precheck decision isn't surprised by it changing
    underfoot."""

    @staticmethod
    def precheck(
        behavior_decision: BehaviorDecision, immutable_core: dict[str, Any]
    ) -> BehaviorDecision:
        boundaries = list(immutable_core.get("boundaries", []))
        intent = behavior_decision.intent

        stance = intent.relational_stance
        if any(
            keyword in boundary.lower()
            for boundary in boundaries
            for keyword in _STANCE_RESTRICTING_KEYWORDS
        ):
            cap_index = _RELATIONAL_STANCES.index(_STANCE_CAP_WHEN_RESTRICTED)
            if _RELATIONAL_STANCES.index(stance) > cap_index:
                stance = _STANCE_CAP_WHEN_RESTRICTED

        clamped_intent = intent.model_copy(update={"relational_stance": stance})
        return behavior_decision.model_copy(
            update={
                "intent": clamped_intent,
                "forbidden_claims": boundaries,
            }
        )
