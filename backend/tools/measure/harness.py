"""Shared plumbing for Stage 3 measurements (audit/ROADMAP.md §7).

Three rules, mirroring evals/ (CLAUDE.md documents the same three for that
harness): nothing in app/ imports from here; every report carries provenance;
and a MOCK_LLM_TEXT-sourced run is refused as evidence unless the caller
explicitly overrides it.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from app.config import Config
from app.measure_trace import add_listener, remove_listener

TraceEvent = tuple[str, str, float, dict[str, object]]

_bootstrapped = False


async def ensure_bootstrapped() -> None:
    """Runs the same schema/stream bootstrap brain_agent.py's main() runs on
    a real deployment (db/schema.sql's surface_actr_memories() and friends),
    idempotent and cached per-process so every measurement module can call it
    without racing a second bootstrap when the CLI runs several in sequence.
    """
    global _bootstrapped
    if _bootstrapped:
        return
    from app.runtime_bootstrap import bootstrap_runtime

    await bootstrap_runtime()
    _bootstrapped = True


class MockProvenanceError(RuntimeError):
    """Raised when a measurement would run against MOCK_LLM_TEXT without
    --allow-mock. A number produced this way is not a measurement."""


def check_live_llm(allow_mock: bool = False) -> str:
    """Returns the provenance label ('live' or 'mock'), raising unless
    --allow-mock was passed for a mock run."""
    if getattr(Config, "MOCK_LLM_TEXT", False):
        if not allow_mock:
            raise MockProvenanceError(
                "MOCK_LLM_TEXT=true: this run would produce fitted strings, "
                "not a measurement. Pass allow_mock=True if that is genuinely "
                "what you want (e.g. smoke-testing the harness itself)."
            )
        return "mock"
    return "live"


@contextlib.contextmanager
def collecting_trace() -> Iterator[list[TraceEvent]]:
    """Turns MEASURE_TRACE on for the duration of the block and returns the
    list of (component, event, ts, fields) tuples fired during it. Restores
    the prior flag value on exit so a measurement run never leaves tracing
    on for whatever runs after it in the same process.
    """
    events: list[TraceEvent] = []

    def _listener(component: str, event: str, ts: float, fields: dict) -> None:
        events.append((component, event, ts, dict(fields)))

    prior = Config.MEASURE_TRACE
    Config.MEASURE_TRACE = True
    add_listener(_listener)
    try:
        yield events
    finally:
        remove_listener(_listener)
        Config.MEASURE_TRACE = prior
