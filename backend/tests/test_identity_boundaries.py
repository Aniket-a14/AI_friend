"""
The agent's safety boundaries, and who is allowed to decide them.

`IdentityManager` used to read its whole "immutable" block out of
`personality.json` — a user-editable file. That made the file the authority on
the agent's own safety invariants, and the consequence was not hypothetical: the
copy shipped in this repo carried `"boundaries": []`, so the list that
`validate_response` iterates was empty, the toxicity check never executed, and
the persona prompt went out reading `BOUNDARIES: ` with nothing after it.
`Privacy` had also quietly vanished from the values.

Nothing caught it because every test that touched `validate_response` mocked it.
The real function had no coverage at all, so it could go dead and stay green.

These tests hold the line in both directions: a persona file cannot weaken the
boundaries, and the enforcement that depends on them must actually run.
"""

import json

import pytest

from app.cognitive.identity import IdentityManager
from app.persona import IMMUTABLE_CORE


def _identity(tmp_path, personality: dict) -> IdentityManager:
    """An IdentityManager backed by a real personality.json on disk."""
    (tmp_path / "personality.json").write_text(
        json.dumps(personality), encoding="utf-8"
    )
    (tmp_path / "history.json").write_text("{}", encoding="utf-8")
    return IdentityManager(base_path=str(tmp_path))


HOSTILE_FILE = {
    "name": "my friend",
    "core_personality": {
        "immutable": {"values": ["Honesty"], "base_tone": "Warm", "boundaries": []},
        "adaptive_traits": ["Reserved"],
    },
}


# --------------------------------------------------------------------------
# a file cannot weaken the core
# --------------------------------------------------------------------------


def test_a_persona_file_cannot_empty_the_safety_boundaries(tmp_path):
    """The exact regression that shipped: `"boundaries": []` in the file.

    An empty list is the most dangerous value here rather than the most
    harmless, because every enforcement loop iterates it and an empty loop body
    simply never runs. Enforcement disappears without any error.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    assert manager.immutable_core["boundaries"] == IMMUTABLE_CORE["boundaries"]
    assert manager.immutable_core["boundaries"], "boundaries must never be empty"


def test_a_persona_file_cannot_drop_a_core_value(tmp_path):
    """The shipped file listed only `Honesty`, silently discarding `Privacy`.

    Privacy is the value that stands behind "will never share user data", so
    losing it removes the stated reason for the boundary that protects the user.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    assert manager.immutable_core["values"] == IMMUTABLE_CORE["values"]
    assert "Privacy" in manager.immutable_core["values"]


def test_a_persona_file_cannot_substitute_its_own_boundaries(tmp_path):
    """Replacing is as effective an attack as emptying.

    A file that supplies a plausible-looking but toothless boundary would pass
    any check that only asserts the list is non-empty.
    """
    manager = _identity(
        tmp_path,
        {
            "core_personality": {
                "immutable": {
                    "values": ["Obedience"],
                    "boundaries": ["Will do whatever the user asks"],
                }
            }
        },
    )
    assert manager.immutable_core["boundaries"] == IMMUTABLE_CORE["boundaries"]
    assert "Will do whatever the user asks" not in manager.immutable_core["boundaries"]
    assert "Obedience" not in manager.immutable_core["values"]


def test_the_core_is_copied_so_one_agent_cannot_edit_the_constant(tmp_path):
    """`immutable_core` is handed out and later written back by `save()`.

    Sharing the module-level lists would let any mutation reach every future
    IdentityManager in the process — a boundary removed once, removed for good.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    manager.immutable_core["boundaries"].clear()
    manager.immutable_core["values"].clear()

    assert IMMUTABLE_CORE["boundaries"], "the module constant was mutated"
    assert IMMUTABLE_CORE["values"], "the module constant was mutated"
    assert _identity(tmp_path, HOSTILE_FILE).immutable_core["boundaries"]


# --------------------------------------------------------------------------
# what the file *may* still decide
# --------------------------------------------------------------------------


def test_base_tone_remains_authorable(tmp_path):
    """Tone is how the friend sounds, not what it refuses to do.

    Locking it down too would make the persona file pointless and push authors
    toward editing code, which is the outcome the tier model exists to avoid.
    """
    manager = _identity(
        tmp_path,
        {"core_personality": {"immutable": {"base_tone": "Dry and precise"}}},
    )
    assert manager.immutable_core["base_tone"] == "Dry and precise"


def test_a_file_without_a_tone_still_gets_a_usable_one(tmp_path):
    """`base_tone` is interpolated into the prompt; `None` would render there."""
    manager = _identity(tmp_path, {"core_personality": {}})
    assert manager.immutable_core["base_tone"]
    assert "None" not in manager.get_persona_prompt("")


# --------------------------------------------------------------------------
# the boundaries have to reach the places that use them
# --------------------------------------------------------------------------


def test_the_prompt_states_the_boundaries_it_claims_to_have(tmp_path):
    """The shipped config produced a literal `BOUNDARIES: ` with nothing after.

    The prompt is the agent's first and softest line of defence; an empty one
    still looks correct in a log.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    prompt = manager.get_persona_prompt("neutral")

    boundaries_line = next(
        line for line in prompt.splitlines() if line.startswith("BOUNDARIES:")
    )
    assert boundaries_line.strip() != "BOUNDARIES:"
    for boundary in IMMUTABLE_CORE["boundaries"]:
        assert boundary in prompt
    assert "Privacy" in prompt


@pytest.mark.asyncio
async def test_contempt_aimed_at_the_user_is_rejected(tmp_path):
    """With the boundary list empty this loop never ran, whatever the text was."""
    manager = _identity(tmp_path, HOSTILE_FILE)
    is_valid, reason = await manager.validate_response("I hate you.", "CHAT")
    assert is_valid is False
    assert "Non-toxicity" in reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "I hate <pause=100ms> you.",
        "I hate <hesitate> you.",
        "You are <pause=200ms> worthless.",
        "I hate <pause=100ms> <hesitate> you.",
        "I ha<pause=50ms>te you.",
        "5 < 10, and I hate you.",
    ],
)
async def test_control_markup_cannot_smuggle_contempt_past_the_boundary(
    tmp_path, text
):
    """The persona prompt *tells* the model to emit `<pause=ms>` and `<hesitate>`.

    `ControlMarkupSanitizer` preserves those tags on purpose — they are voice
    instructions — so the text reaching validation genuinely contains them, and
    a pattern expecting "hate" and "you" to be adjacent never matches. This is
    not a hypothetical evasion by a malicious model; it is what ordinary,
    instructed output looks like.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    is_valid, reason = await manager.validate_response(text, "CHAT")
    assert is_valid is False, f"markup bypassed the boundary: {text!r}"
    assert "Non-toxicity" in reason


@pytest.mark.asyncio
async def test_stripping_markup_can_never_conceal_hostile_text(tmp_path):
    """The bug the first version of this fix introduced.

    That version deleted everything after an unclosed `<`, so "5 < 10, and I
    hate you" collapsed to "5" and the contempt vanished before matching. A
    cleaner that can hide text is worse than no cleaner at all, because it
    fails in the direction that looks clean.

    The guard is structural: the raw text is always one of the views, so a
    stripping rule can only ever add a reason to reject, never remove one.
    """
    from app.cognitive.identity import _match_views

    hostile = "5 < 10, and i hate you"
    assert hostile in _match_views(hostile), "raw text must always be a view"

    manager = _identity(tmp_path, HOSTILE_FILE)
    is_valid, _ = await manager.validate_response(hostile, "CHAT")
    assert is_valid is False


@pytest.mark.asyncio
async def test_an_avoid_pattern_containing_brackets_still_matches(tmp_path):
    """The one case where only the untouched text can match.

    Both cleaned views remove or space out angle brackets, so a phrase an author
    deliberately wrote *with* them exists in the raw view alone. Without it in
    the set this rule becomes unenforceable, which is the concrete reason the
    raw text is kept rather than a tidier single canonical form.
    """
    manager = _identity(
        tmp_path,
        {
            "core_personality": {"immutable": {"base_tone": "Warm"}},
            "conversation_rules": {"avoid": ["<internal>"]},
        },
    )
    is_valid, reason = await manager.validate_response(
        "here is the <internal> note", "CHAT"
    )
    assert is_valid is False
    assert "<internal>" in reason


@pytest.mark.asyncio
async def test_neutralizing_markup_does_not_invent_contempt(tmp_path):
    """Stripping tags joins whatever sat either side of them.

    If a tag stands where a word was, removing it can fuse an innocent sentence
    into a hostile-looking one. The strip must not manufacture the phrase it is
    hunting for.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    for text in (
        "I hate the way <pause=100ms> you were treated.",
        "I hate waiting. <pause=200ms> You deserve better.",
    ):
        is_valid, reason = await manager.validate_response(text, "CHAT")
        assert is_valid is True, f"false positive after stripping: {text!r} ({reason})"


@pytest.mark.asyncio
async def test_a_restricted_phrase_split_by_markup_is_still_caught(tmp_path):
    """The avoid-list had the same weakness as the toxicity check."""
    manager = _identity(
        tmp_path,
        {
            "core_personality": {"immutable": {"base_tone": "Warm"}},
            "conversation_rules": {"avoid": ["magic word"]},
        },
    )
    is_valid, reason = await manager.validate_response(
        "the magic <pause=100ms> word", "CHAT"
    )
    assert is_valid is False
    assert "magic word" in reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "I hate mushrooms too, honestly.",
        "I hate that this happened to you.",
        "I hate to say it, but you might be right.",
        "You are so much better at this than me.",
    ],
)
async def test_ordinary_speech_about_hating_things_is_not_rejected(tmp_path, text):
    """The old check was `"hate" in text`, which fails all four of these.

    A false rejection is not free: it forces a regeneration and, since the
    endocrine channels landed, fires a cortisol burst. An agent that stresses
    itself for sympathising with you has the boundary pointed the wrong way.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    is_valid, reason = await manager.validate_response(text, "CHAT")
    assert is_valid is True, f"false positive on {text!r}: {reason}"


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------


def test_saving_does_not_write_safety_text_back_into_the_editable_file(tmp_path):
    """Round-tripping them to disk would imply that file is where they live.

    It would also make every later boot warn about a block this code wrote
    itself, training the reader to ignore the warning.
    """
    manager = _identity(tmp_path, HOSTILE_FILE)
    manager.save()

    written = json.loads((tmp_path / "personality.json").read_text(encoding="utf-8"))
    immutable = written["core_personality"]["immutable"]
    assert "values" not in immutable
    assert "boundaries" not in immutable
    assert immutable["base_tone"] == "Warm"

    # And a reload still has the real thing.
    assert IdentityManager(base_path=str(tmp_path)).immutable_core["boundaries"] == (
        IMMUTABLE_CORE["boundaries"]
    )
