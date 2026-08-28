"""Isolated NATS JetStream event-bus harness for E2E integration tests.

Wraps the existing ``MockNATSConnection`` from the root ``conftest.py``
into a higher-level ``NatsMeshHarness`` that:

1. Records every inter-agent message in a chronological **event ledger**
   with nanosecond timestamps, enabling ordering and latency assertions.
2. Provides topic-scoped ``wait_for`` helpers so tests can block until a
   specific message lands on a subject instead of sleeping a fixed duration.
3. Exposes typed ``inject()`` / ``collect()`` methods so tests read like
   scenario descriptions rather than raw publish/subscribe calls.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import orjson

# ── Event ledger entry ───────────────────────────────────────────────


@dataclass
class MeshEvent:
    """One observed message on the NATS mesh."""

    subject: str
    data: dict[str, Any] | bytes
    timestamp: float = field(default_factory=time.time)
    headers: dict[str, str] | None = None

    @property
    def is_binary(self) -> bool:
        return isinstance(self.data, (bytes, bytearray))


# ── Harness ──────────────────────────────────────────────────────────


class NatsMeshHarness:
    """Wraps a ``MockNATSConnection`` (from conftest.py) to provide
    structured event capture and injection for E2E scenarios.

    Usage::

        harness = NatsMeshHarness(mock_nats_connection)
        harness.start_recording()

        # ... run agent pipeline ...

        events = harness.events_on("chat.output")
        assert len(events) >= 1
        assert events[0].data["content"] == "Hello!"
    """

    def __init__(self, nc: Any) -> None:
        self.nc = nc
        self.js = nc.jetstream()
        self._ledger: list[MeshEvent] = []
        self._topic_events: dict[str, asyncio.Event] = {}
        self._recording = False
        # Original _trigger saved so we can intercept without breaking it.
        self._original_trigger = nc._trigger

    # ── Recording ────────────────────────────────────────────────

    def start_recording(self) -> None:
        """Monkey-patch the mock connection to intercept every publish."""
        self._recording = True

        original_trigger = self._original_trigger

        def _intercepting_trigger(subject: str, data: Any, headers: Any = None) -> None:
            if self._recording:
                try:
                    if isinstance(data, (bytes, bytearray)):
                        # Try JSON first — inject() serializes dicts to bytes.
                        try:
                            parsed = orjson.loads(data)
                        except Exception:
                            parsed = data  # Genuine binary (PCM audio).
                    elif isinstance(data, str):
                        parsed = json.loads(data)
                    else:
                        parsed = data
                except Exception:
                    parsed = data

                event = MeshEvent(
                    subject=subject,
                    data=parsed,
                    timestamp=time.time(),
                    headers=dict(headers) if headers else None,
                )
                self._ledger.append(event)

                # Wake any waiters for this subject.
                if subject in self._topic_events:
                    self._topic_events[subject].set()

            # Still run the real trigger so subscribers fire.
            original_trigger(subject, data, headers)

        self.nc._trigger = _intercepting_trigger

    def stop_recording(self) -> None:
        self._recording = False
        self.nc._trigger = self._original_trigger

    # ── Querying ─────────────────────────────────────────────────

    @property
    def ledger(self) -> list[MeshEvent]:
        return list(self._ledger)

    def events_on(self, subject: str) -> list[MeshEvent]:
        """Return all recorded events for *subject* in chronological order."""
        return [e for e in self._ledger if e.subject == subject]

    def clear(self) -> None:
        self._ledger.clear()

    # ── Waiting ──────────────────────────────────────────────────

    async def wait_for(self, subject: str, *, timeout: float = 3.0, count: int = 1) -> list[MeshEvent]:
        """Block until at least *count* events have been recorded on *subject*,
        or *timeout* seconds elapse (whichever comes first)."""
        if subject not in self._topic_events:
            self._topic_events[subject] = asyncio.Event()

        deadline = asyncio.get_event_loop().time() + timeout
        while len(self.events_on(subject)) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            self._topic_events[subject].clear()
            try:
                await asyncio.wait_for(self._topic_events[subject].wait(), timeout=remaining)
            except TimeoutError:
                break
        return self.events_on(subject)

    # ── Injection ────────────────────────────────────────────────

    async def inject(self, subject: str, data: dict[str, Any]) -> None:
        """Publish a JSON message onto the mock mesh."""
        payload = orjson.dumps(data)
        await self.js.publish(subject, payload)

    async def inject_binary(self, subject: str, data: bytes, headers: dict[str, str] | None = None) -> None:
        """Publish a binary (PCM) payload onto the mock mesh."""
        self.nc._trigger(subject, data, headers)
        await self.nc.drain()
