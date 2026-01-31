import logging
import asyncio
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
        Initializes STT buffers and VAD. Model loading is deferred.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self.is_loading = False

        # VAD Setup
        self.vad = webrtcvad.Vad(3) # Aggressiveness 3 (Strict) to avoid noise hallucinations
        self.sample_rate = 16000
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000) # 480 samples
        
        # Buffers
        self.buffer = b""
        self.audio_buffer = collections.deque() # Stores valid speech frames
        self.is_speaking = False
        self.silence_start_time = None
        self.speech_start_time = None # Track start of utterance
        self.silence_threshold = 2.0 
        self.max_utterance_duration = 15.0 # Force transcription every 15s to avoid hallucinations
        
        self.active = False # Controls if we are listening

    async def load_model(self):
        """Heavy lifting for model loading, run in a separate thread."""
        if self.model or self.is_loading:
            return
        
        self.is_loading = True
        logger.info(f"Loading Whisper model: {self.model_size} on {self.device}...")
        try:
            # WhisperModel initialization is CPU intensive/blocking
            self.model = await asyncio.to_thread(
                WhisperModel, 
                self.model_size, 
                device=self.device, 
                compute_type=self.compute_type
            )
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
        finally:
            self.is_loading = False

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
        self.speech_start_time = None

    def process_frame(self, pcm_data):
        """
        Process a chunk of PCM audio.
        Returns: (text, True) if a complete utterance is transcribed, else None.
        """
        if not self.active or not self.model:
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
                    self.speech_start_time = time.time()
                self.silence_start_time = None
                self.audio_buffer.append(frame)
                
                # Force transcription if duration is too long
                if self.speech_start_time and (time.time() - self.speech_start_time > self.max_utterance_duration):
                    logger.info("Max utterance duration reached. Forcing transcription...")
                    result = self.transcribe()
                    self.reset()
                    return result
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
        if not self.audio_buffer or not self.model:
            return None

        # Combine frames
        audio_data = b"".join(self.audio_buffer)
        
        # Convert to numpy array float32 for Whisper
        # 16-bit PCM -> float32 normalized to [-1, 1]
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # --- SONIC EMPATHY ANALYSIS ---
        # Calculate RMS energy (volume)
        rms = np.sqrt(np.mean(audio_np**2))
        
        # Determine acoustic cues
        # threshold 0.01 is very soft (whisper), 0.1 is normal, 0.3+ is loud/intense
        sonic_tag = "[Normal Volume]"
        if rms < 0.03:
            sonic_tag = "[Soft/Whisper Voice]"
        elif rms > 0.25:
            sonic_tag = "[Loud/Intense Voice]"
            
        # Optional: Duration/Pace check
        duration = len(audio_np) / self.sample_rate
        words_estimate = len(audio_data) / 2000 # Very rough words estimate
        pace_tag = ""
        if duration > 1.0:
            words_per_sec = words_estimate / duration
            if words_per_sec > 4:
                pace_tag = "[Fast/Agitated Pace]"
            elif words_per_sec < 1.5:
                pace_tag = "[Slow/Heavy Pace]"
        
        sonic_cues = f"{sonic_tag} {pace_tag}".strip()
        # ------------------------------

        try:
            # beam_size=1 is faster and often avoids repetitive hallucinations better than high beams
            # condition_on_previous_text=False prevents "ghosting" from past errors
            segments, info = self.model.transcribe(
                audio_np, 
                beam_size=1, 
                language="en", 
                condition_on_previous_text=False,
                initial_prompt="A natural conversation between two friends."
            )
            raw_text = " ".join([segment.text for segment in segments]).strip()
            # Prefix with acoustic cues so the LLM "hears" the volume and speed
            text = f"{sonic_cues} {raw_text}".strip()
            
            # Post-processing: Deduplicate stuttering hallucinations (e.g., "what, what, what" -> "what")
            words = text.split()
            clean_words = []
            for i, word in enumerate(words):
                normalized_word = word.lower().strip(".,?!")
                if i > 0:
                    prev_normalized = words[i-1].lower().strip(".,?!")
                    if normalized_word == prev_normalized:
                        continue
                clean_words.append(word)
            text = " ".join(clean_words)
            
            if text and len(text.strip()) > 2: # Avoid tiny hallucinated sounds
                logger.info(f"Whisper Transcribed: {text}")
                return text, True
        except Exception as e:
            logger.error(f"Transcription error: {e}")
        
        return None
