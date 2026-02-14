import asyncio
import base64
import logging
import time
from .base import BaseAgent
from ..vision import ScreenLink, CameraLink

logger = logging.getLogger("vision_agent")


class VisionAgent(BaseAgent):
    """
    VisionAgent - Captures visual context and publishes to NATS.
    Allows the Brain to 'see' without direct hardware access.
    """

    def __init__(self, fps=1.0):
        super().__init__(name="vision_agent")
        self.screen = ScreenLink()
        self.camera = CameraLink()
        self.source = "screen"  # screen | camera
        self.fps = fps
        self.running = False

    async def start(self):
        await self.connect()

        # Subscribe to control signals from main.py
        await self.subscribe("vision.control", self._handle_control)

        self.running = True
        logger.info(f"📸 {self.name} started. Publishing at {self.fps} FPS")

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

                    # 3. Publish to mesh
                    await self.publish(
                        "vision.frames",
                        {
                            "frame": frame_b64,
                            "source": self.source,
                            "timestamp": time.time(),
                        },
                    )

                # 4. Throttling
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Vision capture error: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        self.running = False
        self.camera.close()
        await super().stop()


async def main():
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
