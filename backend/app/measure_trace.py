"""Stage 3 (audit/ROADMAP.md §7): a single off-by-default trace primitive
shared by every measurement call site, so MEASURE_TRACE's gate and event shape
live in one place instead of being re-implemented per file.

Not a NATS subject: a new subject here would need an entry in
check_subject_wiring.py's ALLOWLIST for a "subscriber" that lives outside
app/ and crates/ entirely (backend/tools/measure/), which a log line needs no
carve-out for. Every event is both logged (so a containerized run -- e.g.
stt-agent, which can only run in the Linux image on this host -- is still
readable via `docker logs`) and handed to any in-process listeners
backend/tools/measure/ registers, so a harness driving the same process
in-process (no container boundary) can capture structured events directly
instead of re-parsing its own log output.
"""

import hashlib
import logging
import time
from collections.abc import Callable

from .config import Config

_logger = logging.getLogger("measure_trace")

TraceListener = Callable[[str, str, float, dict[str, object]], None]
_listeners: list[TraceListener] = []


def add_listener(listener: TraceListener) -> None:
    """Register an in-process listener. backend/tools/measure/ only -- not
    called from anywhere under app/."""
    _listeners.append(listener)


def remove_listener(listener: TraceListener) -> None:
    if listener in _listeners:
        _listeners.remove(listener)


def trace(component: str, event: str, **fields: object) -> None:
    """No-op unless Config.MEASURE_TRACE is set."""
    if not Config.MEASURE_TRACE:
        return
    ts = time.time()
    rendered = " ".join(f"{k}={v}" for k, v in fields.items())
    _logger.info(
        "MEASURE_TRACE component=%s event=%s ts=%f %s",
        component,
        event,
        ts,
        rendered,
    )
    for listener in _listeners:
        try:
            listener(component, event, ts, fields)
        except Exception:
            _logger.exception("measure_trace listener raised")


def fingerprint(text: str) -> str:
    """Short digest identifying a prompt without reproducing it.

    Same shape as evals/schema.py's fingerprint() (sha256 hex[:16]) --
    duplicated rather than imported, since CLAUDE.md's dependency rule for
    evals/ only runs one way: nothing in app/ may import from evals/.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
