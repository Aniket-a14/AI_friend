"""
Voice Resilience Engine — CVS-1.0

Background loops for maintaining voice pipeline health:
- Resilience loop: Monitors silence gaps and triggers social fillers
- Drift correction: Prevents jitter buffer monotonic drift
"""

import asyncio
import logging
import time

try:
    import numpy as np
except ImportError:
    np = None

from ..config import Config

logger = logging.getLogger(__name__)


async def run_resilience_loop(agent):
    """Monitors perceived silence and triggers fillers or feedback."""
    from .agent import VoicePlaybackState

    min_filler_interval = max(
        0.5, float(getattr(Config, "VOICE_FILLER_MIN_INTERVAL_SECONDS", 1.5))
    )
    max_playback_backlog = max(
        1, int(getattr(Config, "VOICE_FILLER_MAX_PLAYBACK_BACKLOG", 4))
    )

    while True:
        await asyncio.sleep(0.1)
        now = time.time()
        silence_duration = now - agent.last_audio_time

        # Perception-Driven Filler Trigger (>350ms silence while buffering)
        if agent.state in [VoicePlaybackState.BUFFERING] and silence_duration > 0.35:
            if now - agent.last_filler_emit_time < min_filler_interval:
                continue
            if agent.playback_queue.qsize() > max_playback_backlog:
                continue

            pcm_filler = agent.filler_service.get_random_filler()

            if pcm_filler:
                await agent.publish("audio.stream", pcm_filler)
                logger.info("Resilience: Synthesis delay detected. Sent random social filler.")
                agent.last_audio_time = now
                agent.last_filler_emit_time = now
            elif np is not None:
                # Fallback to soft breath if mesh isn't hydrated yet
                duration = 0.4
                t = np.linspace(0, duration, int(agent.sample_rate * duration))
                breath = np.random.normal(0, 0.02, t.shape)
                pcm_fallback = (breath * 32767).astype(np.int16).tobytes()
                await agent.publish("audio.stream", pcm_fallback)
                agent.last_audio_time = now
                agent.last_filler_emit_time = now

        # Segmentation Feedback Publisher
        if agent.override_count > 5:
            await agent.publish("voice.segmentation_feedback", {
                "agent": agent.name,
                "override_rate": agent.override_count,
                "target_chunk_size": 8,
            })
            agent.override_count = 0


async def run_drift_correction_loop(agent):
    """Periodic clock resync to prevent monotonic drift."""
    while True:
        await asyncio.sleep(300)  # Every 5 mins
        logger.info("Adjusting CVS internal clock baseline...")
        if agent.jitter_buffer > 0.010:
            agent.jitter_buffer = max(0.010, agent.jitter_buffer * 0.9)
