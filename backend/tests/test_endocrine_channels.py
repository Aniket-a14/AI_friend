"""
The events that actually move the hormones.

Both hormones had a release API and almost nothing calling it: one channel for
dopamine (somatic comfort recognition) and none at all for cortisol. A hormone
with no channel is only a formula — it can be released in a unit test and never
by anything the agent experiences.

Two channels here:

**Reward prediction error → both hormones.** Not outcome. Firing a burst on any
good turn would double-count what tonic dopamine already tracks, since the tonic
term is valence × arousal and a good turn raises valence by itself. Phasic
dopamine signals *better than expected* (Schultz), and the reappraisal module was
already computing that exact quantity and discarding it after tuning weights.

**Self-correction → cortisol.** Catching yourself mid-sentence about to violate
your own identity constraints is a stressor.
"""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.appraisal import AppraisalVector
from app.cognitive.decision import ActionPlan
from app.cognitive.pipeline import (
    PREDICTION_ERROR_DEADBAND,
    REWARD_PREDICTION_GAIN,
    SELF_CORRECTION_STRESS,
    STRESS_PREDICTION_GAIN,
    CognitivePipeline,
)
from app.cognitive.reappraisal import ReappraisalEngine
from app.state.agent_state import StateService


def _pipeline():
    """A pipeline with a real StateService and everything else stubbed."""
    service = StateService(graph_store=None, db_path=":memory:")
    service.current_state.mood = 0.0
    service.current_state.fatigue = 0.0
    pipeline = CognitivePipeline(*[MagicMock()] * 7)
    pipeline.state = service
    return pipeline, service


# --------------------------------------------------------------------------
# reward prediction error
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_better_than_expected_turn_fires_a_reward_burst():
    """The reward channel. Without it phasic dopamine is unreachable in practice.

    Only the somatic vision path could fire it before, so an agent with no
    camera had a reward hormone that never once fired.
    """
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(0.8)
    assert service.current_state.dopamine_phasic_peak == pytest.approx(
        0.8 * REWARD_PREDICTION_GAIN
    )
    assert service.current_state.cortisol_phasic_peak == 0.0


@pytest.mark.asyncio
async def test_a_worse_than_expected_turn_fires_a_stress_burst():
    """The stress channel — cortisol previously had none at all."""
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(-0.8)
    assert service.current_state.cortisol_phasic_peak == pytest.approx(
        0.8 * STRESS_PREDICTION_GAIN
    )
    assert service.current_state.dopamine_phasic_peak == 0.0


@pytest.mark.asyncio
async def test_disappointment_hits_harder_than_delight():
    """Negativity bias, and the safer failure direction.

    Cortisol narrows the agent's own sampling temperature, so over-reacting to
    a bad turn degrades gracefully while over-reacting to a good one makes it
    erratic exactly when it is already doing well.
    """
    assert STRESS_PREDICTION_GAIN > REWARD_PREDICTION_GAIN

    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(-0.5)
    stress = service.current_state.cortisol_phasic_peak

    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(0.5)
    reward = service.current_state.dopamine_phasic_peak

    assert stress > reward


@pytest.mark.asyncio
async def test_no_evaluation_is_not_the_same_as_no_surprise():
    """`None` means reappraisal declined to evaluate; `0.0` means "as expected".

    Conflating them would push a zero-amount release on every turn the module
    skipped. That is harmless today *only* because the release methods reject
    non-positive amounts — a coincidence downstream, not a guarantee here.
    """
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(None)
    assert service.current_state.dopamine_phasic_peak == 0.0
    assert service.current_state.cortisol_phasic_peak == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [0.0, 0.05, -0.05, PREDICTION_ERROR_DEADBAND - 1e-9])
async def test_an_unsurprising_turn_fires_nothing(error):
    """A fully expected reward must not fire a phasic burst — that is the model.

    Without a deadband the hormones would twitch on every turn's rounding noise
    and the phasic terms would never return to zero.
    """
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(error)
    assert service.current_state.dopamine_phasic_peak == 0.0
    assert service.current_state.cortisol_phasic_peak == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [float("nan"), float("inf"), float("-inf"), "big", object()]
)
async def test_a_malformed_prediction_error_moves_no_hormone(error):
    """NaN passes `abs(x) < deadband` (False) and would reach the release path.

    The release methods have their own finiteness guard, but relying on it from
    here means a caller bug shows up as a hormone reading rather than as an
    ignored input.
    """
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(error)
    assert service.current_state.dopamine_phasic_peak == 0.0
    assert service.current_state.cortisol_phasic_peak == 0.0


@pytest.mark.asyncio
async def test_an_enormous_prediction_error_cannot_push_cortisol_past_its_ceiling():
    """A runaway signal must clamp at the ceiling rather than overflow it.

    `cortisol <= 1.0` alone would be vacuous: with the release deleted entirely
    the hormone sits at its 0.5 tonic baseline and still satisfies it. So assert
    that the burst both landed and stopped at the top.

    Approximate, not exact: the phasic term begins decaying the moment it is
    recorded, so the total is asymptotically 1.0 (0.99999998 here) and never
    precisely it. `== 1.0` would pass or fail on scheduling luck.
    """
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(-500.0)
    assert service.current_state.cortisol_phasic_peak > 0.0
    assert service.current_state.cortisol == pytest.approx(1.0)
    assert service.current_state.cortisol <= 1.0


@pytest.mark.asyncio
async def test_a_mood_collapse_after_a_burst_cannot_push_cortisol_over_one():
    """The tonic floor can rise *underneath* a burst that is already at the top.

    `release_cortisol` clamps the total at release time, but the phasic peak it
    stores is relative to whatever the tonic floor was *then*. If mood then
    collapses, tonic climbs independently and the sum exceeds 1.0 — here 0.5 +
    0.5 becomes roughly 0.9 + 0.5. Only the clamp on the `cortisol` property
    catches that, which is why the release-time clamp alone is not enough.

    It matters because `_compute_endocrine_options` maps cortisol onto sampling
    temperature; a value above 1.0 walks straight out of the intended range.
    """
    pipeline, service = _pipeline()
    await pipeline._apply_reward_prediction_error(-500.0)
    assert service.current_state.cortisol == pytest.approx(1.0)

    # The floor rises after the fact.
    service.current_state.mood = -1.0
    assert service.current_state.cortisol_tonic > 0.5, "fixture failed to lift tonic"
    assert (
        service.current_state.cortisol_tonic + service.current_state.cortisol_phasic
        > 1.0
    ), "fixture does not actually exercise the property clamp"

    assert service.current_state.cortisol <= 1.0


@pytest.mark.asyncio
async def test_a_failing_endocrine_release_does_not_break_the_turn():
    """The hormone modulates how the agent speaks, not whether it can.

    If a release raises, the user must still get their answer.
    """
    pipeline, _ = _pipeline()

    async def boom(*args, **kwargs):
        raise RuntimeError("redis down")

    pipeline.state.release_dopamine = boom
    await pipeline._apply_reward_prediction_error(0.8)  # must not raise


# --------------------------------------------------------------------------
# self-correction
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catching_your_own_violation_raises_cortisol():
    """A metacognitive violation is the clearest stressor the agent has."""
    pipeline, service = _pipeline()
    before = service.current_state.cortisol
    await pipeline._apply_self_correction_stress("Safety/Toxicity boundary violation")
    assert service.current_state.cortisol_phasic_peak > 0.0
    assert service.current_state.cortisol > before


@pytest.mark.asyncio
async def test_the_self_correction_event_is_consumed_not_forwarded():
    """Downstream consumers switch on a small set of chunk types.

    An unrecognised one reaches the transport as a malformed message, so this
    internal signal must be swallowed by the pipeline that acts on it.
    """
    pipeline, service = _pipeline()

    # The real routing method, not a copy of it in the test.
    assert await pipeline._consume_internal_chunk(
        {"type": "self_correction", "data": "boundary violation"}
    ) is True
    assert await pipeline._consume_internal_chunk({"type": "content", "data": "hi"}) is False
    assert await pipeline._consume_internal_chunk({"type": "done"}) is False

    assert service.current_state.cortisol_phasic_peak == pytest.approx(
        SELF_CORRECTION_STRESS
    )


def _full_pipeline_with_failing_validation(retry_chunks):
    """A pipeline driven through `execute()`, forced down the retry branch.

    `validate_response` rejects the first response and accepts the second, which
    is the only way to reach the second `action.execute` loop in stage 9.
    """
    service = StateService(graph_store=None, db_path=":memory:")
    service.current_state.mood = 0.0
    service.current_state.fatigue = 0.0

    perception = AsyncMock()
    perception.perceive.return_value = MagicMock(
        event_type="USER_MESSAGE",
        raw_content="hello",
        intent="CHAT",
        event_id="evt-retry",
        metadata={},
    )
    appraisal = MagicMock()
    appraisal.appraise.return_value = AppraisalVector(
        relevance=1.0,
        novelty=0.5,
        goal_congruence=0.2,
        agency=0.8,
        norm_alignment=1.0,
        relationship_impact=0.1,
    )
    decision = MagicMock()
    decision.decide = AsyncMock(
        return_value=ActionPlan(
            action_type="RESPOND_CHAT",
            goal="GREET",
            payload={"message": "hi", "identity_prompt": "be yourself"},
        )
    )

    calls = {"n": 0}

    async def execute(plan):
        calls["n"] += 1
        if calls["n"] == 1:
            yield {"type": "content", "data": "first attempt"}
            yield {"type": "done", "data": ""}
        else:
            for chunk in retry_chunks:
                yield chunk

    action = MagicMock()
    action.execute.side_effect = execute

    identity = MagicMock()
    identity.get_persona_prompt.return_value = "System prompt"
    identity.validate_response = AsyncMock(
        side_effect=[(False, "Safety/Toxicity boundary violation"), (True, "")]
    )

    pipeline = CognitivePipeline(
        perception=perception,
        appraisal=appraisal,
        state=service,
        decision=decision,
        action=action,
        learning=AsyncMock(),
        identity=identity,
    )
    return pipeline, service, calls


@pytest.mark.asyncio
async def test_the_self_correction_signal_is_consumed_on_the_retry_pass_too():
    """Stage 9's retry loop is a second, easy-to-forget copy of the action loop.

    It is also the likeliest place to emit this signal: it runs only after a
    response was already rejected, with a hardened prompt. Filtering the first
    loop and not this one would leak `self_correction` to the transport on the
    exact path that most deserves the cortisol, and the bug would be invisible
    to any test that only drives the happy path.
    """
    pipeline, service, calls = _full_pipeline_with_failing_validation(
        [
            {"type": "content", "data": "corrected attempt"},
            {"type": "self_correction", "data": "Safety/Toxicity boundary violation"},
            {"type": "done", "data": ""},
        ]
    )

    results = [c async for c in pipeline.execute({"type": "USER_MESSAGE", "content": "hi"})]

    assert calls["n"] == 2, "the retry branch was never reached"
    assert not any(c["type"] == "self_correction" for c in results), (
        "internal signal leaked to the transport from the retry loop"
    )
    assert any(
        c["type"] == "content" and c["data"] == "corrected attempt" for c in results
    ), "the retry's real content must still reach the user"
    assert service.current_state.cortisol_phasic_peak > 0.0, (
        "the retry's self-correction must still raise cortisol"
    )


# --------------------------------------------------------------------------
# the reappraisal contract this depends on
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reappraisal_reports_the_error_with_the_reward_sign_convention():
    """`evaluate_outcome` returns actual − expected, not its internal delta.

    It computes `delta = expected − actual` for weight updates. Returning that
    raw would invert the endocrine channel: every pleasant surprise would fire
    cortisol and every disappointment dopamine. The sign flip is load-bearing.
    """
    engine = ReappraisalEngine()
    if not engine.enabled:
        pytest.skip("reappraisal disabled by config")

    engine.record_pre_response_state({"valence": 0.0, "arousal": 0.5})
    engine.record_expected_outcome("COMFORT", current_valence=0.0)  # expects +0.3
    engine._last_evaluation_time = 0.0

    # Actual outcome far above the expectation → positive prediction error.
    error = await engine.evaluate_outcome(actual_text_valence=0.9, behavioral_signal=0.9)
    assert error is not None
    assert error > 0


@pytest.mark.asyncio
async def test_reappraisal_returns_none_rather_than_zero_when_it_does_not_evaluate():
    """The distinction the pipeline relies on to tell "quiet" from "expected"."""
    engine = ReappraisalEngine()
    # No expectation recorded for this turn.
    assert await engine.evaluate_outcome(actual_text_valence=0.9) is None


@pytest.mark.asyncio
async def test_an_outcome_within_tolerance_reports_no_prediction_error():
    """Reappraisal already ignores |delta| < 0.1 for weight updates.

    Reporting a prediction error it declined to learn from would give the
    endocrine channel a second, looser definition of "significant".
    """
    engine = ReappraisalEngine()
    if not engine.enabled:
        pytest.skip("reappraisal disabled by config")

    engine.record_pre_response_state({"valence": 0.0, "arousal": 0.5})
    engine.record_expected_outcome("COMFORT", current_valence=0.0)
    engine._last_evaluation_time = 0.0

    # Chosen so actual_outcome lands within 0.1 of the 0.3 expectation.
    error = await engine.evaluate_outcome(
        actual_text_valence=0.4, acoustic_delta=0.0, behavioral_signal=0.5
    )
    # Flatly `None`, not "None or something the deadband would filter": the
    # weaker form would still pass if the tolerance branch started reporting a
    # hormone-eligible signal, which is the exact regression this guards.
    assert error is None


def test_the_gains_keep_a_single_turn_from_saturating_a_hormone():
    """One surprising turn should colour the next few minutes, not max out."""
    assert 0.0 < REWARD_PREDICTION_GAIN < 1.0
    assert 0.0 < STRESS_PREDICTION_GAIN < 1.0
    assert 0.0 < SELF_CORRECTION_STRESS < 1.0
    assert math.isfinite(PREDICTION_ERROR_DEADBAND) and PREDICTION_ERROR_DEADBAND > 0.0
