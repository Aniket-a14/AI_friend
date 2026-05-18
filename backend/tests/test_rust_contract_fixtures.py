import json
from pathlib import Path

from app.contracts import AudioPerception, AudioStop, ChatInput, ChatOutput


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
    assert parsed.confidence == 0.9
    assert parsed.intensity == 0.56
    assert parsed.speaking_rate == 1.15
    assert parsed.pause_bias == 0.24
    assert parsed.paralinguistic_tags == ["[laughs]"]
    assert parsed.full_response is None
    assert parsed.generation_error is None
    assert parsed.proactive is False


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


def test_rust_chat_input_fixture_matches_current_pydantic_contract():
    payload = _load_fixture("chat_input_final.json")

    parsed = ChatInput.model_validate(payload)

    assert parsed.text == "hello there"
    assert parsed.utterance_id == "utt-1"
    assert parsed.metadata.source == "whisper"
    assert parsed.metadata.confidence == 0.9
    assert parsed.metadata.utterance_id == "utt-1"
    assert parsed.latency_metadata["source"] == "transport_agent"
