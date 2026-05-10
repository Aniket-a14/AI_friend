"""
GPT-SoVITS Client - API wrapper for local voice synthesis (Async CVS-1.0 Edition)
"""

import aiohttp
import logging
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)


class SoVITSClient:
    """
    Async Client for GPT-SoVITS local TTS API.
    Optimized for CVS-1.0 temporal orchestration.
    """

    def __init__(self, base_url: str = "http://localhost:9871"):
        self.base_url = base_url
        self.api_url = f"{base_url}/tts"
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def synthesize(
        self,
        text: str,
        ref_audio_path: str,
        ref_text: str = "",
        text_lang: str = "en",
        ref_lang: str = "en",
        media_type: str = "raw",
        language: Optional[str] = None,
        speed: Optional[float] = None,
        pitch: Optional[float] = None,
        volume: Optional[float] = None,
    ) -> Optional[bytes]:
        """
        Synthesize speech from text using voice cloning (Async)
        """
        try:
            payload = {
                "text": text,
                "text_lang": language or text_lang,
                "ref_audio_path": ref_audio_path,
                "prompt_text": ref_text,
                "prompt_lang": language or ref_lang,
                "text_split_method": "cut5",
                "batch_size": 1,
                "media_type": media_type,
                "streaming_mode": 0,
            }

            # Keep optional prosody knobs best-effort only for API versions that support them.
            if speed is not None:
                payload["speed_factor"] = speed
            if pitch is not None:
                payload["pitch"] = pitch
            if volume is not None:
                payload["volume"] = volume

            session = await self._get_session()
            async with session.post(self.api_url, json=payload, timeout=30) as response:
                response.raise_for_status()
                return await response.read()

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
        media_type: str = "raw",
        language: Optional[str] = None,
        speed: Optional[float] = None,
        pitch: Optional[float] = None,
        volume: Optional[float] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesized audio in raw PCM chunks (CVS-1.0 Optimal Path)
        """
        try:
            payload = {
                "text": text,
                "text_lang": language or text_lang,
                "ref_audio_path": ref_audio_path,
                "prompt_text": ref_text,
                "prompt_lang": language or ref_lang,
                "text_split_method": "cut5",
                "batch_size": 1,
                "media_type": media_type,
                "streaming_mode": 1,  # mode 1 or True depending on version
            }
            if speed is not None:
                payload["speed_factor"] = speed
            if pitch is not None:
                payload["pitch"] = pitch
            if volume is not None:
                payload["volume"] = volume

            session = await self._get_session()
            async with session.post(self.api_url, json=payload, timeout=60) as response:
                response.raise_for_status()
                # Stream blocks
                async for chunk in response.content.iter_any():
                    if chunk:
                        yield chunk

        except Exception as e:
            logger.error(f"SoVITS streaming failed: {e}")
            yield b""

    async def check_health(self) -> bool:
        """Check if GPT-SoVITS API is reachable"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/", timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    async def set_gpt_weights(self, weights_path: str) -> bool:
        """Set GPT weights file path (Async)"""
        try:
            url = f"{self.base_url}/set_gpt_weights"
            params = {"weights_path": weights_path}
            session = await self._get_session()
            async with session.get(url, params=params, timeout=10) as response:
                response.raise_for_status()
                logger.info(f"GPT weights set to: {weights_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to set GPT weights: {e}")
            return False

    async def set_sovits_weights(self, weights_path: str) -> bool:
        """Set SoVITS weights file path (Async)"""
        try:
            url = f"{self.base_url}/set_sovits_weights"
            params = {"weights_path": weights_path}
            session = await self._get_session()
            async with session.get(url, params=params, timeout=10) as response:
                response.raise_for_status()
                logger.info(f"SoVITS weights set to: {weights_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to set SoVITS weights: {e}")
            return False
