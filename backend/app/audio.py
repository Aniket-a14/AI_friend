try:
    import pyaudio
except ImportError:
    pyaudio = None

import asyncio
import logging
from .config import Config

logger = logging.getLogger(__name__)

class AudioStream:
    def __init__(self, loop=None):
        self.pa = pyaudio.PyAudio() if pyaudio else None
        self.stream = None
        self.loop = loop or asyncio.get_event_loop()
        self.queue = asyncio.Queue()
        self.running = False

    def start(self):
        if not self.pa:
            logger.warning("PyAudio not available. AudioStream will only accept manual frames (e.g. via WebSocket).")
            self.running = True
            return

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
            logger.info("Local Audio stream started")
        except Exception as e:
            logger.error(f"Failed to start local audio stream: {e}")
            self.running = True # Still set running to True so queue works for external frames

    def _callback(self, in_data, frame_count, time_info, status):
        # Callback runs in a separate thread, so use call_soon_threadsafe
        self.loop.call_soon_threadsafe(self.queue.put_nowait, in_data)
        return None, pyaudio.paContinue

    async def put_frame(self, frame: bytes):
        """Manually put a frame into the queue (e.g. from WebSocket)."""
        await self.queue.put(frame)

    async def get_frame(self):
        try:
            # Non-blocking retrieval from asyncio.Queue
            return await self.queue.get()
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
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
        if self.pa:
            self.pa.terminate()

class AudioPlayer:
    def __init__(self):
        self.pa = pyaudio.PyAudio() if pyaudio else None
        self.stream = None

    def create_output_stream(self):
        if not self.pa:
            return None
        return self.pa.open(
            rate=24000,
            channels=1,
            format=pyaudio.paInt16,
            output=True
        )

    async def play_chunk(self, chunk: bytes):
        """Non-blocking play using thread offloading."""
        if not self.pa or not chunk:
            return
            
        if not self.stream:
            self.stream = self.create_output_stream()
            
        if self.stream:
            await asyncio.to_thread(self.stream.write, chunk)

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pa:
            self.pa.terminate()
