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

        # Subscribe to state updates for latency masking
        await self.subscribe(
            "state.update",
            self._handle_state_update,
            deliver_policy="new",
        )

        logger.info(
            f"🎙️ {self.name} started and listening to chat.output, state.update"
        )

    async def _handle_state_update(self, message: Dict[str, Any]):
        """Handle state updates to trigger latency masking fillers"""
        agent_name = message.get("agent")
        state = message.get("state")

        # If brain is thinking, play a filler sound to mask latency
        if agent_name == "brain_agent" and state == "thinking":
            await self._play_filler()

    async def _play_filler(self):
        """Play a random pre-generated filler sound"""
        import random
        import os

        filler_dir = "app/assets/fillers"
        if not os.path.exists(filler_dir):
            return

        fillers = [f for f in os.listdir(filler_dir) if f.endswith(".wav")]
        if not fillers:
            return

        # Don't play filler if we just played one very recently (optional throttle)
        # For now, just pick one
        chosen = random.choice(fillers)
        filepath = os.path.join(filler_dir, chosen)

        logger.info(f"🤔 Brain is thinking... playing filler: {chosen}")
        
        try:
            with open(filepath, "rb") as f:
                audio_data = f.read()
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                
                # Stream the filler directly
                await self.publish(
                    "audio.stream",
                    {"audio": audio_b64, "format": "wav", "sample_rate": 22050},
                )
        except Exception as e:
            logger.error(f"Failed to play filler {chosen}: {e}")

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

        raw_text = message.get("full_response", "")
        if not raw_text or not self.ref_audio_path:
            return

        # Parse emotion and strip tags
        text, emotion = self._parse_emotion(raw_text)
        
        # Select reference audio based on emotion
        # Paths are relative to the GPT-SoVITS container's mounted volume
        emotion_map = {
            "neutral": "output/sample_en_gold.wav",
            "happy": "output/ref_happy.wav",
            "excited": "output/ref_happy.wav",
            "warm": "output/ref_happy.wav",
            "sad": "output/ref_sad.wav",
            "serious": "output/sample_en_gold.wav", # Fallback to neutral/gold for now
        }
        
        current_ref_audio = emotion_map.get(emotion, self.ref_audio_path)
        logger.info(f"🎙️ Synthesizing ({emotion}): {text[:50]}...")
        
        text_lang = self._detect_language(text)

        # Stream audio synthesis from local provider
        async for audio_chunk in self.sovits.synthesize_stream(
            text=text,
            ref_audio_path=current_ref_audio,
            ref_text=self.ref_text, # We might need to update ref_text too if we have transcripts for happy/sad
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

    def _parse_emotion(self, text: str) -> tuple[str, str]:
        """Extract <emotion type='...'> tag and return (clean_text, emotion)"""
        import re
        match = re.search(r'<emotion type=["\'](.*?)["\']>(.*?)</emotion>', text, re.DOTALL)
        if match:
            emotion = match.group(1).lower()
            clean_text = match.group(2).strip()
            return clean_text, emotion
        # Also handle prefix style just in case: <emotion type="happy"> Text
        match_prefix = re.search(r'<emotion type=["\'](.*?)["\']>(.*)', text, re.DOTALL)
        if match_prefix:
             emotion = match_prefix.group(1).lower()
             clean_text = match_prefix.group(2).strip()
             return clean_text, emotion
             
        return text, "neutral"

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
