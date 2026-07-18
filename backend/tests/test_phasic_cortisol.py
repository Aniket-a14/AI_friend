"""
Phasic cortisol — stress that outlives the thing that caused it.

`cortisol` was a pure function of valence and fatigue, which made it the exact
mirror image of tonic dopamine: both derived from valence alone, one rising
precisely as the other fell. Two consequences, both wrong.

First, stress could not outlive its cause. Recover your mood and the alarm
stopped instantly and completely, which is not how a threat response works —
the HPA axis clears on its own schedule, not the mood's.

Second, the agent could never be stressed and rewarded at once, because the
formulae made that arithmetically impossible. Plenty of ordinary experience is
exactly that combination. Phasic dopamine broke the coupling in one direction;
this is the other half.

The first test below is the load-bearing one: with no burst outstanding the
value is bit-for-bit what it always was, so nothing downstream shifts.
"""

import asyncio
import math
import time
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.persona import PersonaProfile, Tier
from app.state.agent_state import AgentState, StateService


def _old_derived_cortisol(state: AgentState) -> float:
    """The formula exactly as it stood before phasic cortisol existed."""
    base = 0.5 - (state.valence / 2.0)
    return max(0.0, min(1.0, base + 0.3 * state.fatigue))


# --------------------------------------------------------------------------
# backward compatibility
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mood,fatigue",
    [(0.8, 0.0), (-0.5, 0.4), (1.0, 1.0), (-1.0, 0.0), (0.0, 0.5), (0.33, 0.66)],
)
def test_without_a_burst_cortisol_is_exactly_the_old_derived_value(mood, fatigue):
    """No burst outstanding must be indistinguishable from the old behaviour.

    Every consumer of `cortisol` — the LLM temperature mapping, the memory
    stress-suppression term, the surfacing agent's vocal modulation — was
    tuned against the derived formula. If an unstressed agent reads even
    slightly differently now, all of them shift underneath at once.
    """
    state = AgentState(mood=mood, fatigue=fatigue)
    assert state.cortisol_phasic == 0.0
    assert state.cortisol == pytest.approx(_old_derived_cortisol(state))


def test_a_fresh_state_carries_no_outstanding_stress():
    """A restored or newly constructed agent must not start out alarmed."""
    assert AgentState().cortisol_phasic_peak == 0.0
    assert AgentState().cortisol_phasic == 0.0


# --------------------------------------------------------------------------
# release
# --------------------------------------------------------------------------


def test_releasing_cortisol_raises_the_level_by_the_requested_amount():
    """A stress event must actually move the hormone, not just the mood."""
    state = AgentState(mood=0.0, fatigue=0.0)
    before = state.cortisol
    after = state.release_cortisol(0.3)
    assert after == pytest.approx(before + 0.3)


def test_cortisol_cannot_be_driven_above_one():
    """Saturation is the ceiling of the range, not an unbounded accumulator."""
    state = AgentState(mood=-1.0, fatigue=1.0)
    assert state.release_cortisol(0.9) == pytest.approx(1.0)


def test_stress_survives_the_mood_recovering():
    """The whole point: cortisol must not vanish the moment valence returns.

    This is the failure the tonic-only formula had. If this regresses, an agent
    that was just frightened reads as perfectly calm the instant its mood
    drifts back up, and nothing downstream can tell the difference.
    """
    # Deliberately not starting at maximum stress: a burst on top of an
    # already-saturated tonic is clipped by the 1.0 ceiling, which would make
    # this test measure the clip rather than the survival.
    state = AgentState(mood=-0.3, fatigue=0.0)
    state.release_cortisol(0.2)
    state.mood = 0.9  # the cause is gone
    assert state.cortisol_tonic == pytest.approx(0.05)
    assert state.cortisol_phasic > 0.15
    assert state.cortisol > state.cortisol_tonic


def test_an_agent_can_be_stressed_and_rewarded_at_the_same_time():
    """Tonic dopamine and tonic cortisol are anti-correlated by construction.

    Before the phasic terms, high cortisol *entailed* low dopamine and vice
    versa, so a state like "this is going well and I am also on edge" was not
    representable at all. Both bursts outstanding must produce it.
    """
    state = AgentState(mood=0.0, energy=0.5, fatigue=0.0)
    state.release_dopamine(0.4)
    state.release_cortisol(0.4)
    assert state.dopamine > 0.35
    assert state.cortisol > 0.85


# --------------------------------------------------------------------------
# rejection of unusable amounts
# --------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [0.0, -0.1, -5.0])
def test_a_non_positive_release_is_ignored(amount):
    """`release_cortisol` fires stress; it is not a way to remove it."""
    state = AgentState(mood=0.2)
    before = state.cortisol
    assert state.release_cortisol(amount) == pytest.approx(before)
    assert state.cortisol_phasic_peak == 0.0


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_release_cannot_fire_a_maximum_stress_response(amount):
    """NaN defeats every guard downstream and would saturate the hormone.

    `nan <= 0.0` is False so it passes the positivity check, and
    `min(1.0, nan)` returns 1.0 — so without an explicit finiteness guard a
    malformed stress signal produces the *maximum possible* stress response,
    the worst available reading of a caller bug. It would then pin the LLM
    temperature to its floor for the whole half-life.
    """
    state = AgentState(mood=0.2)
    assert not math.isnan(state.release_cortisol(amount))
    assert state.cortisol_phasic_peak == 0.0


@pytest.mark.parametrize("amount", ["a lot", None, object()])
def test_a_non_numeric_release_is_ignored(amount):
    """A malformed payload must not crash the cognitive turn."""
    state = AgentState(mood=0.2)
    before = state.cortisol
    assert state.release_cortisol(amount) == pytest.approx(before)
    assert state.cortisol_phasic_peak == 0.0


def test_a_non_finite_release_does_not_clear_an_existing_burst():
    """A bad signal must leave real outstanding stress untouched."""
    state = AgentState(mood=0.0)
    state.release_cortisol(0.5)
    peak = state.cortisol_phasic_peak
    state.release_cortisol(float("nan"))
    assert state.cortisol_phasic_peak == pytest.approx(peak)


# --------------------------------------------------------------------------
# decay
# --------------------------------------------------------------------------


def test_stress_halves_after_exactly_one_half_life():
    """Decay is computed from wall-clock, so it is correct even if ticks stall."""
    state = AgentState(mood=0.0, cortisol_halflife_s=100.0)
    state.release_cortisol(0.4)
    peak = state.cortisol_phasic_peak
    state.cortisol_phasic_at = time.time() - 100.0
    assert state.cortisol_phasic == pytest.approx(peak / 2.0, abs=1e-3)


def test_stress_decays_toward_zero_and_not_below():
    """A long-past burst must leave the tonic reading, not a negative one."""
    state = AgentState(mood=0.0, cortisol_halflife_s=10.0)
    state.release_cortisol(0.5)
    state.cortisol_phasic_at = time.time() - 10_000.0
    assert state.cortisol_phasic == pytest.approx(0.0, abs=1e-6)
    assert state.cortisol == pytest.approx(state.cortisol_tonic)


def test_a_longer_half_life_holds_stress_longer():
    """Half-life is the knob that makes one temperament slower to settle."""
    elapsed = 60.0
    quick = AgentState(mood=0.0, cortisol_halflife_s=30.0)
    slow = AgentState(mood=0.0, cortisol_halflife_s=600.0)
    for state in (quick, slow):
        state.release_cortisol(0.5)
        state.cortisol_phasic_at = time.time() - elapsed
    assert slow.cortisol_phasic > quick.cortisol_phasic


def test_cortisol_clears_slower_than_dopamine_by_default():
    """A fright has a hangover; a pleasure mostly does not.

    If these defaults were ever equalised the endocrine layer would go back to
    describing a creature whose good and bad moments fade at identical rates,
    which is the symmetry the split exists to break.
    """
    assert AgentState().cortisol_halflife_s > AgentState().dopamine_halflife_s


def test_the_tonic_floor_drifts_underneath_an_outstanding_burst():
    """The burst is stored relative to tonic, not absolutely.

    If it were absolute, mood movement during a burst would be double-counted
    into the total and the agent would read as far more stressed than either
    the mood or the event alone warrants.
    """
    state = AgentState(mood=0.0, fatigue=0.0)
    state.release_cortisol(0.2)
    peak = state.cortisol_phasic_peak
    state.mood = -0.6  # tonic rises on its own
    assert state.cortisol_phasic_peak == pytest.approx(peak)
    assert state.cortisol == pytest.approx(state.cortisol_tonic + state.cortisol_phasic)


# --------------------------------------------------------------------------
# half-lives are persona, not deployment config
# --------------------------------------------------------------------------


def test_both_half_lives_are_constitutional_persona_fields():
    """How long feeling lingers is temperament, not an env var.

    Leaving these in Config would mean one process can host exactly one
    emotional metabolism, which is the constraint PersonaProfile exists to
    remove.
    """
    assert PersonaProfile.tier_of("dopamine_halflife_s") is Tier.CONSTITUTIONAL
    assert PersonaProfile.tier_of("cortisol_halflife_s") is Tier.CONSTITUTIONAL


def test_state_service_seeds_state_half_lives_from_the_persona():
    """The persona's values must actually reach the state that decays."""
    persona = PersonaProfile(dopamine_halflife_s=45.0, cortisol_halflife_s=1200.0)
    # ":memory:" so the default constructor does not write state_cache.db into
    # the working directory, which leaves an artifact and fails outright in a
    # read-only workspace.
    service = StateService(graph_store=None, persona=persona, db_path=":memory:")
    assert service.current_state.dopamine_halflife_s == 45.0
    assert service.current_state.cortisol_halflife_s == 1200.0


def test_a_persona_cannot_set_a_half_life_so_short_the_burst_is_never_seen():
    """A near-zero half-life is a broken hormone, not a fast temperament.

    The release would fire and decay below any useful threshold before the next
    turn could read it — indistinguishable from the hormone not existing.

    `ValidationError` specifically, not bare `Exception`: a broad catch would
    also pass if the constructor raised for an unrelated reason — a renamed
    field, a typo in the keyword — and the test would report the bound as
    enforced when it had been silently deleted.
    """
    with pytest.raises(ValidationError):
        PersonaProfile(cortisol_halflife_s=0.0)
    with pytest.raises(ValidationError):
        PersonaProfile(dopamine_halflife_s=0.001)


def test_a_persona_cannot_set_a_half_life_that_outlives_the_conversation():
    """A burst lasting hours would colour sessions it has nothing to do with."""
    with pytest.raises(ValidationError):
        PersonaProfile(dopamine_halflife_s=99_999.0)
    with pytest.raises(ValidationError):
        PersonaProfile(cortisol_halflife_s=99_999.0)


def test_an_unconfigured_deployment_keeps_the_previous_half_life():
    """The dopamine default must not move; it was tuned before this change."""
    assert PersonaProfile.from_config().dopamine_halflife_s == 90.0


# --------------------------------------------------------------------------
# the locked service API
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_service_releases_both_hormones_under_the_state_lock():
    """Affect mutation must go through StateService, holding `_state_lock`.

    The burst peak is computed *relative to the tonic floor*. A fire-and-forget
    System-2 appraisal writes valence concurrently with the synchronous path
    (finding A2), so an unlocked release that interleaves with a valence write
    measures its peak against a floor that has already moved and stores a burst
    of the wrong size. These wrappers are the API the stress and reward
    channels will call.
    """
    service = StateService(graph_store=None, db_path=":memory:")
    service.current_state.mood = 0.0

    assert not service._state_lock.locked()
    level = await service.release_cortisol(0.3, reason="test")
    assert level > service.current_state.cortisol_tonic
    # Released, not merely computed: the burst is outstanding on the state.
    assert service.current_state.cortisol_phasic_peak > 0.0
    # And the lock was given back, or every later turn would hang on it.
    assert not service._state_lock.locked()

    await service.release_dopamine(0.3, reason="test")
    assert service.current_state.dopamine_phasic_peak > 0.0
    assert not service._state_lock.locked()


@pytest.mark.asyncio
async def test_somatic_perception_does_not_deadlock_on_the_release_wrapper():
    """`apply_somatic_perception` already holds the lock across its burst.

    It calls the unlocked `AgentState` primitive on purpose, so the peak is
    measured against the settled tonic after `_enforce_bounds`. If it were ever
    switched to the service wrapper, this would hang forever — `asyncio.Lock`
    is not reentrant — so the test pins the arrangement rather than the comment.
    """
    service = StateService(graph_store=None, db_path=":memory:")
    service._persist_sensory_state_if_due = AsyncMock(return_value=None)

    await asyncio.wait_for(
        service.apply_somatic_perception(
            {"valence_spike": 0.2, "arousal_spike": 0.1, "entities": ["mug"]}
        ),
        timeout=5.0,
    )
    assert service.current_state.dopamine_phasic_peak > 0.0
    assert not service._state_lock.locked()


@pytest.mark.asyncio
async def test_a_release_waits_for_a_held_state_lock():
    """Proves the wrapper actually acquires the lock, rather than merely
    leaving it free.

    The obvious assertion — that `_state_lock` is unlocked after the call —
    passes whether or not the wrapper ever took it, so it cannot detect the
    lock being dropped. Holding the lock and showing the release *blocks* is
    the only version of this test with any detection power.
    """
    service = StateService(graph_store=None, db_path=":memory:")

    async with service._state_lock:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(service.release_cortisol(0.3), timeout=0.25)
        # Blocked, so nothing was written while another writer held the lock.
        assert service.current_state.cortisol_phasic_peak == 0.0

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(service.release_dopamine(0.3), timeout=0.25)
        assert service.current_state.dopamine_phasic_peak == 0.0

    # Released once the lock is free again.
    assert await service.release_cortisol(0.3) > 0.0
    assert service.current_state.cortisol_phasic_peak > 0.0
