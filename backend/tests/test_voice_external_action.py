"""Phase 05 tests for provider-neutral voice and external action boundaries."""

from __future__ import annotations

import time
from pathlib import Path

import cognitive_rust
import pytest
from pydantic import ValidationError

from app.cognitive.action_intent import OutcomeRecord
from app.cognitive.external_action import (
    ActionReversibility,
    ActionRiskLevel,
    ExternalActionDispatcher,
    ExternalActionIntent,
)
from app.cognitive.speech_intent import (
    SpeechAffect,
    SpeechDelivery,
    SpeechEpistemics,
    SpeechRelationship,
    SpeechTimelineMarker,
    TimelineMarkerKind,
    build_speech_intent,
)
from app.contracts import AgentVoiceModulation
from app.voice.compiler import (
    ElevenLabsVoiceCompiler,
    GPTSoVITSVoiceCompiler,
    VoiceCompilerProtocol,
    legacy_expression_to_speech_intent,
    speech_intent_to_legacy_modulation,
)


def _full_intent():
    return build_speech_intent(
        turn_id="turn-voice",
        semantic_text="Please wait here.",
        affect=SpeechAffect(optional_label_hint="warm"),
        delivery=SpeechDelivery(
            relative_rate=1.2,
            relative_pitch=1.1,
            relative_energy=1.1,
            style="warm",
        ),
        timeline=[
            SpeechTimelineMarker(
                kind=TimelineMarkerKind.PAUSE,
                text_span="wait",
                strength_or_duration=0.25,
                reason="turn-taking",
            ),
            SpeechTimelineMarker(
                kind=TimelineMarkerKind.EMPHASIS,
                text_span="Please",
                strength_or_duration=0.8,
                reason="politeness",
            ),
            SpeechTimelineMarker(
                kind=TimelineMarkerKind.VOCALIZATION,
                text_span="hmm",
                strength_or_duration=0.4,
                reason="hesitation",
            ),
        ],
    )


def test_speech_intent_validates_all_sections_and_serializes():
    """A complete Section 23 intent retains nested fields when serialized."""
    intent = _full_intent()

    serialized = intent.model_dump(mode="json")

    assert intent.schema_version == "1.0.0"
    assert intent.intent_id.startswith("speech-")
    assert serialized["delivery"]["relative_pitch"] == 1.1
    assert serialized["timeline"][1]["kind"] == "EMPHASIS"


def test_speech_intent_rejects_affect_outside_the_stable_range():
    """Out-of-range affect would let a provider infer invalid brain state."""
    with pytest.raises(ValidationError):
        SpeechAffect(valence=1.1)


@pytest.mark.parametrize("compiler_type", [ElevenLabsVoiceCompiler, GPTSoVITSVoiceCompiler])
def test_voice_compilers_conform_to_protocol_and_preserve_semantic_text(compiler_type):
    """Every compiler returns the declared payload/telemetry pair for one intent."""
    compiler = compiler_type()
    assert isinstance(compiler, VoiceCompilerProtocol)

    payload, loss = compiler.compile(_full_intent())

    assert payload.compiler_id == compiler.compiler_id
    assert payload.audio_text == "Please wait here."
    assert loss.compiler_id == compiler.compiler_id
    assert 0.0 <= loss.fidelity_score <= 1.0


def test_elevenlabs_loss_telemetry_names_every_unsupported_dimension():
    """Cloud rendering must disclose lost pitch, emphasis, and vocalization cues."""
    _, loss = ElevenLabsVoiceCompiler().compile(_full_intent())

    assert set(loss.dropped_dimensions) == {
        "delivery.relative_pitch",
        "timeline.emphasis",
        "timeline.vocalization",
    }
    assert loss.fidelity_score < 1.0


def test_elevenlabs_logs_style_substitution_instead_of_silently_normalizing():
    """An unsupported vendor style must be visible to intent-loss consumers."""
    intent = build_speech_intent(
        turn_id="turn-style",
        semantic_text="Hello.",
        delivery=SpeechDelivery(style="ceremonial"),
    )

    payload, loss = ElevenLabsVoiceCompiler().compile(intent)

    assert payload.synthesis_parameters["style"] == "neutral"
    assert loss.substituted_dimensions["delivery.style"] == {
        "requested": "ceremonial",
        "applied": "neutral",
    }


def test_gpt_sovits_uses_local_pitch_rate_and_ssml_but_logs_cloud_style_loss():
    """The local compiler preserves pitch/rate through tags and reports style loss."""
    payload, loss = GPTSoVITSVoiceCompiler().compile(_full_intent())

    assert payload.synthesis_parameters["pitch"] == 1.1
    assert payload.synthesis_parameters["rate"] == 1.2
    assert "<prosody" in (payload.ssml_or_tags or "")
    assert "<emphasis" in (payload.ssml_or_tags or "")
    assert loss.dropped_dimensions == ["delivery.style", "affect.optional_label_hint"]


def test_compilers_report_unrenderable_social_and_affect_dimensions():
    """Loss telemetry must expose intent cues that a provider cannot synthesize."""
    intent = build_speech_intent(
        turn_id="turn-loss",
        semantic_text="I may be mistaken.",
        affect=SpeechAffect(valence=-0.4, arousal=0.5, dominance=-0.2, intensity=0.8),
        epistemics=SpeechEpistemics(confidence=0.6, uncertainty=0.4, hedge_required=True),
        relationship=SpeechRelationship(stance="CAUTIOUS", familiarity=0.8, register="FORMAL"),
    )
    social_dimensions = {
        "epistemics.confidence",
        "epistemics.uncertainty",
        "epistemics.hedge_required",
        "relationship.stance",
        "relationship.familiarity",
        "relationship.register",
    }

    _, elevenlabs_loss = ElevenLabsVoiceCompiler().compile(intent)
    _, gpt_sovits_loss = GPTSoVITSVoiceCompiler().compile(intent)

    assert social_dimensions <= set(elevenlabs_loss.dropped_dimensions)
    assert social_dimensions <= set(gpt_sovits_loss.dropped_dimensions)
    assert {
        "affect.valence",
        "affect.arousal",
        "affect.dominance",
        "affect.intensity",
    } <= set(gpt_sovits_loss.dropped_dimensions)
    assert elevenlabs_loss.fidelity_score < 1.0
    assert gpt_sovits_loss.fidelity_score < elevenlabs_loss.fidelity_score


def test_gpt_sovits_emphasis_tags_do_not_nest_for_duplicate_or_overlapping_markers():
    """Repeated spans must not replace text inside a tag emitted by an earlier marker."""
    intent = build_speech_intent(
        turn_id="turn-emphasis",
        semantic_text="Please wait, then please wait.",
        timeline=[
            SpeechTimelineMarker(
                kind=TimelineMarkerKind.EMPHASIS,
                text_span="Please wait",
                strength_or_duration=0.8,
            ),
            SpeechTimelineMarker(
                kind=TimelineMarkerKind.EMPHASIS,
                text_span="wait",
                strength_or_duration=0.6,
            ),
            SpeechTimelineMarker(
                kind=TimelineMarkerKind.EMPHASIS,
                text_span="Please wait",
                strength_or_duration=0.8,
            ),
        ],
    )

    payload, _ = GPTSoVITSVoiceCompiler().compile(intent)

    assert (payload.ssml_or_tags or "").count("<emphasis") == 2
    assert "<emphasis level=\"0.8\">Please wait</emphasis>" in (payload.ssml_or_tags or "")
    assert "<emphasis level=\"0.6\"><emphasis" not in (payload.ssml_or_tags or "")


def test_legacy_modulation_migrates_bidirectionally_without_losing_prosody():
    """Legacy AgentVoiceModulation frames map into and back out of SpeechIntent."""
    legacy = {
        "turn_id": "turn-legacy",
        "semantic_text": "Legacy words.",
        "affect_label": "calm",
        "breath": 0.3,
        "style": "natural",
        "trajectory": [
            {"time_offset_ms": 0, "rate": 1.3, "pitch": 0.9, "volume": 1.1}
        ],
    }

    intent = legacy_expression_to_speech_intent(legacy)
    restored = speech_intent_to_legacy_modulation(intent)
    modulation = AgentVoiceModulation.model_validate(restored)

    assert intent.turn_id == "turn-legacy"
    assert intent.delivery.relative_rate == 1.3
    assert intent.delivery.relative_pitch == 0.9
    assert modulation.trajectory[0].volume == 1.1
    assert restored["affect_label"] == "calm"


def test_legacy_migration_uses_real_apra_steady_state_volume():
    """Rust trajectories fade in at 0.10, which is invalid SpeechDelivery energy."""
    trajectory = cognitive_rust.generate_apra_trajectory(0.2, 0.4, 0.5, 0.1, 0.1, 0.1, 0.1)
    legacy = {
        "turn_id": "turn-apra",
        "semantic_text": "Trajectory words.",
        "trajectory": [
            {"time_offset_ms": t_ms, "rate": rate, "pitch": pitch, "volume": volume}
            for t_ms, rate, pitch, volume in trajectory
        ],
    }

    intent = legacy_expression_to_speech_intent(legacy)

    assert trajectory[0][3] == 0.1
    assert 0.5 <= intent.delivery.relative_energy <= 2.0
    assert intent.delivery.relative_energy != trajectory[0][3]


@pytest.mark.parametrize(
    "risk,reversibility",
    [
        (ActionRiskLevel.HIGH, ActionReversibility.REVERSIBLE),
        (ActionRiskLevel.CRITICAL, ActionReversibility.REVERSIBLE),
        (ActionRiskLevel.LOW, ActionReversibility.IRREVERSIBLE),
    ],
)
def test_external_action_blocks_sensitive_requests_without_authorization(
    risk,
    reversibility,
):
    """No high-risk or irreversible action reaches an executor without consent."""
    dispatcher = ExternalActionDispatcher()
    intent = ExternalActionIntent(
        action_id="act-sensitive",
        turn_id="turn-action",
        tool_or_actuator="door.unlock",
        risk_level=risk,
        reversibility=reversibility,
    )

    valid, reason = dispatcher.validate_action(intent)
    result = dispatcher.dispatch(intent)

    assert not valid
    assert reason == "authorization_token is required for this action"
    assert result["status"] == "CANCELLED"


def test_external_action_authorization_allows_registered_executor_and_terminal_outcome():
    """Authorized execution is represented by a terminal, correlated OutcomeRecord."""
    def unlock(_: ExternalActionIntent) -> dict[str, object]:
        return {"status": "COMPLETED", "message": "Door unlocked."}

    dispatcher = ExternalActionDispatcher({"door.unlock": unlock})
    intent = ExternalActionIntent(
        action_id="act-unlock",
        turn_id="turn-action",
        tool_or_actuator="door.unlock",
        risk_level=ActionRiskLevel.HIGH,
        authorization_token="approved-by-user",
    )

    result = dispatcher.dispatch(intent)
    outcome = dispatcher.create_action_outcome(intent, result, elapsed_ms=12.5)

    assert result["executed"] is True
    assert isinstance(outcome, OutcomeRecord)
    assert outcome.intent_id == "act-unlock"
    assert outcome.turn_id == "turn-action"
    assert outcome.status == "COMPLETED"
    assert outcome.elapsed_ms == 12.5


def test_external_action_low_reversible_request_needs_no_authorization():
    """Low-risk reversible actions must retain the safe simulation escape hatch."""
    dispatcher = ExternalActionDispatcher()
    intent = ExternalActionIntent(
        action_id="act-low",
        turn_id="turn-action",
        tool_or_actuator="lamp.dim",
    )

    result = dispatcher.dispatch(intent)

    assert result["status"] == "COMPLETED"
    assert result["simulated"] is True


def test_external_action_simulation_is_explicit_in_terminal_outcome():
    """Unregistered adapters must never look like a real successful action."""
    dispatcher = ExternalActionDispatcher()
    intent = ExternalActionIntent(
        action_id="act-simulated",
        turn_id="turn-action",
        tool_or_actuator="music.play",
    )

    result = dispatcher.dispatch(intent)
    outcome = dispatcher.create_action_outcome(intent, result, elapsed_ms=1.0)

    assert result["simulated"] is True
    assert result["status"] == "COMPLETED"
    assert result["message"] == "simulated: no adapter registered for music.play"
    assert outcome.actual_delivered_text == result["message"]


def test_external_action_executor_exception_becomes_failed_result():
    """Adapter failures must be terminal results instead of escaping cognition."""
    def broken_executor(_: ExternalActionIntent) -> dict[str, object]:
        raise RuntimeError("adapter unavailable")

    dispatcher = ExternalActionDispatcher({"lamp.dim": broken_executor})
    intent = ExternalActionIntent(
        action_id="act-broken",
        turn_id="turn-action",
        tool_or_actuator="lamp.dim",
    )

    result = dispatcher.dispatch(intent)

    assert result["status"] == "FAILED"
    assert result["executed"] is False
    assert result["error"] == "adapter unavailable"


def test_external_action_timeout_becomes_failed_result():
    """An adapter that exceeds timeout_s must fail before it can block a turn."""
    def slow_executor(_: ExternalActionIntent) -> dict[str, object]:
        time.sleep(0.1)
        return {"status": "COMPLETED"}

    dispatcher = ExternalActionDispatcher({"lamp.dim": slow_executor})
    intent = ExternalActionIntent(
        action_id="act-timeout",
        turn_id="turn-action",
        tool_or_actuator="lamp.dim",
        timeout_s=0.01,
    )

    result = dispatcher.dispatch(intent)

    assert result == {
        "action_id": "act-timeout",
        "executed": False,
        "status": "FAILED",
        "error": "Action timed out after 0.01s",
    }


def test_phase_package_files_are_strict_7_bit_ascii():
    """Non-ASCII source would violate the stable wire and repository contract."""
    backend_root = Path(__file__).resolve().parents[1]
    package_files = [
        backend_root / "app/cognitive/speech_intent.py",
        backend_root / "app/cognitive/external_action.py",
        backend_root / "app/voice/__init__.py",
        backend_root / "app/voice/compiler.py",
        Path(__file__),
    ]

    for path in package_files:
        assert path.read_bytes().isascii(), f"{path} is not pure 7-bit ASCII"
