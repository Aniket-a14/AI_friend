import json
from pathlib import Path

from app.contracts import (
    AudioPerception,
    AudioStop,
    ChatInput,
    ChatOutput,
    SpeechExpressionWire,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "crates" / "contracts" / "fixtures"


def _load_fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_rust_chat_output_fixture_matches_current_pydantic_contract():
    payload = _load_fixture("chat_output_chunk.json")

    parsed = ChatOutput.model_validate(payload)

    assert parsed.content == "Hey there<pause=20ms>friend"
    assert parsed.done is False
    assert parsed.turn_id == "turn-1"
    assert parsed.affect.valence == 0.8
    assert parsed.affect.arousal == 0.7
    assert parsed.affect.dominance == 0.6
    assert parsed.affect.trust == 0.5
    assert parsed.affect.attachment == 0.1
    assert parsed.affect.emotion == "happy"
    assert parsed.full_response is None
    assert parsed.generation_error is None
    assert parsed.proactive is False
    # Phase 3B: the shared fixture predates `expression` and has no producer
    # for it yet -- absent must parse as None, not raise, matching the Rust
    # struct's own `#[serde(default)]` on the same field (see
    # `chat_output_expression_defaults_to_none_when_absent` in
    # crates/contracts/src/lib.rs, same fixture).
    assert parsed.expression is None


def test_rust_audio_stop_fixture_matches_current_pydantic_contract():
    payload = _load_fixture("audio_stop_speculative.json")

    parsed = AudioStop.model_validate(payload)

    assert parsed.interrupt is True
    assert parsed.speculative is True
    assert parsed.intent == "SPECULATIVE_STOP"
    assert parsed.intent_type == "VOICE_INTERRUPTION"
    assert parsed.keywords == ["stop"]
    assert parsed.confidence == 0.9
    assert parsed.perception_text == "stop"
    assert parsed.utterance_id == "utt-1"


def test_rust_audio_perception_fixture_matches_current_pydantic_contract():
    payload = _load_fixture("audio_perception_speculative.json")

    parsed = AudioPerception.model_validate(payload)

    assert parsed.text == "stop"
    assert parsed.intent == "SPECULATIVE_STOP"
    assert parsed.intent_type == "COMMAND"
    assert parsed.keywords == ["stop"]
    assert parsed.confidence == 0.9
    assert parsed.snr == 12.5
    assert parsed.speculative_intent.name == "SPECULATIVE_STOP"
    assert parsed.speculative_intent.utterance_id == "utt-1"
    assert parsed.metadata["text"] == "stop"


def test_chat_output_expression_round_trips_when_present():
    """`expression` is optional and `extra: "allow"` on both sides -- a
    populated value (once a Phase 3A producer exists) must still validate
    and round-trip, not just the absent case the fixture-based test above
    covers."""
    payload = _load_fixture("chat_output_chunk.json")
    payload["expression"] = {
        "affect_label": "warm",
        "breath": 0.4,
        "hesitation": 0.6,
        "style": "soft",
        "trajectory": [0.1, 0.2, 0.3],
    }

    parsed = ChatOutput.model_validate(payload)

    assert isinstance(parsed.expression, SpeechExpressionWire)
    assert parsed.expression.affect_label == "warm"
    assert parsed.expression.breath == 0.4
    assert parsed.expression.hesitation == 0.6
    assert parsed.expression.style == "soft"
    assert parsed.expression.trajectory == [0.1, 0.2, 0.3]


def test_rust_chat_input_fixture_matches_current_pydantic_contract():
    payload = _load_fixture("chat_input_final.json")

    parsed = ChatInput.model_validate(payload)

    assert parsed.text == "hello there"
    assert parsed.utterance_id == "utt-1"
    assert parsed.metadata.source == "whisper"
    assert parsed.metadata.confidence == 0.9
    assert parsed.metadata.utterance_id == "utt-1"
    assert parsed.latency_metadata["source"] == "transport_agent"
