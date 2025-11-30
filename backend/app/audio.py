import pyaudio
import queue
import logging
from .config import Config

logger = logging.getLogger(__name__)

class AudioStream:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.queue = queue.Queue()
        self.running = False

    def start(self):
        if self.running:
            return

        try:
            self.stream = self.pa.open(
                rate=Config.SAMPLE_RATE,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=512, # Porcupine usually likes 512
                stream_callback=self._callback
            )
            self.running = True
            logger.info("Audio stream started")
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            raise

    def _callback(self, in_data, frame_count, time_info, status):
        self.queue.put(in_data)
        return None, pyaudio.paContinue

    def get_frame(self):
        try:
            return self.queue.get(timeout=0.1)
        except queue.Empty:
            return None

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        logger.info("Audio stream stopped")

    def close(self):
        self.stop()
        self.pa.terminate()

class AudioPlayer:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream = None

    def create_output_stream(self):
        return self.pa.open(
            rate=24000,
            channels=1,
            format=pyaudio.paInt16,
            output=True
        )

    def play_stream(self, audio_stream):
        """
        Plays audio from a generator/iterator of bytes.
        """
        if not self.stream:
            self.stream = self.create_output_stream()
        
        try:
            for chunk in audio_stream:
                if chunk:
                    self.stream.write(chunk)
        except Exception as e:
            logger.error(f"Error playing audio stream: {e}")
        finally:
            # Keep stream open for next utterance or close?
            # Usually better to keep open if latency matters, 
            # but for cleanliness we can close or just stop.
            # Let's keep it open but maybe flush?
            pass

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.pa.terminate()
