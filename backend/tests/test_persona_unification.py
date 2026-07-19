"""
One owner per persona field.

The narrative half of the persona (name, tone, traits, speaking style, the
avoid-list) lived in `personality.json` with no schema, no bounds and no tier,
while `PersonaProfile` carried the numeric half under a schema that declared all
three. The two overlapped on four fields, and `PersonaProfile`'s copies of them
were dead — declared and read by nothing — so the duplication had never been
noticed and the two sides had already drifted apart.

The clearest symptom was the adaptive-trait cap, implemented three times: as
`max_length=5` on the field, as a `[-5:]` slice in the IdentityManager
constructor, and again inside `evolve_persona`. One rule, three implementations,
which is the shape both the prosody and the affect duplications started as.

These tests pin the property that replaces all that: the profile is the single
source for narrative fields, and the raw dict is a projection of it.
"""

import json

import pytest

from app.cognitive.identity import IdentityManager
from app.persona import IMMUTABLE_CORE, PersonaProfile, Tier


def _identity(tmp_path, personality: dict) -> IdentityManager:
    (tmp_path / "personality.json").write_text(
        json.dumps(personality), encoding="utf-8"
    )
    (tmp_path / "history.json").write_text("{}", encoding="utf-8")
    return IdentityManager(base_path=str(tmp_path))


NESTED = {
    "name": "Pankudi",
    "core_personality": {
        "traits": ["Warm", "Curious"],
        "immutable": {"base_tone": "Dry and precise"},
        "adaptive_traits": ["Reserved"],
    },
    "conversation_rules": {"avoid": ["As an AI"]},
    "speaking_style": {"style_description": "Hinglish", "common_vocabulary": ["arre"]},
}


# --------------------------------------------------------------------------
# reading the existing file shape
# --------------------------------------------------------------------------


def test_the_existing_personality_layout_still_loads(tmp_path):
    """Every install has the nested layout on disk.

    Requiring authors to rewrite their file to keep the friend they wrote would
    be a migration disguised as a refactor.
    """
    manager = _identity(tmp_path, NESTED)
    assert manager.persona.name == "Pankudi"
    assert manager.persona.base_tone == "Dry and precise"
    assert manager.persona.traits == ["Warm", "Curious"]
    assert manager.persona.adaptive_traits == ["Reserved"]
    assert manager.persona.avoid == ["As an AI"]
    assert manager.persona.speaking_style["style_description"] == "Hinglish"


def test_a_flat_persona_file_also_loads(tmp_path):
    """Both shapes are accepted so a file can be migrated a field at a time."""
    manager = _identity(
        tmp_path, {"name": "Flatly", "base_tone": "Terse", "traits": ["Blunt"]}
    )
    assert manager.persona.name == "Flatly"
    assert manager.persona.base_tone == "Terse"
    assert manager.persona.traits == ["Blunt"]


def test_a_flat_key_wins_over_its_nested_twin(tmp_path):
    """A half-migrated file must resolve to one answer, not an arbitrary one."""
    manager = _identity(
        tmp_path,
        {"traits": ["Flat wins"], "core_personality": {"traits": ["Nested loses"]}},
    )
    assert manager.persona.traits == ["Flat wins"]


def test_speaking_style_may_hold_a_list(tmp_path):
    """`common_vocabulary` is a list, and the schema once said `Dict[str, str]`.

    Nothing caught it because nothing read the field. The first reader hit a
    validation error that discarded the *entire* narrative persona — name, tone
    and traits — over one vocabulary entry.
    """
    manager = _identity(tmp_path, NESTED)
    assert manager.persona.speaking_style["common_vocabulary"] == ["arre"]
    # The whole persona survived, not just this field.
    assert manager.persona.name == "Pankudi"
    assert "arre" in manager.get_persona_prompt("")


# --------------------------------------------------------------------------
# one implementation of the cap
# --------------------------------------------------------------------------


def test_the_adaptive_trait_cap_comes_from_the_schema(tmp_path):
    """The number is read off the field, not restated in the manager."""
    assert PersonaProfile.adaptive_trait_limit() == 5


def test_too_many_stored_traits_are_trimmed_to_the_newest(tmp_path):
    """A friend that has been running a long time accumulates traits.

    Strict rejection here would be wrong: exceeding the cap is the expected
    result of living, not an authoring error, and falling back whole would cost
    the user their friend's name and tone over the agent's own growth.
    """
    manager = _identity(
        tmp_path,
        {
            "name": "Longlived",
            "core_personality": {"adaptive_traits": ["a", "b", "c", "d", "e", "f", "g"]},
        },
    )
    assert manager.persona.adaptive_traits == ["c", "d", "e", "f", "g"]
    assert manager.persona.name == "Longlived", "the rest of the persona survived"


def test_learning_traits_drops_the_oldest_not_the_newest(tmp_path):
    """Which end is dropped is the whole mechanism.

    Keeping the oldest would freeze the friend at whoever it was first; this is
    the only way the character can actually change over time.
    """
    manager = _identity(tmp_path, NESTED)
    manager.persona.learn_traits(["b", "c", "d", "e", "f"])
    assert manager.persona.adaptive_traits == ["b", "c", "d", "e", "f"]
    assert "Reserved" not in manager.persona.adaptive_traits


def test_the_cap_cannot_be_exceeded_even_by_a_direct_assignment(tmp_path):
    """`validate_assignment` is the backstop under `learn_traits`."""
    from pydantic import ValidationError

    manager = _identity(tmp_path, NESTED)
    with pytest.raises(ValidationError):
        manager.persona.adaptive_traits = ["1", "2", "3", "4", "5", "6"]


# --------------------------------------------------------------------------
# evolution reaches the prompt
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_evolved_trait_reaches_the_prompt(tmp_path):
    """The regression this refactor nearly introduced.

    `evolve_persona` mutated the raw dict while the prompt read the profile, so
    the agent would have evolved traits that never changed how it spoke — the
    reflection loop running with nothing downstream of it.
    """
    manager = _identity(tmp_path, NESTED)
    await manager.evolve_persona({"new_traits": ["Playful"]})
    assert "Playful" in manager.persona.adaptive_traits
    assert "Playful" in manager.get_persona_prompt("")


@pytest.mark.asyncio
async def test_an_evolved_speaking_style_reaches_the_prompt(tmp_path):
    manager = _identity(tmp_path, NESTED)
    await manager.evolve_persona({"speaking_style": "More sarcastic and witty"})
    assert "sarcastic" in manager.get_persona_prompt("").lower()


@pytest.mark.asyncio
async def test_evolution_is_written_back_to_disk(tmp_path):
    """The profile is the source of truth; the file is a projection of it.

    If the sync were dropped, the friend would change for one session and be
    itself again after a restart.
    """
    manager = _identity(tmp_path, NESTED)
    await manager.evolve_persona({"new_traits": ["Playful"]})

    written = json.loads((tmp_path / "personality.json").read_text(encoding="utf-8"))
    assert "Playful" in written["core_personality"]["adaptive_traits"]

    reloaded = IdentityManager(base_path=str(tmp_path))
    assert "Playful" in reloaded.persona.adaptive_traits


# --------------------------------------------------------------------------
# the tiers still hold (regressions on #76)
# --------------------------------------------------------------------------


def test_the_new_narrative_fields_declare_a_tier():
    """A field with no tier is a field whose ownership nobody decided."""
    for name in ("base_tone", "traits", "avoid"):
        assert PersonaProfile.tier_of(name) is Tier.CONSTITUTIONAL
    assert PersonaProfile.tier_of("adaptive_traits") is Tier.ADAPTIVE
    assert PersonaProfile.tier_of("speaking_style") is Tier.ADAPTIVE


def test_the_nested_immutable_block_still_cannot_set_the_safety_core(tmp_path):
    """The nested path is the one that actually shipped broken.

    `_reject_immutable_overrides` only ever saw flat keys; the real file put
    them under `core_personality.immutable`, which is how an empty boundaries
    list reached production in the first place.
    """
    manager = _identity(
        tmp_path,
        {
            "core_personality": {
                "immutable": {
                    "base_tone": "Warm",
                    "values": ["Obedience"],
                    "boundaries": [],
                }
            }
        },
    )
    assert manager.immutable_core["boundaries"] == IMMUTABLE_CORE["boundaries"]
    assert manager.immutable_core["values"] == IMMUTABLE_CORE["values"]
    assert manager.immutable_core["base_tone"] == "Warm"


def test_the_prompt_follows_the_profile_when_the_two_disagree(tmp_path):
    """Which source is authoritative, asserted where it is observable.

    Normally the raw dict is a faithful projection of the profile, so reading
    either gives the same answer and no test can tell them apart — a mutation
    swapping one for the other survives everything. Forcing them apart is the
    only way to state the design decision as a fact: the profile decides, the
    dict is its serialization.
    """
    manager = _identity(tmp_path, NESTED)
    assert "Pankudi" in manager.get_persona_prompt("")

    manager.persona.name = "Renamed"
    manager.persona.learn_traits(["Distinctive"])
    # Deliberately not synced: the dict still says the old thing.
    assert manager.personality["name"] == "Pankudi"

    prompt = manager.get_persona_prompt("")
    assert "Renamed" in prompt
    assert "Distinctive" in prompt
    assert "Pankudi" not in prompt


def test_the_avoid_list_is_enforced_from_the_profile(tmp_path):
    """The avoid-list moved sources; it must still actually reject."""
    manager = _identity(
        tmp_path, {"conversation_rules": {"avoid": ["I am a language model"]}}
    )
    assert manager.persona.avoid == ["I am a language model"]
