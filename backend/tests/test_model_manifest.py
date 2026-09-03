import pytest

from app.llm.model_manifest import ModelCapability, get_model_capability


@pytest.mark.parametrize(
    "model_tag",
    ["llama3.2:3b", "qwen2.5:3b", "phi4-mini", "llama3.2:1b"],
)
def test_seeded_model_capabilities_are_typed(model_tag):
    capability = get_model_capability(model_tag)

    assert isinstance(capability, ModelCapability)
    assert capability.context_window > 0
    assert isinstance(capability.supports_thinking_tokens, bool)
    assert capability.streaming is True
    assert capability.structured_output is True
    assert capability.language
    assert capability.quantization is None
    assert capability.expected_latency_p50_ms is None


def test_unknown_model_has_no_capability():
    assert get_model_capability("unknown:model") is None


def test_model_capability_is_returned_without_registry_aliasing():
    capability = get_model_capability("llama3.2:3b")
    capability.language.append("mutated")

    assert "mutated" not in get_model_capability("llama3.2:3b").language
