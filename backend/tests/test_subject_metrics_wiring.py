"""P3-2 -- BaseAgent, CognitiveService and SurfacingAgent route through the
one real `SubjectMetrics` implementation (app/metrics.py) instead of each
hand-rolling its own dict-and-log-line tracker.

Before this fix there were three near-identical, independently-maintained
trackers with no percentiles, no jitter, and no thread safety -- exactly the
duplication `app/metrics.py`'s own docstring says it exists to replace.
`SurfacingAgent` is the case that mattered most to get right: it subclasses
`BaseAgent`, which already sets `self._metrics` in `super().__init__()` for
its own generic mesh-level publish/rx counters. Reusing that attribute name
for `SurfacingAgent`'s business-logic-level counters would silently clobber
the base tracker rather than adding a second one -- a real bug caught while
writing this fix, not a hypothetical.
"""

import time

import pytest

from app.agents.base import BaseAgent
from app.agents.surfacing_agent import SurfacingAgent
from app.cognitive.core import CognitiveService
from app.metrics import SubjectMetrics


def test_base_agent_subject_metric_reaches_the_shared_tracker():
    """A publish/rx event recorded through BaseAgent's own helper must land
    in a real `SubjectMetrics` instance, not a private dict no other code
    can read percentiles or jitter from."""
    agent = BaseAgent(name="metrics_wiring_agent")
    try:
        assert isinstance(agent._metrics, SubjectMetrics)

        agent._record_subject_metric("system.tick", direction="rx", latency_ms=5.0)
        agent._metrics._queue.join()

        metric = agent._metrics._metrics["rx:system.tick"]
        assert metric["count"] == 1.0
        assert metric["latency_samples"] == 1.0
    finally:
        agent._metrics.shutdown()


def test_cognitive_service_subject_metric_reaches_the_shared_tracker():
    """Same guarantee for CognitiveService's own recorder -- it does not
    subclass BaseAgent, so it needs its own SubjectMetrics instance, not a
    third hand-rolled dict alongside the two already found."""
    service = CognitiveService(llm_service=None, memory_store=None, graph_db=None)
    try:
        assert isinstance(service._metrics, SubjectMetrics)

        service._record_subject_metric("memory.surfaced", {}, local_latency_ms=7.0)
        service._metrics._queue.join()

        metric = service._metrics._metrics["cognitive:memory.surfaced"]
        assert metric["count"] == 1.0
        assert metric["latency_samples"] == 1.0
    finally:
        service._metrics.shutdown()


def test_surfacing_agent_metric_lands_in_its_own_tracker_not_base_agents():
    """Regression guard for the attribute-name collision this fix nearly
    introduced: SurfacingAgent's business-logic metrics (`_surfacing_metrics`)
    must be a distinct object from BaseAgent's generic mesh-level tracker
    (`_metrics`, set by super().__init__()). If SurfacingAgent's constructor
    reused `self._metrics`, this would overwrite the base tracker entirely --
    any inherited `publish()` call's rx/publish/downgrade accounting would
    silently vanish."""
    agent = SurfacingAgent()
    try:
        assert isinstance(agent._metrics, SubjectMetrics)
        assert isinstance(agent._surfacing_metrics, SubjectMetrics)
        assert agent._metrics is not agent._surfacing_metrics

        agent._record_surfacing_metric(
            "memory.surfaced", metadata={"start_time": time.time() - 0.01}
        )
        agent._surfacing_metrics._queue.join()

        metric = agent._surfacing_metrics._metrics["surfacing:memory.surfaced"]
        assert metric["count"] == 1.0
        assert metric["latency_samples"] == 1.0

        # The base tracker must be untouched by a call routed through the
        # surfacing-specific one.
        agent._metrics._queue.join()
        assert agent._metrics._metrics == {}
    finally:
        agent._metrics.shutdown()
        agent._surfacing_metrics.shutdown()


@pytest.mark.parametrize("subject", ["not.a.tracked.subject", "vision.frame"])
def test_untracked_subjects_are_silently_dropped_not_errored(subject):
    """The shared tracker must preserve the old dict-based behavior of a
    silent no-op for a subject outside the tracked set -- not raise, and not
    grow an unbounded key for every subject anyone ever mentions."""
    agent = BaseAgent(name="metrics_wiring_untracked_agent")
    try:
        agent._record_subject_metric(subject, direction="rx", latency_ms=1.0)
        agent._metrics._queue.join()

        assert agent._metrics._metrics == {}
    finally:
        agent._metrics.shutdown()
