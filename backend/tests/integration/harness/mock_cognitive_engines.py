"""Deterministic mock LLM and TTS engines for E2E testing.

These replace the real ``OllamaClient`` / cloud LLM and GPT-SoVITS voice
synthesis with controlled, instant responders so the E2E pipeline tests
run in < 3 seconds without needing a GPU or model weights.
"""

from __future__ import annotations

import struct
import time
from collections.abc import AsyncIterator
from typing import Any

# ── Mock LLM ─────────────────────────────────────────────────────────


class MockDeterministicLLM:
    """Predictable LLM that returns controlled, deterministic responses.

    The response is configurable per-test.  By default it streams 7 words
    (one segment's worth at the default ``HybridSegmenter.target_size``),
    word-by-word, simulating a real token-streaming LLM.

    This class is duck-type-compatible with the ``OllamaClient`` /
    ``build_llm_client()`` interface that ``BrainAgent`` and
    ``SubconsciousAgent`` use.
    """

    def __init__(
        self,
        response: str = "Hello there, I am doing great today!",
        intent_json: str | None = None,
    ) -> None:
        self.response = response
        self.intent_json = intent_json or (
            '{"intent": "CHAT", "goal": "ENGAGE", "confidence": 0.9}'
        )
        self.generate_call_count = 0
        self.stream_call_count = 0

    async def generate(self, prompt: str, system: str | None = None, **kwargs: Any) -> str:
        """Non-streaming generation — used for intent classification."""
        self.generate_call_count += 1
        return self.intent_json

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Token-by-token streaming — used for conversational generation."""
        self.stream_call_count += 1
        return self._stream_tokens()

    def _stream_tokens(self) -> AsyncIterator[str]:
        return _TokenIterator(self.response)


class _TokenIterator:
    """Yields words one at a time with a trailing space, mimicking real
    LLM token streaming."""

    def __init__(self, text: str) -> None:
        self._words = text.split()
        self._index = 0

    def __aiter__(self) -> _TokenIterator:
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self._words):
            raise StopAsyncIteration
        word = self._words[self._index]
        self._index += 1
        # Real LLMs yield tokens with trailing whitespace.
        return word + " " if self._index < len(self._words) else word


# ── Mock TTS ─────────────────────────────────────────────────────────


class MockDeterministicTTS:
    """Generates valid PCM audio chunks without calling local GPU
    synthesis.  Each chunk is a 32 kHz mono 16-bit sine burst whose
    duration is proportional to the input text length, mimicking the
    real voice agent's ``_synthesize_chunk`` output shape.

    Also generates timestamped viseme markers for lip-sync verification.
    """

    def __init__(
        self,
        sample_rate: int = 32_000,
        ms_per_character: float = 50.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.ms_per_character = ms_per_character
        self.synthesis_count = 0

    async def synthesize(self, text: str) -> dict[str, Any]:
        """Return a dict matching the voice agent's internal TTS result shape."""
        self.synthesis_count += 1
        duration_ms = max(20, int(len(text) * self.ms_per_character))
        pcm_bytes = self._generate_pcm(duration_ms)
        visemes = self._generate_visemes(text, duration_ms)
        return {
            "audio": pcm_bytes,
            "sample_rate": self.sample_rate,
            "num_channels": 1,
            "duration_ms": duration_ms,
            "visemes": visemes,
        }

    def _generate_pcm(self, duration_ms: int) -> bytes:
        """Generate a short sine tone as raw 16-bit LE PCM."""
        import math

        num_samples = int(self.sample_rate * duration_ms / 1000)
        buf = bytearray(num_samples * 2)
        freq = 440.0
        for i in range(num_samples):
            sample = int(16384 * math.sin(2 * math.pi * freq * i / self.sample_rate))
            struct.pack_into("<h", buf, i * 2, sample)
        return bytes(buf)

    def _generate_visemes(self, text: str, duration_ms: int) -> list[dict[str, Any]]:
        """Deterministic viseme markers spaced evenly across the duration."""
        words = text.split()
        if not words:
            return []
        interval = duration_ms / len(words) if len(words) > 1 else duration_ms
        return [
            {
                "viseme_id": f"V_{i}",
                "target_level": min(1.0, 0.3 + 0.1 * (i % 5)),
                "timestamp": time.time() + (i * interval / 1000),
            }
            for i in range(len(words))
        ]

