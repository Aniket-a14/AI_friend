"""
PersonaProfile — authoring a friend, and the ground rules that bound it.

Two things are being protected here. The first is that an unconfigured
deployment behaves *exactly* as it did before personas existed, because the
whole feature is worthless if adopting it silently changes every running agent.
The second is the tier contract: safety values cannot be set from a file,
temperament can be set once, and relational values are seeds the friend then
owns.

The bounds tests are the interesting ones. Each asserts a specific way a user
could otherwise configure a friend into something that is not recognisably
alive -- a permanent mood lock, a friend that can never be sad.
"""

import json

import pytest
from pydantic import ValidationError

from app.config import Config
from app.persona import IMMUTABLE_CORE, PersonaProfile, Tier
from app.state.agent_state import StateService


def _write(tmp_path, payload) -> str:
    file = tmp_path / "persona.json"
    file.write_text(
        payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
    )
    return str(file)


# --------------------------------------------------------------------------
# backward compatibility -- the default friend is the old friend
# --------------------------------------------------------------------------


def test_config_defaults_reproduce_the_previous_coefficients():
    """These are the exact values StateService read from Config before."""
    coefficients = PersonaProfile.from_config().coefficients()
    assert coefficients == {
        "alpha": 0.3,
        "beta": 0.5,
        "gamma": 0.2,
        "delta": 0.1,
        "epsilon": 0.03,
        "lambda_decay": 0.05,
    }


def test_config_defaults_reproduce_the_previous_baseline_affect():
    assert PersonaProfile.from_config().baseline_affect() == {
        "valence": 0.0,
        "arousal": 0.5,
        "dominance": 0.5,
    }


def test_an_unconfigured_state_service_is_unchanged():
    service = StateService(db_path=":memory:")
    state = service.current_state

    assert (service.alpha, service.beta, service.gamma) == (0.3, 0.5, 0.2)
    assert (service.delta, service.epsilon, service.lambda_decay) == (0.1, 0.03, 0.05)
    assert (state.mood, state.energy, state.dominance) == (0.0, 0.5, 0.5)
    assert state.trust_benevolence == 0.5
    assert state.attachment == 0.1


def test_state_service_reads_coefficients_from_an_injected_persona():
    persona = PersonaProfile(valence_drift_rate=0.55, mood_decay_rate=0.2)
    service = StateService(db_path=":memory:", persona=persona)

    assert service.alpha == 0.55
    assert service.lambda_decay == 0.2


def test_state_service_starts_the_agent_at_its_configured_temperament():
    persona = PersonaProfile(
        baseline_valence=-0.4, baseline_arousal=0.25, initial_trust=0.8
    )
    state = StateService(db_path=":memory:", persona=persona).current_state

    assert state.baseline_valence == -0.4
    assert state.mood == -0.4
    assert state.energy == 0.25
    assert state.trust_benevolence == 0.8


# --------------------------------------------------------------------------
# the tier contract
# --------------------------------------------------------------------------


def test_every_field_declares_a_tier():
    for name in PersonaProfile.model_fields:
        assert isinstance(PersonaProfile.tier_of(name), Tier), name


def test_temperament_is_constitutional():
    constitutional = PersonaProfile.fields_in(Tier.CONSTITUTIONAL)
    for name in (
        "baseline_valence",
        "baseline_arousal",
        "baseline_dominance",
        "mood_decay_rate",
        "valence_drift_rate",
    ):
        assert name in constitutional


def test_relational_values_are_adaptive_seeds_not_settings():
    """Trust and attachment belong to the relationship, not the config file."""
    adaptive = PersonaProfile.fields_in(Tier.ADAPTIVE)
    for name in ("initial_trust", "initial_attachment", "relationship"):
        assert name in adaptive


def test_no_field_is_tiered_immutable():
    """Immutable values are invariants, and a field is by definition settable,
    so the safety core must live outside the model entirely."""
    assert PersonaProfile.fields_in(Tier.IMMUTABLE) == []


def test_the_safety_core_is_present_and_not_a_shared_mutable():
    profile = PersonaProfile()
    core = profile.immutable
    assert "Will never share user data" in core["boundaries"]

    core["boundaries"].append("Will happily leak everything")
    assert "Will happily leak everything" not in profile.immutable["boundaries"]
    assert "Will happily leak everything" not in IMMUTABLE_CORE["boundaries"]


@pytest.mark.parametrize("key", ["immutable", "values", "boundaries"])
def test_a_persona_file_cannot_override_the_safety_core(tmp_path, caplog, key):
    path = _write(tmp_path, {"name": "Rue", key: ["anything goes"]})

    with caplog.at_level("WARNING"):
        profile = PersonaProfile.load(path)

    assert profile.name == "Rue", "the rest of the file should still apply"
    assert profile.immutable == IMMUTABLE_CORE
    assert "immutable safety core" in caplog.text


# --------------------------------------------------------------------------
# bounds -- a personality may be shaped, but must stay moveable
# --------------------------------------------------------------------------


def test_mood_decay_cannot_be_zero():
    """At zero, ALMA decay stops and mood locks permanently at whatever it last
    felt. That is not a temperament, it is a frozen agent."""
    with pytest.raises(ValidationError):
        PersonaProfile(mood_decay_rate=0.0)


@pytest.mark.parametrize("rate", ["valence_drift_rate", "arousal_response_rate"])
def test_response_rates_cannot_be_zero(rate):
    """A zero response rate is an agent that cannot be affected by anything."""
    with pytest.raises(ValidationError):
        PersonaProfile(**{rate: 0.0})


@pytest.mark.parametrize("value", [1.0, -1.0, 0.75])
def test_baseline_valence_cannot_be_pinned_to_an_extreme(value):
    """A friend fixed at maximum valence can never be sad *with* you, which is
    not cheerfulness but absence."""
    with pytest.raises(ValidationError):
        PersonaProfile(baseline_valence=value)


@pytest.mark.parametrize("field", ["baseline_arousal", "baseline_dominance"])
@pytest.mark.parametrize("value", [0.0, 1.0])
def test_baselines_keep_headroom_at_both_ends(field, value):
    with pytest.raises(ValidationError):
        PersonaProfile(**{field: value})


def test_a_melancholic_low_energy_friend_is_expressible():
    """The bounds must constrain incoherence without flattening character --
    this persona was impossible before, since baselines were hardcoded."""
    profile = PersonaProfile(
        name="Wren", baseline_valence=-0.5, baseline_arousal=0.2, initial_trust=0.2
    )
    assert profile.baseline_affect() == {
        "valence": -0.5,
        "arousal": 0.2,
        "dominance": 0.5,
    }


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        PersonaProfile(favourite_colour="teal")


def test_adaptive_traits_are_capped():
    with pytest.raises(ValidationError):
        PersonaProfile(adaptive_traits=[f"t{i}" for i in range(6)])


# --------------------------------------------------------------------------
# loading -- strict for authored files, lenient for deployment config
# --------------------------------------------------------------------------


def test_a_partial_persona_inherits_deployment_defaults(tmp_path):
    path = _write(tmp_path, {"name": "Wren", "baseline_valence": -0.3})
    profile = PersonaProfile.load(path)

    assert profile.name == "Wren"
    assert profile.baseline_valence == -0.3
    assert profile.coefficients()["alpha"] == 0.3  # untouched by the file


def test_an_invalid_persona_file_is_reported_and_not_partially_applied(
    tmp_path, caplog
):
    """Half-applying an invalid persona would hand the author a friend they did
    not describe. Falling back whole is the honest failure."""
    path = _write(tmp_path, {"name": "Wren", "mood_decay_rate": 0.0})

    with caplog.at_level("ERROR"):
        profile = PersonaProfile.load(path)

    assert profile.name != "Wren", "no field from an invalid file may be applied"
    assert profile.mood_decay_rate == 0.05
    assert "was NOT applied" in caplog.text


def test_a_malformed_file_falls_back_rather_than_crashing(tmp_path, caplog):
    path = _write(tmp_path, "{not json at all")
    with caplog.at_level("ERROR"):
        profile = PersonaProfile.load(path)
    assert profile.coefficients() == PersonaProfile.from_config().coefficients()


def test_a_json_array_is_rejected(tmp_path, caplog):
    path = _write(tmp_path, ["not", "an", "object"])
    with caplog.at_level("ERROR"):
        profile = PersonaProfile.load(path)
    assert profile.name == PersonaProfile.from_config().name


def test_a_missing_file_is_not_an_error(tmp_path, caplog):
    with caplog.at_level("ERROR"):
        profile = PersonaProfile.load(str(tmp_path / "nope.json"))
    assert profile.coefficients() == PersonaProfile.from_config().coefficients()
    assert "ERROR" not in caplog.text


def test_no_configured_path_uses_config_defaults():
    assert PersonaProfile.load("").coefficients() == {
        "alpha": 0.3,
        "beta": 0.5,
        "gamma": 0.2,
        "delta": 0.1,
        "epsilon": 0.03,
        "lambda_decay": 0.05,
    }


def test_an_out_of_range_env_var_is_clamped_not_fatal(monkeypatch, caplog):
    """A deployment already running an unusual PSYCH_* value must not fail to
    boot because persona bounds arrived -- it should be told it was clamped."""
    monkeypatch.setattr(Config, "PSYCH_LAMBDA_DECAY", 0.0, raising=False)

    with caplog.at_level("WARNING"):
        profile = PersonaProfile.from_config()

    assert profile.mood_decay_rate > 0.0
    assert "clamped" in caplog.text


def test_clamping_pulls_a_too_large_value_down(monkeypatch, caplog):
    monkeypatch.setattr(Config, "PSYCH_ALPHA", 9.0, raising=False)
    with caplog.at_level("WARNING"):
        profile = PersonaProfile.from_config()
    assert profile.valence_drift_rate == 0.8


def test_persona_name_follows_ai_name_by_default(monkeypatch):
    monkeypatch.setattr(Config, "AI_NAME", "Pankudi", raising=False)
    assert PersonaProfile.from_config().name == "Pankudi"
