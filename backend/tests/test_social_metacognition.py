"""Focused regression coverage for Phase 04 Package A social state."""

from pathlib import Path

import pytest

from app.cognitive.calibration import (
    CapabilityLimitationModel,
    DomainCalibration,
    MetacognitiveDirective,
)
from app.state.agent_state import AgentState, StateService
from app.state.person_model import PersonModel


def test_person_model_initialization_defaults():
    """A new person starts with isolated mutable collections and neutral trust."""
    person = PersonModel(person_id="alex")

    assert person.name is None
    assert person.current_knowledge == {}
    assert person.disclosures == []
    assert person.trust_competence == 0.5
    assert person.trust_benevolence == 0.5


def test_trust_updates_from_reliance_success_and_failure():
    """Reliance failures reduce trust faster than equivalent successes raise it."""
    person = PersonModel(person_id="alex")

    person.update_trust_from_reliance(outcome_success=True, stake_weight=0.5)
    assert person.trust_competence == pytest.approx(0.525)
    assert person.trust_benevolence == pytest.approx(0.51)

    person.update_trust_from_reliance(outcome_success=False, stake_weight=0.5)
    assert person.trust_competence == pytest.approx(0.45)
    assert person.trust_benevolence == pytest.approx(0.46)


def test_rupture_and_repair_asymmetry():
    """A rupture must drop benevolence three times as much as a same-size repair."""
    person = PersonModel(person_id="alex")

    person.record_rupture_repair("rupture", magnitude=0.2, notes="broken promise")
    assert person.trust_benevolence == pytest.approx(0.2)

    person.record_rupture_repair("repair", magnitude=0.2, notes="made amends")
    assert person.trust_benevolence == pytest.approx(0.3)
    assert len(person.rupture_repair_history) == 2
    assert all("timestamp" in entry for entry in person.rupture_repair_history)


def test_cross_person_disclosure_isolation():
    """Private facts cannot cross owner boundaries regardless of relationship state."""
    alex = PersonModel(person_id="alex", trust_benevolence=1.0)

    assert alex.can_disclose("alex", "alex") is True
    assert alex.can_disclose("bea", "alex") is False
    assert alex.can_disclose("bea", "alex", is_private=False) is True
    assert alex.can_disclose("bea", None) is True

    alex.record_disclosure("fact-1", context="asked directly")
    assert alex.disclosures[0]["fact_id"] == "fact-1"
    assert "timestamp" in alex.disclosures[0]


def test_domain_calibration_brier_score_tracking():
    """Incremental observations must retain the running empirical Brier score."""
    calibration = DomainCalibration(domain="weather")

    calibration.record_observation(predicted_prob=0.8, actual_binary_outcome=1)
    calibration.record_observation(predicted_prob=0.2, actual_binary_outcome=1)

    assert calibration.sample_count == 2
    assert calibration.brier_score == pytest.approx(0.34)
    assert calibration.calibrate(0.8) == pytest.approx(0.664)


def test_capability_limitation_abstention():
    """A declared limitation must override otherwise high calibrated confidence."""
    model = CapabilityLimitationModel(known_limitations=["medical diagnosis"])

    directive, confidence = model.evaluate_directive(
        domain="medical",
        raw_confidence=0.99,
        query="Please give a medical diagnosis.",
    )

    assert directive is MetacognitiveDirective.ABSTAIN
    assert confidence == 0.0


@pytest.mark.parametrize(
    ("raw_confidence", "expected_directive"),
    [
        (0.75, MetacognitiveDirective.PROCEED),
        (0.50, MetacognitiveDirective.HEDGE),
        (0.30, MetacognitiveDirective.ASK_CLARIFICATION),
        (0.29, MetacognitiveDirective.VERIFY),
    ],
)
def test_metacognitive_directive_thresholds(raw_confidence, expected_directive):
    """Threshold boundaries must map to their deterministic directive."""
    model = CapabilityLimitationModel()

    directive, confidence = model.evaluate_directive("general", raw_confidence)

    assert directive is expected_directive
    assert confidence == raw_confidence


@pytest.mark.asyncio
async def test_agent_state_person_model_integration():
    """Active person outcomes update only that person and legacy trust mirrors."""
    initial_state = AgentState()
    assert initial_state.active_person_id == "default_user"
    assert initial_state.persons == {}
    assert initial_state.capability_model.known_limitations == []

    service = StateService(graph_store=None, db_path=":memory:")
    service.redis_client = None
    service.current_state.active_person_id = "alex"
    service.current_state.persons["alex"] = PersonModel(
        person_id="alex", trust_competence=0.8, trust_benevolence=0.6
    )

    await service.update_active_person_reliance(False, stake_weight=0.5)
    active_person = service.get_active_person_model()

    assert active_person.person_id == "alex"
    assert active_person.trust_competence == pytest.approx(0.725)
    assert active_person.trust_benevolence == pytest.approx(0.55)
    assert service.current_state.trust_competence == pytest.approx(0.725)
    assert service.current_state.trust_benevolence == pytest.approx(0.55)
    assert service.current_state.persons["default_user"].trust_competence != pytest.approx(
        0.725
    )

    await service.record_active_person_rupture_repair("rupture", 0.2)
    assert service.current_state.trust_benevolence == pytest.approx(0.25)


def test_phase04_codex_files_are_ascii_only():
    """Phase 04 source and test artifacts must remain portable 7-bit ASCII."""
    repository_root = Path(__file__).resolve().parents[2]
    phase_files = [
        repository_root / "backend/app/state/person_model.py",
        repository_root / "backend/app/cognitive/calibration.py",
        repository_root / "backend/app/state/agent_state.py",
        repository_root / "backend/tests/test_social_metacognition.py",
    ]

    for path in phase_files:
        assert path.read_bytes().isascii(), f"non-ASCII byte found in {path}"
