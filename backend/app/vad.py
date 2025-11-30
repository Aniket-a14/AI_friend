import webrtcvad
import logging
from .config import Config

logger = logging.getLogger(__name__)

class VAD:
    def __init__(self, aggressiveness=3):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = Config.SAMPLE_RATE
        self.frame_duration_ms = 30
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000) # 480 samples for 16kHz
        self.buffer = b""

    def process(self, pcm_data):
        """
        Returns True if speech is detected in the processed chunks.
        Handles buffering to match 10/20/30ms frame sizes.
        """
        self.buffer += pcm_data
        is_speech_detected = False
        
        # 2 bytes per sample
        frame_byte_size = self.frame_size * 2
        
        while len(self.buffer) >= frame_byte_size:
            frame = self.buffer[:frame_byte_size]
            self.buffer = self.buffer[frame_byte_size:]
            
            try:
                if self.vad.is_speech(frame, self.sample_rate):
                    is_speech_detected = True
            except Exception as e:
                logger.error(f"VAD error: {e}")
                
        return is_speech_detected

    def reset(self):
        self.buffer = b""
