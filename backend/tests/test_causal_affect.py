"""Focused regression tests for Phase 03 causal affect controls."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.cognitive.action_candidate import ActionCandidate, CandidateSelector
from app.cognitive.appraisal import AppraisalRecord, appraise_event
from app.cognitive.global_controls import (
    GlobalControls,
    derive_global_controls,
    endocrine_to_global_controls,
    global_controls_to_endocrine,
)
from app.state.agent_state import StateService
from app.state.memory_records import BeliefRecord, ExperienceRecord


def test_global_controls_clamp_and_scale_with_declared_inputs():
    """Extreme PAD and load values must stay bounded and shift each control."""
    with pytest.raises(ValidationError):
        GlobalControls(urgency_gain=1.01)

    calm = derive_global_controls(
        {"valence": 1.0, "arousal": 0.0},
        load=0.0,
        urgency=0.0,
        prediction_error=0.0,
    )
    threat = derive_global_controls(
        {"valence": -1.0, "arousal": 1.0},
        load=0.0,
        urgency=1.0,
        prediction_error=1.0,
    )
    exhausted = derive_global_controls(
        {"valence": 0.0, "arousal": 0.5},
        load=1.0,
        urgency=1.0,
        prediction_error=0.0,
    )

    for controls in (calm, threat, exhausted):
        assert all(0.0 <= value <= 1.0 for value in controls.model_dump().values())
    assert threat.urgency_gain > calm.urgency_gain
    assert threat.learning_gain > calm.learning_gain
    assert calm.exploration_budget > exhausted.exploration_budget
    assert exhausted.effort_budget < threat.effort_budget


def test_global_controls_reject_nonfinite_inputs_as_neutral():
    """NaN and infinity must not silently become maximum control intensity."""
    neutral = derive_global_controls(
        {"valence": 0.0, "arousal": 0.0},
        load=0.0,
        urgency=0.0,
        prediction_error=0.0,
    )
    nonfinite = derive_global_controls(
        {"valence": float("nan"), "arousal": float("inf")},
        load=float("nan"),
        urgency=float("inf"),
        prediction_error=float("nan"),
    )

    assert nonfinite == neutral
    assert all(0.0 <= value <= 1.0 for value in nonfinite.model_dump().values())


def test_exploration_budget_includes_positive_arousal_at_full_saturation():
    """Architecture Section 10 assigns 0.20 of exploration to arousal."""
    saturated = derive_global_controls(
        {"valence": 1.0, "arousal": 1.0},
        load=0.0,
        urgency=0.0,
        prediction_error=1.0,
    )
    without_arousal = derive_global_controls(
        {"valence": 1.0, "arousal": 0.0},
        load=0.0,
        urgency=0.0,
        prediction_error=1.0,
    )

    assert saturated.exploration_budget == pytest.approx(1.0)
    assert saturated.exploration_budget - without_arousal.exploration_budget == pytest.approx(
        0.20
    )


def test_appraisal_derives_directional_affect_without_mutating_inputs():
    """Goal fit, novelty, and control must produce the specified PAD directions."""
    event = {
        "event_id": "resolved-task",
        "goal_ids": ["help-user"],
        "novelty": 0.9,
        "controllability": 1.0,
        "agency": 0.5,
    }
    active_goals = ["help-user"]
    event_before = copy.deepcopy(event)
    goals_before = list(active_goals)

    congruent = appraise_event(event, active_goals, expectation=1.0)
    incongruent = appraise_event(
        {"event_id": "blocked-task", "goal_incongruent": True}, active_goals,
        expectation=1.0,
    )
    expected = appraise_event({"event_id": "routine", "novelty": 0.0}, [], 1.0)

    assert congruent.goal_congruence > incongruent.goal_congruence
    assert congruent.affect_delta["pleasure"] > 0.0
    assert incongruent.affect_delta["pleasure"] < 0.0
    assert congruent.affect_delta["arousal"] > expected.affect_delta["arousal"]
    assert congruent.expectation < expected.expectation
    assert congruent.affect_delta["dominance"] > 0.0
    assert event == event_before
    assert active_goals == goals_before
    with pytest.raises(TypeError):
        congruent.affect_delta["pleasure"] = 999.0


@pytest.mark.asyncio
async def test_appraise_and_apply_event_uses_structured_appraisal_inputs(tmp_path):
    """Live state updates must use appraisal values, not relevance proxies."""
    state = StateService(
        db_path=str(tmp_path / "structured-appraisal.db"),
        redis_host="127.0.0.1",
        redis_port=1,
    )

    appraisal, controls = await state.appraise_and_apply_event(
        {
            "event_id": "blocked-task",
            "goal_incongruent": True,
            "novelty": 0.8,
        },
        active_goals=["help-user"],
    )

    assert isinstance(appraisal, AppraisalRecord)
    assert appraisal.event_id == "blocked-task"
    assert appraisal.goal_congruence == -1.0
    assert controls is state.get_global_controls()
    assert controls.urgency_gain > 0.5


@pytest.mark.asyncio
async def test_adrenaline_release_refreshes_urgency_gain_immediately(tmp_path):
    """A startle burst must affect action urgency before the next state update."""
    state = StateService(
        db_path=str(tmp_path / "adrenaline-controls.db"),
        redis_host="127.0.0.1",
        redis_port=1,
    )
    before = state.get_global_controls().urgency_gain

    await state.release_adrenaline(0.6, reason="test")

    assert state.get_global_controls().urgency_gain > before


def test_endocrine_adapters_preserve_legacy_control_meanings():
    """Legacy consumers retain cortisol, dopamine, and fatigue equivalents."""
    controls = endocrine_to_global_controls(cortisol=0.8, dopamine=0.3, fatigue=0.4)
    legacy = global_controls_to_endocrine(controls)

    assert controls.urgency_gain == pytest.approx(0.8)
    assert controls.exploration_budget == pytest.approx(0.3)
    assert controls.effort_budget == pytest.approx(0.6)
    assert legacy == pytest.approx(
        {"cortisol": 0.8, "dopamine": 0.3, "fatigue": 0.4}
    )


@pytest.mark.asyncio
async def test_affect_controls_cannot_mutate_belief_truth_or_evidence(tmp_path):
    """Affect updates must remain isolated from factual records and evidence."""
    state = StateService(
        db_path=str(tmp_path / "causal-affect.db"), redis_host="127.0.0.1", redis_port=1
    )
    belief = BeliefRecord(
        record_id="belief-unchanged",
        subject="sky",
        predicate="color",
        object="blue",
        valid_from=1.0,
        provenance="observation",
    )
    experience = ExperienceRecord(
        record_id="experience-unchanged",
        session_id="session-1",
        participants=["user"],
        interval_start=1.0,
        interval_end=2.0,
        source_evidence_ids=["evidence-1"],
        summary="Observed a blue sky.",
    )
    belief_before = belief.model_dump()
    experience_before = experience.model_dump()

    controls = await state.apply_affect_delta(
        {"pleasure": -0.8, "arousal": 0.6, "dominance": -0.2},
        urgency=0.9,
        prediction_error=0.8,
    )

    assert controls is state.get_global_controls()
    assert controls.urgency_gain > GlobalControls().urgency_gain
    assert belief.model_dump() == belief_before
    assert experience.model_dump() == experience_before


def test_global_controls_are_immutable_action_selection_inputs():
    """Selection may read controls but cannot rewrite a supplied control snapshot."""
    controls = GlobalControls(urgency_gain=0.9, exploration_budget=0.2)
    original = controls.model_dump()
    selector = CandidateSelector()
    candidate = ActionCandidate(
        candidate_id="safe-wait",
        kind="WAIT",
        source="test",
        score=0.1,
    )

    selector.score_and_select([candidate], active_goals=[])

    assert controls.model_dump() == original
    with pytest.raises(ValidationError):
        controls.urgency_gain = 0.1


def test_phase03_owned_files_are_ascii_only():
    """Phase 03 sources must remain portable 7-bit ASCII artifacts."""
    repository_root = Path(__file__).resolve().parents[2]
    owned_files = [
        repository_root / "backend/app/cognitive/global_controls.py",
        repository_root / "backend/app/cognitive/appraisal.py",
        repository_root / "backend/app/state/agent_state.py",
        repository_root / "backend/tests/test_causal_affect.py",
    ]
    orchestration_file = repository_root / "orchestration/PHASE_03/CODEX_RESULT.md"
    if orchestration_file.exists():
        owned_files.append(orchestration_file)

    for path in owned_files:
        assert path.exists(), f"Missing owned file: {path}"
        assert all(byte < 128 for byte in path.read_bytes()), path

