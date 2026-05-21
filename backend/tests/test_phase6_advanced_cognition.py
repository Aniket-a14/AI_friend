import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.cognitive.action import ActionService
from app.cognitive.decision import ActionPlan
from app.agents.subconscious_agent import SubconsciousAgent
import cognitive_rust


@pytest.mark.asyncio
async def test_acoustic_reflex_rust():
    # Asserts that evaluate_acoustic_reflex properly registers loud signals and outputs startle interrupts.
    # Signature in cognitive_rust: evaluate_acoustic_reflex(rms: float, _zcr: float, threshold: float) -> bool
    assert cognitive_rust.evaluate_acoustic_reflex(95.0, 0.0, 80.0) is True
    assert cognitive_rust.evaluate_acoustic_reflex(45.0, 0.0, 80.0) is False


@pytest.mark.asyncio
async def test_subconscious_loop_abort():
    # Simulates NATS activity during a background monologue generation and verifies that the task is immediately canceled.
    mock_state_service = MagicMock()
    mock_state_service.get_context_snapshot.return_value = {
        "emotion": "curious",
        "energy": 0.8,
    }
    mock_state_service.check_proactive_eligibility.return_value = True

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="I should do something.")

    agent = SubconsciousAgent(
        state_service=mock_state_service, graph_db=MagicMock(), memory_store=MagicMock()
    )
    agent.llm = mock_llm

    # Mock NATS connection
    agent.publish = AsyncMock()

    # Create a long running monologue task
    async def long_running_task():
        try:
            await asyncio.sleep(5)
            # This shouldn't be reached if cancelled
        except asyncio.CancelledError:
            raise

    agent._current_monologue_task = asyncio.create_task(long_running_task())
    agent._current_dream_task = asyncio.create_task(long_running_task())

    # Simulate a user message trigger via _on_chat_input
    await agent._on_chat_input({"text": "Hello there!", "metadata": {"source": "user"}})

    # Allow the event loop to yield and process cancellation
    await asyncio.sleep(0.1)

    # Verify that tasks were cancelled
    assert (
        agent._current_monologue_task.cancelled()
        or agent._current_monologue_task.done()
    )
    assert agent._current_dream_task.cancelled() or agent._current_dream_task.done()


@pytest.mark.asyncio
async def test_paralinguistic_tag_injection():
    # Validates that emotional states correctly trigger breathing/sigh tags in responses.
    llm = MagicMock()

    # Mock LLM streaming
    async def mock_stream(*args, **kwargs):
        yield "Hello."

    llm.generate_stream = MagicMock(side_effect=mock_stream)

    action_service = ActionService(llm_service=llm, memory_store=MagicMock())

    # Test case 1: arousal > 0.6 and valence < -0.3 -> prepend <breath_fast>
    plan_breath = ActionPlan(
        action_type="RESPOND_CHAT",
        goal="ENGAGE",
        payload={
            "message": "hello",
            "valence": -0.5,
            "arousal": 0.8,
            "dominance": 0.5,
        },
    )

    chunks = []
    async for chunk in action_service.execute(plan_breath):
        chunks.append(chunk)

    assert len(chunks) > 0
    content_chunks = [c["data"] for c in chunks if c["type"] == "content"]
    assert any("<breath_fast>" in c for c in content_chunks)

    # Test case 2: arousal < 0.4 and valence < 0.0 -> prepend <sigh_soft>
    plan_sigh = ActionPlan(
        action_type="RESPOND_CHAT",
        goal="ENGAGE",
        payload={
            "message": "hello",
            "valence": -0.2,
            "arousal": 0.2,
            "dominance": 0.5,
        },
    )

    chunks = []
    async for chunk in action_service.execute(plan_sigh):
        chunks.append(chunk)

    content_chunks = [c["data"] for c in chunks if c["type"] == "content"]
    assert any("<sigh_soft>" in c for c in content_chunks)


@pytest.mark.asyncio
async def test_metacognitive_self_correction():
    # Simulates an identity drift detection, verifies that control.interrupt is sent, and asserts that a correction phrase is injected.
    llm = MagicMock()

    async def mock_stream_violating(*args, **kwargs):
        yield "I hate this."

    async def mock_stream_corrected(*args, **kwargs):
        yield "Let's be positive."

    streams = [mock_stream_violating, mock_stream_corrected]
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        res = streams[call_count]
        call_count += 1
        return res(*args, **kwargs)

    llm.generate_stream = MagicMock(side_effect=side_effect)

    action_service = ActionService(llm_service=llm, memory_store=MagicMock())
    publish_mock = AsyncMock()
    action_service.publish_cb = publish_mock

    plan = ActionPlan(
        action_type="RESPOND_CHAT",
        goal="ENGAGE",
        payload={
            "message": "hello",
            "valence": 0.0,
            "arousal": 0.5,
            "dominance": 0.5,
        },
    )

    chunks = []
    async for chunk in action_service.execute(plan):
        chunks.append(chunk)

    publish_mock.assert_awaited()
    assert any(
        call.args[0] == "control.interrupt" for call in publish_mock.call_args_list
    )
    assert any(call.args[0] == "audio.stop" for call in publish_mock.call_args_list)

    content_chunks = [c["data"] for c in chunks if c["type"] == "content"]
    assert any("Wait, let me rephrase that..." in c for c in content_chunks)
    assert any("Let's be positive." in c for c in content_chunks)


@pytest.mark.asyncio
async def test_silent_reasoning_stripping():
    # Ensures that <thought> blocks are parsed out of final vocalizations but saved to telemetry.
    llm = MagicMock()

    async def mock_stream(*args, **kwargs):
        yield "<thought>Analyzing the request...</thought>Hello user!"

    llm.generate_stream = MagicMock(side_effect=mock_stream)

    action_service = ActionService(llm_service=llm, memory_store=MagicMock())

    plan = ActionPlan(
        action_type="RESPOND_CHAT",
        goal="ENGAGE",
        payload={
            "message": "hello",
            "valence": 0.0,
            "arousal": 0.5,
            "dominance": 0.5,
        },
    )

    chunks = []
    async for chunk in action_service.execute(plan):
        chunks.append(chunk)

    content_chunks = [c["data"] for c in chunks if c["type"] == "content"]
    full_vocalization = "".join(content_chunks)

    assert "<thought>" not in full_vocalization
    assert "Analyzing the request..." not in full_vocalization
    assert "Hello user!" in full_vocalization


@pytest.mark.asyncio
async def test_sleep_dreaming_neo4j():
    # Mocks Neo4j entity retrieval and verifies that generated dreams are saved as vector memories with the dream source tag.
    mock_state_service = MagicMock()
    mock_state_service.get_context_snapshot.return_value = {"fatigue": 0.9}

    mock_graph_db = MagicMock()
    mock_graph_db.execute_query = AsyncMock(
        return_value=[
            {"name": "Concept A"},
            {"name": "Concept B"},
            {"name": "Concept C"},
        ]
    )

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="I had a dream about A, B, and C.")

    mock_memory_store = MagicMock()
    mock_memory_store.add_memory = AsyncMock()

    agent = SubconsciousAgent(
        state_service=mock_state_service,
        graph_db=mock_graph_db,
        memory_store=mock_memory_store,
    )
    agent.llm = mock_llm

    await agent._run_dream_sequence()

    mock_graph_db.execute_query.assert_awaited()
    mock_memory_store.add_memory.assert_awaited_once_with(
        content="[Dream Insight] I had a dream about A, B, and C.",
        importance=0.6,
        emotion=0.4,
        source="subconscious_dream",
    )
