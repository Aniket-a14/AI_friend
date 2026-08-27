"""
`app/persona/wizard.py` -- rendering a compiled persona for a human to read,
and serializing it back into the exact TOML shape `authoring.py` reads.

The round-trip test is the one that matters most: `serialize_persona_toml`
writes text a real person could open and hand-edit, and `authoring.py`'s
`read_persona_file` reads it back with `tomllib`, a real parser with real
escaping rules -- not this module's own inverse function. A serializer that
mis-escapes a quote or newline produces a file that parses to something other
than what was compiled, silently, and the wizard's whole "preview what you'll
get" promise is broken by the time anyone notices.
"""

import tomllib

from app.persona.compiler import CompiledPersona, Inference
from app.persona.profile import PersonaProfile
from app.persona.wizard import render_preview, serialize_persona_toml


def _profile(**overrides) -> PersonaProfile:
    merged = PersonaProfile.from_config().model_dump()
    merged.update(overrides)
    return PersonaProfile(**merged)


def _compiled(profile: PersonaProfile | None = None, **kwargs) -> CompiledPersona:
    return CompiledPersona(
        profile=profile or _profile(),
        biography_markdown=kwargs.get("biography_markdown", ""),
        inferences=kwargs.get("inferences", []),
        dimensions=kwargs.get("dimensions", {}),
    )


# ---------------------------------------------------------------------------
# serialize_persona_toml: must round-trip through a real TOML parser
# ---------------------------------------------------------------------------


def test_round_trips_plain_values_through_tomllib():
    profile = _profile(
        name="Mira",
        base_tone="Blunt and dry.",
        traits=["blunt", "loyal"],
        baseline_valence=-0.2,
        initial_trust=0.35,
    )
    parsed = tomllib.loads(serialize_persona_toml(profile))

    assert parsed["name"] == "Mira"
    assert parsed["base_tone"] == "Blunt and dry."
    assert parsed["traits"] == ["blunt", "loyal"]
    assert parsed["baseline_valence"] == -0.2
    assert parsed["initial_trust"] == 0.35


def test_round_trips_a_value_containing_a_double_quote():
    profile = _profile(identity_summary='She says "sure, whatever" a lot.')
    parsed = tomllib.loads(serialize_persona_toml(profile))
    assert parsed["identity_summary"] == 'She says "sure, whatever" a lot.'


def test_round_trips_a_value_containing_a_backslash():
    profile = _profile(base_tone="C:\\not\\a\\path but written like one")
    parsed = tomllib.loads(serialize_persona_toml(profile))
    assert parsed["base_tone"] == "C:\\not\\a\\path but written like one"


def test_round_trips_a_value_containing_newlines():
    profile = _profile(identity_summary="Line one.\nLine two.")
    parsed = tomllib.loads(serialize_persona_toml(profile))
    assert parsed["identity_summary"] == "Line one.\nLine two."


def test_speaking_style_renders_as_a_table_and_round_trips():
    profile = _profile(speaking_style={"style_description": "Dry and direct"})
    parsed = tomllib.loads(serialize_persona_toml(profile))
    assert parsed["speaking_style"]["style_description"] == "Dry and direct"


def test_empty_speaking_style_omits_the_table():
    profile = _profile(speaking_style={})
    text = serialize_persona_toml(profile)
    assert "[speaking_style]" not in text


def test_serialized_toml_never_contains_the_word_boundaries_as_a_key():
    # There is no field for IMMUTABLE_CORE on PersonaProfile at all, so this
    # is really asserting the serializer only ever walks _TOML_FIELD_ORDER --
    # a regression here would mean something started writing extra keys.
    text = serialize_persona_toml(_profile())
    parsed = tomllib.loads(text)
    assert "boundaries" not in parsed
    assert "values" not in parsed


# ---------------------------------------------------------------------------
# render_preview
# ---------------------------------------------------------------------------


def test_preview_shows_every_inference_with_its_reason():
    inferences = [
        Inference(field="baseline_valence", value=-0.2, reason="warmth=-0.30 -> cold"),
        Inference(field="mood_decay_rate", value=0.3, reason="resilience=0.70 -> bounces back"),
    ]
    text = render_preview(_compiled(inferences=inferences))
    assert "warmth=-0.30 -> cold" in text
    assert "resilience=0.70 -> bounces back" in text


def test_preview_lists_biography_headings_when_present():
    md = "## Her sister\n\nClose growing up.\n\n## Where she grew up\n\nA cold town."
    text = render_preview(_compiled(biography_markdown=md))
    assert "Her sister" in text
    assert "Where she grew up" in text
    assert "2 passage" in text


def test_preview_states_no_biography_when_none_compiled():
    text = render_preview(_compiled(biography_markdown=""))
    assert "none" in text.lower()


def test_preview_shows_the_immutable_core_but_labels_it_uneditable():
    text = render_preview(_compiled())
    assert "Honesty" in text
    assert "IMMUTABLE" in text
