"""Voice adapter boundary for compiling cognitive speech intent."""

from .compiler import (
    CompiledVoicePayload,
    ElevenLabsVoiceCompiler,
    GPTSoVITSVoiceCompiler,
    IntentLossRecord,
    VoiceCapability,
    VoiceCompilerProtocol,
    legacy_expression_to_speech_intent,
    speech_intent_to_legacy_modulation,
)

__all__ = [
    "CompiledVoicePayload",
    "ElevenLabsVoiceCompiler",
    "GPTSoVITSVoiceCompiler",
    "IntentLossRecord",
    "VoiceCapability",
    "VoiceCompilerProtocol",
    "legacy_expression_to_speech_intent",
    "speech_intent_to_legacy_modulation",
]
