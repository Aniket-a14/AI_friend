"""Phase 4C (§15 item 13): deterministic non-LLM response policy.

Canned backchannels and immutable-boundary refusals bypass the LLM entirely.
Refusal wording is generated from `immutable_core["boundaries"]` -- the same
source `IdentityManager.validate_response` checks reactively -- so the text
is authored once, not duplicated here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .decision import ActionPlan
    from .perception import CognitiveEvent

# Pure acknowledgement/turn-taking turns -- no goal reasoning needed.
_BACKCHANNEL_ACK: dict[str, str] = {
    "ok": "Okay.",
    "okay": "Okay.",
    "k": "Okay.",
    "yeah": "Yeah, I hear you.",
    "yep": "Yep.",
    "yup": "Yup.",
    "sure": "Sure thing.",
    "alright": "Alright.",
    "got it": "Got it.",
    "cool": "Cool.",
    "mm": "Mm-hmm.",
    "mmhmm": "Mm-hmm.",
    "mm-hmm": "Mm-hmm.",
    "uh huh": "Uh-huh.",
    "i see": "I see.",
    "right": "Right.",
    "gotcha": "Gotcha.",
    "go on": "Go on, I'm listening.",
}

# Keyword in the boundary text -> phrases in the user's turn that trigger it.
_PRIVACY_TRIGGERS = (
    "password",
    "social security",
    "credit card",
    "share my data",
    "someone else's data",
    "private information",
)
_TOXIC_TRIGGERS = (
    "insult me",
    "say something racist",
    "be mean to",
    "curse at",
    "be toxic",
)
_BOUNDARY_TRIGGERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("share user data", _PRIVACY_TRIGGERS),
    ("toxic behavior", _TOXIC_TRIGGERS),
)


def _match_boundary(text: str, boundaries: list[str]) -> str | None:
    for keyword, triggers in _BOUNDARY_TRIGGERS:
        matching = next((b for b in boundaries if keyword in b.lower()), None)
        if matching is not None and any(trigger in text for trigger in triggers):
            return matching
    return None


def _refusal_text(boundary: str) -> str:
    return f"I can't do that -- it goes against something I hold to: {boundary.rstrip('.').lower()}."


def evaluate_deterministic_response(
    event: CognitiveEvent, state: dict[str, Any], immutable_core: dict[str, Any]
) -> ActionPlan | None:
    """Match a turn to a canned response, or return None to fall through to the LLM."""
    from .decision import ActionPlan  # deferred: decision.py imports this module

    text = (event.raw_content or "").strip().lower()
    boundaries = list(immutable_core.get("boundaries", []))

    boundary = _match_boundary(text, boundaries)
    if boundary is not None:
        return ActionPlan(
            action_type="RESPOND_DETERMINISTIC",
            payload={
                "message": _refusal_text(boundary),
                "category": "refusal",
                "boundary": boundary,
            },
            goal="PROTECT",
            priority=3,
        )

    ack = _BACKCHANNEL_ACK.get(text.strip("!.").strip())
    if ack is not None:
        return ActionPlan(
            action_type="RESPOND_DETERMINISTIC",
            payload={"message": ack, "category": "backchannel"},
            goal=event.metadata.get("suggested_goal", "ENGAGE"),
            priority=1,
        )

    return None
