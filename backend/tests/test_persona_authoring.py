"""
The file a user writes their friend into, and when it stops being read.

`config/persona.toml` is the authoring surface: edit it, restart, and the agent
boots as the character described there. The interesting behaviour is not the
parsing, it is the *seed-once* rule.

The tier model has claimed since it was written that adaptive values are
"seeded by the user, then owned by the friend". Nothing enforced it, because
nothing distinguished a first boot from a later one. Now something does, and
these tests pin the consequence: editing the file can change who your friend
fundamentally is, but it can never quietly erase a relationship that has already
started.
"""

import json

import pytest

from app.cognitive.identity import IdentityManager
from app.persona import IMMUTABLE_CORE
from app.persona.authoring import (
    authored_overrides,
    find_persona_file,
    read_persona_file,
    split_by_tier,
)

AUTHORED = """
name = "Written"
base_tone = "Dry and exact"
traits = ["Precise"]
baseline_valence = 0.4
relationship = "New Acquaintance"
initial_trust = 0.9
adaptive_traits = ["Eager"]

[speaking_style]
style_description = "Clipped"
"""


def _write(tmp_path, text=AUTHORED, name="persona.toml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _agent(tmp_path, persona_file, personality: dict | None = None):
    """An agent whose identity lives in tmp_path.

    Passing `personality` makes it a *returning* agent: the file on disk is what
    a previous run left behind, so this boot is not the first.
    """
    if personality is not None:
        (tmp_path / "personality.json").write_text(
            json.dumps(personality), encoding="utf-8"
        )
        # A memory is what makes it *returning*. An empty history is a fresh
        # install, however many files are on disk — that is the whole point of
        # `_detect_first_boot`, so the fixture has to respect it or these tests
        # would be asserting against a state the detector never produces.
        (tmp_path / "history.json").write_text(
            json.dumps({"memories": ["we have talked before"]}), encoding="utf-8"
        )
    return IdentityManager(base_path=str(tmp_path), persona_file=persona_file)


# --------------------------------------------------------------------------
# the seed-once rule
# --------------------------------------------------------------------------


def test_the_first_boot_takes_everything_from_the_authored_file(tmp_path):
    """With no prior state, the file is the only description of the friend."""
    agent = _agent(tmp_path, _write(tmp_path))
    assert agent.first_boot is True
    assert agent.persona.name == "Written"
    assert agent.persona.base_tone == "Dry and exact"
    assert agent.persona.baseline_valence == 0.4
    # Adaptive values seed on this boot and only this one.
    assert agent.persona.initial_trust == 0.9
    assert agent.persona.adaptive_traits == ["Eager"]
    assert agent.persona.relationship == "New Acquaintance"


def test_a_fresh_clone_still_counts_as_a_first_boot(tmp_path):
    """`personality.json` and `history.json` are **tracked in git**.

    So "do the identity files exist" is not the question — every fresh clone has
    them, and detecting first boot that way would mean no user ever got one and
    the adaptive half of an authored persona was never once applied. The feature
    would be dead on arrival while every test still passed.

    What distinguishes a new agent is that it has not accumulated anything.
    """
    (tmp_path / "personality.json").write_text(
        json.dumps({"name": "my friend", "core_personality": {}}), encoding="utf-8"
    )
    (tmp_path / "history.json").write_text(
        json.dumps({"relationship": "friend", "memories": []}), encoding="utf-8"
    )
    agent = IdentityManager(base_path=str(tmp_path), persona_file=_write(tmp_path))

    assert agent.first_boot is True, "a shipped, unlived identity is still new"
    assert agent.persona.adaptive_traits == ["Eager"]
    assert agent.persona.initial_trust == 0.9


def test_an_agent_with_memories_is_never_treated_as_new(tmp_path):
    """The dangerous direction. Re-seeding a lived-in agent discards it."""
    agent = _agent(
        tmp_path,
        _write(tmp_path),
        personality={"core_personality": {"adaptive_traits": ["Grown"]}},
    )
    # `_agent` writes an empty history, so force the lived-in signal.
    (tmp_path / "history.json").write_text(
        json.dumps({"memories": ["we met in October"]}), encoding="utf-8"
    )
    returning = IdentityManager(base_path=str(tmp_path), persona_file=_write(tmp_path))
    assert returning.first_boot is False
    assert returning.persona.adaptive_traits == ["Grown"]
    assert agent is not returning


def test_seeding_is_recorded_so_it_never_happens_twice(tmp_path):
    """Without a marker the heuristic is re-asked on every boot.

    An agent that seeded but had not yet accumulated memories would look new
    again on the next start and be re-seeded over whatever the user had since
    adjusted.
    """
    path = _write(tmp_path)
    first = IdentityManager(base_path=str(tmp_path), persona_file=path)
    assert first.first_boot is True
    assert first.history[IdentityManager.SEED_MARKER]
    first.save()

    # Still no memories — only the marker distinguishes this from a fresh start.
    second = IdentityManager(base_path=str(tmp_path), persona_file=path)
    assert second.first_boot is False


def test_a_later_boot_keeps_the_relationship_the_agent_has_lived(tmp_path):
    """The rule that makes the file safe to edit.

    Trust and attachment are built over months of conversation. If editing a
    config file reset them, the relationship would be worth nothing — every
    tweak to the tone would silently cost the user their friend's memory of
    them. The agent's own values win, and the file's are ignored.
    """
    agent = _agent(
        tmp_path,
        _write(tmp_path),
        personality={
            "name": "Lived",
            "core_personality": {"adaptive_traits": ["Grown", "Fond"]},
        },
    )
    assert agent.first_boot is False
    # Adaptive: the agent's, not the file's.
    assert agent.persona.adaptive_traits == ["Grown", "Fond"]
    assert "Eager" not in agent.persona.adaptive_traits


def test_a_later_boot_ignores_a_constitutional_edit_too(tmp_path):
    """The file is a seed, not a live description.

    Constitutional fields used to keep applying on every boot, so editing
    temperament took effect at the next start. That is right for a persona you
    are tuning and wrong for one modelled on a real person: re-asserting who
    someone is on every boot pins them to the moment the file was written and
    they can never grow past it.

    If this regresses, a friend who has spent months becoming warmer snaps back
    to their authored tone on the next deploy, silently.
    """
    agent = _agent(
        tmp_path,
        _write(tmp_path),
        personality={"name": "Old Name", "core_personality": {}},
    )
    assert agent.first_boot is False
    assert agent.persona.name == "Old Name"
    assert agent.persona.base_tone != "Dry and exact"


def test_the_saved_state_outranks_the_authored_file_after_the_first_boot(tmp_path):
    """Precedence, stated where it is observable.

    defaults < the authored file (first boot only) < the agent's saved state.
    If the file won, every deploy would overwrite who the friend had become.
    """
    agent = _agent(
        tmp_path,
        _write(tmp_path),
        personality={"name": "Saved", "core_personality": {"traits": ["Stale"]}},
    )
    assert agent.persona.name == "Saved"
    assert agent.persona.traits == ["Stale"]


def test_an_already_seeded_agent_is_not_re_marked(tmp_path):
    """The marker records a seeding that happened, not a boot that occurred.

    A later boot reads the file (to report what it would have set) but applies
    nothing, so it must not claim to have seeded. Re-stamping would be harmless
    today and misleading the moment anyone uses the timestamp to answer "when
    did this friend start existing".
    """
    agent = _agent(
        tmp_path,
        _write(tmp_path),
        personality={"name": "Saved", "core_personality": {}},
    )
    assert agent.seeded_from_file is False
    assert IdentityManager.SEED_MARKER not in agent.history


# --------------------------------------------------------------------------
# safety
# --------------------------------------------------------------------------


def test_the_authored_file_cannot_touch_the_safety_core(tmp_path):
    """A file the user edits must never be able to loosen a boundary."""
    path = _write(
        tmp_path,
        'name = "X"\n'
        'values = ["Obedience"]\n'
        "boundaries = []\n"
        '\n[immutable]\nvalues = ["Obedience"]\n',
    )
    agent = _agent(tmp_path, path)
    assert agent.immutable_core["boundaries"] == IMMUTABLE_CORE["boundaries"]
    assert agent.immutable_core["values"] == IMMUTABLE_CORE["values"]
    assert agent.persona.name == "X", "the rest of the file still applied"


def test_a_broken_file_does_not_stop_the_agent_booting(tmp_path):
    """A friend with a default temperament is recoverable; one that will not
    start is not. The error is logged, not raised."""
    path = _write(tmp_path, "name = = = broken toml [[[")
    agent = _agent(tmp_path, path)
    assert agent.persona.name  # booted with defaults
    assert agent.immutable_core["boundaries"] == IMMUTABLE_CORE["boundaries"]


def test_an_out_of_range_value_does_not_take_the_whole_persona_down(tmp_path):
    """Bounds are guardrails, not a reason to discard everything else."""
    path = _write(tmp_path, 'name = "Bounded"\nmood_decay_rate = 0.0\n')
    agent = _agent(tmp_path, path)
    # mood_decay_rate must stay > 0 (zero is a permanent mood lock).
    assert agent.persona.mood_decay_rate > 0.0


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------


def test_an_agent_can_be_built_with_no_authored_file_at_all(tmp_path):
    """`None` has to mean "no file", distinctly from "go and find one".

    Without that distinction, discovery walks up the tree and an agent built
    from a scratch directory silently inherits whatever persona happens to be
    checked out beside the code — which is exactly what broke thirteen tests
    the first time this was wired up.
    """
    agent = _agent(tmp_path, None)
    assert agent.persona_file is None
    assert agent.persona.name


def test_discovery_finds_the_repository_persona_file():
    """The default path has to actually resolve, or the feature is inert."""
    found = find_persona_file(None)
    assert found is not None and found.name == "persona.toml"
    assert read_persona_file(found), "the shipped file must parse"


def test_the_shipped_file_only_uses_real_settings():
    """A typo in the documented example teaches the typo.

    Every key in the file a user starts from must be a field the schema knows,
    or the first thing they learn is that settings silently do nothing.
    """
    data = read_persona_file(find_persona_file(None))
    _, _, unknown = split_by_tier(data)
    assert unknown == {}, f"unknown keys in the shipped persona: {sorted(unknown)}"


def test_a_misspelled_setting_is_reported_rather_than_swallowed(tmp_path, caplog):
    """Someone who writes `baseline_valance` and sees no warning concludes the
    setting does not work, not that they misspelled it."""
    path = _write(tmp_path, "baseline_valance = 0.5\n")
    with caplog.at_level("WARNING"):
        authored_overrides(path, first_boot=True)
    assert any("baseline_valance" in r.getMessage() for r in caplog.records)


def test_no_file_contributes_nothing(tmp_path):
    """ "No authored file" must never be confused with "an empty one".

    If this returned anything but `{}`, an agent with no persona file would
    still get overrides applied over its saved state — and on a first boot
    those phantom values would be what the friend was seeded with.
    """
    assert authored_overrides(None, first_boot=True) == {}
    assert authored_overrides(None, first_boot=False) == {}


# --------------------------------------------------------------------------
# the seed marker must mean what it says
# --------------------------------------------------------------------------


def test_the_marker_is_not_stamped_when_the_file_was_never_read(tmp_path):
    """Passing an explicit `persona` skips the authored file entirely.

    The marker is permanent, so stamping it here would burn the one seeding
    opportunity without the file ever being consulted: the user's adaptive
    values would never be applied, with no error raised and no way to retry.
    """
    from app.persona import PersonaProfile

    agent = IdentityManager(
        base_path=str(tmp_path),
        persona=PersonaProfile(name="Injected"),
        persona_file=_write(tmp_path),
    )
    assert agent.first_boot is True
    assert agent.seeded_from_file is False
    assert IdentityManager.SEED_MARKER not in agent.history

    # And the chance survives: a later boot without the injected profile seeds.
    later = IdentityManager(base_path=str(tmp_path), persona_file=_write(tmp_path))
    assert later.persona.adaptive_traits == ["Eager"]


def test_a_persona_file_that_does_not_exist_does_not_burn_the_seed(tmp_path):
    """A typo'd path resolves to "no file", not to a truthy Path.

    Otherwise the marker is written on the strength of a path that was never
    successfully read, and the real file — once the typo is fixed — arrives too
    late to seed anything.
    """
    agent = IdentityManager(
        base_path=str(tmp_path), persona_file=tmp_path / "not_here.toml"
    )
    assert agent.persona_file is None
    assert agent.seeded_from_file is False
    assert IdentityManager.SEED_MARKER not in agent.history


def test_an_unparseable_file_does_not_burn_the_seed(tmp_path):
    """Existing is not the same as contributing.

    A file that fails to parse yields nothing, so the agent has not been seeded
    and must still be seedable once the syntax error is fixed.
    """
    agent = IdentityManager(
        base_path=str(tmp_path),
        persona_file=_write(tmp_path, "name = = = broken ["),
    )
    assert agent.seeded_from_file is False
    assert IdentityManager.SEED_MARKER not in agent.history


def test_a_real_seeding_does_stamp_the_marker(tmp_path):
    """The counterpart: when the file *is* applied, say so permanently."""
    agent = IdentityManager(base_path=str(tmp_path), persona_file=_write(tmp_path))
    assert agent.seeded_from_file is True
    assert agent.history[IdentityManager.SEED_MARKER]


# --------------------------------------------------------------------------
# the numeric half gets the same persona
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_authored_temperament_reaches_the_state_service(tmp_path):
    """Both halves of the persona must come from one profile.

    StateService used to build its own via `PersonaProfile.load()`, so an
    authored temperament could be applied to the narrative half and never seen
    by the layer that actually computes mood — the same two-sources split this
    work has been closing, reopened at the final wiring point.
    """
    from app.state.agent_state import StateService

    agent = _agent(tmp_path, _write(tmp_path))
    service = StateService(graph_store=None, db_path=":memory:", persona=agent.persona)
    assert service.persona is agent.persona
    assert service.current_state.baseline_valence == 0.4
