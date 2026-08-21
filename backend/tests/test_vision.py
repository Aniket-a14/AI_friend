"""
Test suite for the Tier-4 Vision Intelligence Agent and Visual Appraisal Service.
Validates VLM appraisals, rate-limiting, source switching controls, and NATS emissions.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.contracts import Topics, VisionDescription
from app.vision.agent import VisionAgent
from app.vision.appraisal import VisualAppraisalService


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
    async def test_appraisal_initial_call_triggers_vlm(
        self, mock_appraisal_service, mock_ollama_client
    ):
        # Initial call should trigger the VLM describe_image call
        desc = await mock_appraisal_service.appraise("fake_base64_string")
        assert desc == "A developer coding on a laptop."
        mock_ollama_client.describe_image.assert_awaited_once_with(
            image_b64="fake_base64_string",
            prompt="Describe what you see.",
            model="moondream",
        )

    @pytest.mark.asyncio
    async def test_appraisal_rate_limiting_returns_cached_description(
        self, mock_appraisal_service, mock_ollama_client
    ):
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
    async def test_appraisal_error_tolerance_returns_cache(
        self, mock_appraisal_service, mock_ollama_client
    ):
        # Call once successfully to establish cache
        await mock_appraisal_service.appraise("fake_base64_string")

        # Force next VLM call to raise an exception
        mock_ollama_client.describe_image = AsyncMock(
            side_effect=Exception("Ollama Connection Timeout")
        )

        # Advance time beyond the appraisal interval to trigger a new VLM call
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0

        # Call service; it should gracefully catch exception and return last cached value
        desc = await mock_appraisal_service.appraise("new_frame_b64")
        assert desc == "A developer coding on a laptop."

    @pytest.mark.asyncio
    async def test_vlm_pipeline_failure_does_not_advance_habituation_baseline(
        self, mock_appraisal_service, mock_ollama_client
    ):
        """H8: `describe_image` returning `None` (the call itself failed)
        must NOT be treated as an observed baseline - the next tick should
        still retry the VLM rather than skip it via sensory habituation,
        which is what advancing `_last_visual_vector`/`_last_appraisal_time`
        here would cause.
        """
        mock_ollama_client.describe_image = AsyncMock(return_value=None)
        forced_last_appraisal_time = time.time() - 2.0
        mock_appraisal_service._last_appraisal_time = forced_last_appraisal_time

        desc = await mock_appraisal_service.appraise("new_frame_b64")

        assert desc == ""  # falls back to the (empty) initial cache
        assert mock_appraisal_service._last_visual_vector is None
        # Unchanged from what we forced it to, not bumped to "now" - a bump
        # here would let a subsequent frame's habituation check treat this
        # failed call as an observed baseline instead of retrying the VLM.
        assert mock_appraisal_service._last_appraisal_time == forced_last_appraisal_time

    @pytest.mark.asyncio
    async def test_vlm_confirmed_quiet_scene_advances_habituation_baseline(
        self, mock_appraisal_service, mock_ollama_client
    ):
        """H8: `describe_image` returning `""` (a successful call that found
        nothing worth describing) IS a real observation and should advance
        the habituation baseline, unlike a `None` pipeline failure above.
        """
        mock_ollama_client.describe_image = AsyncMock(return_value="")
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0

        desc = await mock_appraisal_service.appraise("new_frame_b64")

        assert desc == ""
        assert mock_appraisal_service._last_visual_vector is not None
        assert mock_appraisal_service._last_appraisal_time > 0.0

    @pytest.mark.asyncio
    async def test_sensory_habituation_bypasses_vlm_if_below_threshold(
        self, mock_appraisal_service, mock_ollama_client
    ):
        # 1. Establish the initial frame and cache
        import base64

        frame_data = b"identical_frame_data"
        frame_b64 = base64.b64encode(frame_data).decode("utf-8")

        desc1 = await mock_appraisal_service.appraise(frame_b64)
        assert desc1 == "A developer coding on a laptop."
        assert mock_ollama_client.describe_image.call_count == 1

        # Reset VLM mock and advance time beyond interval
        mock_ollama_client.describe_image.reset_mock()
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0

        # 2. Call again with the same base64 frame (delta will be 0.0 < VLM_HABITUATION_THRESHOLD)
        desc2 = await mock_appraisal_service.appraise(frame_b64)
        assert desc2 == "A developer coding on a laptop."
        # Should bypass describe_image call completely due to habituation
        mock_ollama_client.describe_image.assert_not_awaited()


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
    async def test_vision_agent_source_switching(
        self, mock_camera_cls, mock_screen_cls
    ):
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
    async def test_vision_agent_run_appraisal_publishes_event(
        self, mock_camera_cls, mock_screen_cls
    ):
        agent = VisionAgent()
        agent.publish = AsyncMock()

        # Mock appraisal service to return a description
        mock_appraisal = MagicMock()
        mock_appraisal.should_appraise.return_value = True
        mock_appraisal.appraise = AsyncMock(
            return_value="A clean glass desk with three monitors."
        )
        agent.appraisal = mock_appraisal

        # We pass a simple valid base64 string for a tiny 1x1 black png or blank bytes
        import base64

        blank_frame_b64 = base64.b64encode(b"\x00" * 100).decode("utf-8")
        await agent._run_appraisal(blank_frame_b64)

        # Verify appraisal was invoked and output published to Topics.VISION_DESCRIPTION
        mock_appraisal.appraise.assert_awaited_once_with(blank_frame_b64)
        agent.publish.assert_awaited_once()

        topic, payload = agent.publish.await_args.args
        assert topic == Topics.VISION_DESCRIPTION

        # Verify schema compliance and user_distance presence
        msg = VisionDescription.model_validate(payload)
        assert msg.description == "A clean glass desk with three monitors."
        assert msg.source == "screen"
        assert msg.user_distance is not None
        assert msg.user_distance == 1.0  # Fallback since frame is invalid/blank
