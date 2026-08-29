"""
#120 (H9): PerceptionService used to run its own REMEMBER/memorize keyword
heuristic for USER_MESSAGE events, independently of DecisionService's heuristic
(_apply_heuristic_intent_and_goal), which runs later in the pipeline and always
overwrites `event.intent`. The two could disagree — e.g. "do you remember my
hometown?" — and Perception's answer was never actually observable downstream.
These tests pin the simplified behavior: Perception only distinguishes
SYSTEM_TICK (-> REFLECT) from everything else (-> CHAT), and does not attempt
REMEMBER classification at all.
"""

import pytest

from app.cognitive.perception import PerceptionService


@pytest.mark.asyncio
async def test_user_message_is_always_chat_regardless_of_remember_keywords():
    """If this regresses to keyword-based REMEMBER classification, a message
    like 'do you remember my hometown?' would again disagree with
    DecisionService's question-guarded heuristic, reintroducing H9."""
    service = PerceptionService(llm_service=object())

    event = await service.perceive(
        {
            "id": "evt-1",
            "type": "USER_MESSAGE",
            "content": "please remember to memorize this for me",
            "metadata": {},
        }
    )

    assert event.intent == "CHAT"


@pytest.mark.asyncio
async def test_user_message_is_chat_even_without_an_llm_service():
    service = PerceptionService(llm_service=None)

    event = await service.perceive(
        {
            "id": "evt-2",
            "type": "USER_MESSAGE",
            "content": "hello there",
            "metadata": {},
        }
    )

    assert event.intent == "CHAT"


@pytest.mark.asyncio
async def test_system_tick_is_reflect():
    """REFLECT must keep surviving to DecisionService's BT: its heuristic only
    ever touches USER_MESSAGE events, so this is the one intent Perception sets
    that is actually load-bearing."""
    service = PerceptionService(llm_service=None)

    event = await service.perceive(
        {"id": "evt-3", "type": "SYSTEM_TICK", "content": "", "metadata": {}}
    )

    assert event.intent == "REFLECT"
