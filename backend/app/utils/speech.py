from typing import Any

from ..contracts import ChatOutput, ChatOutputAffect


class SpeechCoordinator:
    """
    Coordinates text-to-speech chunking and attaches the affect vector.

    Prosody is deliberately *not* computed here. The voice agent derives it
    from `affect` via `contracts::vad_to_prosody` (Rust) and has never read the
    values this class used to attach, so the second implementation on this side
    produced output that crossed the wire and went straight into the bin.

    Worse, the two had drifted apart. This computed a *linear* speaking rate
    (`1.0 + 0.20·Ar - 0.10·V - 0.25·F`) while Rust computes a `tanh`-saturated
    one over the same terms, and Rust additionally models pitch, volume, and
    user-distance adaptation that had no counterpart here at all. Both carried
    the same "Continuous formulas from AI Friend Roadmap" comment, so the
    disagreement did not look like one. Anyone reading this file to learn how
    fast the agent talks got an answer that had never been true in production.

    The fix is one implementation, not a better second one: emit the affect
    vector and let the single prosody mapping consume it.
    """

    def __init__(self, segmenter, formation_buffer_s: float = 0.300):
        # Bucket 5 (VOICE_REMEDIATION_PLAN.md): this used to be named
        # `formation_buffer_ms` but held 0.030 -- compared directly against a
        # `time.perf_counter()` delta (seconds) in brain_agent.py, so it was
        # actually a 30ms threshold despite the name. At typical LLM token
        # inter-arrival times, 30ms elapses before a chunk even reaches 3
        # words, so the timer almost always won the race against the
        # semantic segmenter below it, flushing every 3 words regardless of
        # where a clause boundary actually was. Renamed to reflect the real
        # unit and raised to a real clause-formation window (300ms, matching
        # `calculate_pacing_parameters`'s own base_silence) so the segmenter
        # -- not a timer racing against normal streaming latency -- decides
        # where a chunk ends.
        self.segmenter = segmenter
        self.formation_buffer_s = formation_buffer_s

    def create_chunk_payload(
        self,
        words: list[str] | None = None,
        state_snap: dict[str, Any] | None = None,
        turn_id: str | None = None,
        done: bool = False,
        full_response: str | None = None,
        generation_error: str | None = None,
        proactive: bool = False,
        user_distance: float | None = None,
    ) -> ChatOutput:
        text = " ".join(words).strip() if words else None
        state_snap = state_snap or {}

        return ChatOutput(
            content=text,
            done=done,
            turn_id=turn_id,
            full_response=full_response,
            generation_error=generation_error,
            proactive=proactive,
            affect=ChatOutputAffect(
                valence=state_snap.get("valence", state_snap.get("mood", 0.0)),
                arousal=state_snap.get("arousal", state_snap.get("energy", 0.5)),
                dominance=state_snap.get("dominance", 0.5),
                trust=state_snap.get("trust", 0.5),
                attachment=state_snap.get("attachment", 0.1),
                emotion=state_snap.get("emotion", "neutral"),
                fatigue=state_snap.get("fatigue", 0.0),
                user_distance=user_distance,
            ),
        )
