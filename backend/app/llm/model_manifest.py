from __future__ import annotations

from pydantic import BaseModel


class ModelCapability(BaseModel):
    context_window: int
    supports_thinking_tokens: bool
    streaming: bool
    structured_output: bool
    language: list[str]
    quantization: str | None = None
    expected_latency_p50_ms: float | None = None


MODEL_CAPABILITIES: dict[str, ModelCapability] = {
    "llama3.2:3b": ModelCapability(
        context_window=131072,
        supports_thinking_tokens=False,
        streaming=True,
        structured_output=True,
        language=["en"],
    ),
    "qwen2.5:3b": ModelCapability(
        context_window=32768,
        supports_thinking_tokens=False,
        streaming=True,
        structured_output=True,
        language=["en", "zh"],
    ),
    "phi4-mini": ModelCapability(
        context_window=128000,
        supports_thinking_tokens=False,
        streaming=True,
        structured_output=True,
        language=["en"],
    ),
    "llama3.2:1b": ModelCapability(
        context_window=131072,
        supports_thinking_tokens=False,
        streaming=True,
        structured_output=True,
        language=["en"],
    ),
}


def get_model_capability(model_tag: str) -> ModelCapability | None:
    capability = MODEL_CAPABILITIES.get(model_tag)
    return capability.model_copy(deep=True) if capability is not None else None
