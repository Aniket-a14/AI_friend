import asyncio
import base64
import logging
import time
from ..agents.base import BaseAgent
from .links import ScreenLink, CameraLink
from ..llm.ollama_client import OllamaClient
from .appraisal import VisualAppraisalService
from ..config import Config
from ..contracts import Topics, VisionDescription

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
            )

    async def start(self):
        await self.connect()

        # Subscribe to control signals from main.py
        await self.subscribe(Topics.VISION_CONTROL, self._handle_control)

        self.running = True
        vlm_status = f"VLM={Config.VLM_MODEL}" if self.vlm_enabled else "VLM=disabled"
        logger.info(f"📸 {self.name} started. {vlm_status} | {self.fps} FPS")

        asyncio.create_task(self._capture_loop())

    async def _handle_control(self, data: dict):
        """Handle vision source switching"""
        new_source = data.get("source")
        if new_source in ["screen", "camera"]:
            self.source = new_source
            logger.info(f"Vision source switched to: {new_source}")

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
        try:
            import cv2
            import numpy as np

            frame_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return 1.0

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)

            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            if len(faces) > 0:
                max_w = max(w for (x, y, w, h) in faces)
                img_width = img.shape[1]
                S = max_w / img_width if img_width > 0 else 0.0
                if S > 0.0:
                    d = 0.15 / S
                    return float(np.clip(d, 0.2, 5.0))

            return 1.0
        except Exception as e:
            logger.debug(f"Failed to calculate user distance: {e}")
            return 1.0

    async def _run_appraisal(self, frame_b64: str):
        """Run VLM appraisal if the interval has elapsed and publish the description."""
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
                await self.publish(
                    Topics.VISION_DESCRIPTION, msg.model_dump()
                )
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
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
