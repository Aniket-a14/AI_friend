"""
The facial reflex channel (Bucket 13, voice remediation Phase 3) — the
CPU-only counterpart to the VLM's slow, turn-suspended appraisal loop.

`score_blendshapes` is deliberately a pure function over a plain
{category_name: score} dict, with no MediaPipe import, so these tests never
need a camera, a model, or MediaPipe installed at all — only the threshold
and refractory logic that decides whether a raw blendshape frame becomes an
affect nudge.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.decision import DecisionService
from app.state.adaptive_weights_store import AdaptiveWeightsStore
from app.state.agent_state import StateService
from app.vision.reflex import (
    BROW_FURROW_THRESHOLD,
    SMILE_THRESHOLD,
    STARTLE_EYE_THRESHOLD,
    STARTLE_JAW_THRESHOLD,
    FacialReflexTracker,
    score_blendshapes,
)


def _blendshapes(**overrides: float) -> dict[str, float]:
    base = {
        "mouthSmileLeft": 0.0,
        "mouthSmileRight": 0.0,
        "browDownLeft": 0.0,
        "browDownRight": 0.0,
        "eyeWideLeft": 0.0,
        "eyeWideRight": 0.0,
        "jawOpen": 0.0,
    }
    base.update(overrides)
    return base


def test_a_neutral_face_produces_no_signals():
    """A calm face must never nudge affect -- the reflex channel firing on
    every frame regardless of expression would flatten into noise instead of
    a genuine reflex."""
    tracker = FacialReflexTracker()
    signals = score_blendshapes(_blendshapes(), now=0.0, tracker=tracker)
    assert signals == []


def test_a_clear_smile_fires_a_positive_valence_signal():
    frame = _blendshapes(
        mouthSmileLeft=SMILE_THRESHOLD + 0.1, mouthSmileRight=SMILE_THRESHOLD + 0.1
    )
    tracker = FacialReflexTracker()
    signals = score_blendshapes(frame, now=0.0, tracker=tracker)
    names = [s.name for s in signals]
    assert names == ["smile"]
    assert signals[0].valence_delta > 0.0
    assert signals[0].dopamine_spike > 0.0
    assert signals[0].arousal_delta == 0.0


def test_a_brow_furrow_fires_a_negative_valence_signal_with_no_reward():
    """A furrow reads as tension, not reward -- it must never carry a
    dopamine spike the way a smile does."""
    frame = _blendshapes(
        browDownLeft=BROW_FURROW_THRESHOLD + 0.1,
        browDownRight=BROW_FURROW_THRESHOLD + 0.1,
    )
    tracker = FacialReflexTracker()
    signals = score_blendshapes(frame, now=0.0, tracker=tracker)
    assert [s.name for s in signals] == ["brow_furrow"]
    assert signals[0].valence_delta < 0.0
    assert signals[0].dopamine_spike == 0.0


def test_startle_requires_both_wide_eyes_and_an_open_jaw():
    """jawOpen alone fires constantly during ordinary speech -- if either
    half of the compound gate were sufficient, the startle signal would be
    pure noise during any conversation, not a genuine reflex."""
    tracker = FacialReflexTracker()

    jaw_only = _blendshapes(jawOpen=STARTLE_JAW_THRESHOLD + 0.2)
    assert score_blendshapes(jaw_only, now=0.0, tracker=tracker) == []

    eyes_only = _blendshapes(
        eyeWideLeft=STARTLE_EYE_THRESHOLD + 0.2, eyeWideRight=STARTLE_EYE_THRESHOLD + 0.2
    )
    assert score_blendshapes(eyes_only, now=0.0, tracker=tracker) == []

    both = _blendshapes(
        eyeWideLeft=STARTLE_EYE_THRESHOLD + 0.2,
        eyeWideRight=STARTLE_EYE_THRESHOLD + 0.2,
        jawOpen=STARTLE_JAW_THRESHOLD + 0.2,
    )
    signals = score_blendshapes(both, now=0.0, tracker=tracker)
    assert [s.name for s in signals] == ["startle"]


def test_startle_carries_arousal_but_no_valence_direction():
    """A startle can be delight or alarm -- guessing the direction would be
    worse than not guessing, so it must only ever move arousal."""
    frame = _blendshapes(
        eyeWideLeft=STARTLE_EYE_THRESHOLD + 0.2,
        eyeWideRight=STARTLE_EYE_THRESHOLD + 0.2,
        jawOpen=STARTLE_JAW_THRESHOLD + 0.2,
    )
    tracker = FacialReflexTracker()
    signals = score_blendshapes(frame, now=0.0, tracker=tracker)
    assert signals[0].arousal_delta > 0.0
    assert signals[0].valence_delta == 0.0


def test_a_held_expression_fires_once_not_every_frame():
    """A five-second smile sampled at video frame rate is dozens of frames
    all scoring above threshold -- without refractory gating this would fire
    dozens of affect nudges for what a person would call one smile."""
    frame = _blendshapes(
        mouthSmileLeft=SMILE_THRESHOLD + 0.1, mouthSmileRight=SMILE_THRESHOLD + 0.1
    )
    tracker = FacialReflexTracker()

    first = score_blendshapes(frame, now=0.0, tracker=tracker)
    second = score_blendshapes(frame, now=0.1, tracker=tracker)
    third = score_blendshapes(frame, now=1.0, tracker=tracker)

    assert len(first) == 1
    assert second == []
    assert third == []


def test_the_same_signal_can_fire_again_after_the_refractory_window():
    frame = _blendshapes(
        mouthSmileLeft=SMILE_THRESHOLD + 0.1, mouthSmileRight=SMILE_THRESHOLD + 0.1
    )
    tracker = FacialReflexTracker()

    first = score_blendshapes(frame, now=0.0, tracker=tracker)
    later = score_blendshapes(frame, now=10.0, tracker=tracker)

    assert len(first) == 1
    assert len(later) == 1


def test_refractory_gating_is_independent_per_signal():
    """Firing 'smile' must not suppress 'brow_furrow' -- these are meant to
    be able to co-occur (e.g. a tense smile) without one gate blocking the
    other."""
    frame = _blendshapes(
        mouthSmileLeft=SMILE_THRESHOLD + 0.1,
        mouthSmileRight=SMILE_THRESHOLD + 0.1,
        browDownLeft=BROW_FURROW_THRESHOLD + 0.1,
        browDownRight=BROW_FURROW_THRESHOLD + 0.1,
    )
    tracker = FacialReflexTracker()
    signals = score_blendshapes(frame, now=0.0, tracker=tracker)
    assert {s.name for s in signals} == {"smile", "brow_furrow"}


def test_missing_blendshape_keys_degrade_to_no_signal_rather_than_raising():
    """A caller that only detected a partial landmark set (or a hand-built
    test fixture missing keys) must degrade safely, not crash the reflex
    loop."""
    tracker = FacialReflexTracker()
    signals = score_blendshapes({}, now=0.0, tracker=tracker)
    assert signals == []


# --------------------------------------------------------------------------
# StateService.apply_facial_reflex -- turning a signal into affect
# --------------------------------------------------------------------------


def _state():
    service = StateService(graph_store=None)
    service._persist_sensory_state_if_due = AsyncMock(return_value=None)
    return service


def test_facial_reflex_lifts_valence_and_fires_dopamine_on_a_smile():
    service = _state()
    service.current_state.valence = 0.1
    service.current_state.arousal = 0.4
    before_dopamine = service.current_state.dopamine

    asyncio.run(
        service.apply_facial_reflex(
            {"name": "smile", "valence_delta": 0.04, "dopamine_spike": 0.08}
        )
    )

    assert service.current_state.valence == pytest.approx(0.14)
    assert service.current_state.dopamine > before_dopamine


def test_facial_reflex_can_lower_valence_unlike_somatic_perception():
    """Somatic spikes are always-positive by construction; a facial reflex
    must be able to move valence in either direction, since a brow furrow is
    a genuinely negative-valenced signal."""
    service = _state()
    service.current_state.valence = 0.3

    asyncio.run(
        service.apply_facial_reflex({"name": "brow_furrow", "valence_delta": -0.03})
    )

    assert service.current_state.valence == pytest.approx(0.27)


def test_a_brow_furrow_never_fires_dopamine():
    service = _state()
    before_dopamine = service.current_state.dopamine

    asyncio.run(
        service.apply_facial_reflex({"name": "brow_furrow", "valence_delta": -0.03})
    )

    assert service.current_state.dopamine == pytest.approx(before_dopamine)


def test_facial_reflex_is_bounded_at_one():
    service = _state()
    service.current_state.valence = 0.99
    service.current_state.arousal = 0.99

    asyncio.run(
        service.apply_facial_reflex(
            {"name": "smile", "valence_delta": 0.5, "arousal_delta": 0.5}
        )
    )

    assert service.current_state.valence <= 1.0
    assert service.current_state.arousal <= 1.0


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"name": "smile", "valence_delta": 0.0, "arousal_delta": 0.0},
        {"name": "smile", "valence_delta": "warm", "arousal_delta": "warm"},
    ],
)
def test_no_signal_never_moves_affect(payload):
    """An all-zero or malformed reflex must not be applied as a real event --
    the same rule `apply_somatic_perception` enforces, and for the same
    reason: silently blending a zero delta in on every frame would flatten
    the agent's affect the longer a face stays simply calm."""
    service = _state()
    service.current_state.valence = 0.42
    service.current_state.arousal = 0.37

    asyncio.run(service.apply_facial_reflex(payload))

    assert service.current_state.valence == pytest.approx(0.42)
    assert service.current_state.arousal == pytest.approx(0.37)
    service._persist_sensory_state_if_due.assert_not_awaited()


def test_startle_raises_arousal_only():
    service = _state()
    service.current_state.valence = 0.2
    service.current_state.arousal = 0.3

    asyncio.run(
        service.apply_facial_reflex({"name": "startle", "arousal_delta": 0.06})
    )

    assert service.current_state.valence == pytest.approx(0.2)
    assert service.current_state.arousal == pytest.approx(0.36)


def test_arousal_delta_moves_the_baseline_not_the_fatigue_inflated_reading():
    """`arousal` is a derived property (`energy` + fatigue-restlessness +
    adrenaline-lift, see its getter in agent_state.py). Reading that derived
    value and writing back through its setter -- which stores into `energy`
    alone -- would permanently bake whatever fatigue happens to be active
    right now into the stored baseline. Every other test in this file leaves
    fatigue at its zero default, so the bug is invisible there; this one
    exists specifically to catch it."""
    service = _state()
    service.current_state.energy = 0.3
    service.current_state.fatigue = 0.5  # contributes 0.2 * 0.5 = 0.10 to derived arousal

    asyncio.run(
        service.apply_facial_reflex({"name": "startle", "arousal_delta": 0.06})
    )

    assert service.current_state.energy == pytest.approx(0.36)


# --------------------------------------------------------------------------
# BrainAgent._on_facial_reflex -- the mesh subscriber wiring
# --------------------------------------------------------------------------


def _brain_stub():
    """The collaborators `_on_facial_reflex` touches: affect state, the
    (real, pure) decision arbiter, and a mocked mesh `publish` -- mirrors
    `test_somatic_vision.py`'s `_brain_stub` for the sibling
    `_on_vision_description` path, extended for Bucket 17's competition
    check. `_turn_state_lock`/`_active_response_turn_id` are the real
    `BrainAgent.__init__` defaults (see brain_agent.py:113/134) reproduced
    by hand since `__new__` skips `__init__` entirely."""
    from app.agents.brain_agent import BrainAgent

    agent = BrainAgent.__new__(BrainAgent)
    agent.cognitive_core = MagicMock()
    agent.cognitive_core.state = _state()
    agent.cognitive_core.decision = DecisionService(
        llm_service=None,
        memory_store=None,
        weights_store=AdaptiveWeightsStore(":memory:"),
    )
    agent._turn_state_lock = asyncio.Lock()
    agent._active_response_turn_id = None
    agent.publish = AsyncMock()
    return agent


def test_on_facial_reflex_applies_the_event_to_affect():
    agent = _brain_stub()
    agent.cognitive_core.state.current_state.valence = 0.1

    asyncio.run(
        agent._on_facial_reflex({"name": "smile", "valence_delta": 0.04})
    )

    assert agent.cognitive_core.state.current_state.valence == pytest.approx(0.14)


def test_on_facial_reflex_swallows_a_failure_rather_than_raising():
    """A dropped reflex signal must never take down the mesh subscriber --
    mirrors `_appraise_somatic`'s own failure containment."""
    agent = _brain_stub()
    agent.cognitive_core.state.apply_facial_reflex = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    asyncio.run(agent._on_facial_reflex({"name": "smile", "valence_delta": 0.04}))
    # No exception means it worked; nothing else to assert.


# --------------------------------------------------------------------------
# Bucket 17 (voice remediation Phase 4) -- competing for the workspace
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reflex_name,expected",
    [
        ("startle", True),
        ("smile", False),
        ("brow_furrow", False),
        ("unknown_signal", False),
        ("", False),
    ],
)
def test_is_facial_reflex_interruption_worthy(reflex_name, expected):
    """Only `startle` -- the compound, highest-arousal reflex -- is salient
    enough to compete for the workspace. An agent that stopped talking
    because the user smiled would be wrong, not attentive."""
    decision = DecisionService(
        llm_service=None, memory_store=None, weights_store=AdaptiveWeightsStore(":memory:")
    )
    assert decision.is_facial_reflex_interruption_worthy(reflex_name) is expected


def test_a_startle_during_an_active_turn_publishes_a_confirmed_audio_stop():
    """The plan's own verify line: a startle arriving mid-turn must
    demonstrably compete for the workspace -- not just log the event and
    update background affect for whatever turn comes next."""
    agent = _brain_stub()
    agent._active_response_turn_id = "turn-123"

    asyncio.run(
        agent._on_facial_reflex(
            {"name": "startle", "arousal_delta": 0.2, "evidence": "startle=0.9"}
        )
    )

    agent.publish.assert_awaited_once()
    (subject, payload), _ = agent.publish.call_args
    from app.contracts import Topics

    assert subject == Topics.AUDIO_STOP
    assert payload["reason"] == "facial_reflex_startle"
    assert payload["intent_type"] == "VISION_INTERRUPTION"
    assert payload["turn_id"] == "turn-123"
    assert payload["speculative"] is False


def test_a_smile_during_an_active_turn_does_not_interrupt():
    """Arbitration must actually gate, not fire on every reflex -- affect is
    still updated, but the workspace is not contested over a smile."""
    agent = _brain_stub()
    agent._active_response_turn_id = "turn-123"
    agent.cognitive_core.state.current_state.valence = 0.1

    asyncio.run(
        agent._on_facial_reflex({"name": "smile", "valence_delta": 0.04})
    )

    agent.publish.assert_not_awaited()
    assert agent.cognitive_core.state.current_state.valence == pytest.approx(0.14)


def test_a_startle_with_no_active_turn_does_not_publish():
    """Nothing to interrupt -- a startle between turns is still a real affect
    event (handled above), just not a workspace contest."""
    agent = _brain_stub()
    assert agent._active_response_turn_id is None

    asyncio.run(
        agent._on_facial_reflex({"name": "startle", "arousal_delta": 0.2})
    )

    agent.publish.assert_not_awaited()
