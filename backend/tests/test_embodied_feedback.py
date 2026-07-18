import asyncio

import pytest
from app.state import ConversationHistoryStore
from app.agents.brain_agent import BrainAgent


@pytest.mark.asyncio
async def test_dialogue_truncation_on_interruption(
    mock_llm_service, mock_graph_db, mock_memory_store
):
    # Initialize ConversationHistoryStore which falls back to our mock asyncpg (SQLite)
    store = ConversationHistoryStore()
    await store.initialize()

    # Start session
    await store.start_session()

    # Log an assistant message
    original_text = "I was planning to buy a coffee, but I forgot my wallet."
    await store.log_message("assistant", original_text)

    # Verify the message is logged
    brief = await store.get_last_interaction_brief()
    assert brief == original_text

    # Instantiate BrainAgent with injected dependencies
    agent = BrainAgent(
        ollama_url="http://dummy",
        graph_db=mock_graph_db,
        memory_store=mock_memory_store,
        conversation_store=store,
    )

    # Set agent's state
    agent.last_assistant_response = original_text

    # Simulate receiving audio.playback.progress
    # Slice at "I was planning to buy a coffee" (length 30)
    progress_data = {
        "utterance_id": "utt-1",
        "character_offset": 30,
        "word_index": 6,
        "completed": False,
    }
    await agent._on_audio_playback_progress(progress_data)
    assert agent.last_audio_progress is not None
    assert agent.last_audio_progress.character_offset == 30

    # Simulate receiving confirmed AUDIO_STOP
    stop_data = {
        "interrupt": True,
        "speculative": False,
        "reason": "confirmed_stop",
        "intent_type": "VOICE_INTERRUPTION",
    }
    await agent._on_audio_stop(stop_data)

    # Verify database has the truncated text
    new_brief = await store.get_last_interaction_brief()
    assert new_brief == "I was planning to buy a coffee"

    # Verify last_audio_progress has been cleared
    assert agent.last_audio_progress is None

    await store.close()


@pytest.mark.asyncio
async def test_dialogue_truncation_via_estimation_fallback(
    mock_llm_service, mock_graph_db, mock_memory_store, monkeypatch
):
    store = ConversationHistoryStore()
    await store.initialize()

    await store.start_session()
    original_text = "I was planning to buy a coffee, but I forgot my wallet."
    await store.log_message("assistant", original_text)

    agent = BrainAgent(
        ollama_url="http://dummy",
        graph_db=mock_graph_db,
        memory_store=mock_memory_store,
        conversation_store=store,
    )

    agent.last_assistant_response = original_text
    import time

    fixed_time = 1713330000.0
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    agent.assistant_response_start_time = fixed_time - 2.0

    assert agent.last_audio_progress is None

    stop_data = {
        "interrupt": True,
        "speculative": False,
        "reason": "confirmed_stop",
        "intent_type": "VOICE_INTERRUPTION",
    }
    await agent._on_audio_stop(stop_data)

    new_brief = await store.get_last_interaction_brief()
    assert new_brief == "I was planning to buy a coffee"

    await store.close()


@pytest.mark.asyncio
async def test_cancel_active_generation_waits_for_task_to_fully_unwind(
    mock_llm_service, mock_graph_db, mock_memory_store
):
    """A4 regression: cancelling the active generation task must wait for the
    task to actually stop touching shared turn state, not just request
    cancellation and move on. Otherwise a new turn (or a semantic interrupt)
    can reset last_assistant_response while the old, "cancelled" task is still
    mid-flight and about to write stale data on top of it.
    """
    store = ConversationHistoryStore()
    await store.initialize()
    await store.start_session()

    agent = BrainAgent(
        ollama_url="http://dummy",
        graph_db=mock_graph_db,
        memory_store=mock_memory_store,
        conversation_store=store,
    )

    cleanup_done = asyncio.Event()

    async def slow_old_turn():
        try:
            agent.last_assistant_response = "partial-old-turn-text"
            await asyncio.sleep(10)
        finally:
            # Simulates a still-unwinding _stream_to_speech/_process_chat_input_flow
            # writing turn state after being cancelled.
            agent.last_assistant_response = (
                (agent.last_assistant_response or "") + "-cleanup-write"
            )
            cleanup_done.set()

    task = asyncio.create_task(slow_old_turn())
    agent._active_generation_task = task

    # Let the task actually start and set its initial state.
    await asyncio.sleep(0)
    assert agent.last_assistant_response == "partial-old-turn-text"

    await agent._cancel_active_generation("test cancellation")

    # By the time _cancel_active_generation returns, the old task's cleanup
    # must have already run (not still pending on the event loop).
    assert cleanup_done.is_set()
    assert agent.last_assistant_response == "partial-old-turn-text-cleanup-write"
    assert agent._active_generation_task is None

    await store.close()
