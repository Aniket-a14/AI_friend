"""
Visual Somatic Homeostasis — vision finally reaching the endocrine system.

Before this, `_on_vision_description` stored the VLM sentence as prompt text
and stopped. The agent could describe something it loves and feel nothing.
These tests cover the path that closes that gap, plus the capture-capability
probe that makes a blind agent say so instead of failing silently.
"""

import asyncio
import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cognitive.somatic import (
    SOMATIC_AROUSAL_SPIKE,
    SOMATIC_REFRACTORY_SECONDS,
    SOMATIC_VALENCE_SPIKE,
    SomaticAppraiser,
)
from app.state.agent_state import StateService


class _Clock:
    """Controllable time so refractory/TTL behaviour is deterministic."""

    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def _graph(rows):
    graph = MagicMock()
    graph.execute_query = AsyncMock(return_value=rows)
    return graph


def _appraiser(rows, clock=None):
    clock = clock or _Clock()
    appraiser = SomaticAppraiser(graph_store=_graph(rows), now_fn=clock)
    asyncio.run(appraiser.refresh(force=True))
    return appraiser, clock


# --------------------------------------------------------------------------
# learned vocabulary — nothing is hardcoded
# --------------------------------------------------------------------------


def test_no_learned_comforts_means_no_spike_ever():
    """The honest cold start: an agent that has never discussed anything
    somatic recognises nothing, exactly like the mental lexicon (B1)."""
    appraiser, _ = _appraiser([])
    assert appraiser.known_terms == []
    assert appraiser.appraise("a steaming cup of cardamom tea and rasgulla") is None


def test_comforts_are_read_from_the_graph_not_a_constant():
    appraiser, _ = _appraiser(
        [
            {"name": "Cardamom Tea", "confidence": 0.9},
            {"name": "Rasgulla", "confidence": 0.8},
        ]
    )
    assert appraiser.known_terms == ["cardamom tea", "rasgulla"]


def test_graph_failure_keeps_previous_terms_and_does_not_raise():
    """Neo4j being down must not stop the agent seeing or talking."""
    appraiser, clock = _appraiser([{"name": "chai", "confidence": 1.0}])
    appraiser.graph.execute_query = AsyncMock(side_effect=RuntimeError("neo4j down"))
    clock.advance(10_000)

    assert asyncio.run(appraiser.refresh()) == 1
    assert appraiser.appraise("a cup of chai") is not None


def test_absent_graph_is_tolerated():
    appraiser = SomaticAppraiser(graph_store=None)
    assert asyncio.run(appraiser.refresh(force=True)) == 0
    assert appraiser.appraise("chai") is None


@pytest.mark.parametrize(
    "rows",
    [
        [{"name": None, "confidence": 1.0}],
        [{"name": "", "confidence": 1.0}],
        [{"name": "it", "confidence": 1.0}],  # too short to match safely
        [{"nope": "chai"}],
    ],
)
def test_malformed_or_unusable_graph_rows_are_skipped(rows):
    appraiser, _ = _appraiser(rows)
    assert appraiser.known_terms == []


def test_non_numeric_confidence_falls_back_rather_than_raising():
    appraiser, _ = _appraiser([{"name": "chai", "confidence": "very"}])
    result = appraiser.appraise("some chai")
    assert result is not None and result["confidence"] == 1.0


@pytest.mark.parametrize("nan_value", ["nan", "NaN", float("nan")])
def test_nan_confidence_from_the_graph_never_reaches_a_spike(nan_value):
    """L9 was filed as a missing NaN guard, but investigation showed the
    existing clamp already closes it: `float("nan")` and a literal NaN both
    parse successfully (the `except (TypeError, ValueError)` never catches
    either), yet `max(0.0, min(1.0, confidence))` deterministically resolves
    NaN to 1.0 in CPython - NaN compares False against everything, so
    `min(1.0, nan)` always keeps the first (non-NaN) argument, and the outer
    `max` does the same. Verified stable across 1000 runs before trusting it.
    An explicit `math.isnan()` guard was written and found to be a genuine
    no-op (mutation-tested: removing it did not make this test fail) - not
    kept, since dead code claiming to guard something it cannot affect is
    worse than no comment at all. This test stands as the regression guard
    should that clamp ever change shape.
    """
    appraiser, _ = _appraiser([{"name": "chai", "confidence": nan_value}])
    result = appraiser.appraise("some chai")
    assert result is not None
    assert not math.isnan(result["confidence"])


# --------------------------------------------------------------------------
# recognition
# --------------------------------------------------------------------------


def test_recognising_a_comfort_produces_a_positive_spike():
    appraiser, _ = _appraiser([{"name": "chai", "confidence": 1.0}])
    result = appraiser.appraise("The user is holding a cup of chai.")

    assert result["entities"] == ["chai"]
    assert result["valence_spike"] == pytest.approx(SOMATIC_VALENCE_SPIKE)
    assert result["arousal_spike"] == pytest.approx(SOMATIC_AROUSAL_SPIKE)


def test_unrecognised_scene_returns_none_not_a_zero_spike():
    """None means 'no evidence'. A zero spike blended in every interval would
    drag mood toward neutral and flatten the agent -- the same trap documented
    for a missing acoustic emotion estimate."""
    appraiser, _ = _appraiser([{"name": "chai", "confidence": 1.0}])
    assert appraiser.appraise("An empty desk and a monitor.") is None


def test_matching_is_whole_word():
    """'tea' must not fire on 'steam'."""
    appraiser, _ = _appraiser([{"name": "tea", "confidence": 1.0}])
    assert appraiser.appraise("steam rising from the kettle") is None
    assert appraiser.appraise("a cup of tea") is not None


def test_confidence_scales_the_spike():
    appraiser, _ = _appraiser([{"name": "chai", "confidence": 0.5}])
    result = appraiser.appraise("chai")
    assert result["valence_spike"] == pytest.approx(SOMATIC_VALENCE_SPIKE * 0.5)


def test_multiple_comforts_saturate_rather_than_stack():
    appraiser, _ = _appraiser(
        [
            {"name": "chai", "confidence": 1.0},
            {"name": "rasgulla", "confidence": 1.0},
            {"name": "kettle", "confidence": 1.0},
        ]
    )
    result = appraiser.appraise("chai, rasgulla and a kettle on the table")

    assert len(result["entities"]) == 3
    # Three matches, but the multiplier caps at 2.0.
    assert result["valence_spike"] == pytest.approx(SOMATIC_VALENCE_SPIKE * 2.0)


def test_repeat_sightings_are_refractory():
    """Staring at the same mug must not re-spike every appraisal interval."""
    appraiser, clock = _appraiser([{"name": "chai", "confidence": 1.0}])

    assert appraiser.appraise("a cup of chai") is not None
    clock.advance(SOMATIC_REFRACTORY_SECONDS / 2)
    assert appraiser.appraise("a cup of chai") is None

    clock.advance(SOMATIC_REFRACTORY_SECONDS)
    assert appraiser.appraise("a cup of chai") is not None


def test_empty_description_is_ignored():
    appraiser, _ = _appraiser([{"name": "chai", "confidence": 1.0}])
    assert appraiser.appraise("") is None


def test_cache_is_reused_within_ttl_then_refreshed():
    appraiser, clock = _appraiser([{"name": "chai", "confidence": 1.0}])
    calls_after_initial = appraiser.graph.execute_query.await_count

    asyncio.run(appraiser.refresh())
    assert appraiser.graph.execute_query.await_count == calls_after_initial

    clock.advance(10_000)
    asyncio.run(appraiser.refresh())
    assert appraiser.graph.execute_query.await_count == calls_after_initial + 1


def test_refresh_prunes_spike_history_for_terms_no_longer_learned():
    """M8: `_last_spike_at` used to grow forever - a term dropped from the
    graph (renamed, forgotten, decayed away) stayed in the refractory map
    indefinitely. `refresh()` must drop spike history for anything no longer
    in the current term set.
    """
    appraiser, clock = _appraiser([{"name": "chai", "confidence": 1.0}])
    appraiser.appraise("a cup of chai")
    assert "chai" in appraiser._last_spike_at

    clock.advance(10_000)  # force the TTL to expire so refresh() re-queries
    appraiser.graph.execute_query = AsyncMock(
        return_value=[{"name": "sunlight", "confidence": 1.0}]
    )
    asyncio.run(appraiser.refresh())

    assert "chai" not in appraiser._last_spike_at


def test_refresh_prunes_spike_timestamps_that_have_already_left_refractory():
    """Even if a term is still learned, a spike timestamp older than the
    refractory window is dead weight - `_in_refractory` would already treat
    it as expired, so keeping it around forever serves no purpose.
    """
    appraiser, clock = _appraiser([{"name": "chai", "confidence": 1.0}])
    appraiser.appraise("a cup of chai")
    assert "chai" in appraiser._last_spike_at

    clock.advance(SOMATIC_REFRACTORY_SECONDS * 2)
    asyncio.run(appraiser.refresh(force=True))

    assert "chai" not in appraiser._last_spike_at


# --------------------------------------------------------------------------
# state application
# --------------------------------------------------------------------------


def _state():
    service = StateService(graph_store=None)
    service._persist_sensory_state_if_due = AsyncMock(return_value=None)
    return service


def test_somatic_perception_lifts_valence_arousal_and_dopamine():
    """The roadmap's dopamine spike is realised through valence/arousal, since
    dopamine here is derived (max(0, V) * Ar), not a stored field."""
    service = _state()
    service.current_state.valence = 0.1
    service.current_state.arousal = 0.4
    before_dopamine = service.current_state.dopamine

    asyncio.run(
        service.apply_somatic_perception(
            {"entities": ["chai"], "valence_spike": 0.15, "arousal_spike": 0.10}
        )
    )

    assert service.current_state.valence == pytest.approx(0.25)
    assert service.current_state.dopamine > before_dopamine


def test_somatic_perception_is_bounded_at_one():
    service = _state()
    service.current_state.valence = 0.95
    service.current_state.arousal = 0.95

    asyncio.run(
        service.apply_somatic_perception(
            {"entities": ["chai"], "valence_spike": 0.5, "arousal_spike": 0.5}
        )
    )

    assert service.current_state.valence <= 1.0
    assert service.current_state.arousal <= 1.0


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"valence_spike": 0.0, "arousal_spike": 0.0},
        {"valence_spike": "warm", "arousal_spike": "warm"},
    ],
)
def test_no_evidence_never_moves_affect(payload):
    """A non-match must not be applied as a neutral reading."""
    service = _state()
    service.current_state.valence = 0.42
    service.current_state.arousal = 0.37

    asyncio.run(service.apply_somatic_perception(payload))

    assert service.current_state.valence == pytest.approx(0.42)
    assert service.current_state.arousal == pytest.approx(0.37)
    # Adding 0.0 would leave affect unchanged anyway, so state equality alone
    # cannot tell whether the guard fired. The observable difference is that a
    # no-evidence reading must not reach the persistence path at all.
    service._persist_sensory_state_if_due.assert_not_awaited()


# --------------------------------------------------------------------------
# end-to-end: a vision.description actually reaches the endocrine system
# --------------------------------------------------------------------------


def _brain_stub(rows):
    """The two collaborators _on_vision_description touches, nothing more."""
    from app.agents.brain_agent import BrainAgent

    agent = BrainAgent.__new__(BrainAgent)
    agent.somatic_appraiser = SomaticAppraiser(graph_store=_graph(rows))
    agent.cognitive_core = MagicMock()
    agent.cognitive_core.state = _state()
    agent.last_visual_context = ""
    agent.last_user_distance = 1.0
    return agent


def test_seeing_a_learned_comfort_changes_how_the_agent_feels():
    """The gap this whole change exists to close: before, a description became
    prompt text and affect never moved."""
    agent = _brain_stub([{"name": "chai", "confidence": 1.0}])
    state = agent.cognitive_core.state
    state.current_state.valence = 0.0
    before = state.current_state.valence

    asyncio.run(
        agent._on_vision_description(
            {"description": "A warm cup of chai on the desk.", "source": "camera"}
        )
    )

    assert state.current_state.valence > before
    # And the visual context is still recorded as before.
    assert "chai" in agent.last_visual_context


def test_seeing_something_unremarkable_leaves_affect_untouched():
    agent = _brain_stub([{"name": "chai", "confidence": 1.0}])
    state = agent.cognitive_core.state
    state.current_state.valence = 0.3

    asyncio.run(
        agent._on_vision_description(
            {"description": "An empty desk.", "source": "screen"}
        )
    )

    assert state.current_state.valence == pytest.approx(0.3)


def test_somatic_failure_does_not_lose_the_visual_context():
    """Vision degrading must not take the description with it."""
    agent = _brain_stub([{"name": "chai", "confidence": 1.0}])
    agent.somatic_appraiser.refresh = AsyncMock(side_effect=RuntimeError("boom"))

    asyncio.run(
        agent._on_vision_description(
            {"description": "A cup of chai.", "source": "camera"}
        )
    )

    assert "chai" in agent.last_visual_context


# --------------------------------------------------------------------------
# capture capability probe
# --------------------------------------------------------------------------


def _vision_agent():
    from app.vision.agent import VisionAgent

    agent = VisionAgent.__new__(VisionAgent)
    agent.screen = MagicMock()
    agent.camera = MagicMock()
    agent.source = "screen"
    agent.health_file = ""
    agent.can_capture = False
    return agent


def test_preflight_detects_a_blind_container():
    """Silent blindness is the failure mode this exists to prevent: ScreenLink
    swallows its own error and returns None forever while the process lives on
    (the shape of finding E1)."""
    agent = _vision_agent()
    agent.screen.capture_frame = MagicMock(return_value=None)
    assert agent.preflight() is False


def test_preflight_passes_when_capture_works():
    agent = _vision_agent()
    agent.screen.capture_frame = MagicMock(return_value=b"jpegbytes")
    assert agent.preflight() is True


def test_preflight_probes_the_selected_source():
    agent = _vision_agent()
    agent.source = "camera"
    agent.camera.capture_frame = MagicMock(return_value=b"frame")
    agent.screen.capture_frame = MagicMock(return_value=None)

    assert agent.preflight() is True
    agent.camera.capture_frame.assert_called_once()


def test_health_sentinel_is_written_on_capture(tmp_path):
    """The container healthcheck reads this. `pgrep python` would pass just as
    happily with every frame coming back None."""
    agent = _vision_agent()
    sentinel = tmp_path / "vision_healthy"
    agent.health_file = str(sentinel)

    agent._mark_capture_healthy()
    assert sentinel.exists()


def test_health_sentinel_write_failure_is_not_fatal():
    agent = _vision_agent()
    agent.health_file = "/nonexistent-dir/vision_healthy"
    agent._mark_capture_healthy()  # must not raise
