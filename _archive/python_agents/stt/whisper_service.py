import logging
import asyncio
import numpy as np
import webrtcvad
import collections
import time
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class WhisperSTTService:
    """
    Optimized STT Service with VAD and Sonic Empathy Analysis.
    Targeted for <500ms latency mesh architecture.
    """

    def __init__(
        self, model_size="small", device="cpu", compute_type="int8", language="en"
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.model = None
        self.is_loading = False

        # VAD Setup (Strict mode to filter environment noise)
        self.vad = webrtcvad.Vad(3)
        self.sample_rate = 16000
        self.frame_duration_ms = 30  # standard for webrtcvad
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)

        # Buffers & State
        self.buffer = b""
        self.audio_buffer = collections.deque()
        self.is_speaking = False
        self.silence_start_time = None
        self.speech_start_time = None
        self.silence_threshold = 0.8  # Aggressive cut-off for fast conversation
        self.max_utterance_duration = 12.0  # Safety break
        self.active = False

    async def load_model(self):
        """Thread-safe model loading"""
        if self.model or self.is_loading:
            return

        self.is_loading = True
        logger.info(f"🎙️ Loading Whisper ({self.model_size}) on {self.device}...")
        try:
            self.model = await asyncio.to_thread(
                WhisperModel,
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("✅ Whisper engine ready.")
        except Exception as e:
            logger.error(f"❌ Failed to load Whisper: {e}")
        finally:
            self.is_loading = False

    def start(self):
        self.active = True
        self.reset()
        logger.info("STT Service Active.")

    def stop(self):
        self.active = False
        self.reset()

    def reset(self):
        """Clean buffers between turns"""
        self.buffer = b""
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_start_time = None
        self.speech_start_time = None

    def process_frame(self, pcm_data: bytes):
        """Processes real-time PCM data; returns (text, is_final, is_partial) if complete/partial."""
        if not self.active or not self.model:
            return None

        self.buffer += pcm_data
        frame_byte_size = self.frame_size * 2

        while len(self.buffer) >= frame_byte_size:
            frame = self.buffer[:frame_byte_size]
            self.buffer = self.buffer[frame_byte_size:]

            is_speech = self.vad.is_speech(frame, self.sample_rate)

            if is_speech:
                if not self.is_speaking:
                    self.is_speaking = True
                    self.speech_start_time = time.time()
                    self.last_partial_time = time.time()
                self.silence_start_time = None
                self.audio_buffer.append(frame)

                # 1. Early Intent Trigger (Partial lookahead every 800ms)
                if time.time() - getattr(self, "last_partial_time", 0) > 0.8:
                    self.last_partial_time = time.time()
                    res = self.transcribe(is_partial=True)
                    if res:
                        text, _ = res
                        return text, False, True

                # 2. Check for forced break
                if self.speech_start_time and (
                    time.time() - self.speech_start_time > self.max_utterance_duration
                ):
                    res = self.transcribe()
                    if res:
                        text, _ = res
                        return text, True, False
            else:
                if self.is_speaking:
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()

                    self.audio_buffer.append(frame)

                    # Cut-off logic (Final)
                    if time.time() - self.silence_start_time > self.silence_threshold:
                        res = self.transcribe()
                        if res:
                            text, _ = res
                            return text, True, False

        return None

    def _analyze_sonic_cues(self, audio_np: np.ndarray) -> str:
        """Analyze volume and pace for empathy tags."""
        rms = np.sqrt(np.mean(audio_np**2))
        volume = "Normal"
        if rms < 0.03:
            volume = "Soft"
        elif rms > 0.25:
            volume = "Loud"

        duration = len(audio_np) / self.sample_rate
        pace = ""
        if duration > 1.5:
            # Rough estimate: higher volume variance can imply agitation
            variance = np.var(audio_np)
            if variance > 0.05:
                pace = "Agitated"

        return f"[{volume} Volume {pace}]".replace("  ", " ").strip()

    def transcribe(self, is_partial=False):
        """Execute Whisper transcription on buffered audio (supports partial lookahead)."""
        if not self.audio_buffer or not self.model:
            return None

        audio_data = b"".join(self.audio_buffer)
        audio_np = (
            np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        )

        sonic_label = self._analyze_sonic_cues(audio_np)

        # Only reset on final transcription
        if not is_partial:
            self.reset()

        try:
            segments, _ = self.model.transcribe(
                audio_np,
                beam_size=1,
                language=self.language,
                condition_on_previous_text=False,
                initial_prompt="A natural conversation between two friends.",
            )

            segments_list = list(segments)
            if not segments_list:
                return None

            raw_text = " ".join([s.text for s in segments_list]).strip()
            # Calculate average probability as confidence
            confidence = sum([s.avg_logprob for s in segments_list]) / len(
                segments_list
            )
            # Convert logprob to 0.0-1.0 roughly (Exp approximation)
            confidence = min(1.0, max(0.0, np.exp(confidence)))

            if not raw_text or len(raw_text) < 2:
                return None

            # Clean stuttering/hallucinations
            words = raw_text.split()
            unique_words = []
            for i, word in enumerate(words):
                if i > 0 and word.lower() == words[i - 1].lower():
                    continue
                unique_words.append(word)

            final_text = f"{sonic_label} {' '.join(unique_words)}".strip()
            logger.info(
                f"🎙️ STT ({'Partial' if is_partial else 'Final'}): {final_text} [Conf: {confidence:.2f}]"
            )
            return final_text, confidence

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
