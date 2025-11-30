from elevenlabs import stream
from elevenlabs.client import ElevenLabs
import logging
from .config import Config

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)
        self.voice_id = Config.ELEVENLABS_VOICE_ID

    def stream_audio(self, text):
        """
        Generates audio stream for the given text.
        Returns an iterator of audio chunks.
        """
        try:
            audio_stream = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_v3",
                output_format="pcm_24000",
            )
            return audio_stream
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None
