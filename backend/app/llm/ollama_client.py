import json
import logging
import asyncio
import aiohttp
import random
from typing import AsyncGenerator, Callable, Any

logger = logging.getLogger("ollama_client")

class OllamaClient:
    """
    Resilient Ollama Client for CVS-1.0.
    Implements Exponential Backoff with Jitter for high-load reliability.
    """
    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b"
    ):
        self.base_url = base_url
        self.model = model
        self.max_retries = 3
        self.base_delay = 1.0 # 1 second baseline

    async def _request_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Helper to execute async functions with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"❌ Ollama request failed after {self.max_retries} attempts: {e}")
                    raise
                
                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(f"⚠️ Ollama Busy/Down. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(delay)
        return None

    async def generate_stream(
        self, prompt: str, system: str = None, model: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream responses from Ollama with Resilience Guard.
        """
        full_prompt = f"{system}\n\nUser: {prompt}\nAssistant:" if system else prompt

        payload = {
            "model": model or self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 256, "num_thread": 8},
        }

        try:
            # We don't fully backoff the generator here to avoid complex state management, 
            # but we protect the initial connection.
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if not chunk.get("done"):
                                    yield chunk.get("response", "")
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            yield "I'm having trouble thinking right now..."

    async def generate(self, prompt: str, system: str = None, model: str = None) -> str:
        """
        Non-blocking generation with Exponential Backoff.
        """
        full_prompt = f"{system}\n\nUser: {prompt}\nAssistant:" if system else prompt

        payload = {
            "model": model or self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "top_p": 0.9, "num_predict": 128},
        }

        async def _do_gen():
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload, timeout=30) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result.get("response", "")

        try:
            return await self._request_with_backoff(_do_gen)
        except Exception:
            return "Error generating response."

    async def check_health(self) -> bool:
        """Check if Ollama is reachable"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=5) as response:
                    return response.status == 200
        except Exception:
            return False
