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
    client.request_context = "probe:identity.name"
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
    assert request["request_context"] == "probe:identity.name"


@pytest.mark.asyncio
async def test_ollama_records_installed_model_digest_when_tags_exposes_one():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "phi4-mini:latest",
                        "digest": "sha256:model-digest",
                        "size": 123,
                        "modified_at": "2026-09-03T00:00:00Z",
                        "details": {"quantization_level": "Q4_K_M"},
                    }
                ]
            },
        )

    client = OllamaClient(base_url="http://ollama.test:11434", model="phi4-mini")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    try:
        provenance = await client.get_model_provenance()
    finally:
        await client.close()

    assert provenance["requested_model"] == "phi4-mini"
    assert provenance["name"] == "phi4-mini:latest"
    assert provenance["digest"] == "sha256:model-digest"
    assert provenance["details"]["quantization_level"] == "Q4_K_M"


def test_request_provenance_stays_bounded_on_a_long_running_client():
    """brain_agent/subconscious_agent hold one OllamaClient for the process's
    whole uptime and call generate on every turn forever. Without a cap this
    list grows one dict per call for as long as the process runs -- a slow
    memory leak that only ever benefits the eval harness, which never sees a
    single run anywhere near this many requests."""
    client = OllamaClient(base_url="http://ollama.test:11434")
    cap = client._MAX_REQUEST_PROVENANCE

    for i in range(cap + 50):
        client._record_request(
            "/api/chat", {"model": f"call-{i}", "options": {}}, successful=True
        )

    assert len(client.request_provenance) == cap
    assert client.request_provenance_dropped == 50
    # Trimming drops the oldest entries, so the most recent calls survive.
    assert client.request_provenance[-1]["model"] == f"call-{cap + 49}"
    assert client.request_provenance[0]["model"] == "call-50"
