"""
GPT-SoVITS Client - API wrapper for local voice synthesis (Async CVS-1.0 Edition)
"""

import httpx
import logging
from typing import Optional, AsyncGenerator
from ..config import Config

logger = logging.getLogger(__name__)


class SoVITSClient:
    """
    Async Client for GPT-SoVITS local TTS API.
    Optimized for CVS-1.0 temporal orchestration.
    Uses httpx for high-performance async I/O.
    """

    def __init__(self, base_url: str = "http://localhost:9871"):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/tts"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(10.0, read=60.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

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

            if speed is not None:
                payload["speed_factor"] = speed
            if pitch is not None:
                payload["pitch"] = pitch
            if volume is not None:
                payload["volume"] = volume

            client = await self._get_client()
            response = await client.post("/tts", json=payload, timeout=30.0)
            response.raise_for_status()
            return response.content

        except Exception as e:
            if getattr(Config, "VOICE_TTS_MOCK", False):
                logger.info(f"SoVITS fallback: Mocking synthesis for '{text[:20]}...'")
                return b"\x00" * 32000  # 1s of silence
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
                "streaming_mode": 1,
            }
            if speed is not None:
                payload["speed_factor"] = speed
            if pitch is not None:
                payload["pitch"] = pitch
            if volume is not None:
                payload["volume"] = volume

            client = await self._get_client()
            async with client.stream(
                "POST", "/tts", json=payload, timeout=60.0
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

        except Exception as e:
            if getattr(Config, "VOICE_TTS_MOCK", False):
                logger.info(f"SoVITS fallback: Mocking stream for '{text[:20]}...'")
                yield b"\x00" * 1600  # small chunk of silence
                return
            logger.error(f"SoVITS streaming failed: {e}")
            yield b""

    async def check_health(self) -> bool:
        """Check if GPT-SoVITS API is reachable"""
        try:
            client = await self._get_client()
            response = await client.get("/", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def set_gpt_weights(self, weights_path: str) -> bool:
        """Set GPT weights file path (Async)"""
        try:
            url = "/set_gpt_weights"
            params = {"weights_path": weights_path}
            client = await self._get_client()
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            logger.info(f"GPT weights set to: {weights_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to set GPT weights: {e}")
            return False

    async def set_sovits_weights(self, weights_path: str) -> bool:
        """Set SoVITS weights file path (Async)"""
        try:
            url = "/set_sovits_weights"
            params = {"weights_path": weights_path}
            client = await self._get_client()
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            logger.info(f"SoVITS weights set to: {weights_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to set SoVITS weights: {e}")
            return False
