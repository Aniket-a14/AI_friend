import json
import logging
import asyncio
import httpx
import random
from typing import AsyncGenerator, Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ollama_client")


class OllamaClient:
    """
    Resilient Ollama Client for CVS-1.0.
    Implements Exponential Backoff with Jitter for high-load reliability.
    Uses httpx for unified async stack and connection pooling.
    """

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "llama3.2:1b"
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = 3
        self.base_delay = 1.0
        self.timeout = httpx.Timeout(10.0, read=180.0, connect=5.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_generate_prompt(self, prompt: str, system: str = None) -> str:
        safe_prompt = prompt.replace("System:", "").replace("Assistant:", "")
        return f"{system}\n\nUser: {safe_prompt}\nAssistant:" if system else safe_prompt

    def _build_chat_messages(
        self, prompt: str, system: str = None
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_payload_attempts(
        self,
        prompt: str,
        system: str,
        model: str,
        stream: bool,
        num_predict: int,
        options_override: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, Dict[str, Any], str]]:
        model_variants = self._build_model_variants(model)

        options = {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": num_predict,
            "num_thread": 6,
            "num_ctx": 2048,
        }
        if options_override:
            options.update(options_override)

        attempts: List[Tuple[str, Dict[str, Any], str]] = []
        for model_variant in model_variants:
            generate_payload = {
                "model": model_variant,
                "prompt": self._build_generate_prompt(prompt, system),
                "stream": stream,
                "options": options,
                "keep_alive": "20m",
            }
            chat_payload = {
                "model": model_variant,
                "messages": self._build_chat_messages(prompt, system),
                "stream": stream,
                "options": options,
                "keep_alive": "20m",
            }
            attempts.append(("/api/chat", chat_payload, model_variant))
            attempts.append(("/api/generate", generate_payload, model_variant))

        return attempts

    def _build_model_variants(self, model: str) -> List[str]:
        variants = [model]
        if ":" not in model:
            variants.append(f"{model}:latest")
        return list(dict.fromkeys(variants))

    def _extract_response_text(self, payload: Dict[str, Any]) -> str:
        text = payload.get("response")
        if isinstance(text, str):
            return text

        message = payload.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
        return ""

    async def generate_stream(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        options_override: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        payload_attempts = self._build_payload_attempts(
            prompt=prompt,
            system=system,
            model=model or self.model,
            stream=True,
            num_predict=40,
            options_override=options_override,
        )

        errors: List[str] = []
        client = await self._get_client()

        for attempt in range(self.max_retries):
            for endpoint, payload, model_variant in payload_attempts:
                try:
                    async with client.stream(
                        "POST", endpoint, json=payload
                    ) as response:
                        if response.status_code >= 400:
                            details = (await response.aread())[:200].decode()
                            errors.append(
                                f"{endpoint} ({model_variant}): HTTP {response.status_code} {details}"
                            )
                            continue

                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                if chunk.get("done"):
                                    continue
                                text = self._extract_response_text(chunk)
                                if text:
                                    yield text
                            except json.JSONDecodeError:
                                continue
                        return
                except (httpx.HTTPError, asyncio.TimeoutError) as e:
                    errors.append(f"{endpoint} ({model_variant}): {type(e).__name__}")
                    continue

            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2**attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(delay)

        yield "I'm having trouble thinking right now..."

    async def generate(
        self,
        prompt: str,
        system: str = None,
        model: str = None,
        options_override: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload_attempts = self._build_payload_attempts(
            prompt=prompt,
            system=system,
            model=model or self.model,
            stream=False,
            num_predict=64,
            options_override=options_override,
        )

        client = await self._get_client()
        errors: List[str] = []

        for attempt in range(self.max_retries):
            for endpoint, payload, model_variant in payload_attempts:
                try:
                    response = await client.post(endpoint, json=payload)
                    if response.status_code >= 400:
                        errors.append(f"{endpoint}: HTTP {response.status_code}")
                        continue

                    result = response.json()
                    text = self._extract_response_text(result)
                    if text:
                        return text
                except (httpx.HTTPError, asyncio.TimeoutError) as e:
                    errors.append(f"{endpoint}: {type(e).__name__}")
                    continue

            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2**attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(delay)

        return "Error generating response."

    async def describe_image(
        self,
        image_b64: str,
        prompt: str = "What do you see?",
        model: str = None,
    ) -> str:
        target_model = model or self.model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 128},
            "keep_alive": "10m",
        }

        client = await self._get_client()
        try:
            response = await client.post("/api/generate", json=payload, timeout=120.0)
            if response.status_code == 200:
                return self._extract_response_text(response.json())
        except Exception:
            pass
        return ""

    async def check_health(self) -> bool:
        client = await self._get_client()
        try:
            response = await client.get("/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
