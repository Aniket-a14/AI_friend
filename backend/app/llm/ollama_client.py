import json
import logging
import asyncio
import aiohttp
import random
from typing import AsyncGenerator, Callable, Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ollama_client")


class OllamaClient:
    """
    Resilient Ollama Client for CVS-1.0.
    Implements Exponential Backoff with Jitter for high-load reliability.
    """

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "llama3.2:1b"
    ):
        self.base_url = base_url
        self.model = model
        self.max_retries = 3
        self.base_delay = 1.0  # 1 second baseline
        self.stream_timeout = 180

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
    ) -> List[Tuple[str, Dict[str, Any], str]]:
        model_variants = self._build_model_variants(model)

        options = {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": num_predict,
            "num_thread": 6,
            "num_ctx": 2048,
        }

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

            # /api/chat has been more stable than /api/generate in CPU-only environments.
            attempts.append(("/api/chat", chat_payload, model_variant))
            attempts.append(("/api/generate", generate_payload, model_variant))

        return attempts

    def _build_model_variants(self, model: str) -> List[str]:
        """Provide lightweight model-name compatibility similar to embedding endpoint fallbacks."""
        variants = [model]

        # If tag is omitted, try explicit :latest as a compatibility fallback.
        if ":" not in model:
            variants.append(f"{model}:latest")

        deduped: List[str] = []
        seen = set()
        for variant in variants:
            if variant in seen:
                continue
            seen.add(variant)
            deduped.append(variant)

        return deduped

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

    def _parse_json_line(self, raw_line: bytes) -> Optional[Dict[str, Any]]:
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            return None

        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return None
        return None

    async def _iter_json_payloads(
        self, stream_content: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Parse newline-delimited JSON payloads from chunked HTTP stream content."""
        buffer = b""
        async for chunk in stream_content:
            if not chunk:
                continue
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8", errors="ignore")

            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                payload = self._parse_json_line(raw_line)
                if payload is not None:
                    yield payload

        tail_payload = self._parse_json_line(buffer)
        if tail_payload is not None:
            yield tail_payload

    async def _request_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Helper to execute async functions with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"❌ Ollama request failed after {self.max_retries} attempts: {e}"
                    )
                    raise

                delay = self.base_delay * (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    f"⚠️ Ollama Busy/Down. Retrying in {delay:.2f}s (Attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
        return None

    async def generate_stream(
        self, prompt: str, system: str = None, model: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream responses from Ollama with Resilience Guard.
        """
        payload_attempts = self._build_payload_attempts(
            prompt=prompt,
            system=system,
            model=model or self.model,
            stream=True,
            num_predict=40,
        )

        errors: List[str] = []

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    for endpoint, payload, model_variant in payload_attempts:
                        try:
                            async with session.post(
                                f"{self.base_url}{endpoint}",
                                json=payload,
                                timeout=self.stream_timeout,
                            ) as response:
                                if response.status >= 400:
                                    details = (await response.text())[:200]
                                    errors.append(
                                        f"{endpoint} ({model_variant}): HTTP {response.status} {details}"
                                    )
                                    logger.warning(
                                        "Ollama endpoint %s (model=%s) returned HTTP %s, trying fallback. %s",
                                        endpoint,
                                        model_variant,
                                        response.status,
                                        details,
                                    )
                                    continue

                                async for chunk in self._iter_json_payloads(
                                    response.content
                                ):
                                    if chunk.get("done"):
                                        continue
                                    text = self._extract_response_text(chunk)
                                    if text:
                                        yield text
                                return
                        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                            errors.append(
                                f"{endpoint} ({model_variant}): {type(e).__name__} {e}"
                            )
                            logger.warning(
                                "Ollama streaming endpoint %s (model=%s) failed, trying fallback: %s",
                                endpoint,
                                model_variant,
                                repr(e),
                            )
                            continue

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "⚠️ Ollama stream generation retrying in %.2fs (Attempt %s/%s)",
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    await asyncio.sleep(delay)
            except Exception as e:
                errors.append(f"stream_attempt_{attempt + 1}: {type(e).__name__} {e}")

        logger.error(
            "Ollama streaming failed after %s attempts. %s",
            self.max_retries,
            " | ".join(errors[-6:]),
        )
        yield "I'm having trouble thinking right now..."

    async def generate(self, prompt: str, system: str = None, model: str = None) -> str:
        """
        Non-blocking generation with Exponential Backoff.
        """
        payload_attempts = self._build_payload_attempts(
            prompt=prompt,
            system=system,
            model=model or self.model,
            stream=False,
            num_predict=64,
        )

        async def _do_gen():
            async with aiohttp.ClientSession() as session:
                errors: List[str] = []
                for endpoint, payload, model_variant in payload_attempts:
                    try:
                        async with session.post(
                            f"{self.base_url}{endpoint}",
                            json=payload,
                            timeout=45,
                        ) as response:
                            if response.status >= 400:
                                details = (await response.text())[:200]
                                errors.append(
                                    f"{endpoint} ({model_variant}): HTTP {response.status} {details}"
                                )
                                logger.warning(
                                    "Ollama endpoint %s (model=%s) returned HTTP %s, trying fallback. %s",
                                    endpoint,
                                    model_variant,
                                    response.status,
                                    details,
                                )
                                continue

                            result = await response.json()
                            text = self._extract_response_text(result)
                            if text:
                                return text
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        errors.append(
                            f"{endpoint} ({model_variant}): {type(e).__name__} {e}"
                        )
                        logger.warning(
                            "Ollama endpoint %s (model=%s) request failed, trying fallback: %s",
                            endpoint,
                            model_variant,
                            repr(e),
                        )
                        continue

                raise RuntimeError(
                    "No compatible Ollama generation endpoint found. "
                    + " | ".join(errors)
                )

        try:
            return await self._request_with_backoff(_do_gen)
        except Exception as e:
            logger.error("Ollama non-stream generation failed hard: %s", e)
            return "Error generating response."

    async def check_health(self) -> bool:
        """Check if Ollama is reachable"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags", timeout=5
                ) as response:
                    return response.status == 200
        except Exception:
            return False
