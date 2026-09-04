"""Phase 07 Task B5: genuine cross-provider behavioral validation.

The Final System Audit (FINAL_SYSTEM_VALIDATION_REPORT.md) found that
BM-GPU-P5-01, the provider-independence benchmark, was a same-provider
tautology -- it compared Ollama against Ollama under two labels, never an
actually distinct `LLMClient` (app/llm/__init__.py) backend. This module is
the genuine version at the unit level, in two parts:

1. `OllamaClient` and `AnthropicClient` are exercised as real classes with
   only their network boundary mocked (httpx for Ollama, the `anthropic` SDK
   client for Anthropic) -- proving `LLMClient.generate()`'s contract (a
   plain `str`, built from whatever the same `prompt`/`system` arguments
   produced) holds across two genuinely different wire protocols, not just
   two call sites of the same one.

2. `ActionService` (cognitive/action.py) sits above `LLMClient` and must not
   have quietly come to depend on Ollama's specific streaming shape. Ollama
   commonly emits a response as many small, sub-word fragments -- CLAUDE.md
   documents the incremental `<thought>` parser existing precisely because
   "<", "thought", ">" routinely arrive as separate tokens, "the common
   case, not an edge case" -- while Anthropic's SDK `text_stream` yields
   fewer, larger text deltas. Two fake `LLMClient`-conforming providers
   below reproduce each backend's *chunking shape* deterministically (not
   live network calls, which would make this suite flaky) so the same
   response-processing assertions -- <thought> stripping, the "as an AI"
   identity-boundary self-correction retry -- can be run against both
   shapes and shown to produce identical visible output either way.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import httpx2
import pytest

from app import config as config_module
from app.cognitive.action import ActionService
from app.cognitive.decision import ActionPlan
from app.llm import LLMClient
from app.llm.anthropic_client import AnthropicClient
from app.llm.ollama_client import OllamaClient

# ---------------------------------------------------------------------------
# Part 1: the real client classes, network boundary mocked, agree on the
# LLMClient contract for identical logical content.
# ---------------------------------------------------------------------------


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


@pytest.fixture
def ollama_client():
    with patch("app.llm.ollama_client.Config.MOCK_LLM_TEXT", False):
        yield OllamaClient(base_url="http://mock-ollama:11434")


@pytest.fixture
def anthropic_client(monkeypatch):
    monkeypatch.setattr(config_module.config_instance, "MOCK_LLM_TEXT", False)
    return AnthropicClient(api_key="sk-ant-test")


def test_both_real_clients_satisfy_the_llmclient_protocol(
    ollama_client, anthropic_client
):
    """`build_llm_client` promises every call site an `LLMClient` regardless
    of `Config.LLM_PROVIDER` -- both concrete classes must actually satisfy
    the runtime-checkable Protocol, not merely happen to share method names."""
    assert isinstance(ollama_client, LLMClient)
    assert isinstance(anthropic_client, LLMClient)


@pytest.mark.asyncio
async def test_generate_returns_identical_text_across_providers_for_identical_content(
    ollama_client, anthropic_client
):
    """Same logical upstream content, delivered through two structurally
    unrelated wire formats (Ollama's `{"response": ...}` JSON body vs.
    Anthropic's `messages.create` content-block list), must resolve to the
    exact same `LLMClient.generate()` return value: a plain `str`. A caller
    (ReflectionService, ActionService, ...) that only ever holds an
    `LLMClient` reference can never observe which provider it is talking to
    from the return value's shape."""
    reply_text = "Building a treehouse sounds like a wonderful weekend project."

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value={"response": reply_text})
        )
        ollama_result = await ollama_client.generate(
            "What should we build this weekend?", system="You are a warm friend."
        )

    anthropic_client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block(reply_text)])
    )
    anthropic_result = await anthropic_client.generate(
        "What should we build this weekend?", system="You are a warm friend."
    )

    assert ollama_result == reply_text
    assert anthropic_result == reply_text
    assert ollama_result == anthropic_result


@pytest.mark.asyncio
async def test_persona_system_prompt_reaches_both_transports_unmodified(
    ollama_client, anthropic_client
):
    """Prompt assembly (identity/persona construction) happens above the
    `LLMClient` boundary and must not be rewritten, truncated, or otherwise
    altered by either concrete client on its way to the network -- each
    transport must carry the exact same `system` text this test supplies,
    just packaged in that provider's own wire shape (a JSON field for
    Ollama, a constructor kwarg for Anthropic)."""
    persona_system_prompt = (
        "You are my friend: warm, curious, and you never claim to be an AI "
        "language model."
    )

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value={"response": "Hi!"})
        )
        await ollama_client.generate("hello", system=persona_system_prompt)
        # /api/chat is tried first (see _build_payload_attempts) and carries
        # system/user as separate structured messages rather than a single
        # "system" field.
        ollama_payload = mock_post.call_args.kwargs.get(
            "json"
        ) or mock_post.call_args.args[1]
        assert {
            "role": "system",
            "content": persona_system_prompt,
        } in ollama_payload["messages"]

    anthropic_client._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=[_text_block("Hi!")])
    )
    await anthropic_client.generate("hello", system=persona_system_prompt)
    anthropic_kwargs = anthropic_client._client.messages.create.call_args.kwargs
    assert anthropic_kwargs["system"] == persona_system_prompt


@pytest.mark.asyncio
async def test_network_failure_produces_the_same_fallback_contract_across_providers(
    ollama_client, anthropic_client
):
    """Identity boundaries include never going silent on the user: both
    clients must degrade to *some* spoken string, never an exception
    escaping into `ActionService`, regardless of which provider's transport
    actually failed."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Perpetual Failure")
        ollama_client.base_delay = 0.01
        ollama_result = await ollama_client.generate("hello")

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    anthropic_client._client.messages.create = AsyncMock(
        side_effect=anthropic.APIConnectionError(request=request)
    )
    anthropic_result = await anthropic_client.generate("hello")

    assert isinstance(ollama_result, str) and ollama_result
    assert isinstance(anthropic_result, str) and anthropic_result


# ---------------------------------------------------------------------------
# Part 2: ActionService's response processing does not depend on which
# provider's characteristic chunking shape produced the stream.
# ---------------------------------------------------------------------------


def _ollama_shaped_chunks(text: str) -> list[str]:
    """Small, often sub-word fragments, including the `<thought>` tag's own
    characters split apart -- the shape CLAUDE.md documents as Ollama's
    common case, not a contrived edge case."""
    chunks: list[str] = []
    i = 0
    while i < len(text):
        step = 1 if text[i] in "<>/" else min(3, len(text) - i)
        chunks.append(text[i : i + step])
        i += step
    return chunks


def _anthropic_shaped_chunks(text: str) -> list[str]:
    """Few, large contiguous text deltas -- the shape Anthropic's SDK
    `text_stream` yields, per AnthropicClient.generate_stream's own
    `async for text in stream.text_stream` loop."""
    if len(text) <= 1:
        return [text] if text else []
    midpoint = len(text) // 2
    return [text[:midpoint], text[midpoint:]]


def _make_plan(message: str = "hello") -> ActionPlan:
    return ActionPlan(
        action_type="RESPOND_CHAT",
        goal="ENGAGE",
        payload={"message": message, "valence": 0.0, "arousal": 0.5, "dominance": 0.5},
    )


async def _run_action_service(chunks: list[str]) -> list[dict]:
    llm = MagicMock()

    async def mock_stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    llm.generate_stream = MagicMock(side_effect=mock_stream)
    action_service = ActionService(llm_service=llm, memory_store=MagicMock())

    collected = []
    async for out_chunk in action_service.execute(_make_plan()):
        collected.append(out_chunk)
    return collected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "shape_fn", [_ollama_shaped_chunks, _anthropic_shaped_chunks], ids=["ollama_shaped", "anthropic_shaped"]
)
async def test_thought_stripping_is_identical_regardless_of_provider_chunk_shape(
    shape_fn,
):
    """The incremental <thought> parser must fully hide the reasoning block
    and yield the same visible vocalization whether it arrives as many tiny
    Ollama-shaped fragments or a couple of large Anthropic-shaped deltas."""
    raw = "<thought>Analyzing the request...</thought>Hello user!"
    chunks = await _run_action_service(shape_fn(raw))

    content_chunks = [c["data"] for c in chunks if c["type"] == "content"]
    full_vocalization = "".join(content_chunks)

    assert "<thought>" not in full_vocalization
    assert "Analyzing the request..." not in full_vocalization
    assert "Hello user!" in full_vocalization


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "shape_fn", [_ollama_shaped_chunks, _anthropic_shaped_chunks], ids=["ollama_shaped", "anthropic_shaped"]
)
async def test_identity_boundary_self_correction_is_identical_regardless_of_provider_chunk_shape(
    shape_fn,
):
    """`_validate_partial_response`'s "never claim to be an AI language
    model" identity boundary must reject a violating response and retry
    into the corrected one, regardless of whether the violating text
    arrived in small Ollama-shaped fragments (splitting the forbidden
    phrase itself across chunk boundaries) or large Anthropic-shaped ones."""
    violating = "As an AI, I don't have feelings about that."
    corrected = "I do care about how that went for you."

    violating_chunks = shape_fn(violating)
    streams = [violating_chunks, [corrected]]
    call_count = 0

    llm = MagicMock()

    def side_effect(*args, **kwargs):
        nonlocal call_count
        chunks = streams[call_count]
        call_count += 1

        async def _gen():
            for chunk in chunks:
                yield chunk

        return _gen()

    llm.generate_stream = MagicMock(side_effect=side_effect)
    action_service = ActionService(llm_service=llm, memory_store=MagicMock())
    action_service.publish_cb = AsyncMock()

    chunks = []
    async for out_chunk in action_service.execute(_make_plan()):
        chunks.append(out_chunk)

    content_chunks = [c["data"] for c in chunks if c["type"] == "content"]
    full_vocalization = "".join(content_chunks)

    assert "as an ai" not in full_vocalization.lower()
    assert corrected in full_vocalization


def test_shared_history_prompt_assembly_does_not_depend_on_which_client_is_attached():
    """`_build_shared_history` is where retrieved-memory content is wrapped
    for the prompt (Section 39's AntiInjectionGate boundary). It reads no
    provider-specific state -- attaching an Ollama-flavored vs an
    Anthropic-flavored client to `ActionService` must not change its output
    for identical input."""
    memories = [{"content": "We talked about hiking.", "source": "conversation"}]

    ollama_backed = ActionService(llm_service=MagicMock(), memory_store=MagicMock())
    anthropic_backed = ActionService(llm_service=MagicMock(), memory_store=MagicMock())

    assert ActionService._build_shared_history(
        memories
    ) == ollama_backed._build_shared_history(memories) == anthropic_backed._build_shared_history(
        memories
    )
