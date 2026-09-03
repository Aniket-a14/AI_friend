import pytest

from app.cognitive.action import (
    ActionService,
    ControlMarkupSanitizer,
    _ChatStreamState,
    _parse_typed_realization,
)
from app.cognitive.decision import ActionPlan


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            (
                '{"spoken_text":"hello","realization_confidence":0.8,'
                '"unanswered_questions":[],"claim_ids_used":[]}'
            ),
            "hello",
        ),
        ("not json", None),
        ('{"spoken_text":"","realization_confidence":0.8}', None),
        ('{"spoken_text":"hello","realization_confidence":2}', None),
        ('{"spoken_text":"hello","realization_confidence":true}', None),
        ('{"spoken_text":"hello","realization_confidence":0.8,"claim_ids_used":"x"}', None),
    ],
)
def test_typed_realization_parser_fails_closed(raw, expected):
    parsed = _parse_typed_realization(raw)
    assert parsed is None if expected is None else parsed["spoken_text"] == expected


class _StreamingLLM:
    def __init__(self, chunks):
        self.chunks = chunks
        self.system_instruction = None

    async def generate_stream(self, **kwargs):
        self.system_instruction = kwargs.get("system")
        for chunk in self.chunks:
            yield chunk


async def _stream(service, plan, monkeypatch, enabled):
    import app.config as config_module

    monkeypatch.setattr(
        config_module.config_instance, "LLM_TYPED_REALIZATION_ENABLED", enabled
    )
    return [
        item
        async for item in service._stream_primary_response(
            plan=plan,
            user_prompt="hello",
            system_instruction="system",
            model=None,
            endocrine_options={},
            sanitizer=ControlMarkupSanitizer(),
            stream_budget=15,
            state=_ChatStreamState(),
            surfaced=[],
            msg="hello",
        )
    ]


@pytest.mark.asyncio
async def test_typed_realization_stream_emits_only_spoken_text(monkeypatch):
    service = ActionService(
        llm_service=_StreamingLLM(
            [
                '{"spoken_text":"bounded ',
                'reply","realization_confidence":0.9,"unanswered_questions":[],',
                '"claim_ids_used":[]}',
            ]
        )
    )
    plan = ActionPlan(action_type="RESPOND_CHAT", payload={}, goal="ENGAGE")

    outputs = await _stream(service, plan, monkeypatch, enabled=True)

    assert [item["data"] for item in outputs if item["type"] == "content"] == [
        "bounded reply"
    ]
    assert outputs[-1] == {"type": "done", "data": "finished"}


@pytest.mark.asyncio
async def test_invalid_typed_realization_falls_back_to_raw_text(monkeypatch):
    service = ActionService(_StreamingLLM(["not a JSON envelope"]))
    plan = ActionPlan(action_type="RESPOND_CHAT", payload={}, goal="ENGAGE")

    outputs = await _stream(service, plan, monkeypatch, enabled=True)

    assert [item["data"] for item in outputs if item["type"] == "content"] == [
        "not a JSON envelope"
    ]


@pytest.mark.asyncio
async def test_typed_realization_is_opt_in_and_legacy_streaming_is_preserved(monkeypatch):
    service = ActionService(_StreamingLLM(["hello", " world"]))
    plan = ActionPlan(action_type="RESPOND_CHAT", payload={}, goal="ENGAGE")

    outputs = await _stream(service, plan, monkeypatch, enabled=False)

    assert [item["data"] for item in outputs if item["type"] == "content"] == [
        "hello",
        " world",
    ]


@pytest.mark.asyncio
async def test_typed_realization_guidance_is_appended_only_when_enabled(monkeypatch):
    import app.config as config_module

    service = ActionService(_StreamingLLM(["hello"]))
    plan = ActionPlan(
        action_type="RESPOND_CHAT",
        payload={"message": "hello"},
        goal="ENGAGE",
    )

    monkeypatch.setattr(
        config_module.config_instance, "LLM_TYPED_REALIZATION_ENABLED", True
    )
    outputs = [item async for item in service._execute_respond_chat(plan)]

    assert "spoken_text" in service.llm.system_instruction
    assert "claim_ids_used" in service.llm.system_instruction
    assert outputs[-1] == {"type": "done", "data": "finished"}
