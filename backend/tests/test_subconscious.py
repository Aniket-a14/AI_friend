"""
Test suite for the Tier-5 Subconscious Engine.
Validates idle checking, internal thought generation, and routing to the BrainAgent.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.contracts import ChatInput, Topics


@pytest.fixture
def mock_state_service():
    service = MagicMock()
    service.check_proactive_eligibility.return_value = True
    service.get_context_snapshot.return_value = {"emotion": "curious", "energy": 0.8}
    service.current_state.last_user_interaction = 0.0
    return service


@pytest.fixture
def mock_llm_service():
    llm = MagicMock()
    llm.generate = AsyncMock(return_value='"I should ask them about their day."')
    return llm


class TestSubconsciousAgent:
    @pytest.mark.asyncio
    async def test_subconscious_agent_ignores_tick_when_ineligible(
        self, mock_state_service, mock_llm_service
    ):
        from app.agents.subconscious_agent import SubconsciousAgent

        mock_state_service.check_proactive_eligibility.return_value = False

        agent = SubconsciousAgent(
            state_service=mock_state_service, graph_db=MagicMock()
        )
        agent.llm = mock_llm_service
        agent.publish = AsyncMock()

        await agent._on_system_tick({"timestamp": 1234567890})

        # Should not generate thought or publish anything
        agent.llm.generate.assert_not_awaited()
        agent.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_subconscious_agent_generates_and_publishes_thought(
        self, mock_state_service, mock_llm_service
    ):
        from app.agents.subconscious_agent import SubconsciousAgent

        agent = SubconsciousAgent(
            state_service=mock_state_service, graph_db=MagicMock()
        )
        agent.llm = mock_llm_service
        agent.publish = AsyncMock()

        await agent._on_system_tick({"timestamp": 1234567890})

        # Ensure LLM was prompted
        agent.llm.generate.assert_awaited_once()
        prompt = agent.llm.generate.await_args.args[0]
        assert "curious" in prompt
        assert "0.8" in prompt

        # Ensure it published to CHAT_INPUT
        agent.publish.assert_awaited_once()
        topic, payload = agent.publish.await_args.args
        assert topic == Topics.CHAT_INPUT

        # Verify the payload structure
        msg = ChatInput.model_validate(payload)
        assert msg.text == "I should ask them about their day."
        assert msg.metadata.source == "subconscious"

        # Verify attempt was marked
        mock_state_service.mark_proactive_attempt.assert_called_once()


class TestBrainAgentSubconsciousRouting:
    @pytest.mark.asyncio
    async def test_brain_agent_routes_subconscious_thought_to_proactive_generator(self):
        from app.agents.brain_agent import BrainAgent

        agent = BrainAgent(graph_db=None, memory_store=None, conversation_store=None)
        agent.cognitive_core.state = MagicMock()
        agent.cognitive_core.state.get_context_snapshot.return_value = {
            "valence": 0.0,
            "arousal": 0.5,
            "dominance": 0.5,
            "fatigue": 0.0,
        }
        agent.cognitive_core.generate_proactive_response = MagicMock()
        agent.cognitive_core.process_event = MagicMock()
        agent._stream_to_speech = AsyncMock(return_value="Hello there.")

        # Simulate a subconscious thought arriving on chat.input
        thought_msg = {
            "text": "I should say hi.",
            "metadata": {"source": "subconscious"},
        }

        await agent._on_chat_input(thought_msg)

        # 1. Ensure user interaction was NOT recorded
        agent.cognitive_core.state.record_user_interaction.assert_not_called()

        # 2. Ensure it routed to generate_proactive_response, NOT process_event
        agent.cognitive_core.process_event.assert_not_called()
        agent.cognitive_core.generate_proactive_response.assert_called_once_with(
            thought_prompt="I should say hi."
        )

        # 3. Ensure stream_to_speech was called with is_proactive=True
        agent._stream_to_speech.assert_awaited_once()
        assert agent._stream_to_speech.await_args.kwargs["is_proactive"] is True
