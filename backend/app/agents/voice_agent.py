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
    The Voice Agent handles text-to-speech synthesis with State-aware prosody.
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
        await self.connect()
        await self.subscribe(
            "chat.output",
            self._handle_text_input,
            durable=self.durable_name,
            deliver_policy="new",
        )
        logger.info(f"🎙️ {self.name} online with State-Aware prosody.")

    async def _handle_text_input(self, message: Dict[str, Any]):
        """Handle incoming text with internal state metadata."""
        # removed blocking done check for streaming latency

        raw_text = message.get("content", "") or message.get("full_response", "") # Handle streamed chunks or final response
        state = message.get("state", {})
        energy = state.get("energy", 0.8)
        mood = state.get("mood", 0.0)
        
        if not raw_text or len(raw_text.strip()) < 2: # Ignore tiny fragments
            return

        text, emotion = self._parse_emotion(raw_text)
        
        # Decide reference audio based on energy and mood
        ref_audio = self.ref_audio_path
        if energy < 0.4:
            ref_audio = "output/ref_tired.wav"
        elif mood > 0.6:
            ref_audio = "output/ref_happy.wav"
        elif mood < -0.6:
            ref_audio = "output/ref_sad.wav"
        
        logger.info(f"🎙️ Voice Synthesis [Mood: {mood:.2f}, Energy: {energy:.2f}] -> {ref_audio}")
        
        text_lang = self._detect_language(text)

        try:
            async for audio_chunk in self.sovits.synthesize_stream(
                text=text,
                ref_audio_path=ref_audio,
                ref_text=self.ref_text,
                text_lang=text_lang,
                ref_lang="en",
            ):
                if audio_chunk:
                    audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                    await self.publish(
                        "audio.stream",
                        {"audio": audio_b64, "format": "pcm", "sample_rate": 22050},
                    )
            await self.publish("audio.stream", {"audio": "", "done": True})
            logger.info("✅ Synthesis complete.")
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")

    def _parse_emotion(self, text: str) -> tuple[str, str]:
        import re
        match = re.search(r'<emotion type=["\'](.*?)["\']>(.*?)</emotion>', text, re.DOTALL)
        if match:
            return match.group(2).strip(), match.group(1).lower()
        return text, "neutral"

    def _detect_language(self, text: str) -> str:
        return "en"

    async def stop(self):
        await super().stop()
        logger.info(f"🎙️ {self.name} stopped.")

async def main():
    agent = VoiceAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
