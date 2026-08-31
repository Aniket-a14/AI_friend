import asyncio
import logging
import time
import uuid
from typing import Any
import numpy as np
import torch
import whisper

from app.agents.base import BaseAgent
from app.config import Config
from app.contracts import ChatInput, ChatInputMetadata, Topics

logger = logging.getLogger("stt_agent")


class STTAgent(BaseAgent):
    """
    Real-Time STT Sensory Agent.
    Subscribes to `audio.inbound` (PCM frames from WebRTC TransportAgent).
    Performs Energy/VAD segmentation and Whisper GPU transcription.
    Publishes final transcription on `chat.input` (ChatInput contract).
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        nats_url: str = Config.NATS_URL,
    ):
        super().__init__(name="stt_agent", nats_url=nats_url)
        self.model_size = model_size
        self.device = device
        self.model = None

        self.target_sample_rate = 16000
        self.audio_chunks: list[np.ndarray] = []

        self.is_speaking = False
        self.speech_start_time = 0.0
        self.last_speech_time = 0.0

        self.silence_threshold_sec = 0.6  # 600ms silence completes utterance
        self.min_speech_duration_sec = (
            0.35  # 350ms minimum speech length to avoid noise
        )
        self.energy_threshold = 0.018  # Robust voice threshold

        self._processing_queue = asyncio.Queue(maxsize=16)
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        """Initialize NATS connection, load Whisper model, and begin stream processing."""
        await self.connect()

        logger.info("🎙️ Loading Whisper (%s) on %s...", self.model_size, self.device)
        self.model = await asyncio.to_thread(
            whisper.load_model,
            self.model_size,
            device=self.device,
        )
        logger.info("✅ Whisper engine ready on %s.", self.device)

        self._worker_task = asyncio.create_task(self._transcription_worker())

        await self.subscribe(
            Topics.AUDIO_INBOUND,
            self._on_audio_inbound,
            deliver_policy="new",
        )
        logger.info(f"🎙️ {self.name} Online | Whisper Speech-to-Text Pipeline Active.")

    async def _on_audio_inbound(self, data: Any, metadata: dict | None = None):
        """Receive raw audio bytes from TransportAgent."""
        if not isinstance(data, (bytes, bytearray)):
            return

        sample_rate = metadata.get("sample_rate", 16000) if metadata else 16000

        # Convert int16 PCM bytes to float32 numpy array
        int16_audio = np.frombuffer(data, dtype=np.int16)
        if len(int16_audio) == 0:
            return

        float_audio = int16_audio.astype(np.float32) / 32768.0

        # Resample if not 16kHz
        if sample_rate != self.target_sample_rate and sample_rate > 0:
            indices = np.linspace(
                0,
                len(float_audio) - 1,
                int(len(float_audio) * self.target_sample_rate / sample_rate),
            )
            float_audio = np.interp(
                indices, np.arange(len(float_audio)), float_audio
            ).astype(np.float32)

        # Compute RMS energy
        rms = float(np.sqrt(np.mean(float_audio**2) + 1e-12))
        now = time.time()

        if rms > self.energy_threshold:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_start_time = now
                logger.info("🗣️ Speech onset detected (RMS: %.4f)", rms)

            self.last_speech_time = now
            self.audio_chunks.append(float_audio)
        else:
            if self.is_speaking:
                self.audio_chunks.append(float_audio)
                if now - self.last_speech_time > self.silence_threshold_sec:
                    duration = self.last_speech_time - self.speech_start_time
                    if (
                        duration >= self.min_speech_duration_sec
                        and len(self.audio_chunks) > 0
                    ):
                        full_audio = np.concatenate(self.audio_chunks).astype(
                            np.float32
                        )
                        self.audio_chunks.clear()
                        self.is_speaking = False
                        logger.info(
                            "🎤 Speech completed (duration: %.2fs); sending to Whisper",
                            duration,
                        )
                        try:
                            self._processing_queue.put_nowait(full_audio)
                        except asyncio.QueueFull:
                            logger.warning(
                                "Transcription queue full; dropping utterance"
                            )
                    else:
                        self.audio_chunks.clear()
                        self.is_speaking = False

    async def _transcription_worker(self):
        """Worker that transcribes completed audio utterances using Whisper."""
        while True:
            try:
                audio_data = await self._processing_queue.get()
                try:
                    text = await asyncio.to_thread(self._transcribe_sync, audio_data)
                    if text:
                        logger.info("🗣️ Transcribed user speech: %r", text)
                        chat_input = ChatInput(
                            text=text,
                            utterance_id=f"utt_{uuid.uuid4().hex[:8]}",
                            metadata=ChatInputMetadata(
                                source="whisper", confidence=0.95
                            ),
                        )
                        await self.publish(Topics.CHAT_INPUT, chat_input.model_dump())
                    else:
                        logger.debug("Empty or filtered transcription.")
                finally:
                    self._processing_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in STT transcription worker: %s", e, exc_info=True)

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        """Run Whisper inference synchronously on the thread pool."""
        try:
            audio_f32 = audio.astype(np.float32)
            result = self.model.transcribe(
                audio_f32,
                language="en",
                fp16=(self.device == "cuda"),
                without_timestamps=True,
            )
            cleaned = result.get("text", "").strip()
            # Filter out known whisper hallucinations on silence
            hallucinations = [
                "Thank you.",
                "Thanks for watching!",
                "you",
                "Bye.",
                "",
                "Thank you for watching.",
                "Thank you very much.",
                "Bye-bye.",
            ]
            if cleaned in hallucinations or len(cleaned) < 2:
                return ""
            return cleaned
        except Exception as e:
            logger.error("Whisper inference error: %s", e, exc_info=True)
            return ""

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()
        await super().stop()
