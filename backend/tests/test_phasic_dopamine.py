"""
Phasic dopamine — reward that outlives the mood swing that caused it.

`dopamine` used to be a pure function of current valence and arousal, which
meant it had no memory: the instant mood drifted back, the reward was gone, and
the roadmap's `D_t = min(1.0, D_{t-1} + 0.25)` had no `D_{t-1}` to add to. It is
now a tonic term (the old formula, unchanged) plus a decaying phasic burst.

The first test below is the important one: with no burst outstanding the value
is bit-for-bit what it always was, so nothing downstream shifts underneath.
"""

import asyncio
import math
import time
from unittest.mock import AsyncMock

import pytest

from app.config import Config
from app.state.agent_state import SOMATIC_DOPAMINE_SPIKE, AgentState, StateService


def _old_derived_dopamine(state: AgentState) -> float:
    """The formula exactly as it stood before phasic dopamine existed."""
    return max(0.0, min(1.0, max(0.0, state.valence) * state.arousal))


def _state_service():
    service = StateService(graph_store=None)
    service._persist_sensory_state_if_due = AsyncMock(return_value=None)
    return service


# --------------------------------------------------------------------------
# backward compatibility
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mood,energy",
    [(0.8, 0.7), (-0.5, 0.9), (1.0, 0.0), (1.0, 1.0), (0.0, 0.5), (0.33, 0.66)],
)
def test_without_a_burst_dopamine_is_exactly_the_old_derived_value(mood, energy):
    """No burst outstanding must be indistinguishable from the old behaviour."""
    state = AgentState(mood=mood, energy=energy)
    assert state.dopamine_phasic == 0.0
    assert state.dopamine == pytest.approx(_old_derived_dopamine(state))


def test_tonic_term_is_the_old_formula():
    state = AgentState(mood=0.8, energy=0.7)
    assert state.dopamine_tonic == pytest.approx(0.56, abs=0.01)


# --------------------------------------------------------------------------
# the roadmap equation, now literally implementable
# --------------------------------------------------------------------------


def test_release_implements_the_roadmap_increment():
    """D_t = min(1.0, D_{t-1} + 0.25)."""
    state = AgentState(mood=0.4, energy=0.5)  # tonic = 0.20
    before = state.dopamine

    after = state.release_dopamine(0.25)

    assert after == pytest.approx(min(1.0, before + 0.25))
    assert state.dopamine == pytest.approx(after)


def test_release_saturates_at_one():
    state = AgentState(mood=1.0, energy=1.0)  # tonic = 1.0 already
    assert state.release_dopamine(0.5) == pytest.approx(1.0)


def test_successive_releases_accumulate_toward_the_cap():
    state = AgentState(mood=0.0, energy=0.5)  # tonic = 0.0
    first = state.release_dopamine(0.25)
    second = state.release_dopamine(0.25)

    assert first == pytest.approx(0.25)
    assert second == pytest.approx(0.5)


@pytest.mark.parametrize("amount", [0.0, -0.3, None, "lots"])
def test_a_non_positive_or_invalid_release_is_a_no_op(amount):
    state = AgentState(mood=0.4, energy=0.5)
    before = state.dopamine

    assert state.release_dopamine(amount) == pytest.approx(before)
    assert state.dopamine_phasic_peak == 0.0


@pytest.mark.parametrize("amount", [0.0, -0.5, None, "lots"])
def test_a_non_positive_release_cannot_eat_an_outstanding_burst(amount):
    """With no burst outstanding the guard looks redundant -- a negative amount
    clamps to zero anyway. It is load-bearing only once a burst exists, which is
    exactly the case worth protecting: reward must not be cancellable by a bad
    caller passing a negative number."""
    state = AgentState(mood=0.0, energy=0.5)
    state.release_dopamine(0.6)
    peak = state.dopamine_phasic_peak

    state.release_dopamine(amount)

    assert state.dopamine_phasic_peak == pytest.approx(peak)


@pytest.mark.parametrize(
    "amount", [float("nan"), float("inf"), float("-inf")]
)
def test_a_non_finite_release_is_ignored(amount):
    """NaN survives float() and then defeats every comparison: `nan <= 0.0` is
    False so it passes the guard, and `min(1.0, nan)` returns 1.0 -- so before
    this check a NaN reward fired a *maximum* burst."""
    state = AgentState(mood=0.0, energy=0.5)
    before = state.dopamine

    assert state.release_dopamine(amount) == pytest.approx(before)
    assert state.dopamine_phasic_peak == 0.0


@pytest.mark.parametrize("amount", [float("nan"), float("inf")])
def test_a_non_finite_release_cannot_disturb_an_outstanding_burst(amount):
    state = AgentState(mood=0.0, energy=0.5)
    state.release_dopamine(0.4)
    peak = state.dopamine_phasic_peak

    state.release_dopamine(amount)

    assert state.dopamine_phasic_peak == pytest.approx(peak)


def test_repeated_releases_cannot_build_an_unboundedly_long_burst():
    """The cap belongs inside release, not only on the reported value. Storing
    an over-large peak would read as 1.0 after clamping while taking many extra
    half-lives to fall back -- the agent pinned at peak reward far too long."""
    state = AgentState(mood=0.0, energy=0.5)
    for _ in range(20):
        state.release_dopamine(0.25)

    assert state.dopamine_phasic_peak <= 1.0
    state.dopamine_phasic_at -= Config.DOPAMINE_PHASIC_HALFLIFE_S * 3
    assert state.dopamine < 0.2


# --------------------------------------------------------------------------
# decay
# --------------------------------------------------------------------------


def test_burst_halves_after_one_half_life():
    state = AgentState(mood=0.0, energy=0.5)  # tonic = 0.0, isolates the burst
    state.release_dopamine(0.8)
    peak = state.dopamine_phasic

    state.dopamine_phasic_at -= Config.DOPAMINE_PHASIC_HALFLIFE_S

    assert state.dopamine_phasic == pytest.approx(peak / 2, rel=1e-3)


def test_burst_decays_toward_nothing():
    state = AgentState(mood=0.0, energy=0.5)
    state.release_dopamine(1.0)

    state.dopamine_phasic_at -= Config.DOPAMINE_PHASIC_HALFLIFE_S * 20

    assert state.dopamine_phasic == pytest.approx(0.0, abs=1e-5)
    # approx(0.0) defaults to abs=1e-12, which a residual burst legitimately
    # exceeds; the claim here is convergence to the tonic floor, not equality.
    assert state.dopamine == pytest.approx(state.dopamine_tonic, abs=1e-5)


def test_decay_is_time_based_not_tick_based():
    """The level must be right even if system.tick never runs."""
    state = AgentState(mood=0.0, energy=0.5)
    state.release_dopamine(0.6)

    elapsed = Config.DOPAMINE_PHASIC_HALFLIFE_S * 0.5
    state.dopamine_phasic_at -= elapsed
    expected = 0.6 * math.exp(
        -math.log(2.0) * elapsed / Config.DOPAMINE_PHASIC_HALFLIFE_S
    )

    assert state.dopamine_phasic == pytest.approx(expected, rel=1e-3)


def test_dopamine_never_falls_below_its_tonic_floor():
    state = AgentState(mood=0.8, energy=0.7)  # tonic = 0.56
    state.release_dopamine(0.3)
    state.dopamine_phasic_at -= Config.DOPAMINE_PHASIC_HALFLIFE_S * 50

    assert state.dopamine == pytest.approx(state.dopamine_tonic)
    assert state.dopamine == pytest.approx(0.56, abs=0.01)


def test_tonic_may_drift_under_a_live_burst_without_double_counting():
    """The burst is stored relative to the tonic floor, so a later mood change
    moves the floor rather than being folded into the burst."""
    state = AgentState(mood=0.0, energy=0.5)  # tonic 0.0
    state.release_dopamine(0.4)
    assert state.dopamine == pytest.approx(0.4)

    state.mood = 0.6  # tonic becomes 0.30
    assert state.dopamine_tonic == pytest.approx(0.30, abs=0.01)
    # 0.30 floor + the 0.40 burst still outstanding.
    assert state.dopamine == pytest.approx(0.70, abs=0.01)


def test_dopamine_stays_within_bounds_when_tonic_rises_under_a_burst():
    state = AgentState(mood=0.0, energy=1.0)
    state.release_dopamine(0.9)
    state.mood = 1.0  # tonic jumps to 1.0 beneath a 0.9 burst

    assert 0.0 <= state.dopamine <= 1.0


# --------------------------------------------------------------------------
# the behavioural payoff, through the somatic path
# --------------------------------------------------------------------------


def test_somatic_reward_outlives_the_valence_it_arrived_with():
    """The point of the whole change. Previously, mood drifting back to neutral
    erased the reward instantly, because dopamine was a pure function of it."""
    service = _state_service()
    service.current_state.mood = 0.0
    service.current_state.energy = 0.5

    asyncio.run(
        service.apply_somatic_perception(
            {"entities": ["chai"], "valence_spike": 0.15, "arousal_spike": 0.10}
        )
    )
    spiked = service.current_state.dopamine

    # The mood swing fades, as ALMA decay would eventually take it.
    service.current_state.mood = 0.0
    service.current_state.energy = 0.5

    surviving = service.current_state.dopamine
    assert service.current_state.dopamine_tonic == pytest.approx(0.0)
    # The tonic contribution correctly leaves with the mood; the burst does not.
    # Under the old derived-only dopamine this would now be exactly 0.0.
    assert surviving > 0.0, "reward vanished with the mood"
    assert surviving == pytest.approx(SOMATIC_DOPAMINE_SPIKE, abs=0.02)
    assert surviving < spiked


def test_somatic_perception_fires_a_burst_of_the_roadmap_size():
    service = _state_service()
    service.current_state.mood = 0.0
    service.current_state.energy = 0.5

    asyncio.run(
        service.apply_somatic_perception(
            {"entities": ["chai"], "valence_spike": 0.0, "arousal_spike": 0.0001}
        )
    )

    assert service.current_state.dopamine_phasic == pytest.approx(
        SOMATIC_DOPAMINE_SPIKE, abs=0.01
    )


def test_caller_may_override_the_burst_size():
    service = _state_service()
    service.current_state.mood = 0.0
    service.current_state.energy = 0.5

    asyncio.run(
        service.apply_somatic_perception(
            {
                "entities": ["chai"],
                "valence_spike": 0.1,
                "arousal_spike": 0.0,
                "dopamine_spike": 0.05,
            }
        )
    )

    assert service.current_state.dopamine_phasic == pytest.approx(0.05, abs=0.01)


def test_a_non_match_fires_no_burst():
    service = _state_service()
    asyncio.run(service.apply_somatic_perception(None))
    assert service.current_state.dopamine_phasic == 0.0


def test_snapshot_reports_the_burst():
    service = _state_service()
    service.current_state.mood = 0.0
    service.current_state.energy = 0.5
    service.current_state.release_dopamine(0.4)

    snapshot = service.get_context_snapshot()

    assert snapshot["dopamine"] == pytest.approx(0.4, abs=0.01)


def test_a_fresh_state_starts_with_no_outstanding_burst():
    state = AgentState()
    assert state.dopamine_phasic_peak == 0.0
    assert state.dopamine_phasic == 0.0
    assert state.dopamine_phasic_at <= time.time() + 1
