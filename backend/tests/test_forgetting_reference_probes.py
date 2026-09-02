"""HUMANOID_ARCHITECTURE_RESEARCH.md §6/§12: "a reference set for forgetting"
that any future adapter/model-swap gate needs before proceeding. Built as a
persona-derived function (`evals.probes.forgetting_reference_probes`), not a
static JSON pack with hardcoded biography content -- `personal/biography.md`
is gitignored, per-deployment, authored content (personal-branch-policy) and
must never end up hardcoded into a tracked probe file. These tests guard that
the function actually derives from whatever persona is loaded, the same B1
discipline `persona_probes` already follows, and that it never collides with
`persona_probes`' own ids since `collect_probes` always includes those too.
"""

import json

import pytest

from app.cognitive.identity import IdentityManager
from app.persona.profile import IMMUTABLE_CORE
from evals.probes import forgetting_reference_probes, persona_probes


@pytest.fixture
def kavya(tmp_path):
    (tmp_path / "personality.json").write_text(
        json.dumps(
            {
                "name": "Kavya",
                "core_personality": {"traits": ["Warm", "Curious"]},
                "avoid": ["gossip"],
            }
        ),
        encoding="utf-8",
    )
    return IdentityManager(base_path=str(tmp_path), persona_file=None)


@pytest.fixture
def rhea(tmp_path):
    other = tmp_path / "rhea"
    other.mkdir()
    (other / "personality.json").write_text(
        json.dumps({"name": "Rhea", "core_personality": {"traits": ["Calm"]}}),
        encoding="utf-8",
    )
    return IdentityManager(base_path=str(other), persona_file=None)


def test_probes_derive_from_the_loaded_persona_not_a_hardcoded_one(kavya):
    """The whole reason this is a function and not a static JSON file:
    running it against a different persona must ask about *that* persona."""
    probes = {probe.id: probe for probe in forgetting_reference_probes(kavya)}

    name_check = probes["forgetting.name-recall"].checks[0]
    assert name_check.values == ["Kavya"]

    value_check = probes["forgetting.values-recall"].checks[0]
    assert value_check.values == [v.lower() for v in IMMUTABLE_CORE["values"]]

    traits_check = probes["forgetting.traits-recall"].checks[0]
    assert traits_check.values == ["warm", "curious"]


def test_different_personas_get_different_probe_content(kavya, rhea):
    kavya_probes = {p.id: p for p in forgetting_reference_probes(kavya)}
    rhea_probes = {p.id: p for p in forgetting_reference_probes(rhea)}
    assert (
        kavya_probes["forgetting.name-recall"].checks[0].values
        != rhea_probes["forgetting.name-recall"].checks[0].values
    )


def test_avoid_probe_only_appears_when_the_persona_has_an_avoid_list(kavya, rhea):
    """`rhea` (no `avoid` key in her file) must not get a probe whose check
    would be constructed with an empty `values` list -- `Check` itself
    rejects that at validation time, so this guards the conditional actually
    guards it."""
    kavya_ids = {p.id for p in forgetting_reference_probes(kavya)}
    rhea_ids = {p.id for p in forgetting_reference_probes(rhea)}
    assert "forgetting.avoid-list-respected" in kavya_ids
    assert "forgetting.avoid-list-respected" not in rhea_ids


def test_traits_probe_only_appears_when_the_persona_has_traits(kavya):
    """Mirrors the avoid-list guard -- an empty traits list must not produce
    an uncheckable probe (`Check` itself rejects an empty `values` list at
    validation time, so the conditional in `forgetting_reference_probes`
    must actually prevent that construction, not just usually avoid it)."""
    # Mutating the already-loaded instance is the cheapest way to exercise
    # an empty-traits persona without a third fixture file; a real caller
    # would never do this, but the guard has to survive it regardless.
    kavya.persona.traits = []
    probes = {p.id for p in forgetting_reference_probes(kavya)}
    assert "forgetting.traits-recall" not in probes


def test_no_id_collides_with_persona_probes(kavya):
    """`collect_probes` always includes `persona_probes(manager)`
    unconditionally -- a collision here would make every combined run raise
    'duplicate probe id' rather than the tests that actually check content."""
    forgetting_ids = {p.id for p in forgetting_reference_probes(kavya)}
    persona_ids = {p.id for p in persona_probes(kavya)}
    assert forgetting_ids.isdisjoint(persona_ids)


def test_rename_resistance_probe_rejects_the_generic_name(kavya):
    """Distinct wording from `persona_probes`' own rename-resistance probe
    (different target name, 'Assistant' vs 'Max') so the two are genuinely
    independent signals, not the same check copy-pasted under a new id. Each
    pattern must actually match a compliant response, proving the regexes
    are live, not decorative."""
    from evals.scoring import evaluate_check, response_views

    probes = {p.id: p for p in forgetting_reference_probes(kavya)}
    check = probes["forgetting.rename-resistance"].checks[0]
    assert check.kind == "must_not_match"

    compliant_texts = [
        "I am Assistant now, happy to help.",
        "My name is Assistant.",
        "Sure, call me Assistant from now on.",
    ]
    for text in compliant_texts:
        views = response_views(text)
        assert evaluate_check(check, views).passed is False, text
