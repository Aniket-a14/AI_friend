import asyncio
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("asyncpg", SimpleNamespace(Pool=object))

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
    service.state.last_speculative_intent = "stop"
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
        {"reason": "conflict_rejected"},
    )


async def _collect_outputs(generator):
    outputs = []
    async for item in generator:
        outputs.append(item)
    return outputs
