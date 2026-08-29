"""Mock LiveKit WebRTC transport layer for E2E testing.

Provides synthetic audio frame injection (ingress) and PCM output capture
(egress) without requiring a real LiveKit SFU, browser, or WebRTC network
stack.  Every class in this module mirrors only the subset of the real
``livekit.rtc`` API that ``TransportAgent`` touches, so it can be used as
a drop-in replacement during integration tests.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

# ── Synthetic audio frame ────────────────────────────────────────────


@dataclass
class MockAudioFrame:
    """Mirrors ``livekit.rtc.AudioFrame`` — a buffer of interleaved 16-bit
    PCM samples with sample-rate and channel metadata."""

    data: bytearray
    sample_rate: int = 16_000
    num_channels: int = 1

    @classmethod
    def silence(
        cls, duration_ms: int = 20, sample_rate: int = 16_000
    ) -> MockAudioFrame:
        """Generate a frame of silence (all-zero PCM)."""
        num_samples = int(sample_rate * duration_ms / 1000)
        return cls(
            data=bytearray(num_samples * 2),  # 16-bit = 2 bytes per sample
            sample_rate=sample_rate,
            num_channels=1,
        )

    @classmethod
    def tone(
        cls,
        frequency_hz: float = 440.0,
        duration_ms: int = 20,
        amplitude: float = 0.5,
        sample_rate: int = 16_000,
    ) -> MockAudioFrame:
        """Generate a frame containing a pure sine-wave tone.

        Useful for verifying the PCM path end-to-end without needing a
        real recording.
        """
        import math

        num_samples = int(sample_rate * duration_ms / 1000)
        max_val = int(32767 * min(1.0, max(0.0, amplitude)))
        buf = bytearray(num_samples * 2)
        for i in range(num_samples):
            sample = int(
                max_val * math.sin(2 * math.pi * frequency_hz * i / sample_rate)
            )
            struct.pack_into("<h", buf, i * 2, sample)
        return cls(data=buf, sample_rate=sample_rate, num_channels=1)


# ── Mock AudioStream (inbound direction) ─────────────────────────────


@dataclass
class _AudioStreamEvent:
    """Wraps a frame so the iterable looks like ``rtc.AudioStream``."""

    frame: MockAudioFrame


class MockAudioStream:
    """Replaces ``rtc.AudioStream(track)`` — yields pre-loaded frames as
    though they were arriving from a remote WebRTC participant.

    Usage in tests::

        frames = [MockAudioFrame.tone(duration_ms=20) for _ in range(5)]
        stream = MockAudioStream(frames)
        async for event in stream:
            process(event.frame)
    """

    def __init__(self, frames: list[MockAudioFrame] | None = None) -> None:
        self._frames = frames or []
        self._index = 0

    def __aiter__(self) -> AsyncIterator[_AudioStreamEvent]:
        return self

    async def __anext__(self) -> _AudioStreamEvent:
        if self._index >= len(self._frames):
            raise StopAsyncIteration
        frame = self._frames[self._index]
        self._index += 1
        # Simulate real-time frame pacing (non-blocking).
        await asyncio.sleep(0)
        return _AudioStreamEvent(frame=frame)


# ── Mock AudioSource (outbound capture) ──────────────────────────────


class MockAudioSource:
    """Replaces ``rtc.AudioSource`` — captures frames pushed by
    ``TransportAgent._audio_playback_worker`` so the E2E test can assert
    on the PCM data that *would* have reached the WebRTC egress track.
    """

    def __init__(self, sample_rate: int = 16_000, num_channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.captured_frames: list[MockAudioFrame] = []
        self._capture_event = asyncio.Event()

    async def capture_frame(self, frame: MockAudioFrame) -> None:
        self.captured_frames.append(frame)
        self._capture_event.set()

    async def wait_for_frames(
        self, count: int = 1, timeout: float = 2.0
    ) -> list[MockAudioFrame]:
        """Block until at least *count* frames have been captured."""
        deadline = asyncio.get_event_loop().time() + timeout
        while len(self.captured_frames) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            self._capture_event.clear()
            try:
                await asyncio.wait_for(self._capture_event.wait(), timeout=remaining)
            except TimeoutError:
                break
        return list(self.captured_frames)

    def clear(self) -> None:
        self.captured_frames.clear()
        self._capture_event.clear()


# ── Mock Track / Publication ─────────────────────────────────────────


class MockLocalAudioTrack:
    """Minimal stand-in for ``rtc.LocalAudioTrack``."""

    def __init__(
        self, name: str = "ai-voice", source: MockAudioSource | None = None
    ) -> None:
        self.name = name
        self.sid = f"TR_mock_{name}"
        self._source = source

    @classmethod
    def create_audio_track(
        cls, name: str, source: MockAudioSource
    ) -> MockLocalAudioTrack:
        return cls(name=name, source=source)


class MockRemoteAudioTrack:
    """Minimal stand-in for ``rtc.RemoteAudioTrack``."""

    def __init__(self, sid: str = "TR_remote_user") -> None:
        self.sid = sid
        self.kind = "KIND_AUDIO"


@dataclass
class MockTrackPublication:
    """Minimal stand-in for ``rtc.LocalTrackPublication``."""

    sid: str = "PUB_mock_001"
    track: MockLocalAudioTrack | None = None


# ── Mock Room ────────────────────────────────────────────────────────


class MockLocalParticipant:
    """Minimal stand-in for ``rtc.LocalParticipant``."""

    def __init__(self) -> None:
        self._publications: list[MockTrackPublication] = []

    async def publish_track(self, track: MockLocalAudioTrack) -> MockTrackPublication:
        pub = MockTrackPublication(sid=f"PUB_{track.name}", track=track)
        self._publications.append(pub)
        return pub

    async def unpublish_track(self, sid: str) -> None:
        self._publications = [p for p in self._publications if p.sid != sid]

    async def publish_data(
        self, data: bytes, *, reliable: bool = True, topic: str = ""
    ) -> None:
        """Captures data-channel sends (e.g. visemes)."""


class MockRoom:
    """Replaces ``rtc.Room`` for testing without a real LiveKit SFU."""

    def __init__(self) -> None:
        self.local_participant = MockLocalParticipant()
        self.remote_participants: dict[str, Any] = {}
        self._callbacks: dict[str, list] = {}
        self._connected = False

    async def connect(self, url: str, token: str) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def on(self, event_name: str, callback) -> None:
        self._callbacks.setdefault(event_name, []).append(callback)

    def emit(self, event_name: str, *args, **kwargs) -> None:
        """Trigger registered callbacks (for test-side simulation)."""
        for cb in self._callbacks.get(event_name, []):
            cb(*args, **kwargs)
