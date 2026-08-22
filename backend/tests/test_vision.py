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

    @pytest.mark.asyncio
    async def test_breaker_opens_after_consecutive_failures_and_stops_calling_vlm(
        self, mock_appraisal_service, mock_ollama_client
    ):
        """M3-R3: a down VLM used to be retried every tick with a full
        frame, with no backoff. After breaker_failure_threshold consecutive
        pipeline failures, the VLM must not be called again until the
        cooldown elapses."""
        mock_appraisal_service._breaker_failure_threshold = 2
        mock_ollama_client.describe_image = AsyncMock(return_value=None)

        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        await mock_appraisal_service.appraise("f1")
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        await mock_appraisal_service.appraise("f2")
        assert mock_appraisal_service._consecutive_failures == 2
        assert mock_appraisal_service._breaker_opened_at > 0.0

        mock_ollama_client.describe_image.reset_mock()
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        desc = await mock_appraisal_service.appraise("f3")

        mock_ollama_client.describe_image.assert_not_awaited()
        assert desc == ""

    @pytest.mark.asyncio
    async def test_breaker_half_open_trial_after_cooldown_recovers_on_success(
        self, mock_appraisal_service, mock_ollama_client
    ):
        """Once the cooldown has elapsed, the next call is a real attempt
        (a half-open trial) - a success must close the breaker rather than
        leaving it permanently open."""
        mock_appraisal_service._breaker_failure_threshold = 1
        mock_ollama_client.describe_image = AsyncMock(return_value=None)
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        await mock_appraisal_service.appraise("f1")
        assert mock_appraisal_service._breaker_opened_at > 0.0

        # Simulate the cooldown window having elapsed.
        mock_appraisal_service._breaker_cooldown_s = 0.01
        mock_appraisal_service._breaker_opened_at = time.time() - 1.0
        mock_ollama_client.describe_image = AsyncMock(return_value="Recovered scene.")
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0

        desc = await mock_appraisal_service.appraise("f2")

        mock_ollama_client.describe_image.assert_awaited_once()
        assert desc == "Recovered scene."
        assert mock_appraisal_service._consecutive_failures == 0
        assert mock_appraisal_service._breaker_opened_at == 0.0

    @pytest.mark.asyncio
    async def test_breaker_success_resets_failure_count_below_threshold(
        self, mock_appraisal_service, mock_ollama_client
    ):
        """A transient failure followed by a success must not accumulate
        toward the threshold across unrelated errors."""
        mock_appraisal_service._breaker_failure_threshold = 3
        mock_ollama_client.describe_image = AsyncMock(return_value=None)
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        await mock_appraisal_service.appraise("f1")
        assert mock_appraisal_service._consecutive_failures == 1

        mock_ollama_client.describe_image = AsyncMock(return_value="Back to normal.")
        mock_appraisal_service._last_appraisal_time = time.time() - 2.0
        await mock_appraisal_service.appraise("f2")

        assert mock_appraisal_service._consecutive_failures == 0
        assert mock_appraisal_service._breaker_opened_at == 0.0


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

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_appraisal_suspended_while_turn_in_flight(
        self, mock_camera_cls, mock_screen_cls
    ):
        """P1-7: the VLM and the conversational LLM contend on one Ollama
        endpoint (MEASURED -44%/-47% decode rate in audit/HARDWARE.md).
        While a cognitive turn is in flight, appraisal must not call the
        VLM at all - not even a rate-limited one."""
        import base64

        agent = VisionAgent()
        agent.publish = AsyncMock()
        mock_appraisal = MagicMock()
        mock_appraisal.should_appraise.return_value = True
        mock_appraisal.appraise = AsyncMock(return_value="Should not run.")
        agent.appraisal = mock_appraisal

        await agent._on_chat_input({})
        assert agent._turn_in_flight is True

        blank_frame_b64 = base64.b64encode(b"\x00" * 100).decode("utf-8")
        await agent._run_appraisal(blank_frame_b64)

        mock_appraisal.appraise.assert_not_awaited()
        agent.publish.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_appraisal_resumes_once_turn_output_is_done(
        self, mock_camera_cls, mock_screen_cls
    ):
        agent = VisionAgent()

        await agent._on_chat_input({})
        assert agent._turn_in_flight is True

        # A non-final chunk must not close the turn.
        await agent._on_chat_output({"done": False, "content": "partial"})
        assert agent._turn_in_flight is True

        await agent._on_chat_output({"done": True})
        assert agent._turn_in_flight is False

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_turn_watchdog_resumes_appraisal_if_done_never_arrives(
        self, mock_camera_cls, mock_screen_cls
    ):
        """A crashed brain_agent or a dropped chat.output must not blind
        vision forever - bounded by LLM_STREAM_MAX_SECONDS, the same
        deadline a turn itself is allowed to run for."""
        from app.config import Config

        agent = VisionAgent()
        agent._turn_in_flight = True
        agent._turn_started_at = time.time() - (Config.LLM_STREAM_MAX_SECONDS + 1)

        assert agent._is_turn_in_flight() is False
        assert agent._turn_in_flight is False

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_turn_watchdog_does_not_fire_before_deadline(
        self, mock_camera_cls, mock_screen_cls
    ):
        agent = VisionAgent()
        agent._turn_in_flight = True
        agent._turn_started_at = time.time()

        assert agent._is_turn_in_flight() is True

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_appraisal_not_suspended_when_flag_disabled(
        self, mock_camera_cls, mock_screen_cls, monkeypatch
    ):
        """VISION_SUSPEND_DURING_TURN=False must fully restore the
        pre-P1-7 behavior - a stuck or unwanted turn-in-flight flag must
        not silently gate appraisal when the feature is off."""
        import base64

        from app import config as config_module

        monkeypatch.setattr(
            config_module.config_instance, "VISION_SUSPEND_DURING_TURN", False
        )

        agent = VisionAgent()
        agent.publish = AsyncMock()
        agent._turn_in_flight = True  # simulate a stuck flag
        mock_appraisal = MagicMock()
        mock_appraisal.should_appraise.return_value = True
        mock_appraisal.appraise = AsyncMock(return_value="Seen anyway.")
        agent.appraisal = mock_appraisal

        blank_frame_b64 = base64.b64encode(b"\x00" * 100).decode("utf-8")
        await agent._run_appraisal(blank_frame_b64)

        mock_appraisal.appraise.assert_awaited_once()
        agent.publish.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.vision.agent.ScreenLink")
    @patch("app.vision.agent.CameraLink")
    async def test_turn_tracking_subscribes_for_new_messages_only(
        self, mock_camera_cls, mock_screen_cls
    ):
        """These two subscriptions are liveness signals, not work items. On
        JetStream's "all" default a fresh durable replays the whole retained
        chat history at startup - and chat.output carries one message per
        response chunk - so every vision restart would re-walk the entire
        conversation and end up suspended by a turn that finished hours ago,
        blind until the watchdog fired. Every other subscription in the mesh
        names a policy explicitly; these must too."""
        agent = VisionAgent()
        agent.connect = AsyncMock()
        agent.subscribe = AsyncMock()
        agent.preflight = MagicMock(return_value=False)
        agent._capture_loop = AsyncMock()

        await agent.start()

        policies = {
            call.args[0]: call.kwargs.get("deliver_policy")
            for call in agent.subscribe.await_args_list
        }
        assert policies[Topics.CHAT_INPUT] == "new"
        assert policies[Topics.CHAT_OUTPUT] == "new"
