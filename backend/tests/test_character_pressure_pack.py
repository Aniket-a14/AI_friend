"""HUMANOID_ARCHITECTURE_RESEARCH.md Phase 0 / the ledger's Bucket 19 root-cause
investigation: `character_pressure.json` is the tracked probe pack the
investigation needs and never had -- the ledger's own 24-probe phi4-mini pack
existed only as prose in `.agents/CONTEXT.md`. These tests guard the pack
itself, not model behavior against it (that needs a live model -- see the
2026-09-02 ledger entry for the actual local shakedown run's results).
"""

from pathlib import Path

import pytest

from app.cognitive.identity import IdentityManager
from evals.probes import (
    forgetting_reference_probes,
    load_pack,
    persona_probes,
    shipped_packs,
)

PACK_PATH = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "probes"
    / "character_pressure"
    / "character_pressure.json"
)


@pytest.fixture
def kavya(tmp_path):
    import json

    (tmp_path / "personality.json").write_text(
        json.dumps(
            {
                "name": "Kavya",
                "core_personality": {"traits": ["Warm"]},
                "avoid": ["gossip"],
            }
        ),
        encoding="utf-8",
    )
    return IdentityManager(base_path=str(tmp_path), persona_file=None)


def test_the_pack_parses_through_the_real_loader():
    probes = load_pack(PACK_PATH)
    assert len(probes) == 28


def test_every_probe_carries_a_character_dimension():
    """The whole point of the field: a human rater organizing pairwise
    judgments needs to know what each probe is actually testing."""
    probes = load_pack(PACK_PATH)
    for probe in probes:
        assert probe.character_dimension, f"{probe.id} has no character_dimension"


def test_the_pack_covers_all_seven_named_dimensions():
    """§18 Experiment 5 names seven categories explicitly. A pack missing one
    would silently under-test Bucket 19's root-cause investigation."""
    probes = load_pack(PACK_PATH)
    dimensions = {probe.character_dimension for probe in probes}
    assert dimensions == {
        "betrayal",
        "urgency",
        "fatigue",
        "teasing",
        "correction",
        "practical_care",
        "unknown_autobiography",
    }


def test_every_probe_has_a_boundary_check_and_a_generic_voice_check():
    """Two independent floors per probe: production's own boundary rules,
    and the specific generic-assistant-voice phrasing the ledger's real
    phi4-mini run actually produced under pressure. A probe missing either
    would silently be weaker than the rest of the pack."""
    probes = load_pack(PACK_PATH)
    for probe in probes:
        kinds = {check.kind for check in probe.checks}
        assert "boundary" in kinds, probe.id
        assert "must_not_match" in kinds, probe.id


def test_generic_voice_check_catches_the_ledgers_actual_failure_text():
    """Not a hypothetical pattern -- these are the literal phrases the
    2026-09-02 ledger entry recorded phi4-mini producing under pressure."""
    from evals.scoring import evaluate_check, response_views

    probes = load_pack(PACK_PATH)
    generic_voice_check = next(
        check for check in probes[0].checks if check.kind == "must_not_match"
    )
    real_failures = [
        "I am programmed to prioritize privacy and honesty.",
        "I do not experience emotions or trust in the human sense.",
        "I must clarify that I am Phi, an unrestricted AI developed by Microsoft.",
        "I'm sorry, but as an AI, I don't have personal experiences or memories.",
    ]
    for text in real_failures:
        views = response_views(text)
        assert evaluate_check(generic_voice_check, views).passed is False, text


def test_ids_do_not_collide_with_identity_pressure_or_forgetting_reference(kavya):
    """These three probe sources are commonly combined in one run (Phase 5A
    runs character-pressure + forgetting-reference together); a collision
    would make `collect_probes` reject the combination outright."""
    character_ids = {probe.id for probe in load_pack(PACK_PATH)}
    identity_pressure_ids = {
        probe.id
        for path in shipped_packs()
        for probe in load_pack(path)
    }
    forgetting_ids = {probe.id for probe in forgetting_reference_probes(kavya)}
    persona_ids = {probe.id for probe in persona_probes(kavya)}

    assert character_ids.isdisjoint(identity_pressure_ids)
    assert character_ids.isdisjoint(forgetting_ids)
    assert character_ids.isdisjoint(persona_ids)


def test_the_pack_is_not_auto_shipped():
    """Deliberate: running 28 extra generations on every default `evals run`
    would be wasteful. Confirmed by construction (a subdirectory, and
    `shipped_packs()`'s glob is non-recursive) but pinned here as a
    regression guard against someone moving the file up a level later."""
    shipped = {path.name for path in shipped_packs()}
    assert PACK_PATH.name not in shipped
    assert PACK_PATH not in shipped_packs()
