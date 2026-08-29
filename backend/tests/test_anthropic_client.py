"""
`AnthropicClient` (roadmap Phase 4.2) is the cloud fallback every construction
site reaches through `build_llm_client`. Three things about it are load-bearing
enough to break the agent silently if wrong:

1. `_translate_options` -- the endocrine->sampling mapping
   (`action.py::_compute_endocrine_options`) hands it Ollama-shaped keys
   (`num_predict`, `num_thread`, `num_ctx`); a wrong translation means
   cortisol/dopamine stop reaching the model's actual sampling params under
   this provider even though the caller never sees an error.
2. `MOCK_LLM_TEXT` must block every real network call here exactly like it
   does for `OllamaClient` -- a leak would mean the hermetic test suite (or a
   dev running with the mock flag on) makes real, billed API calls.
3. `describe_image`'s `None` (call failed) vs `""` (model saw nothing) split
   -- `VisualAppraisalService` (H8) tells these apart, so collapsing them back
   into one value would make a down VLM look like a quiet room again.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import httpx2
import pytest

from app import config as config_module
from app.llm.anthropic_client import AnthropicClient, _translate_options


def _connection_error() -> anthropic.APIConnectionError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


# ---------------------------------------------------------------------------
# _translate_options
# ---------------------------------------------------------------------------


def test_translate_options_returns_empty_dict_for_none():
    assert _translate_options(None) == {}


def test_translate_options_returns_empty_dict_for_empty_dict():
    assert _translate_options({}) == {}


def test_translate_options_carries_temperature_and_top_p_unchanged():
    out = _translate_options({"temperature": 0.42, "top_p": 0.81})
    assert out["temperature"] == 0.42
    assert out["top_p"] == 0.81


def test_translate_options_maps_num_predict_to_max_tokens():
    out = _translate_options({"num_predict": 150})
    assert out["max_tokens"] == 150
    assert "num_predict" not in out


def test_translate_options_drops_ollama_only_knobs():
    out = _translate_options({"num_ctx": 4096, "num_thread": 6})
    assert "num_ctx" not in out
    assert "num_thread" not in out
    assert out == {}


# ---------------------------------------------------------------------------
# MOCK_LLM_TEXT must short-circuit before any network call
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return AnthropicClient(api_key="sk-ant-test")


@pytest.mark.asyncio
async def test_generate_under_mock_never_touches_the_real_client(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", True)
    client._client.messages.create = AsyncMock(
        side_effect=AssertionError("must not be called under MOCK_LLM_TEXT")
    )
    result = await client.generate("hello")
    assert isinstance(result, str) and result
    client._client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_generate_stream_under_mock_never_touches_the_real_client(
    monkeypatch, client
):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", True)
    client._client.messages.stream = AsyncMock(
        side_effect=AssertionError("must not be called under MOCK_LLM_TEXT")
    )
    chunks = [c async for c in client.generate_stream("hello")]
    assert "".join(chunks)
    client._client.messages.stream.assert_not_called()


@pytest.mark.asyncio
async def test_describe_image_under_mock_never_touches_the_real_client(
    monkeypatch, client
):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", True)
    client._client.messages.create = AsyncMock(
        side_effect=AssertionError("must not be called under MOCK_LLM_TEXT")
    )
    result = await client.describe_image("ZmFrZQ==")
    assert isinstance(result, str) and result
    client._client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_joins_only_text_blocks(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="reasoning..."),
            _text_block("Hello "),
            _text_block("there."),
        ]
    )
    client._client.messages.create = AsyncMock(return_value=response)
    result = await client.generate("hi")
    assert result == "Hello there."


@pytest.mark.asyncio
async def test_generate_passes_num_predict_as_max_tokens(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("ok")])
    )
    await client.generate("hi", options_override={"num_predict": 77})
    _, kwargs = client._client.messages.create.call_args
    assert kwargs["max_tokens"] == 77


@pytest.mark.asyncio
async def test_generate_defaults_max_tokens_when_no_override_given(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("ok")])
    )
    await client.generate("hi")
    _, kwargs = client._client.messages.create.call_args
    assert kwargs["max_tokens"] > 0


@pytest.mark.asyncio
async def test_generate_omits_system_kwarg_when_not_given(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("ok")])
    )
    await client.generate("hi")
    _, kwargs = client._client.messages.create.call_args
    assert "system" not in kwargs


@pytest.mark.asyncio
async def test_generate_passes_system_when_given(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("ok")])
    )
    await client.generate("hi", system="You are terse.")
    _, kwargs = client._client.messages.create.call_args
    assert kwargs["system"] == "You are terse."


@pytest.mark.asyncio
async def test_generate_returns_fallback_string_on_api_error(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(side_effect=_connection_error())
    result = await client.generate("hi")
    assert result == "Error generating response."


# ---------------------------------------------------------------------------
# generate_stream()
# ---------------------------------------------------------------------------


class _FakeStreamCM:
    def __init__(self, chunks):
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    async def text_stream(self):
        for chunk in self._chunks:
            yield chunk


@pytest.mark.asyncio
async def test_generate_stream_yields_each_chunk(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.stream = lambda **kwargs: _FakeStreamCM(["Hel", "lo"])
    chunks = [c async for c in client.generate_stream("hi")]
    assert chunks == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_generate_stream_yields_fallback_string_on_api_error(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)

    def _raise(**kwargs):
        raise _connection_error()

    client._client.messages.stream = _raise
    chunks = [c async for c in client.generate_stream("hi")]
    assert chunks == ["I'm having trouble thinking right now..."]


# ---------------------------------------------------------------------------
# describe_image() -- the H8 None-vs-"" contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_describe_image_returns_text_on_success(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("a cat on a desk")])
    )
    result = await client.describe_image("ZmFrZQ==")
    assert result == "a cat on a desk"


@pytest.mark.asyncio
async def test_describe_image_returns_empty_string_when_model_says_nothing(
    monkeypatch, client
):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(return_value=SimpleNamespace(content=[]))
    result = await client.describe_image("ZmFrZQ==")
    assert result == ""


@pytest.mark.asyncio
async def test_describe_image_returns_none_when_the_call_itself_fails(
    monkeypatch, client
):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(side_effect=_connection_error())
    result = await client.describe_image("ZmFrZQ==")
    assert result is None


@pytest.mark.asyncio
async def test_describe_image_sends_jpeg_media_type(monkeypatch, client):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("ok")])
    )
    await client.describe_image("ZmFrZQ==")
    _, kwargs = client._client.messages.create.call_args
    image_block = kwargs["messages"][0]["content"][0]
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert image_block["source"]["data"] == "ZmFrZQ=="


# ---------------------------------------------------------------------------
# check_health()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_health_true_when_retrieve_succeeds(client):
    client._client.models.retrieve = AsyncMock(return_value=SimpleNamespace(id="m"))
    assert await client.check_health() is True


@pytest.mark.asyncio
async def test_check_health_false_when_retrieve_raises(client):
    client._client.models.retrieve = AsyncMock(side_effect=_connection_error())
    assert await client.check_health() is False
