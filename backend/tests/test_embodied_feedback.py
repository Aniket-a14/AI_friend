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
