"""
What the transcript records when the user interrupts.

The stored assistant message is not a log. Memory reads it, and the persona
prompt reads it back, so a wrong cut point does not merely misreport history --
it becomes what the agent believes it said.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.brain_agent import BrainAgent

REPLY = "I looked it up and the museum opens at ten, so we have plenty of time."


def _agent(progress=None, response=REPLY):
    agent = object.__new__(BrainAgent)
    agent.last_audio_progress = progress
    agent.last_assistant_response = response
    agent.conversation_store = SimpleNamespace(
        update_last_assistant_message=AsyncMock()
    )
    return agent


def _stop(speculative=False):
    return {
        "interrupt": True,
        "speculative": speculative,
        "reason": "confirmed_command",
        "command_text": "stop",
        "keywords": ["stop"],
        "utterance_id": "u1",
        "turn_id": None,
    }


def test_real_playback_progress_still_truncates_where_it_says():
    """The accurate path must keep working; it is the only one that knows."""
    progress = SimpleNamespace(completed=False, character_offset=26)
    agent = _agent(progress)

    asyncio.run(agent._on_audio_stop(_stop()))

    agent.conversation_store.update_last_assistant_message.assert_awaited_once()
    stored = agent.conversation_store.update_last_assistant_message.await_args.args[0]
    assert stored == REPLY[:26].strip()


def test_an_interruption_without_progress_does_not_invent_a_cut_point(caplog):
    """This replaces a hardcoded 15 characters/second estimate.

    Real speech rate varies with prosody, pauses and the synthesiser, so the
    estimate cut wherever the arithmetic landed and nothing downstream could
    tell the sentence had been reconstructed. Keeping the full text is also
    imperfect — the agent may believe it said more than was heard — but it is
    wrong honestly and visibly rather than by fabrication.
    """
    agent = _agent(progress=None)

    with caplog.at_level("INFO"):
        asyncio.run(agent._on_audio_stop(_stop()))

    agent.conversation_store.update_last_assistant_message.assert_not_awaited()
    assert any("keeping the full" in r.getMessage() for r in caplog.records)


def test_a_speculative_stop_never_rewrites_history():
    """Speculative stops are guesses about the user, not confirmed interrupts.

    Truncating on one would edit the transcript because the agent *thought* it
    heard the user start talking.
    """
    progress = SimpleNamespace(completed=False, character_offset=26)
    agent = _agent(progress)

    asyncio.run(agent._on_audio_stop(_stop(speculative=True)))

    agent.conversation_store.update_last_assistant_message.assert_not_awaited()


def test_progress_is_cleared_even_when_nothing_was_truncated():
    """Otherwise a stale offset survives into the next interruption.

    The reset lived only on the branch that truncated, so a stop matching none
    of the guards left the marker in place — and the *next* barge-in would cut
    the new reply at an offset measured against a reply that had already ended.
    """
    progress = SimpleNamespace(completed=True, character_offset=26)  # completed
    agent = _agent(progress)

    asyncio.run(agent._on_audio_stop(_stop()))

    agent.conversation_store.update_last_assistant_message.assert_not_awaited()
    assert agent.last_audio_progress is None


def test_the_response_start_timestamp_is_gone():
    """It was written on one streaming path and read only by the estimate.

    Leaving it would be a field that looks like turn state, is set on one of the
    two paths that produce a reply, and is read by nothing — the exact shape of
    the bug it enabled, where elapsed time could be measured from an earlier
    turn.
    """
    import inspect

    from app.agents import brain_agent

    source = inspect.getsource(brain_agent)
    assert "self.assistant_response_start_time = time.time()" not in source


@pytest.mark.parametrize("offset", [0, len(REPLY), len(REPLY) + 50])
def test_an_out_of_range_offset_leaves_the_reply_alone(offset):
    """A zero or past-the-end offset means "nothing useful is known".

    Zero would store an empty message; past-the-end would strip the trailing
    whitespace off a reply that was heard in full and rewrite it for no reason.
    """
    progress = SimpleNamespace(completed=False, character_offset=offset)
    agent = _agent(progress)

    asyncio.run(agent._on_audio_stop(_stop()))

    agent.conversation_store.update_last_assistant_message.assert_not_awaited()
