import asyncio
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("asyncpg", SimpleNamespace(Pool=object))

from app.agents.brain_agent import BrainAgent  # noqa: E402
from app.agents.surfacing_agent import SurfacingAgent  # noqa: E402
sys.modules.setdefault("numpy", SimpleNamespace())
from app.voice.agent import VoiceAgent, VoicePlaybackState  # noqa: E402
from app.cognitive.action import ActionService  # noqa: E402
from app.cognitive.core import CognitiveService  # noqa: E402
from app.cognitive.decision import ActionPlan  # noqa: E402
from app.cognitive.identity import IdentityManager  # noqa: E402
from app.state.agent_state import StateService  # noqa: E402
from app.state.conversation_store import ConversationHistoryStore  # noqa: E402


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
        "utterance_id": "utt-1",
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
        {
            "reason": "conflict_rejected",
            "perception_text": "stop please",
            "utterance_id": "utt-1",
        },
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
        "utterance_id": "utt-2",
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
            "utterance_id": "utt-2",
            "turn_id": None,
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

    assert call_order[0] == "connect"
    assert call_order.index("connect") < call_order.index("initialize")
    assert call_order.index("conversation_initialize") < call_order.index("initialize")


def test_brain_agent_emits_fallback_when_stream_errors_without_content():
    agent = BrainAgent(graph_db=None, memory_store=None, conversation_store=None)
    agent.set_state = AsyncMock()
    agent.publish = AsyncMock()
    agent._publish_speech_chunk = AsyncMock()
    agent.cognitive_core.state.get_context_snapshot = MagicMock(return_value={"emotion": "neutral"})

    async def _error_only_stream(_raw_event):
        yield {"type": "error", "data": "No compatible Ollama generation endpoint found"}
        yield {"type": "done", "data": ""}

    agent.cognitive_core.process_event = _error_only_stream

    asyncio.run(agent._on_chat_input({"text": "hello", "turn_id": "turn-404"}))

    agent._publish_speech_chunk.assert_awaited_once()
    fallback_words, fallback_turn_id = agent._publish_speech_chunk.await_args.args
    assert "trouble" in " ".join(fallback_words)
    assert fallback_turn_id == "turn-404"

    done_call = agent.publish.await_args_list[-1]
    assert done_call.args[0] == "chat.output"
    assert done_call.args[1]["done"] is True
    assert done_call.args[1]["turn_id"] == "turn-404"
    assert done_call.args[1]["full_response"] == "I'm having trouble thinking right now..."
    assert "No compatible Ollama generation endpoint found" in done_call.args[1]["generation_error"]


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


def test_voice_final_stop_fences_old_synthesis_generation():
    agent = VoiceAgent()
    agent.set_state = AsyncMock()

    stale_item = {"turn_id": "turn-1", "generation": agent.generation}
    assert agent._is_current_item(stale_item)

    asyncio.run(agent._on_audio_stop({"speculative": False, "turn_id": "turn-1"}))

    assert not agent._is_current_item(stale_item)
    assert agent._is_current_item({"turn_id": "turn-2", "generation": agent.generation})


def test_voice_resume_ignores_stale_utterance_id():
    agent = VoiceAgent()
    agent.set_state = AsyncMock()
    agent.state = VoicePlaybackState.SPECULATIVE_PAUSE
    agent.paused_utterance_id = "utt-current"

    asyncio.run(agent._on_audio_resume({"utterance_id": "utt-old"}))

    assert agent.state == VoicePlaybackState.SPECULATIVE_PAUSE
    agent.set_state.assert_not_awaited()


def test_voice_silence_uses_configured_sample_rate():
    agent = VoiceAgent()
    agent.sample_rate = 16000

    assert len(agent._silence_pcm(10)) == 320


def test_state_ignores_low_confidence_acoustic_bias():
    state = StateService(graph_store=None)
    state.persist_state = AsyncMock()
    state.current_state.mood = 0.4

    asyncio.run(state.apply_sensory_perception({
        "emotional_bias": -1.0,
        "confidence": 0.1,
        "events": [],
    }))

    assert state.current_state.mood == 0.4
    state.persist_state.assert_not_awaited()


def test_state_debounces_high_frequency_sensory_persistence():
    state = StateService(graph_store=None)
    state.persist_state = AsyncMock()
    state.sensory_persist_interval = 999
    state._last_sensory_persist = 0

    asyncio.run(state.apply_sensory_perception({
        "emotional_bias": 1.0,
        "confidence": 1.0,
        "events": [],
    }))
    asyncio.run(state.apply_sensory_perception({
        "emotional_bias": -1.0,
        "confidence": 1.0,
        "events": [],
    }))

    assert state.persist_state.await_count == 1


def test_identity_hydrates_from_durable_config_store():
    store = SimpleNamespace()
    store.get_agent_config = AsyncMock(return_value={
        "personality": '{"name": "durable friend", "core_personality": {"immutable": {"values": ["Honesty"], "base_tone": "Calm", "boundaries": []}}}',
        "history": '{"relationship": "Trusted Friend", "memories": []}',
        "evolved_learnings": "prefers quiet pacing",
    })

    manager = IdentityManager(base_path="/missing/path")
    asyncio.run(manager.hydrate_from_config_store(store))

    assert manager.personality["name"] == "durable friend"
    assert manager.history["relationship"] == "Trusted Friend"
    assert manager.history["evolved_learnings"] == "prefers quiet pacing"


async def _collect_outputs(generator):
    outputs = []
    async for item in generator:
        outputs.append(item)
    return outputs
