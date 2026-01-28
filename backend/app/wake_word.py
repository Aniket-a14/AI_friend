import os
import pvporcupine
import struct
import logging
from .config import Config

logger = logging.getLogger(__name__)

class WakeWordDetector:
    def __init__(self):
        self.porcupine = None
        self.buffer = bytearray()
        try:
            path = Config.WAKE_WORD_PATH
            if path and os.path.exists(path):
                logger.info(f"Initializing Porcupine with custom file: {os.path.basename(path)}")
                self.porcupine = pvporcupine.create(
                    access_key=Config.PORCUPINE_ACCESS_KEY,
                    keyword_paths=[path]
                )
            else:
                logger.warning("No platform-matching .ppn file found. Falling back to built-in 'porcupine' keyword.")
                self.porcupine = pvporcupine.create(
                    access_key=Config.PORCUPINE_ACCESS_KEY,
                    keywords=["porcupine"]
                )
            
            self.frame_bytes = self.porcupine.frame_length * 2 
            logger.info(f"Porcupine initialized. Frame Length: {self.porcupine.frame_length} samples ({self.frame_bytes} bytes)")
        except Exception as e:
            logger.error(f"Failed to initialize Porcupine: {e}")
            raise

    def process(self, pcm_chunk: bytes):
        """
        Process incoming audio chunks. Handles buffering for browser-based streams.
        Returns: True if wake word detected, False otherwise.
        """
        if not self.porcupine:
            return False

        # Add new chunk to the sliding buffer
        self.buffer.extend(pcm_chunk)

        detected = False
        # Process all full frames currently in the buffer
        while len(self.buffer) >= self.frame_bytes:
            # Extract exactly one frame
            frame_data = self.buffer[:self.frame_bytes]
            # Remove that frame from the buffer (sliding window)
            self.buffer = self.buffer[self.frame_bytes:]

            # Unpack and process
            pcm = struct.unpack_from("h" * self.porcupine.frame_length, frame_data)
            result = self.porcupine.process(pcm)
            
            if result >= 0:
                logger.info("Wake word detected!")
                detected = True
                # Clear buffer on detection to prevent duplicate triggers
                self.buffer.clear()
                break # Return immediately on detection
                
        return detected

    def delete(self):
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
            self.buffer.clear()
