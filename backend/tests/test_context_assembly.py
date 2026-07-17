"""Tests for context assembly in the Action layer.

Covers two anti-degradation goals:
  * "lost in the middle" — edge-loading the most relevant memories, and
  * hallucination — a grounding constraint in the system prompt.
"""

import pytest
from unittest.mock import MagicMock

from app.cognitive.action import (
    ActionService,
    reorder_for_long_context,
    _memory_relevance,
)
from app.cognitive.decision import ActionPlan


def _mem(content, score=None, relevance=None):
    m = {"content": content}
    if score is not None:
        m["score"] = score
    if relevance is not None:
        m["relevance"] = relevance
    return m


class TestReorderForLongContext:
    def test_most_relevant_land_on_the_edges(self):
        mems = [
            _mem("A", score=5.0),
            _mem("B", score=4.0),
            _mem("C", score=3.0),
            _mem("D", score=2.0),
            _mem("E", score=1.0),
        ]
        ordered = [m["content"] for m in reorder_for_long_context(mems)]
        # A (best) and B (second) bracket the block; E (worst) sits in the middle.
        assert ordered == ["A", "C", "E", "D", "B"]

    def test_input_order_is_not_trusted(self):
        # Shuffled input must produce the same relevance-driven layout.
        mems = [
            _mem("C", score=3.0),
            _mem("E", score=1.0),
            _mem("A", score=5.0),
            _mem("D", score=2.0),
            _mem("B", score=4.0),
        ]
        ordered = [m["content"] for m in reorder_for_long_context(mems)]
        assert ordered[0] == "A"
        assert ordered[-1] == "B"
        assert ordered[len(ordered) // 2] == "E"

    def test_relevance_key_is_honoured_like_score(self):
        # The proactive surfacing path emits `relevance`, not `score`.
        mems = [
            _mem("low", relevance=0.1),
            _mem("high", relevance=0.9),
            _mem("mid", relevance=0.5),
        ]
        ordered = [m["content"] for m in reorder_for_long_context(mems)]
        assert ordered[0] == "high"

    def test_no_memory_is_dropped_or_duplicated(self):
        mems = [_mem(str(i), score=float(i)) for i in range(7)]
        ordered = reorder_for_long_context(mems)
        assert len(ordered) == 7
        assert {m["content"] for m in ordered} == {str(i) for i in range(7)}

    def test_unranked_items_do_not_crash(self):
        mems = [_mem("x"), _mem("y"), _mem("z")]
        ordered = reorder_for_long_context(mems)
        assert {m["content"] for m in ordered} == {"x", "y", "z"}

    def test_empty_and_single(self):
        assert reorder_for_long_context([]) == []
        one = reorder_for_long_context([_mem("only", score=1.0)])
        assert [m["content"] for m in one] == ["only"]

    def test_relevance_ignores_bool_scores(self):
        # bool is an int subclass; it must not be read as a numeric relevance.
        assert _memory_relevance({"score": True}) == 0.0
        assert _memory_relevance({"score": 2.5}) == 2.5
        assert _memory_relevance({"relevance": 0.4}) == 0.4
        assert _memory_relevance({}) == 0.0


class TestActionPromptAssembly:
    @pytest.fixture
    def action_service(self):
        return ActionService(llm_service=MagicMock())

    async def _capture_prompt(self, action_service, plan):
        captured = {}

        async def capturing_stream(prompt, system=None, model=None, options_override=None):
            captured["prompt"] = prompt
            captured["system"] = system
            yield "ok."

        action_service.llm.generate_stream = MagicMock(side_effect=capturing_stream)
        async for _ in action_service.execute(plan):
            pass
        return captured

    @pytest.mark.asyncio
    async def test_shared_history_is_edge_loaded(self, action_service):
        plan = ActionPlan(
            action_type="RESPOND_CHAT",
            goal="ENGAGE",
            payload={
                "message": "what do you remember?",
                "identity_prompt": "You are my friend.",
                "emotion_state": "neutral",
                "surfaced_memories": [
                    _mem("MOST relevant fact", score=9.0),
                    _mem("second fact", score=7.0),
                    _mem("third fact", score=5.0),
                    _mem("LEAST relevant fact", score=1.0),
                ],
            },
        )
        captured = await self._capture_prompt(action_service, plan)
        prompt = captured["prompt"]

        # The strongest memory opens the block; the least relevant is not last.
        pos_most = prompt.index("MOST relevant fact")
        pos_second = prompt.index("second fact")
        pos_least = prompt.index("LEAST relevant fact")
        # Most relevant appears before the least; the second-best is edge-loaded
        # to the tail, so it comes after the least-relevant (middle) item.
        assert pos_most < pos_least < pos_second

    @pytest.mark.asyncio
    async def test_system_prompt_carries_grounding_constraint(self, action_service):
        plan = ActionPlan(
            action_type="RESPOND_CHAT",
            goal="ENGAGE",
            payload={
                "message": "hi",
                "identity_prompt": "You are my friend.",
                "emotion_state": "neutral",
            },
        )
        captured = await self._capture_prompt(action_service, plan)
        assert "GROUNDING" in captured["system"]
        assert "Do not invent" in captured["system"]
