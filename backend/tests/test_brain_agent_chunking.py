"""Bucket 5 (VOICE_REMEDIATION_PLAN.md): `_stream_to_speech`'s chunk-flush
logic had no dedicated test file, and nothing in the suite exercised either
defect a live capture surfaced:

  1. The "formation buffer" was named `formation_buffer_ms` but held 0.030,
     compared directly against a `time.perf_counter()` delta (seconds) --
     an actual 30ms threshold. At typical LLM token inter-arrival latency,
     30ms elapses before a chunk even reaches 3 words, so this timer almost
     always won the race against the semantic segmenter below it and
     flushed every 3 words regardless of where a real clause boundary was.
  2. `HybridSegmenter.score_split_point` gives a comma/colon/semicolon 0.4
     and the at-or-past-target_size length pressure 0.3 -- summing to
     exactly 0.7 against production's `target_size=7`, which a strict `>`
     comparison can never satisfy. The single most natural prosodic
     boundary (a comma) could never fire on its own.

This file tests brain_agent's actual flush decisions end-to-end against a
synthetic streaming generator, not just the segmenter's raw score (that
narrower check lives in test_segmentation.py) -- the real bug was in how
the two signals (timer, score) combined at the call site.
"""

import asyncio

import pytest

from app.agents.brain_agent import BrainAgent
from app.utils.segmentation import HybridSegmenter
from app.utils.speech import SpeechCoordinator


def _agent() -> BrainAgent:
    agent = BrainAgent(graph_db=None, memory_store=None, conversation_store=None)
    agent.set_state = AsyncMockCompat()
    agent.cognitive_core.state.get_context_snapshot = lambda: {"emotion": "neutral"}
    return agent


def test_production_default_formation_buffer_is_a_real_clause_window_not_30ms():
    """The other tests in this file all construct their own SpeechCoordinator
    with an explicit formation_buffer_s to control timing precisely -- none
    of them would notice a regression in BrainAgent.__init__'s own default.
    This is the one test that actually looks at what production ships:
    0.030 (30ms, the original bug) must never come back, and the value must
    be large enough that normal LLM token latency won't race ahead of the
    semantic segmenter the way it used to.
    """
    agent = BrainAgent(graph_db=None, memory_store=None, conversation_store=None)

    assert agent.coordinator.formation_buffer_s >= 0.1, (
        f"formation_buffer_s={agent.coordinator.formation_buffer_s} is too close to "
        "the original 30ms bug -- normal token latency would race ahead of the "
        "segmenter again"
    )


class AsyncMockCompat:
    """A minimal async no-op callable -- avoids importing unittest.mock just
    for a method this suite never asserts on."""

    async def __call__(self, *args, **kwargs):
        return None


async def _word_stream(words: list[str], delay_s: float):
    """Simulates one LLM token per word, `delay_s` apart, ending the turn.
    Mirrors real streaming: each word arrives as its own `content` event,
    not pre-joined -- `_handle_content_output` is exercised exactly as the
    real generator drives it.
    """
    for i, word in enumerate(words):
        if i > 0:
            await asyncio.sleep(delay_s)
        yield {"type": "content", "data": word + " "}
    yield {"type": "done", "data": ""}


async def _published_chunks(agent: BrainAgent, words: list[str], delay_s: float) -> list[str]:
    """Drives _stream_to_speech and returns each published chunk's text, in
    order, by capturing _publish_speech_chunk's `words` argument directly --
    the same call `_publish_tracked` makes internally on every flush."""
    published: list[str] = []

    async def _capture(chunk_words, *_args, **_kwargs):
        published.append(" ".join(chunk_words))

    agent._publish_speech_chunk = _capture
    agent._publish_final_chunk_payload = AsyncMockCompat()

    await agent._stream_to_speech(
        _word_stream(words, delay_s), turn_id="turn-bucket5", is_proactive=False
    )
    return published


@pytest.mark.asyncio
async def test_flush_timer_no_longer_wins_against_normal_streaming_latency():
    """The Punjab sentence from VOICE_REMEDIATION_PLAN.md's own verification
    target, minus its internal comma (isolated in the next test) -- 8 plain
    words with no punctuation until the end. At the old 30ms/3-word timer,
    any realistic per-word delay (even a fast ~50ms/token model) would have
    fragmented this into at least 3 separate chunks. With formation_buffer_s
    raised to a real clause-formation window, a delay well under it must
    let the sentence-ending period (score 0.8) decide the boundary instead.
    """
    # Margin sized generously: real asyncio.sleep overshoots its nominal
    # duration by a double-digit percentage per call (measured ~10% over 7
    # iterations of 10ms), so a tight ratio here would make this test flaky
    # under system load rather than actually verifying the fix -- a 1s
    # buffer against ~35ms of real cumulative delay leaves over an order of
    # magnitude of headroom.
    agent = _agent()
    agent.coordinator = SpeechCoordinator(
        segmenter=HybridSegmenter(target_size=7), formation_buffer_s=1.0
    )
    words = ["Hi", "I", "am", "Aniket", "I", "study", "at", "college."]

    chunks = await _published_chunks(agent, words, delay_s=0.005)

    assert chunks == ["Hi I am Aniket I study at college."], (
        f"expected the whole sentence as one chunk, got {len(chunks)} chunks: {chunks}"
    )


@pytest.mark.asyncio
async def test_flush_timer_still_acts_as_a_latency_safety_net_when_it_should():
    """Raising the threshold must not disable the timer outright -- it is a
    legitimate fallback for when the model stalls and a clause boundary
    never arrives in reasonable time. A per-word delay that exceeds
    formation_buffer_s must still flush once >= 3 words have accumulated.
    """
    agent = _agent()
    agent.coordinator = SpeechCoordinator(
        segmenter=HybridSegmenter(target_size=7), formation_buffer_s=0.05
    )
    words = ["This", "is", "taking", "a", "while", "to", "arrive."]

    chunks = await _published_chunks(agent, words, delay_s=0.08)

    assert len(chunks) > 1, (
        "a per-word delay exceeding the formation buffer must still trigger "
        "at least one timer-driven flush before the sentence ends"
    )


@pytest.mark.asyncio
async def test_comma_at_target_size_now_triggers_a_flush():
    """The off-by-epsilon fix: a comma landing exactly at chunk_len ==
    target_size (7) scores 0.4 + 0.3 == 0.7 -- production's `score >= 0.7`
    must flush right there, splitting the clause instead of silently
    absorbing the comma into a longer chunk decided by something else.
    """
    agent = _agent()
    agent.coordinator = SpeechCoordinator(
        segmenter=HybridSegmenter(target_size=7), formation_buffer_s=10.0
    )
    # "college," is the 7th word -- score_split_point("college,", 7) == 0.7.
    words = ["Hi", "I", "am", "Aniket", "I", "study", "college,", "in", "Punjab."]

    chunks = await _published_chunks(agent, words, delay_s=0.0)

    assert chunks == [
        "Hi I am Aniket I study college,",
        "in Punjab.",
    ], f"expected a split right after the comma at position 7, got: {chunks}"


@pytest.mark.asyncio
async def test_comma_before_target_size_does_not_force_a_premature_flush():
    """A comma that appears before target_size is reached scores only 0.4
    (no length-pressure term yet) and must not flush -- only an at-or-past-
    target_size comma, or sentence-ending punctuation, should."""
    agent = _agent()
    agent.coordinator = SpeechCoordinator(
        segmenter=HybridSegmenter(target_size=7), formation_buffer_s=10.0
    )
    words = ["Well,", "I", "guess", "that", "is", "true."]

    chunks = await _published_chunks(agent, words, delay_s=0.0)

    assert chunks == ["Well, I guess that is true."]
