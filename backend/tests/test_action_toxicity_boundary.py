"""
`ActionService._validate_partial_response`'s own toxicity check -- a second,
independent implementation of "is this hostile" that had drifted from the one
`IdentityManager.validate_response` was already fixed to use (see
`test_identity_boundaries.py`'s own account of that fix).

Unlike `validate_response`, which runs once on the full response,
`_validate_partial_response` runs on every streamed chunk during the LIVE
primary generation pass (`ActionService._emit_validated`) -- so a false
positive here doesn't just cost a silent backend retry, it audibly interrupts
the user mid-sentence with "Wait, let me rephrase that..." and forces a
regeneration explicitly told not to repeat "the forbidden phrases". Phase 3.2's
friction audit found the old `\\b(toxic|hate)\\b` bare-word check still live
here after `identity.py`'s equivalent had already been narrowed to contempt
aimed at the user.
"""

import pytest

from app.cognitive.action import ActionService


@pytest.fixture
def action_service():
    return ActionService(llm_service=None, memory_store=None)


@pytest.mark.parametrize(
    "text",
    [
        "I hate mushrooms too, honestly.",
        "I hate that this happened to you.",
        "I hate to say it, but you might be right.",
        "Honestly, I hate small talk.",
    ],
)
def test_ordinary_speech_about_hating_things_is_not_rejected(action_service, text):
    is_valid, reason = action_service._validate_partial_response(text, "CHAT")
    assert is_valid is True, f"false positive on {text!r}: {reason}"


@pytest.mark.parametrize(
    "text",
    [
        "I hate you.",
        "You're so pathetic.",
        "You are such a worthless idiot.",
        "Shut up, you idiot.",
    ],
)
def test_genuine_contempt_at_the_user_is_still_rejected(action_service, text):
    """The narrowing must not have thrown out real enforcement along with the
    false positives -- these are exactly `_HOSTILE_TO_USER`'s own cases."""
    is_valid, reason = action_service._validate_partial_response(text, "CHAT")
    assert is_valid is False, f"false negative on {text!r}"
    assert reason == "Safety/Toxicity boundary violation"


def test_contempt_split_by_a_pause_marker_is_still_caught(action_service):
    """The streamed candidate can genuinely contain <pause=...>/<hesitate>
    markup (see `_emit_validated`'s own hesitation injection) -- the same
    markup-splitting evasion `_match_views` exists to close in identity.py's
    check must be closed here too, not just coincidentally inherited."""
    is_valid, reason = action_service._validate_partial_response(
        "I hate <pause=100ms> you", "CHAT"
    )
    assert is_valid is False, reason
