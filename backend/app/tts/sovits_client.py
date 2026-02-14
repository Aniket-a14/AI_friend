"""
GPT-SoVITS Client - API wrapper for local voice synthesis
"""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SoVITSClient:
    """
    Client for GPT-SoVITS local TTS API
    """

    def __init__(self, base_url: str = "http://localhost:9871"):
        self.base_url = base_url
        self.api_url = f"{base_url}/tts"

    def synthesize(
        self,
        text: str,
        ref_audio_path: str,
        ref_text: str = "",
        text_lang: str = "en",
        ref_lang: str = "en",
    ) -> Optional[bytes]:
        """
        Synthesize speech from text using voice cloning

        Args:
            text: Text to synthesize
            ref_audio_path: Path to reference audio (speaker voice)
            ref_text: Transcript of reference audio (optional)
            text_lang: Language of input text (en, zh, ja, etc.)
            ref_lang: Language of reference audio

        Returns:
            Audio bytes (WAV format) or None if failed
        """
        try:
            payload = {
                "text": text,
                "text_lang": text_lang,
                "ref_audio_path": ref_audio_path,
                "prompt_text": ref_text,
                "prompt_lang": ref_lang,
                "text_split_method": "cut5",  # Split by punctuation
                "batch_size": 1,
                "media_type": "wav",
                "streaming_mode": False,
            }

            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()

            return response.content

        except Exception as e:
            logger.error(f"SoVITS synthesis failed: {e}")
            return None

    async def synthesize_stream(
        self,
        text: str,
        ref_audio_path: str,
        ref_text: str = "",
        text_lang: str = "en",
        ref_lang: str = "en",
    ):
        """
        Stream synthesized audio in chunks

        Yields audio chunks as they're generated
        """
        try:
            payload = {
                "text": text,
                "text_lang": text_lang,
                "ref_audio_path": ref_audio_path,
                "prompt_text": ref_text,
                "prompt_lang": ref_lang,
                "text_split_method": "cut5",
                "batch_size": 1,
                "media_type": "wav",
                "streaming_mode": True,
            }

            response = requests.post(
                self.api_url, json=payload, stream=True, timeout=60
            )
            response.raise_for_status()

            # Stream audio chunks
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk

        except Exception as e:
            logger.error(f"SoVITS streaming failed: {e}")
            yield b""

    def check_health(self) -> bool:
        """Check if GPT-SoVITS API is reachable"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
