"""PersonaPolicy.precheck (Phase 1B, §15 item 5) -- the proactive check on a
BehaviorDecision before generation, sitting next to (not replacing)
IdentityManager.validate_response's reactive regex check."""

from app.cognitive.behavior_contracts import BehaviorDecision, CommunicativeIntent
from app.persona.policy import PersonaPolicy

_DEFAULT_CORE = {
    "values": ["Honesty", "Privacy"],
    "boundaries": [
        "Will never share user data",
        "Will not adopt toxic behavior",
    ],
}


def test_precheck_populates_forbidden_claims_from_boundaries():
    decision = BehaviorDecision(
        intent=CommunicativeIntent(act="CHAT", goal="ENGAGE")
    )
    result = PersonaPolicy.precheck(decision, _DEFAULT_CORE)
    assert result.forbidden_claims == _DEFAULT_CORE["boundaries"]


def test_precheck_does_not_clamp_stance_under_default_boundaries():
    """Today's default IMMUTABLE_CORE (privacy, non-toxicity) says nothing
    about relational closeness -- "close" must pass through unclamped."""
    decision = BehaviorDecision(
        intent=CommunicativeIntent(act="CHAT", goal="ENGAGE", relational_stance="close")
    )
    result = PersonaPolicy.precheck(decision, _DEFAULT_CORE)
    assert result.intent.relational_stance == "close"


def test_precheck_clamps_stance_when_a_boundary_restricts_it():
    core = {
        "values": ["Honesty"],
        "boundaries": ["Will not engage in romantic or sexual roleplay"],
    }
    decision = BehaviorDecision(
        intent=CommunicativeIntent(act="CHAT", goal="ENGAGE", relational_stance="close")
    )
    result = PersonaPolicy.precheck(decision, core)
    assert result.intent.relational_stance == "warm"


def test_precheck_leaves_an_already_capped_stance_alone():
    core = {
        "values": [],
        "boundaries": ["Will not engage in romantic or sexual roleplay"],
    }
    decision = BehaviorDecision(
        intent=CommunicativeIntent(
            act="CHAT", goal="ENGAGE", relational_stance="guarded"
        )
    )
    result = PersonaPolicy.precheck(decision, core)
    assert result.intent.relational_stance == "guarded"


def test_precheck_does_not_mutate_the_input_decision():
    """A caller holding a reference to the pre-precheck decision (e.g. for
    logging) must not see it change underfoot."""
    decision = BehaviorDecision(
        intent=CommunicativeIntent(act="CHAT", goal="ENGAGE", relational_stance="close")
    )
    core = {"boundaries": ["Will not engage in romantic or sexual roleplay"]}
    PersonaPolicy.precheck(decision, core)
    assert decision.intent.relational_stance == "close"
    assert decision.forbidden_claims == []
