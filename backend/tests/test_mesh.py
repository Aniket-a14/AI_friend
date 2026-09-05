"""
Multi-Agent Cognitive Mesh Test Suite
Tests for the decentralized micro-agent architecture.
"""

import pytest

from app.agents.base import BaseAgent
from app.config import Config


class TestBaseAgent:
    """Test the foundational BaseAgent lifecycle."""

    @pytest.mark.asyncio
    async def test_agent_connection(self):
        """Verify agent can connect to NATS mesh."""
        agent = BaseAgent(name="test_agent", nats_url="nats://127.0.0.1:4222")

        try:
            await agent.connect()
            assert agent.nc is not None, "NATS connection should be established"
            assert agent.js is not None, "JetStream should be initialized"
        finally:
            await agent.stop()

    @pytest.mark.asyncio
    async def test_agent_publish(self):
        """Verify agent can publish to the mesh."""
        agent = BaseAgent(name="test_publisher")

        try:
            await agent.connect()
            # Publish a test message
            await agent.publish("chat.test", {"message": "hello"})
            # If no exception, publish succeeded
            assert True
        finally:
            await agent.stop()

    @pytest.mark.asyncio
    async def test_agent_state_broadcast(self):
        """Verify agent can broadcast state updates."""
        agent = BaseAgent(name="test_state_agent")

        try:
            await agent.connect()
            await agent.set_state("thinking")
            # State broadcast should not raise exceptions
            assert True
        finally:
            await agent.stop()


class TestConfiguration:
    """Test environment-aware configuration."""

    def test_config_defaults(self):
        """Verify default configuration values."""
        assert Config.NATS_URL is not None
        assert Config.SAMPLE_RATE == 32000

    def test_config_environment_override(self, monkeypatch):
        """Verify environment variables override defaults."""
        from app.config import AppSettings

        with monkeypatch.context() as m:
            m.setenv("NATS_URL", "nats://custom:4222")
            settings = AppSettings()
            assert settings.NATS_URL == "nats://custom:4222"



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
