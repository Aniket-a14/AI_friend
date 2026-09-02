"""The eval report must describe the request Ollama actually received."""

import httpx
import pytest

from app.llm.ollama_client import OllamaClient


@pytest.mark.asyncio
async def test_ollama_records_successful_endpoint_model_and_full_options():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = OllamaClient(base_url="http://ollama.test:11434", model="phi4-mini")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    try:
        assert await client.generate("question", system="persona", options_override={"seed": 42}) == "ok"
    finally:
        await client.close()

    successful = [item for item in client.request_provenance if item["successful"]]
    assert successful
    request = successful[-1]
    assert request["base_url"] == "http://ollama.test:11434"
    assert request["endpoint"] == "/api/chat"
    assert request["model"] == "phi4-mini"
    assert request["options"]["num_thread"] == 6
    assert request["options"]["num_ctx"] == 8192
    assert request["keep_alive"] == "20m"
    assert request["prompt_sha256"]
    assert request["system_prompt_sha256"]
