"""
P3-4: shutdown consistency. The agent owning the most resources
(brain_agent: LLM client, graph driver, two DB pools, the whole cognitive
core) used to close none of them on stop() -- and every agent, brain
included, leaked its BaseAgent-level SubjectMetrics background thread
forever, a gap explicitly deferred from Cluster 2 (P3-2/telemetry).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import BaseAgent
from app.agents.brain_agent import BrainAgent
from app.agents.subconscious_agent import SubconsciousAgent
from app.agents.surfacing_agent import SurfacingAgent
from app.vision.agent import VisionAgent
from app.vision.links import ScreenLink


def _stopped_base_agent() -> BaseAgent:
    agent = BaseAgent(name="test_shutdown_agent")
    agent.nc = None  # skip the real drain() path
    return agent


@pytest.mark.asyncio
async def test_base_agent_stop_shuts_down_its_own_metrics_thread():
    agent = _stopped_base_agent()
    agent._metrics.shutdown = MagicMock()

    await agent.stop()

    agent._metrics.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_brain_agent_stop_closes_every_owned_resource(
    mock_llm_service, mock_graph_db, mock_memory_store
):
    from app.state import ConversationHistoryStore

    store = ConversationHistoryStore()
    await store.initialize()

    mock_memory_store.close = AsyncMock()
    agent = BrainAgent(
        ollama_url="http://dummy",
        graph_db=mock_graph_db,
        memory_store=mock_memory_store,
        conversation_store=store,
    )
    agent.ollama.close = AsyncMock()
    agent.cognitive_core.close = MagicMock()
    agent.nc = None

    await agent.stop()

    agent.ollama.close.assert_awaited_once()
    mock_graph_db.close.assert_awaited_once()
    mock_memory_store.close.assert_awaited_once()
    agent.cognitive_core.close.assert_called_once()

    await store.close()


@pytest.mark.asyncio
async def test_brain_agent_stop_cancels_an_in_flight_generation_task(
    mock_llm_service, mock_graph_db, mock_memory_store
):
    agent = BrainAgent(
        ollama_url="http://dummy",
        graph_db=mock_graph_db,
        memory_store=mock_memory_store,
        conversation_store=None,
    )
    agent.ollama.close = AsyncMock()
    agent.cognitive_core.close = MagicMock()
    agent.nc = None

    started = asyncio.Event()

    async def _long_running():
        started.set()
        await asyncio.sleep(60)

    task = asyncio.create_task(_long_running())
    agent._active_generation_task = task
    await started.wait()

    await agent.stop()

    assert task.done()
    assert task.cancelled()


@pytest.mark.asyncio
async def test_subconscious_agent_stop_closes_graph_db(mock_graph_db):
    mock_memory_store = MagicMock()
    mock_memory_store.close = AsyncMock()
    agent = SubconsciousAgent(
        memory_store=mock_memory_store,
        reflection_service=MagicMock(),
        graph_db=mock_graph_db,
    )
    agent.llm.close = AsyncMock()
    agent.nc = None

    await agent.stop()

    mock_graph_db.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_surfacing_agent_stop_closes_memory_and_its_own_metrics(mock_graph_db):
    mock_memory_store = MagicMock()
    mock_memory_store.close = AsyncMock()
    agent = SurfacingAgent(memory_store=mock_memory_store, graph_db=mock_graph_db)
    agent._surfacing_metrics.shutdown = MagicMock()
    agent.nc = None

    await agent.stop()

    mock_memory_store.close.assert_awaited_once()
    agent._surfacing_metrics.shutdown.assert_called_once()


def test_screen_link_close_releases_and_clears_sct():
    link = ScreenLink.__new__(ScreenLink)
    fake_sct = MagicMock()
    link.sct = fake_sct

    link.close()

    fake_sct.close.assert_called_once()
    assert link.sct is None


def test_screen_link_close_is_a_no_op_when_already_headless():
    link = ScreenLink.__new__(ScreenLink)
    link.sct = None

    link.close()  # must not raise

    assert link.sct is None


@pytest.mark.asyncio
async def test_vision_agent_stop_closes_screen_and_vlm_client():
    agent = VisionAgent.__new__(VisionAgent)
    agent.running = True
    agent.camera = MagicMock()
    agent.screen = MagicMock()
    agent.vlm_client = MagicMock()
    agent.vlm_client.close = AsyncMock()
    agent.nc = None
    agent._metrics = MagicMock()
    agent._background_tasks = set()

    await agent.stop()

    assert agent.running is False
    agent.camera.close.assert_called_once()
    agent.screen.close.assert_called_once()
    agent.vlm_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_vision_agent_stop_tolerates_a_disabled_vlm_client():
    """VLM_ENABLED=False leaves `vlm_client` as None -- stop() must not
    crash trying to close something that was never created."""
    agent = VisionAgent.__new__(VisionAgent)
    agent.running = True
    agent.camera = MagicMock()
    agent.screen = MagicMock()
    agent.vlm_client = None
    agent.nc = None
    agent._metrics = MagicMock()
    agent._background_tasks = set()

    await agent.stop()  # must not raise

    assert agent.running is False


def test_cognitive_service_close_shuts_down_its_own_metrics(
    mock_llm_service, mock_graph_db, mock_memory_store
):
    from app.cognitive import CognitiveService

    service = CognitiveService(
        llm_service=mock_llm_service,
        memory_store=mock_memory_store,
        graph_db=mock_graph_db,
    )
    service._metrics.shutdown = MagicMock()

    service.close()

    service._metrics.shutdown.assert_called_once()
