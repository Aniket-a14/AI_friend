"""
Voice Agent for AI Friend Mesh.
Subscribes to `chat.output`, synthesizes high-fidelity human speech via GPT-SoVITS on GPU,
and streams 32kHz 16-bit PCM chunks to `audio.stream` for LiveKit WebRTC playout.
"""

import asyncio
import json
import logging
import time
import urllib.request
from typing import Any

import numpy as np

from ..config import Config
from ..contracts import ChatOutput, Topics
from .base import BaseAgent, install_shutdown_signal_handlers

logger = logging.getLogger("voice_agent")


class VoiceAgent(BaseAgent):
    """Voice Synthesis Agent bridging BrainAgent text to GPT-SoVITS on GPU."""

    def __init__(
        self,
        nats_url: str = Config.NATS_URL,
        sovits_url: str = "http://127.0.0.1:9871/tts",
        ref_audio_path: str = "output/human_emma_warm.wav",
        ref_prompt_text: str = "Tom's diner seems like it would be a good karaoke song, just surely for the fact that you can't get it out of your head, so it's kind of...",
    ):
        super().__init__(name="voice_agent", nats_url=nats_url)
        self.sovits_url = sovits_url
        self.ref_audio_path = ref_audio_path
        self.ref_prompt_text = ref_prompt_text
        self.is_interrupted = False
        self._current_playback_task: asyncio.Task | None = None

    async def start(self):
        """Connect to NATS and start subscriptions."""
        await self.connect()
        await self._setup_subscriptions()
        logger.info(f"🎙️ {self.name} Online | GPT-SoVITS Bridge Active.")

    async def _setup_subscriptions(self):
        """Subscribe to chat.output and audio.stop."""
        await self.subscribe(
            Topics.CHAT_OUTPUT,
            self._handle_chat_output,
            durable="voice_agent_chat_output",
            deliver_policy="new",
        )
        await self.subscribe(
            Topics.AUDIO_STOP,
            self._handle_audio_stop,
            durable="voice_agent_audio_stop",
            deliver_policy="new",
        )
        logger.info("🎙️ VoiceAgent subscribed to 'chat.output' and 'audio.stop'.")

    async def _handle_audio_stop(self, data: dict[str, Any]):
        """Barge-in interruption received -- stop playing audio immediately."""
        self.is_interrupted = True
        if self._current_playback_task and not self._current_playback_task.done():
            self._current_playback_task.cancel()
        logger.info("🛑 VoiceAgent received audio.stop: flushed audio output.")

    async def _handle_chat_output(self, data: dict[str, Any]):
        """Process incoming speech text chunk from BrainAgent."""
        try:
            chat_out = ChatOutput.model_validate(data)
        except Exception as e:
            logger.warning(f"Malformed chat.output message: {e}")
            return

        if not chat_out.content or chat_out.content.strip() == "":
            return

        text = chat_out.content.strip()
        turn_id = chat_out.turn_id or f"turn_{int(time.time() * 1000)}"
        logger.info(f"🎙️ VoiceAgent synthesizing [{turn_id}]: {text}")

        # Pick reference emotion if provided
        ref_audio = self.ref_audio_path
        prompt_text = self.ref_prompt_text
        if chat_out.affect:
            emotion = chat_out.affect.emotion.lower()
            if emotion in ["joy", "excited", "happy"]:
                ref_audio = "output/human_angie_5s.wav"
                prompt_text = "changed my life, becoming a Cambodian family, changed my life. So there was never a plan to, we should make this movie."
            elif emotion in ["sad", "calm", "tired", "fatigue"]:
                ref_audio = "output/human_daniel_5s.wav"
                prompt_text = "You also may have heard that the release of the film has been delayed due to public health concerns."

        self.is_interrupted = False
        loop = asyncio.get_running_loop()
        try:
            audio_pcm = await loop.run_in_executor(
                None,
                self._synthesize_audio,
                text,
                ref_audio,
                prompt_text,
            )
            if audio_pcm and not self.is_interrupted:
                self._current_playback_task = asyncio.create_task(
                    self._stream_audio_chunks(audio_pcm, turn_id)
                )
                await self._current_playback_task
        except Exception as err:
            logger.error(f"TTS synthesis error: {err}")

    def _synthesize_audio(self, text: str, ref_audio: str, prompt_text: str) -> bytes:
        """Synchronous HTTP call to local GPT-SoVITS server."""
        payload = {
            "text": text,
            "text_lang": "en",
            "ref_audio_path": ref_audio,
            "prompt_text": prompt_text,
            "prompt_lang": "en",
            "streaming_mode": 0,
        }
        req = urllib.request.Request(
            self.sovits_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            duration_s = len(data) / 64000.0
            logger.info(
                f"✅ Generated {len(data):,} bytes (~{duration_s:.2f}s) in {elapsed_ms:.1f}ms"
            )
            return data

    async def _stream_audio_chunks(self, audio_pcm: bytes, turn_id: str):
        """Streams 20ms chunks (1280 bytes = 640 samples at 32kHz 16-bit) to audio.stream."""
        chunk_size = 1280  # 20ms at 32kHz 16-bit mono
        for offset in range(0, len(audio_pcm), chunk_size):
            if self.is_interrupted:
                logger.info("Playback aborted due to interruption.")
                break

            chunk = audio_pcm[offset : offset + chunk_size]
            if len(chunk) < chunk_size:
                chunk = chunk + b"\x00" * (chunk_size - len(chunk))

            # Compute normalized viseme level (0.0 to 1.0)
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples**2)))
            viseme_level = min(1.0, rms * 4.0)

            headers = {
                "X-Latency-Meta": json.dumps(
                    {
                        "turn_id": turn_id,
                        "offset": offset,
                        "viseme": viseme_level,
                    }
                )
            }
            if self.js:
                await self.js.publish(Topics.AUDIO_STREAM.value, chunk, headers=headers)
            await asyncio.sleep(0.018)  # Paced slightly faster than 20ms clock


async def main():
    agent = VoiceAgent()
    await agent.start()
    shutdown_trigger = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_trigger)
    await shutdown_trigger.wait()
    await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
