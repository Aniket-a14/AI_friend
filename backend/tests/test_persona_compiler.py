"""
The persona compiler -- freeform prose to a validated `PersonaProfile`.

Two kinds of thing are being protected. First, the deterministic half: the
dimension-to-field formulas in `_infer_temperament` must move each field in
the direction its dimension implies and must never escape `PersonaProfile`'s
own bounds, since that mapping is the one part of the compiler a user
cannot see reasoned about by the model -- it has to be right by construction.
Second, the LLM-facing half: `_extract_json_object` must survive the ways a
real model's output actually misbehaves (prose around the JSON, code fences),
and `compile_persona` must never let a hallucinated `values`/`boundaries` key
or an oversized list reach `PersonaProfile` un-clamped.

The friction requirement itself -- that a blunt description produces a blunt
persona rather than a softened one -- is NOT testable here: it depends on
what a real model actually returns, which a mocked client can't exercise
honestly. That is `backend/scripts/testing/verify_persona_compiler_friction.py`,
a live-model script run manually, not part of this hermetic suite.
"""

import json
from unittest.mock import AsyncMock

import pytest

from app.persona.compiler import (
    CompiledPersona,
    Inference,
    PersonaCompilationError,
    _as_float,
    _as_str_list,
    _biography_markdown,
    _extract_json_object,
    _infer_temperament,
    compile_persona,
)
from app.persona.profile import IMMUTABLE_CORE, PersonaProfile

# ---------------------------------------------------------------------------
# _infer_temperament: the deterministic dimension -> field mapping
# ---------------------------------------------------------------------------


def test_higher_warmth_produces_higher_baseline_valence():
    cold, _ = _infer_temperament({"warmth": -1.0})
    warm, _ = _infer_temperament({"warmth": 1.0})
    assert warm["baseline_valence"] > cold["baseline_valence"]


def test_higher_volatility_produces_faster_arousal_response_and_valence_drift():
    steady, _ = _infer_temperament({"volatility": 0.0})
    volatile, _ = _infer_temperament({"volatility": 1.0})
    assert volatile["arousal_response_rate"] > steady["arousal_response_rate"]
    assert volatile["valence_drift_rate"] > steady["valence_drift_rate"]


def test_higher_resilience_produces_faster_mood_decay():
    # A mutation that inverted this formula would have a friend described as
    # "bounces back quickly" mood-lock instead -- exactly the failure the
    # persona schema's own mood_decay_rate floor exists to prevent.
    dwells, _ = _infer_temperament({"resilience": 0.0})
    bounces_back, _ = _infer_temperament({"resilience": 1.0})
    assert bounces_back["mood_decay_rate"] > dwells["mood_decay_rate"]


def test_every_inferred_field_stays_within_persona_bounds_at_extremes():
    """Every dimension pinned to its extreme in both directions must still
    produce a value `PersonaProfile` itself accepts -- constructing the
    profile is the real assertion here."""
    for warmth in (-1.0, 1.0):
        for other in (0.0, 1.0):
            fields, _ = _infer_temperament(
                {
                    "warmth": warmth,
                    "energy": other,
                    "assertiveness": other,
                    "volatility": other,
                    "resilience": other,
                    "opinion_firmness": other,
                    "openness_to_trust": other,
                    "warmth_growth": other,
                    "emotional_lingering": other,
                }
            )
            merged = PersonaProfile.from_config().model_dump()
            merged.update(fields)
            PersonaProfile(**merged)  # raises ValidationError on failure


def test_missing_dimensions_fall_back_to_neutral_defaults():
    """A description that only mentions warmth must not corrupt the fields
    driven by dimensions it never scored."""
    fields, _ = _infer_temperament({"warmth": 0.5})
    baseline, _ = _infer_temperament({})
    for key in fields:
        if key == "baseline_valence":
            continue
        assert fields[key] == baseline[key]


def test_each_field_produces_exactly_one_inference_with_its_reason():
    fields, inferences = _infer_temperament({"warmth": 0.3, "energy": 0.7})
    by_field = {inf.field: inf for inf in inferences}
    assert set(by_field) == set(fields)
    for name, inf in by_field.items():
        assert isinstance(inf, Inference)
        assert inf.value == fields[name]
        assert inf.reason  # never silently applied


# ---------------------------------------------------------------------------
# _extract_json_object: surviving real LLM output shapes
# ---------------------------------------------------------------------------


def test_extracts_clean_json():
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_extracts_json_wrapped_in_prose_and_code_fence():
    text = 'Sure, here you go:\n```json\n{"a": 1, "b": [1, 2]}\n```\nHope that helps!'
    assert _extract_json_object(text) == {"a": 1, "b": [1, 2]}


def test_unbalanced_brace_inside_a_string_does_not_close_the_object_early():
    # A single unmatched `}` inside the string value would, under naive
    # (non-string-aware) brace counting, be read as closing the outer object
    # right there -- truncating everything after it, including the "n" key.
    text = '{"text": "closing brace } inside a string", "n": 2}'
    result = _extract_json_object(text)
    assert result["n"] == 2
    assert result["text"] == "closing brace } inside a string"


def test_no_json_object_raises_compilation_error():
    with pytest.raises(PersonaCompilationError):
        _extract_json_object("I'm not sure how to answer that.")


def test_unclosed_json_object_raises_compilation_error():
    with pytest.raises(PersonaCompilationError):
        _extract_json_object('{"a": 1')


def test_json_array_at_top_level_raises_compilation_error():
    with pytest.raises(PersonaCompilationError):
        _extract_json_object("[1, 2, 3]")


# ---------------------------------------------------------------------------
# small coercion helpers
# ---------------------------------------------------------------------------


def test_as_float_reads_a_numeric_string():
    assert _as_float("0.7", default=0.0) == 0.7


def test_as_float_falls_back_to_default_on_garbage():
    assert _as_float("not a number", default=0.42) == 0.42
    assert _as_float(None, default=0.42) == 0.42


def test_as_str_list_truncates_to_max_items():
    result = _as_str_list(["a", "b", "c", "d"], max_items=2)
    assert result == ["a", "b"]


def test_as_str_list_drops_non_string_and_blank_entries():
    result = _as_str_list(["ok", "", None, 5, "  ", "also ok"], max_items=10)
    assert result == ["ok", "also ok"]


def test_biography_markdown_renders_headings_as_h2():
    md = _biography_markdown(
        [{"heading": "Her sister", "text": "Close, three years apart."}]
    )
    assert md.startswith("## Her sister")
    assert "Close, three years apart." in md


def test_biography_markdown_empty_for_no_entries():
    assert _biography_markdown([]) == ""
    assert _biography_markdown(None) == ""


# ---------------------------------------------------------------------------
# compile_persona: end to end against a mocked client
# ---------------------------------------------------------------------------


def _canned_response(**overrides) -> str:
    payload = {
        "name": "Mira",
        "base_tone": "Blunt, dry, protective under the sarcasm.",
        "identity_summary": "Mira does not sugarcoat anything and will tell you "
        "when you're wrong. She grew up somewhere cold and it shows.",
        "traits": ["blunt", "loyal", "sarcastic"],
        "speech_patterns": ['"sure, whatever you say"'],
        "avoid": ["baby talk"],
        "relationship": "old friend",
        "speaking_style": "Dry and matter-of-fact, even when she's being kind.",
        "biography": [
            {
                "heading": "Where she grew up",
                "text": "A small town up north, cold winters.",
            }
        ],
        "dimensions": {
            "warmth": -0.2,
            "energy": 0.4,
            "assertiveness": 0.8,
            "volatility": 0.6,
            "resilience": 0.7,
            "opinion_firmness": 0.9,
            "openness_to_trust": 0.3,
            "warmth_growth": 0.4,
            "emotional_lingering": 0.5,
        },
    }
    payload.update(overrides)
    return json.dumps(payload)


def _mock_client(response_text: str) -> AsyncMock:
    client = AsyncMock()
    client.generate = AsyncMock(return_value=response_text)
    return client


@pytest.mark.asyncio
async def test_compile_persona_builds_a_valid_profile():
    client = _mock_client(_canned_response())
    compiled = await compile_persona("she's blunt and loyal", llm=client)

    assert isinstance(compiled, CompiledPersona)
    assert compiled.profile.name == "Mira"
    assert "blunt" in compiled.profile.traits
    assert compiled.profile.relationship == "old friend"
    assert compiled.profile.baseline_valence < 0  # warmth was negative
    assert "Where she grew up" in compiled.biography_markdown
    # One per temperament field -- 14 since Bucket 11 (voice remediation
    # Phase 3, item 2) added adrenaline_halflife_s alongside dopamine's and
    # cortisol's.
    assert len(compiled.inferences) == 14


@pytest.mark.asyncio
async def test_compile_persona_never_lets_a_hallucinated_immutable_key_through():
    """The model is never asked for `values`/`boundaries`, but a real model can
    still hallucinate extra keys. compile_persona only ever reads the keys it
    knows about, so a hallucinated safety-core key must be silently ignored,
    never merged into the constructed profile."""
    response = _canned_response(values=["Whatever"], boundaries=["None at all"])
    client = _mock_client(response)
    compiled = await compile_persona("test", llm=client)

    assert compiled.profile.immutable == IMMUTABLE_CORE
    assert "values" not in compiled.profile.model_dump()
    assert "boundaries" not in compiled.profile.model_dump()


@pytest.mark.asyncio
async def test_compile_persona_rejects_a_bare_pronoun_as_a_name():
    """Observed live against a real 3B model: asked for "a name" on a
    description starting "He is...", it echoed back "He" as the name.
    The prompt now says not to; this is the code-level backstop for when a
    (usually smaller/weaker) model does it anyway."""
    response = _canned_response(name="He")
    client = _mock_client(response)
    compiled = await compile_persona("He is blunt and loyal", llm=client)
    assert compiled.profile.name == "Friend"


@pytest.mark.asyncio
async def test_compile_persona_keeps_a_real_proper_name():
    response = _canned_response(name="Mira")
    client = _mock_client(response)
    compiled = await compile_persona("test", llm=client)
    assert compiled.profile.name == "Mira"


@pytest.mark.asyncio
async def test_compile_persona_truncates_oversized_lists_instead_of_failing():
    """PersonaProfile.traits caps at 8. A model returning more must be
    truncated by the compiler, not raise a ValidationError the user did
    nothing to cause."""
    response = _canned_response(traits=[f"trait{i}" for i in range(20)])
    client = _mock_client(response)
    compiled = await compile_persona("test", llm=client)
    assert len(compiled.profile.traits) <= 8


@pytest.mark.asyncio
async def test_compile_persona_raises_on_unparseable_llm_output():
    client = _mock_client("I don't understand the request.")
    with pytest.raises(PersonaCompilationError):
        await compile_persona("test", llm=client)


@pytest.mark.asyncio
async def test_compile_persona_rejects_an_empty_description():
    client = _mock_client(_canned_response())
    with pytest.raises(PersonaCompilationError):
        await compile_persona("   ", llm=client)


@pytest.mark.asyncio
async def test_compile_persona_defaults_biography_to_empty_when_none_mentioned():
    response = _canned_response(biography=[])
    client = _mock_client(response)
    compiled = await compile_persona("test", llm=client)
    assert compiled.biography_markdown == ""
