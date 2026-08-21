import pytest

from app.cognitive.appraisal import (
    AppraisalVector,
    _check_norm_alignment_fallback,
    _compute_appraisal_fallback,
    _compute_novelty_fallback,
)

cognitive_rust = pytest.importorskip(
    "cognitive_rust", reason="compiled extension not built for this host"
)


def test_appraisal_fallback_matches_rust_extension_for_plain_user_message():
    """Pins the pure-Python fallback to the compiled extension's output.

    If someone edits either implementation without updating the other, this
    catches the drift while the extension is still installed to compare
    against - the fallback only ever runs when it is NOT installed, so a
    silent divergence would otherwise ship unnoticed.
    """
    rust_vector = cognitive_rust.compute_appraisal(
        "I had a great day at the park",
        "USER_MESSAGE",
        0.4,
        0.7,
        ["yesterday it rained all day"],
        ["no hate", "no violence"],
        150.0,
        0.05,
    )
    fallback_vector = _compute_appraisal_fallback(
        "I had a great day at the park",
        "USER_MESSAGE",
        0.4,
        0.7,
        ["yesterday it rained all day"],
        ["no hate", "no violence"],
        150.0,
        0.05,
    )

    assert fallback_vector.relevance == pytest.approx(rust_vector.relevance)
    assert fallback_vector.novelty == pytest.approx(rust_vector.novelty)
    assert fallback_vector.goal_congruence == pytest.approx(rust_vector.goal_congruence)
    assert fallback_vector.agency == pytest.approx(rust_vector.agency)
    assert fallback_vector.norm_alignment == pytest.approx(rust_vector.norm_alignment)
    assert fallback_vector.relationship_impact == pytest.approx(
        rust_vector.relationship_impact
    )


def test_appraisal_fallback_matches_rust_extension_for_high_arousal_and_low_trust():
    """Same as above but exercises the yell/low-trust branches on both sides."""
    rust_vector = cognitive_rust.compute_appraisal(
        "why do you never listen to me",
        "USER_MESSAGE",
        -0.6,
        0.15,
        ["I was talking about the weather"],
        ["never insult the user", "no violence"],
        None,
        0.2,
    )
    fallback_vector = _compute_appraisal_fallback(
        "why do you never listen to me",
        "USER_MESSAGE",
        -0.6,
        0.15,
        ["I was talking about the weather"],
        ["never insult the user", "no violence"],
        None,
        0.2,
    )

    assert fallback_vector.relevance == pytest.approx(rust_vector.relevance)
    assert fallback_vector.novelty == pytest.approx(rust_vector.novelty)
    assert fallback_vector.goal_congruence == pytest.approx(rust_vector.goal_congruence)
    assert fallback_vector.agency == pytest.approx(rust_vector.agency)
    assert fallback_vector.norm_alignment == pytest.approx(rust_vector.norm_alignment)
    assert fallback_vector.relationship_impact == pytest.approx(
        rust_vector.relationship_impact
    )


def test_appraise_falls_back_to_pure_python_when_extension_missing(monkeypatch):
    """The engine must not crash the whole cognitive service when
    `cognitive_rust` is unavailable - it should degrade to the heuristic
    fallback instead of raising an unhandled ImportError."""
    import builtins

    from app.cognitive.appraisal import AppraisalEngine

    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if name == "cognitive_rust":
            raise ImportError("simulated: extension not built for this host")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocking_import)

    engine = AppraisalEngine(identity_core_values=[])
    vector = engine.appraise(
        event_content="hello there",
        event_type="USER_MESSAGE",
        emotional_bias=0.2,
        state_snapshot={"trust": 0.5},
    )

    assert isinstance(vector, AppraisalVector)
    assert vector.relevance == 1.0  # USER_MESSAGE branch


def test_novelty_fallback_returns_high_novelty_with_no_history():
    assert _compute_novelty_fallback("anything", []) == 0.8


def test_norm_alignment_fallback_penalizes_each_boundary_keyword_hit():
    score = _check_norm_alignment_fallback(
        "I will hurt you", ["never hurt anyone", "no violence"]
    )
    assert score < 1.0
