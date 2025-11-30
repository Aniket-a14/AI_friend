import logging
import numpy as np
import webrtcvad
import collections
import time
from faster_whisper import WhisperModel
from .config import Config

logger = logging.getLogger(__name__)

class WhisperSTTService:
    def __init__(self, model_size="small", device="cpu", compute_type="int8"):
        """
        Initializes Whisper model and VAD.
        """
        logger.info(f"Loading Whisper model: {model_size} on {device}...")
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

        # VAD Setup
        self.vad = webrtcvad.Vad(3) # Aggressiveness 3 (High)
        self.sample_rate = 16000
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000) # 480 samples
        
        # Buffers
        self.buffer = b""
        self.audio_buffer = collections.deque() # Stores valid speech frames
        self.is_speaking = False
        self.silence_start_time = None
        self.silence_threshold = 1.0 # seconds of silence to trigger transcription
        
        self.active = False # Controls if we are listening

    def start(self):
        self.active = True
        self.reset()
        logger.info("Whisper STT started listening.")

    def stop(self):
        self.active = False
        self.reset()
        logger.info("Whisper STT stopped.")

    def reset(self):
        self.buffer = b""
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_start_time = None

    def process_frame(self, pcm_data):
        """
        Process a chunk of PCM audio.
        Returns: (text, True) if a complete utterance is transcribed, else None.
        """
        if not self.active:
            return None

        # Buffer incoming data to match VAD frame size
        self.buffer += pcm_data
        frame_byte_size = self.frame_size * 2 # 16-bit = 2 bytes
        
        result = None

        while len(self.buffer) >= frame_byte_size:
            frame = self.buffer[:frame_byte_size]
            self.buffer = self.buffer[frame_byte_size:]
            
            is_speech = False
            try:
                is_speech = self.vad.is_speech(frame, self.sample_rate)
            except Exception:
                pass

            if is_speech:
                if not self.is_speaking:
                    logger.debug("Speech started")
                    self.is_speaking = True
                self.silence_start_time = None
                self.audio_buffer.append(frame)
            else:
                if self.is_speaking:
                    # We were speaking, now silence
                    if self.silence_start_time is None:
                        self.silence_start_time = time.time()
                    
                    # Keep buffering silence for a bit to capture trailing sounds
                    self.audio_buffer.append(frame)
                    
                    # Check silence duration
                    if time.time() - self.silence_start_time > self.silence_threshold:
                        logger.debug("Silence threshold reached. Transcribing...")
                        result = self.transcribe()
                        self.reset() # Ready for next utterance
                        # If we have a result, we return it. 
                        # Note: The while loop might continue if we had more data, 
                        # but usually we process real-time chunks so one transcribe per call is fine.
                        return result
        
        return None

    def transcribe(self):
        if not self.audio_buffer:
            return None

        # Combine frames
        audio_data = b"".join(self.audio_buffer)
        
        # Convert to numpy array float32 for Whisper
        # 16-bit PCM -> float32 normalized to [-1, 1]
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, info = self.model.transcribe(audio_np, beam_size=5, language="en")
            text = " ".join([segment.text for segment in segments]).strip()
            
            if text:
                logger.info(f"Whisper Transcribed: {text}")
                return text, True
        except Exception as e:
            logger.error(f"Transcription error: {e}")
        
        return None
