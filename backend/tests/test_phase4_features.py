"""
The Brain→Voice affect contract, and prosody having exactly one source.

This file used to assert Python's PAD-to-prosody formulas in fine numeric
detail. Those assertions were green for the life of the project and proved
nothing about the running system: the voice agent computes prosody itself from
the `affect` vector via `contracts::vad_to_prosody` (Rust) and never read the
values Python attached. The two implementations had also drifted — Python's
speaking rate was linear where Rust's is `tanh`-saturated, and Rust models
pitch, volume, and distance adaptation that Python did not have at all.

So the tests here now pin the contract that actually exists: the brain emits a
complete and accurate **affect vector**, and does not emit prosody. A test
asserting a formula nobody consumes is worse than no test, because it makes
dead code look load-bearing and dares the next reader to delete it.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.utils.speech import SpeechCoordinator
from app.utils.segmentation import HybridSegmenter
from app.contracts import ChatOutput, ChatOutputAffect
from app.agents.brain_agent import BrainAgent


def test_the_coordinator_no_longer_computes_prosody():
    """Python must not grow a second prosody implementation again.

    If this method returns, the system once more has two disagreeing answers to
    "how fast does the agent talk", only one of which reaches the speaker.
    """
    assert not hasattr(SpeechCoordinator, "map_affect_to_prosody")


def test_a_chunk_payload_carries_the_full_affect_vector():
    """Affect is the real contract: it is the sole input to Rust prosody.

    Every field here is read by `vad_to_prosody`, so a value silently dropped
    or defaulted on this side changes how the agent sounds.
    """
    coordinator = SpeechCoordinator(segmenter=HybridSegmenter(target_size=8))

    payload = coordinator.create_chunk_payload(
        words=["hello", "there"],
        state_snap={
            "valence": 0.5,
            "arousal": 0.7,
            "dominance": 0.6,
            "trust": 0.8,
            "attachment": 0.4,
            "emotion": "happy",
            "fatigue": 0.2,
        },
        turn_id="turn-4",
        done=False,
        user_distance=1.2,
    )

    assert isinstance(payload, ChatOutput)
    assert payload.content == "hello there"
    assert payload.turn_id == "turn-4"
    assert payload.done is False

    assert isinstance(payload.affect, ChatOutputAffect)
    assert payload.affect.valence == 0.5
    assert payload.affect.arousal == 0.7
    assert payload.affect.dominance == 0.6
    assert payload.affect.trust == 0.8
    assert payload.affect.attachment == 0.4
    assert payload.affect.emotion == "happy"
    assert payload.affect.fatigue == 0.2
    assert payload.affect.user_distance == 1.2


def test_the_legacy_mood_and_energy_keys_still_map_onto_affect():
    """`get_context_snapshot` has emitted both namings historically.

    Dropping the fallback would send valence 0.0 / arousal 0.5 — a flat,
    neutral-sounding agent — rather than failing loudly.
    """
    coordinator = SpeechCoordinator(segmenter=HybridSegmenter(target_size=8))
    payload = coordinator.create_chunk_payload(
        words=["hi"], state_snap={"mood": -0.7, "energy": 0.9}, turn_id="t"
    )
    assert payload.affect.valence == -0.7
    assert payload.affect.arousal == 0.9


def test_an_absent_state_snapshot_produces_neutral_affect_not_a_crash():
    """A chunk published before state exists must still be speakable."""
    coordinator = SpeechCoordinator(segmenter=HybridSegmenter(target_size=8))
    payload = coordinator.create_chunk_payload(words=["hi"], state_snap=None)
    assert payload.affect.valence == 0.0
    assert payload.affect.arousal == 0.5
    assert payload.affect.emotion == "neutral"


def test_the_brain_declares_no_prosody_fields_at_all():
    """Strengthened from asserting the deprecated fields sat at their defaults.

    They used to be kept, inert, for deserialization compatibility. They are now
    removed outright, which is a stronger guarantee than "present but default":
    a field that does not exist cannot be quietly repopulated with a second
    opinion that disagrees with what the voice agent computes from `affect`.

    Asserted on the model's declared fields rather than on attribute access,
    because `ChatOutput` is `extra: "allow"` -- reading `payload.speaking_rate`
    on an instance built from an *older* message would still succeed, so
    attribute access cannot tell "removed" from "carried through".
    """
    coordinator = SpeechCoordinator(segmenter=HybridSegmenter(target_size=8))
    payload = coordinator.create_chunk_payload(
        words=["hi"], state_snap={"valence": 0.9, "arousal": 0.9, "fatigue": 0.9}
    )

    gone = {
        "confidence",
        "intensity",
        "speaking_rate",
        "pause_bias",
        "paralinguistic_tags",
    }
    assert gone.isdisjoint(ChatOutput.model_fields)
    assert gone.isdisjoint(payload.model_dump())


@pytest.mark.asyncio
async def test_brain_agent_publishes_the_affect_vector_to_chat_output():
    """The end-to-end Brain→Voice contract, as it is actually consumed."""
    agent = BrainAgent(
        ollama_url="http://127.0.0.1:11434",
        graph_db=MagicMock(),
        memory_store=MagicMock(),
        conversation_store=MagicMock(),
    )

    state_snap = {
        "valence": -0.2,
        "arousal": 0.6,
        "dominance": 0.4,
        "trust": 0.7,
        "attachment": 0.2,
        "emotion": "sad",
        "fatigue": 0.4,
    }
    agent.cognitive_core = MagicMock()
    agent.cognitive_core.state.get_context_snapshot.return_value = state_snap
    agent.last_user_distance = 1.8
    agent.publish = AsyncMock()

    await agent._publish_speech_chunk(
        words=["testing", "continuous", "prosody"], turn_id="turn-5"
    )

    agent.publish.assert_called_once()
    nats_topic, nats_payload = agent.publish.call_args[0]

    assert nats_topic == "chat.output"
    assert isinstance(nats_payload, dict)

    parsed = ChatOutput.model_validate(nats_payload)
    assert parsed.content == "testing continuous prosody"
    assert parsed.done is False
    assert parsed.turn_id == "turn-5"

    # Every field the snapshot supplied, because affect is now the whole
    # contract: anything dropped between here and the wire is a change in how
    # the agent sounds that nothing else would catch.
    assert parsed.affect.valence == -0.2
    assert parsed.affect.arousal == 0.6
    assert parsed.affect.dominance == 0.4
    assert parsed.affect.trust == 0.7
    assert parsed.affect.attachment == 0.2
    assert parsed.affect.emotion == "sad"
    assert parsed.affect.fatigue == 0.4
    # Distance drives the whisper/call-out volume and pitch shift in Rust, so
    # losing it here silently flattens how the agent projects.
    assert parsed.affect.user_distance == 1.8

    # The brain must not attach a second opinion on prosody. The deprecated
    # fields are gone from the contract entirely now, so the check is that the
    # published payload carries no key by those names -- a producer that
    # reintroduced one would be shipping a value the voice agent never asked
    # for and would disagree with.
    published = parsed.model_dump()
    assert {
        "confidence",
        "intensity",
        "speaking_rate",
        "pause_bias",
        "paralinguistic_tags",
    }.isdisjoint(published)
