"""Bucket 10 (revised scope): `SurfacingAgent._on_agent_state` widens the APRA
vocal-modulation trajectory from PAD-only to PAD-plus-endocrine.

Before this change `generate_apra_trajectory` never saw cortisol, dopamine, or
adrenaline, so two turns at identical valence/arousal sounded identical even
when one was a dopamine-lit reward and the other a cortisol-tight recovery
from stress. These tests pin the wiring: the hormones on the incoming
`state.update` payload must actually reach the published trajectory, not just
sit read but unused (as `cortisol` already did before this fix — tracked into
`_current_cortisol` for mood-congruent recall but never passed to the Rust
trajectory generator).
"""

import asyncio

import pytest

from app.agents.surfacing_agent import SurfacingAgent


def _pitch_at_frame_zero(trajectory: list) -> float:
    # `AgentVoiceModulation.model_dump()` (called before publish) turns each
    # `ProsodyFrame` into a plain dict, so the published payload is dicts,
    # not model instances. Frame 0's t_ms=0 also makes the vibrato ripple's
    # sin(0) term exactly zero regardless of amplitude, isolating the
    # additive hormone terms -- the same property the Rust-side unit tests
    # use.
    return trajectory[0]["pitch"]


@pytest.mark.asyncio
async def test_adrenaline_on_the_wire_raises_the_published_trajectorys_pitch():
    """A startled state must sound different from a calm one at the same PAD
    coordinates -- if this fails, adrenaline is being read into agent state
    (Bucket 11) but never reaching the voice the user actually hears."""
    agent = SurfacingAgent()
    published = []

    async def fake_publish(subject, data, **kwargs):
        published.append(data)

    agent.publish = fake_publish

    base_state = {
        "valence": 0.0,
        "arousal": 0.5,
        "dominance": 0.5,
        "fatigue": 0.0,
        "cortisol": 0.0,
        "dopamine": 0.0,
    }
    await agent._on_agent_state(base_state)
    await asyncio.sleep(0)  # let the spawned publish task actually run

    await agent._on_agent_state({**base_state, "adrenaline": 0.8})
    await asyncio.sleep(0)

    assert len(published) == 2
    calm_pitch = _pitch_at_frame_zero(published[0]["trajectory"])
    startled_pitch = _pitch_at_frame_zero(published[1]["trajectory"])
    assert startled_pitch > calm_pitch


@pytest.mark.asyncio
async def test_dopamine_on_the_wire_raises_pitch_and_cortisol_lowers_it_by_comparison():
    """Two turns with the same PAD coordinates but opposite hormone stories
    (reward vs. stress) must not render as the same delivery."""
    agent = SurfacingAgent()
    published = []

    async def fake_publish(subject, data, **kwargs):
        published.append(data)

    agent.publish = fake_publish

    base_state = {
        "valence": 0.0,
        "arousal": 0.5,
        "dominance": 0.5,
        "fatigue": 0.0,
        "adrenaline": 0.0,
    }
    await agent._on_agent_state({**base_state, "cortisol": 0.7, "dopamine": 0.0})
    await asyncio.sleep(0)
    await agent._on_agent_state({**base_state, "cortisol": 0.0, "dopamine": 0.7})
    await asyncio.sleep(0)

    assert len(published) == 2
    stressed_pitch = _pitch_at_frame_zero(published[0]["trajectory"])
    rewarded_pitch = _pitch_at_frame_zero(published[1]["trajectory"])
    # Both raise pitch relative to a hormone-free baseline (see the Rust unit
    # tests for that), but a reward event is designed to brighten pitch more
    # than a threat event's tension-driven raise, at equal magnitude -- 0.10
    # vs 0.08 in `generate_apra_trajectory`'s own coefficients.
    assert rewarded_pitch > stressed_pitch


@pytest.mark.asyncio
async def test_missing_hormone_fields_default_to_zero_not_a_crash():
    """A `state.update` payload built before this fix (or from a stale
    producer) has no `adrenaline` key at all -- must degrade to 0.0, not
    raise, since a KeyError here would take down vocal modulation entirely."""
    agent = SurfacingAgent()
    published = []

    async def fake_publish(subject, data, **kwargs):
        published.append(data)

    agent.publish = fake_publish

    await agent._on_agent_state({"mood": 0.1, "energy": 0.4})
    await asyncio.sleep(0)

    assert len(published) == 1
    assert len(published[0]["trajectory"]) == 60
