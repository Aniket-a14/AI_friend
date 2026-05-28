import asyncio
import random
import logging
from typing import Dict, Any, AsyncGenerator
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

    async def monitor_stream_and_fill(
        self,
        generator: AsyncGenerator[Dict[str, Any], None],
        turn_id: str,
        state_snap: Dict[str, Any],
        user_distance: float = 1.0,
        is_proactive: bool = False,
        incoming_metadata: Dict[str, Any] = None,
        incoming_latency_metadata: Dict[str, Any] = None,
        flow_start_time: float = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Monitors TTFT. If first token takes > 400ms, sends an early hesitation filler.
        """
        first_token_received = False
        filler_sent = False

        async def send_filler():
            nonlocal filler_sent
            # Wait up to 400ms since the conversational turn started
            import time

            sleep_dur = 0.4
            if flow_start_time:
                elapsed = time.time() - flow_start_time
                sleep_dur = max(0.01, 0.4 - elapsed)

            await asyncio.sleep(sleep_dur)
            if not first_token_received and not is_proactive and self.publish_cb:
                filler_sent = True
                filler = random.choice(FILLERS)
                logger.info(
                    f"⏱️ [ConversationalRuntime] TTFT exceeded 400ms. Dispatching filler: '{filler}'"
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

                payload = ChatOutput(
                    content=f"<hesitate> {filler}<pause=200ms>",
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

    def calculate_pacing_parameters(self, state_snap: Dict[str, Any]) -> Dict[str, Any]:
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
