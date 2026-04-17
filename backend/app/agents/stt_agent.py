import base64
import logging
import numpy as np
import asyncio
from .base import BaseAgent
from ..whisper_stt_service import WhisperSTTService
import soxr
from ..config import Config

logger = logging.getLogger("stt_agent")


class STTAgent(BaseAgent):
    """
    Consumes raw audio from NATS, performs STT, and publishes text.
    Handles VAD and Interruption triggers based on acoustic energy.
    """

    def __init__(self, model_size=Config.STT_MODEL_SIZE, device=Config.STT_DEVICE):
        super().__init__(name="stt_agent")
        self.stt_service = WhisperSTTService(model_size=model_size, device=device)
        # STT pipeline (VAD/Whisper) strictly requires 16kHz
        self.target_sample_rate = self.stt_service.sample_rate

    async def start(self):
        """Standard startup sequence for Micro-Agents"""
        await self.connect()

        # Load the model
        await self.stt_service.load_model()
        self.stt_service.start()

        # Subscribe to inbound audio from TransportAgent
        await self.subscribe(
            "audio.inbound", self._on_audio_inbound, deliver_policy="new"
        )
        logger.info(f"🎙️ {self.name} started and listening to audio.inbound")

    async def _on_audio_inbound(self, data: dict):
        """Process real-time PCM frames from the mesh"""
        try:
            audio_b64 = data.get("audio")
            source_sr = data.get("sample_rate", 48000)

            if not audio_b64:
                return

            # 1. Decode and normalize
            audio_bytes = base64.b64decode(audio_b64)
            audio_np = (
                np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            )

            # 2. Resample if necessary (Whisper expects 16kHz)
            # 2. Resample if necessary (Whisper expects 16kHz)
            if source_sr != self.target_sample_rate:
                audio_np = soxr.resample(audio_np, source_sr, self.target_sample_rate)

            # 3. Convert back to 16-bit PCM for VAD
            pcm_16 = (audio_np * 32767).astype(np.int16).tobytes()

            # 4. Process through VAD/Whisper
            result = self.stt_service.process_frame(pcm_16)

            # 5. Handle Interruption
            # If the service detects the user is speaking, signal the VoiceAgent to stop
            if (
                self.stt_service.is_speaking
                and self.stt_service.silence_start_time is None
            ):
                await self.publish("audio.stop", {"interrupt": True})

            if result:
                text, is_final = result
                if is_final:
                    logger.info(f"User said: {text}")
                    # 6. Trigger Brain for reasoning
                    await self.publish("chat.input", {"text": text})

        except Exception as e:
            logger.error(f"Error processing inbound audio: {e}")


async def main():
    agent = STTAgent()
    try:
        await agent.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
