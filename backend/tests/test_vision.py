"""
Test suite for the Tier-4 Vision Intelligence Agent and Visual Appraisal Service.
Validates VLM appraisals, rate-limiting, source switching controls, and NATS emissions.
"""

import pytest
import base64
import time
from unittest.mock import MagicMock, AsyncMock, patch
from app.vision.appraisal import VisualAppraisalService
from app.vision.agent import VisionAgent
from app.contracts import Topics, VisionDescription


@pytest.fixture
def mock_ollama_client():
    client = MagicMock()
    client.describe_image = AsyncMock(return_value="A developer coding on a laptop.")
    return client


@pytest.fixture
def mock_appraisal_service(mock_ollama_client):
    service = VisualAppraisalService(
        ollama_client=mock_ollama_client,
        model="moondream",
        interval=1.0,
        prompt="Describe what you see.",
    )
    return service


class TestVisualAppraisalService:
    @pytest.mark.asyncio
    async def test_appraisal_initial_call_triggers_vlm(self, mock_appraisal_service, mock_ollama_client):
        # Initial call should trigger the VLM describe_image call
        desc = await mock_appraisal_service.appraise("fake_base64_string")
        assert desc == "A developer coding on a laptop."
        mock_ollama_client.describe_image.assert_awaited_once_with(
            image_b64="fake_base64_string",
            prompt="Describe what you see.",
            model="moondream",
        )

    @pytest.mark.asyncio
    async def test_appraisal_rate_limiting_returns_cached_description(self, mock_appraisal_service, mock_ollama_client):
        # Call it once to populate the cache
        desc1 = await mock_appraisal_service.appraise("fake_base64_string")
        assert desc1 == "A developer coding on a laptop."

        # Call it again immediately; it should respect rate limiting and NOT trigger a second VLM call
        mock_ollama_client.describe_image.reset_mock()
        desc2 = await mock_appraisal_service.appraise("another_fake_base64_string")
        
        # Returns cached value from first call
        assert desc2 == "A developer coding on a laptop."
        mock_ollama_client.describe_image.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_appraisal_error_tolerance_returns_cache(self, mock_appraisal_service, mock_ollama_client):
        # Call once successfully to establish cache
        await mock_appraisal_service.appraise("fake_base64_string")

        # Force next VLM call to raise an exception
        mock_ollama_client.describe_image = AsyncMock(side_effect=Exception("Ollama Connection Timeout"))
        
        # Advance time beyond the appraisal interval to trigger a new VLM call
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        
        # Call service; it should gracefully catch exception and return last cached value
        desc = await mock_appraisal_service.appraise("new_frame_b64")
        assert desc == "A developer coding on a laptop."


class TestVisionAgent:
    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_vision_agent_initialization(self, mock_camera_cls, mock_screen_cls):
        agent = VisionAgent()
        assert agent.source == "screen"
        assert agent.vlm_enabled is True
        assert agent.running is False

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_vision_agent_source_switching(self, mock_camera_cls, mock_screen_cls):
        agent = VisionAgent()
        
        # Initial source defaults to screen
        assert agent.source == "screen"

        # Switch to camera
        await agent._handle_control({"source": "camera"})
        assert agent.source == "camera"

        # Switch to screen
        await agent._handle_control({"source": "screen"})
        assert agent.source == "screen"

        # Switch to invalid source; should ignore
        await agent._handle_control({"source": "invalid_source"})
        assert agent.source == "screen"

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_vision_agent_run_appraisal_publishes_event(self, mock_camera_cls, mock_screen_cls):
        agent = VisionAgent()
        agent.publish = AsyncMock()
        
        # Mock appraisal service to return a description
        mock_appraisal = MagicMock()
        mock_appraisal.should_appraise.return_value = True
        mock_appraisal.appraise = AsyncMock(return_value="A clean glass desk with three monitors.")
        agent.appraisal = mock_appraisal

        await agent._run_appraisal("frame_payload_b64")

        # Verify appraisal was invoked and output published to Topics.VISION_DESCRIPTION
        mock_appraisal.appraise.assert_awaited_once_with("frame_payload_b64")
        agent.publish.assert_awaited_once()
        
        topic, payload = agent.publish.await_args.args
        assert topic == Topics.VISION_DESCRIPTION
        
        # Verify schema compliance
        msg = VisionDescription.model_validate(payload)
        assert msg.description == "A clean glass desk with three monitors."
        assert msg.source == "screen"
