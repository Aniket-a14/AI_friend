import asyncio
import logging
import base64
from typing import Dict, Any
from .base import BaseAgent
from ..tts.sovits_client import SoVITSClient
from ..config import Config

logger = logging.getLogger(__name__)


class VoiceAgent(BaseAgent):
    """
    The Voice Agent handles text-to-speech synthesis using local GPT-SoVITS.
    """

    def __init__(
        self,
        sovits_url: str = Config.SOVITS_URL,
        ref_audio_path: str = "output/sample_en_gold.wav",
        ref_text: str = "At the end of the exam, the program shows the performance summary which includes the total number of questions.",
        durable_name: str = None,
    ):
        super().__init__(name="voice_agent")
        self.durable_name = durable_name or f"{self.name}_durable"
        self.sovits = SoVITSClient(base_url=sovits_url)
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self.current_task = None

    async def start(self):
        """Initialize and start the agent"""
        await self.connect()

        # Subscribe to chat output events (start from new messages only)
        await self.subscribe(
            "chat.output",
            self._handle_text_input,
            durable=self.durable_name,
            deliver_policy="new",
        )

        # Subscribe to interruption signals (Ephemeral, no durable)
        # FIXME: Adding this caused timeouts. Disabling for now to stabilize startup.
        # await self.subscribe("audio.stop", self._handle_interruption, deliver_policy="new")

        logger.info(
            f"🎙️ {self.name} started and listening to chat.output and audio.stop"
        )

    async def _handle_interruption(self, message: Dict[str, Any]):
        """Handle 'audio.stop' signal from STT agent"""
        if self.current_task and not self.current_task.done():
            logger.info("🛑 Interruption received. Cancelling active synthesis.")
            self.current_task.cancel()

    async def _handle_text_input(self, message: Dict[str, Any]):
        """Handle incoming text messages from NATS"""
        # Create a cancelable task for synthesis
        self.current_task = asyncio.current_task()

        # Only process complete responses (avoid partial streaming synthesis for now)
        if not message.get("done"):
            return

        text = message.get("full_response", "")
        if not text or not self.ref_audio_path:
            return

        logger.info(f"🎙️ Synthesizing: {text[:50]}...")
        text_lang = self._detect_language(text)

        # Stream audio synthesis from local provider
        async for audio_chunk in self.sovits.synthesize_stream(
            text=text,
            ref_audio_path=self.ref_audio_path,
            ref_text=self.ref_text,
            text_lang=text_lang,
            ref_lang="en",
        ):
            if audio_chunk:
                # Base64 encode for NATS JSON transport
                audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")

                # Publish audio chunk to the mesh bridge
                await self.publish(
                    "audio.stream",
                    {"audio": audio_b64, "format": "wav", "sample_rate": 22050},
                )

        # Signal end of stream
        await self.publish("audio.stream", {"audio": "", "done": True})
        logger.info("✅ Voice synthesis complete")

    def _detect_language(self, text: str) -> str:
        """Simple language detection for Hinglish"""
        # GPT-SoVITS handles en/zh/ja/etc.
        # For Hinglish, 'en' works best with the current models.
        return "en"

    async def stop(self):
        await super().stop()
        logger.info(f"🎙️ {self.name} stopped")


async def main():
    agent = VoiceAgent()
    try:
        await agent.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
