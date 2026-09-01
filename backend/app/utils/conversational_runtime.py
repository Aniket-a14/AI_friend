import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any

from ..config import Config
from ..contracts import ChatOutput, ChatOutputAffect, Topics

logger = logging.getLogger("conversational_runtime")

FILLERS = ["hmm", "let's see", "well", "ah", "right"]


class ConversationalRuntime:
    """
    Manages turn pacing, latency filler injection, and turn-taking distributions.
    Translates agent baseline and transient affect vectors into conversational dynamics.
    """

    def __init__(self, publish_cb=None):
        self.publish_cb = publish_cb
        # Bucket 3 (VOICE_REMEDIATION_PLAN.md): wires
        # VOICE_FILLER_MIN_INTERVAL_SECONDS, previously referenced nowhere in
        # the codebase. Instance-scoped (one ConversationalRuntime per
        # brain_agent process) rather than per-turn, since the whole point is
        # to remember the last fire *across* turns.
        self._last_filler_fired_at: float = 0.0

    async def monitor_stream_and_fill(
        self,
        generator: AsyncGenerator[dict[str, Any], None],
        turn_id: str,
        state_snap: dict[str, Any],
        user_distance: float = 1.0,
        is_proactive: bool = False,
        incoming_metadata: dict[str, Any] | None = None,
        incoming_latency_metadata: dict[str, Any] | None = None,
        generation_start_time: float | None = None,
        playback_backlog: int = 0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Monitors TTFT. If first token takes longer than VOICE_FILLER_THRESHOLD,
        sends an early hesitation filler -- unless a previous turn's audio is
        still backed up (VOICE_FILLER_MAX_PLAYBACK_BACKLOG) or a filler fired
        too recently (VOICE_FILLER_MIN_INTERVAL_SECONDS).
        """
        first_token_received = False
        filler_sent = False

        async def send_filler():
            nonlocal filler_sent
            # Wait up to VOICE_FILLER_THRESHOLD since generation started.
            import time

            sleep_dur = Config.VOICE_FILLER_THRESHOLD
            if generation_start_time:
                elapsed = time.time() - generation_start_time
                sleep_dur = max(0.01, Config.VOICE_FILLER_THRESHOLD - elapsed)

            await asyncio.sleep(sleep_dur)
            if first_token_received or is_proactive or not self.publish_cb:
                return

            if playback_backlog >= Config.VOICE_FILLER_MAX_PLAYBACK_BACKLOG:
                logger.debug(
                    "Suppressing filler: playback backlog %s >= max %s.",
                    playback_backlog,
                    Config.VOICE_FILLER_MAX_PLAYBACK_BACKLOG,
                )
                return

            now = time.time()
            since_last_filler = now - self._last_filler_fired_at
            if since_last_filler < Config.VOICE_FILLER_MIN_INTERVAL_SECONDS:
                logger.debug(
                    "Suppressing filler: fired %.2fs ago, min interval is %ss.",
                    since_last_filler,
                    Config.VOICE_FILLER_MIN_INTERVAL_SECONDS,
                )
                return

            filler_sent = True
            self._last_filler_fired_at = now
            filler = random.choice(FILLERS)  # nosec B311 - picking a filler word, not cryptographic
            logger.info(
                f"⏱️ [ConversationalRuntime] TTFT exceeded {Config.VOICE_FILLER_THRESHOLD * 1000:.0f}ms. Dispatching filler: '{filler}'"
            )

            # Setup affect payload
            affect_msg = ChatOutputAffect(
                valence=state_snap.get("valence", 0.0),
                arousal=state_snap.get("arousal", 0.5),
                dominance=state_snap.get("dominance", 0.5),
                trust=state_snap.get("trust", 0.5),
                attachment=state_snap.get("attachment", 0.1),
                emotion=state_snap.get("emotion", "neutral"),
                fatigue=state_snap.get("fatigue", 0.0),
                user_distance=user_distance,
            )

            # Bucket 3: no leading `<hesitate>` -- that token synthesizes its
            # own fixed "Mm..." (see voice-agent's HESITATION_FILLER_TEXT) in
            # a *separate* GPT-SoVITS call from the filler word that follows
            # it, so every turn used to open with two different filler sounds
            # back to back. The filler word alone is a single TemporalPart::Text.
            payload = ChatOutput(
                content=f"{filler}<pause=200ms>",
                done=False,
                turn_id=turn_id,
                affect=affect_msg,
                metadata=incoming_metadata,
                latency_metadata=incoming_latency_metadata,
            )

            await self.publish_cb(Topics.CHAT_OUTPUT, payload.model_dump())

        # Start background timer task for filler
        filler_task = asyncio.create_task(send_filler())

        try:
            async for output in generator:
                if output.get("type") == "content":
                    first_token_received = True
                    if not filler_task.done():
                        filler_task.cancel()
                yield output
        finally:
            if not filler_task.done():
                filler_task.cancel()

    def calculate_pacing_parameters(self, state_snap: dict[str, Any]) -> dict[str, Any]:
        """
        Calculates turn pacing, silence durations, and turn-taking probabilities.
        """
        V = state_snap.get("valence", 0.0)
        Ar = state_snap.get("arousal", 0.5)
        D = state_snap.get("dominance", 0.5)
        F = state_snap.get("fatigue", 0.0)

        # High arousal -> quicker response. High fatigue -> slower response. Low dominance -> hesitant/longer silence.
        base_silence = 300.0  # ms
        arousal_modifier = (1.0 - Ar) * 400.0
        dominance_modifier = (1.0 - D) * 200.0
        fatigue_modifier = F * 500.0

        silence_ms = max(
            50.0,
            base_silence + arousal_modifier + dominance_modifier + fatigue_modifier,
        )

        # Turn-taking probability: high dominance -> higher probability to take turn, low dominance -> lower.
        turn_probability = 0.5 + 0.3 * D - 0.1 * F + 0.2 * V
        turn_probability = max(0.1, min(0.99, turn_probability))

        return {
            "silence_duration_ms": silence_ms,
            "turn_taking_probability": turn_probability,
        }
