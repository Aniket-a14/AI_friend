import asyncio
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("asyncpg", SimpleNamespace(Pool=object))

from app.agents.brain_agent import BrainAgent  # noqa: E402
from app.agents.surfacing_agent import SurfacingAgent  # noqa: E402
from app.cognitive.action import ActionService  # noqa: E402
from app.cognitive.core import CognitiveService  # noqa: E402
from app.cognitive.decision import ActionPlan  # noqa: E402
from app.conversation_history_store import ConversationHistoryStore  # noqa: E402


def test_get_last_session_time_without_current_session_builds_valid_query():
    store = ConversationHistoryStore()
    conn = AsyncMock()
    expected = datetime.now(timezone.utc)
    conn.fetchrow.return_value = {"ended_at": expected}

    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    store.pool = pool
    store.current_session_id = None

    result = asyncio.run(store.get_last_session_time())

    assert result == expected
    query = conn.fetchrow.await_args.args[0]
    assert "FROM sessions" in query
    assert "WHERE ended_at IS NOT NULL" in query


def test_cognitive_resume_recovery_accepts_type_key():
    service = CognitiveService(llm_service=None, memory_store=None, graph_db=None)
    service.agent = SimpleNamespace(publish=AsyncMock())
    service.state.last_speculative_intent = {
        "name": "SPECULATIVE_STOP",
        "keywords": ["stop"],
        "text": "stop please",
        "confidence": 0.9,
    }
    service.state.hydrate_state = AsyncMock()
    service.state.get_context_snapshot = MagicMock(
        return_value={
            "emotion": "neutral",
            "mood": 0.0,
            "energy": 0.5,
            "trust": 0.5,
            "attachment": 0.1,
            "active_goals": [],
        }
    )
    service.state.get_behavioral_directive = MagicMock(return_value="stay calm")
    service.perception.perceive = AsyncMock(
        return_value=SimpleNamespace(
            metadata={},
            intent="CHAT",
            event_id="evt-1",
            raw_content="please continue",
        )
    )
    service.decision.is_speculative_stop_confirmed = MagicMock(return_value=False)
    service.decision.decide = AsyncMock(
        return_value=ActionPlan(
            action_type="BACKGROUND_CONSOLIDATION",
            payload={},
            goal="ENGAGE",
        )
    )
    service.learning.trigger_reflection = AsyncMock()

    async def _empty_execute(plan):
        yield {"type": "done", "data": ""}

    service.action.execute = _empty_execute

    outputs = list(
        asyncio.run(
            _collect_outputs(
                service.process_event({"type": "USER_MESSAGE", "content": "please continue"})
            )
        )
    )

    assert outputs[0] == {"type": "mesh_signal", "data": "audio.resume"}
    service.agent.publish.assert_awaited_once_with(
        "audio.resume",
        {"reason": "conflict_rejected", "perception_text": "stop please"},
    )
    service.state.hydrate_state.assert_not_awaited()


def test_cognitive_confirmed_stop_escalates_to_final_audio_stop():
    service = CognitiveService(llm_service=None, memory_store=None, graph_db=None)
    service.agent = SimpleNamespace(publish=AsyncMock())
    service.state.last_speculative_intent = {
        "name": "SPECULATIVE_STOP",
        "keywords": ["stop"],
        "text": "stop",
        "confidence": 0.9,
    }
    service.perception.perceive = AsyncMock()
    service.decision.is_speculative_stop_confirmed = MagicMock(return_value=True)
    service.decision.decide = AsyncMock()

    outputs = list(
        asyncio.run(
            _collect_outputs(
                service.process_event({"type": "USER_MESSAGE", "content": "stop right now"})
            )
        )
    )

    assert outputs == [{"type": "mesh_signal", "data": "audio.stop"}]
    service.agent.publish.assert_awaited_once_with(
        "audio.stop",
        {
            "interrupt": True,
            "speculative": False,
            "reason": "confirmed_command",
            "command_text": "stop right now",
            "keywords": ["stop"],
        },
    )
    service.decision.decide.assert_not_awaited()
    service.perception.perceive.assert_not_awaited()


def test_cognitive_service_uses_shared_identity_manager():
    service = CognitiveService(llm_service=None, memory_store=None, graph_db=None)
    assert service.learning.identity is service.identity


def test_brain_agent_connects_before_cognitive_initialize():
    call_order = []

    async def _connect():
        call_order.append("connect")

    async def _initialize(agent=None):
        call_order.append("initialize")

    async def _subscribe(*args, **kwargs):
        call_order.append("subscribe")

    conversation_store = MagicMock()
    conversation_store.initialize = AsyncMock(side_effect=lambda: call_order.append("conversation_initialize"))
    conversation_store.start_session = AsyncMock(side_effect=lambda: call_order.append("start_session"))

    agent = BrainAgent(graph_db=None, memory_store=None, conversation_store=conversation_store)
    agent.connect = AsyncMock(side_effect=_connect)
    agent.subscribe = AsyncMock(side_effect=_subscribe)
    agent.cognitive_core.initialize = AsyncMock(side_effect=_initialize)

    asyncio.run(agent.start())

    assert call_order[:2] == ["connect", "initialize"]


def test_action_service_strips_emotion_wrappers_but_keeps_pause_tags():
    llm = MagicMock()

    async def _stream(prompt, model=None):
        yield "<emotion type='sad'>hey"
        yield " there</emotion><pause=300ms>"

    llm.generate_stream.side_effect = _stream
    action = ActionService(llm_service=llm)
    plan = ActionPlan(
        action_type="RESPOND_CHAT",
        payload={"message": "hello", "identity_prompt": "be natural", "emotion_state": "sad"},
        goal="ENGAGE",
    )

    outputs = list(asyncio.run(_collect_outputs(action.execute(plan))))
    content = "".join(item["data"] for item in outputs if item["type"] == "content")

    assert content == "hey there<pause=300ms>"


def test_surfacing_agent_suppresses_recently_recalled_memories():
    memory_store = MagicMock()
    memory_store.search_memories = AsyncMock(
        return_value=[{"content": "We talked about your exam", "score": 0.95}]
    )

    agent = SurfacingAgent(memory_store=memory_store)
    agent.publish = AsyncMock()
    agent.last_context = "exam stress"

    asyncio.run(agent._surface_relevant_memories())
    asyncio.run(agent._surface_relevant_memories())

    assert agent.publish.await_count == 1
    second_call = memory_store.search_memories.await_args_list[1]
    assert second_call.kwargs["refresh_on_recall"] is False
    assert second_call.kwargs["exclude_contents"] == ["We talked about your exam"]


async def _collect_outputs(generator):
    outputs = []
    async for item in generator:
        outputs.append(item)
    return outputs
