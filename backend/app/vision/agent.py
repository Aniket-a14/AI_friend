import asyncio
import base64
import logging
import time

from ..agents.base import BaseAgent, install_shutdown_signal_handlers
from ..config import Config
from ..contracts import Topics, VisionDescription
from ..llm.ollama_client import OllamaClient
from .appraisal import VisualAppraisalService
from .links import CameraLink, ScreenLink

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

# Distance estimation parameters
ASSUMED_FACE_WIDTH_M = 0.15
MIN_DISTANCE_M = 0.2
MAX_DISTANCE_M = 5.0
HAAR_SCALE_FACTOR = 1.1
HAAR_MIN_NEIGHBORS = 4

logger = logging.getLogger("vision_agent")


class VisionAgent(BaseAgent):
    """
    VisionAgent — Tier-4 Visual Intelligence.
    Captures visual context, runs VLM appraisal, and publishes
    both raw frames and semantic descriptions to the NATS mesh.
    """

    def __init__(self, fps=1.0):
        super().__init__(name="vision_agent")
        self.screen = ScreenLink()
        self.camera = CameraLink()
        self.source = "screen"  # screen | camera
        self.fps = fps
        self.running = False
        self.can_capture = False
        self.health_file = getattr(Config, "VISION_HEALTH_FILE", "")

        # Tier-4: VLM Appraisal Pipeline
        self.vlm_enabled = Config.VLM_ENABLED
        self.vlm_client = None
        self.appraisal = None

        if self.vlm_enabled:
            self.vlm_client = OllamaClient(
                base_url=Config.OLLAMA_URL, model=Config.VLM_MODEL
            )
            self.appraisal = VisualAppraisalService(
                ollama_client=self.vlm_client,
                model=Config.VLM_MODEL,
                interval=Config.VLM_APPRAISAL_INTERVAL,
                prompt=Config.VLM_PROMPT,
                breaker_failure_threshold=Config.VLM_BREAKER_FAILURE_THRESHOLD,
                breaker_cooldown_s=Config.VLM_BREAKER_COOLDOWN_S,
            )

        # P1-7: true while a cognitive turn is in flight (chat.input seen,
        # no chat.output done=True yet), so _capture_loop can suspend VLM
        # appraisal for its duration rather than contend with the
        # conversational LLM on the same Ollama endpoint. Bounded by
        # LLM_STREAM_MAX_SECONDS so a dropped/never-arriving `done` cannot
        # blind vision permanently.
        self._turn_in_flight = False
        self._turn_started_at = 0.0

    def preflight(self) -> bool:
        """Probe whether this process can actually see anything.

        Capture is host-bound. `mss` needs a real display connection and
        `cv2.VideoCapture(0)` needs a `/dev/video*` node, so inside a Linux
        container neither exists unless the host is also Linux and the X11
        socket plus video device are explicitly passed through. On a Windows or
        macOS host that passthrough is not possible at all -- Docker runs the
        container in a Linux VM that has no access to the host's display or USB
        webcam.

        Without this probe the failure is silent and expensive: ScreenLink
        catches its own error, sets `headless`, and `capture_frame()` returns
        None forever while the process stays happily alive. That is exactly the
        shape of finding E1, where a healthcheck passed because the thing it was
        checking had been stubbed out.
        """
        probe = (
            self.camera.capture_frame()
            if self.source == "camera"
            else self.screen.capture_frame()
        )
        if probe:
            return True

        logger.error(
            "🚫 [Vision] Cannot capture from '%s'. Screen capture needs a display "
            "connection and camera capture needs a /dev/video* node. If this is a "
            "container: run the vision agent on the HOST instead "
            "(`python -m app.vision.agent`), or on a Linux host pass through "
            "`/tmp/.X11-unix` + DISPLAY (screen) or `--device=/dev/video0` (camera). "
            "The agent stays up so the mesh is unaffected, but it is blind.",
            self.source,
        )
        return False

    def _mark_capture_healthy(self):
        """Touch the sentinel the container healthcheck reads.

        The probe must test the real path, not process liveness: `pgrep python`
        succeeds just as readily when every frame comes back None.
        """
        if not self.health_file:
            return
        try:
            with open(self.health_file, "w") as fh:
                fh.write(str(time.time()))
        except OSError as e:
            logger.debug("[Vision] Could not write health sentinel: %s", e)

    async def start(self):
        await self.connect()

        # Subscribe to control signals from main.py
        await self.subscribe(Topics.VISION_CONTROL, self._handle_control)

        # P1-7: track turn boundaries so appraisal can suspend during one.
        if Config.VISION_SUSPEND_DURING_TURN:
            await self.subscribe(Topics.CHAT_INPUT, self._on_chat_input)
            await self.subscribe(Topics.CHAT_OUTPUT, self._on_chat_output)

        self.running = True
        vlm_status = f"VLM={Config.VLM_MODEL}" if self.vlm_enabled else "VLM=disabled"
        self.can_capture = self.preflight()
        sight = "seeing" if self.can_capture else "BLIND (no capture device)"
        logger.info(
            f"📸 {self.name} started. {vlm_status} | {self.fps} FPS | {sight}"
        )

        asyncio.create_task(self._capture_loop())

    async def _handle_control(self, data: dict):
        """Handle vision source switching"""
        new_source = data.get("source")
        if new_source in ["screen", "camera"]:
            self.source = new_source
            logger.info(f"Vision source switched to: {new_source}")

    async def _on_chat_input(self, data: dict):
        """A turn is starting: suspend VLM appraisal until it ends."""
        self._turn_in_flight = True
        self._turn_started_at = time.time()

    async def _on_chat_output(self, data: dict):
        """`done=True` closes the turn; any other chunk leaves it open."""
        if data.get("done"):
            self._turn_in_flight = False

    def _is_turn_in_flight(self) -> bool:
        """Watchdog: a `done` that never arrives (crash, dropped message)
        must not blind vision forever. Bounded by the same
        LLM_STREAM_MAX_SECONDS a turn is itself allowed to run for."""
        if not self._turn_in_flight:
            return False
        if time.time() - self._turn_started_at > Config.LLM_STREAM_MAX_SECONDS:
            logger.warning(
                "[Vision] Turn-in-flight watchdog fired after %.0fs with no "
                "chat.output done=True; resuming appraisal.",
                Config.LLM_STREAM_MAX_SECONDS,
            )
            self._turn_in_flight = False
            return False
        return True

    async def _capture_loop(self):
        while self.running:
            try:
                start_time = time.time()

                # 1. Capture frame
                if self.source == "camera":
                    frame = self.camera.capture_frame()
                else:
                    frame = self.screen.capture_frame()

                if frame:
                    if not self.can_capture:
                        # Recovered: a display or camera appeared after startup.
                        logger.info("👁️  [Vision] Capture recovered; the agent can see.")
                        self.can_capture = True
                    self._mark_capture_healthy()

                    # 2. Base64 encode for NATS
                    frame_b64 = base64.b64encode(frame).decode("utf-8")

                    # 3. Publish raw frame to mesh (TEMPORARILY DISABLED FOR DIAGNOSTICS)
                    # await self.publish(
                    #     Topics.VISION_FRAMES,
                    #     {
                    #         "frame": frame_b64,
                    #         "source": self.source,
                    #         "timestamp": time.time(),
                    #     },
                    # )

                    # 4. Tier-4: VLM Appraisal (rate-limited internally)
                    if self.vlm_enabled and self.appraisal:
                        await self._run_appraisal(frame_b64)

                # 5. Throttling
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Vision capture error: {e}")
                await asyncio.sleep(1)

    def _calculate_user_distance(self, frame_b64: str) -> float:
        if cv2 is None or np is None:
            logger.debug(
                "OpenCV or NumPy is not installed. Bypassing user distance calculation."
            )
            return 1.0
        try:
            frame_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return 1.0

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)

            faces = face_cascade.detectMultiScale(
                gray, HAAR_SCALE_FACTOR, HAAR_MIN_NEIGHBORS
            )
            if len(faces) > 0:
                max_w = max(w for (x, y, w, h) in faces)
                img_width = img.shape[1]
                S = max_w / img_width if img_width > 0 else 0.0
                if S > 0.0:
                    d = ASSUMED_FACE_WIDTH_M / S
                    return float(np.clip(d, MIN_DISTANCE_M, MAX_DISTANCE_M))

            return 1.0
        except Exception as e:
            logger.debug("Failed to calculate user distance: %s", e)
            return 1.0

    async def _run_appraisal(self, frame_b64: str):
        """Run VLM appraisal if the interval has elapsed and publish the description."""
        if Config.VISION_SUSPEND_DURING_TURN and self._is_turn_in_flight():
            return
        if not self.appraisal.should_appraise():
            return

        try:
            description = await self.appraisal.appraise(frame_b64)
            if description:
                user_distance = self._calculate_user_distance(frame_b64)
                msg = VisionDescription(
                    description=description,
                    source=self.source,
                    user_distance=user_distance,
                )
                await self.publish(Topics.VISION_DESCRIPTION, msg.model_dump())
        except Exception as e:
            logger.error(f"[VisionAgent] VLM appraisal publish error: {e}")

    async def stop(self):
        self.running = False
        self.camera.close()
        await super().stop()


async def main():
    from app.logging_config import setup_logging

    setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))

    agent = VisionAgent()
    await agent.start()
    shutdown_trigger = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_trigger)
    await shutdown_trigger.wait()
    await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
