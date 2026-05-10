"""
Voice Playback Engine — CVS-1.0

Manages the playback loop state machine, binary PCM streaming,
Overlap-Add (OLA) signal continuity, and speculative pause gating.
"""

import asyncio
import logging
import time
from typing import Dict, Any

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)


def silence_pcm(ms: int, sample_rate: int) -> bytes:
    """Generate silent PCM16 data of given duration in milliseconds."""
    bytes_per_ms = int(sample_rate * 2 / 1000)
    return b"\x00" * (ms * bytes_per_ms)


def drain_queue(queue: asyncio.Queue):
    """Empty a queue without blocking."""
    while not queue.empty():
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break


def make_playback_item(
    pcm: bytes, item: Dict[str, Any], segment_start: bool
) -> Dict[str, Any]:
    """Construct a typed playback queue entry."""
    return {
        "pcm": pcm,
        "metadata": item.get("metadata"),
        "segment_start": segment_start,
        "turn_id": item.get("turn_id"),
        "generation": item.get("generation"),
    }


async def run_playback_loop(
    agent,
    playback_queue: asyncio.Queue,
    ingestion_queue: asyncio.Queue,
):
    """
    Worker: Publishes BINARY PCM chunks to 'audio.stream'.

    Handles:
    - Speculative pause gating (waits for resume or final stop)
    - Generation fencing (discards stale audio)
    - OLA fade-in for segment boundaries
    """

    # Import locally to avoid circular dependency
    from .agent import VoicePlaybackState

    while True:
        queue_item_claimed = False
        try:
            playback_item = await playback_queue.get()
            queue_item_claimed = True
            pcm_data = playback_item["pcm"]
            segment_start = playback_item.get("segment_start", False)

            # CVS-1.0: Speculative State Gating
            while agent.state == VoicePlaybackState.SPECULATIVE_PAUSE:
                await asyncio.sleep(0.01)

            if not agent._is_current_item(playback_item):
                agent.speculative_buffer = None
                continue

            await agent._set_playback_state(VoicePlaybackState.PLAYING)

            # --- CVS-1.0 SOLID STATE SIGNAL CONTINUITY (OLA) ---
            if np is not None:
                samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
                fade_len = int(0.015 * agent.sample_rate)  # 15ms window

                if segment_start and len(samples) > fade_len and np.any(samples):
                    fade_in = np.linspace(0.0, 1.0, fade_len)
                    samples[:fade_len] *= fade_in

                pcm_data = np.clip(samples, -32768, 32767).astype(np.int16).tobytes()

            await asyncio.sleep(agent.jitter_buffer)
            await agent.publish("audio.stream", pcm_data)

            agent.last_audio_time = time.time()

            if playback_queue.empty() and ingestion_queue.empty():
                await asyncio.sleep(0.2)
                await agent._set_playback_state(VoicePlaybackState.IDLE)

        except Exception as e:
            logger.error(f"Playback Loop error: {e}")
            await asyncio.sleep(0.1)
        finally:
            if queue_item_claimed:
                playback_queue.task_done()
