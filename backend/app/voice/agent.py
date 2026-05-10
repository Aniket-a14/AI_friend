import asyncio
import logging
import random
import re
import time
from enum import Enum
from typing import Dict, Any, List

try:
    import numpy as np
except ImportError:
    np = None

from ..agents.base import BaseAgent
from ..config import Config
from .sovits_client import SoVITSClient
from .filler_service import FillerService
from .normalizer import AudioNormalizer
from .cache import AudioCache
from .prosody import vad_to_prosody, has_temporal_marker, force_split
from .playback import silence_pcm, drain_queue, make_playback_item, run_playback_loop
from .resilience import run_resilience_loop, run_drift_correction_loop
from ..contracts import ChatOutput, AudioStop, AudioResume

logger = logging.getLogger(__name__)

class VoicePlaybackState(Enum):
    IDLE = "IDLE"
    BUFFERING = "BUFFERING"
    PLAYING = "PLAYING"
    SPECULATIVE_PAUSE = "SPECULATIVE_PAUSE"
    INSERT_WINDOW = "INSERT_WINDOW"
    TRANSITION = "TRANSITION"
    COOLDOWN = "COOLDOWN"


class VoiceAgent(BaseAgent):
    """
    The CVS-1.0 Cognitive Voice System Agent.
    A state-machine driven, persistent signal runtime.

    Delegates to extracted sub-modules:
    - prosody.py:     VAD → speech parameter mapping
    - playback.py:    PCM streaming, OLA continuity, queue management
    - resilience.py:  Filler injection, drift correction
    """
    def __init__(
        self,
        sovits_url: str = Config.SOVITS_URL,
        ref_audio_path: str = "output/sample_en_gold.wav",
        ref_text: str = "At the end of the exam, the program shows the performance summary.",
    ):
        super().__init__(name="voice_agent")
        self.sovits = SoVITSClient(base_url=sovits_url)
        self.normalizer = AudioNormalizer()
        self.cache = AudioCache()
        self.filler_service = FillerService()

        # State & Scheduling
        self.state = VoicePlaybackState.IDLE
        self.state_lock = asyncio.Lock()
        self.ingestion_queue = asyncio.PriorityQueue()
        self.playback_queue = asyncio.Queue()
        self.queue_seq = 0
        self.speculative_buffer = None  # Holds PCM for potential resume
        self.generation = 0
        self.stopped_turn_ids = set()
        self.paused_utterance_id = None

        # Audio Context
        self.sample_rate = Config.SAMPLE_RATE
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self.last_audio_time = time.time()
        self.last_filler_emit_time = 0.0
        self.jitter_buffer = 0.010  # 10ms baseline

        # Resilience & Feedback
        self.override_count = 0
        self.active_tasks = []

    async def start(self):
        await self.connect()
        identity_ready = await self._warm_start_identity()

        if identity_ready:
            await self.publish("voice.warm", {
                "agent": self.name,
                "status": "ready",
                "identity": "fine_tuned",
                "timestamp": time.time(),
            })
        else:
            await self.publish("voice.warm", {
                "agent": self.name,
                "status": "degraded_no_weights",
                "identity": "fallback",
                "expected_gpt_path": Config.CUSTOM_GPT_PATH,
                "expected_sovits_path": Config.CUSTOM_SOVITS_PATH,
                "timestamp": time.time(),
            })

        # 2. Start CVS Runtime Loops (delegated to extracted modules)
        self.active_tasks.append(asyncio.create_task(self._synthesis_loop()))
        self.active_tasks.append(asyncio.create_task(
            run_playback_loop(self, self.playback_queue, self.ingestion_queue)
        ))
        self.active_tasks.append(asyncio.create_task(run_resilience_loop(self)))
        self.active_tasks.append(asyncio.create_task(run_drift_correction_loop(self)))

        # 3. Hydrate Social Mesh (optional async background)
        if Config.VOICE_FILLER_HYDRATE_ON_STARTUP:
            asyncio.create_task(self.filler_service.hydrate(
                self.sovits, self.ref_audio_path, self.ref_text
            ))
        else:
            logger.info("Skipping filler hydration (VOICE_FILLER_HYDRATE_ON_STARTUP=false).")

        # 4. Subscribe to Mesh Perception Channels
        await self.subscribe("chat.output", self._handle_input, deliver_policy="new")
        await self.subscribe("audio.stop", self._on_audio_stop, deliver_policy="new", durable="voice_agent_audio_stop")
        await self.subscribe("audio.resume", self._on_audio_resume, deliver_policy="new", durable="voice_agent_audio_resume")

        logger.info("CVS-1.0 System Online | Solid State Social Mesh Active.")

    async def _warm_start_identity(self) -> bool:
        """Attempt to load configured voice identity in warning mode (non-fatal)."""
        if not (Config.CUSTOM_GPT_PATH or Config.CUSTOM_SOVITS_PATH):
            logger.warning("No custom voice weight paths configured; running in fallback mode.")
            await self.set_state("warning_no_weights")
            return False

        retries = max(1, int(getattr(Config, "VOICE_WEIGHT_LOAD_RETRIES", 3)))
        gpt_required = bool(Config.CUSTOM_GPT_PATH)
        sovits_required = bool(Config.CUSTOM_SOVITS_PATH)

        for i in range(retries):
            gpt_ok = True
            sovits_ok = True

            if gpt_required:
                gpt_ok = await self.sovits.set_gpt_weights(Config.CUSTOM_GPT_PATH)
            if sovits_required:
                sovits_ok = await self.sovits.set_sovits_weights(Config.CUSTOM_SOVITS_PATH)

            if gpt_ok and sovits_ok:
                logger.info("Persistent Voice Identity 'ai_friend_voice' loaded.")
                return True

            if i < retries - 1:
                logger.warning(
                    "Voice weights not ready (attempt %s/%s). Retrying in 5s...",
                    i + 1,
                    retries,
                )
                await asyncio.sleep(5)

        logger.warning(
            "Voice identity unavailable. Expected GPT=%s SoVITS=%s",
            Config.CUSTOM_GPT_PATH,
            Config.CUSTOM_SOVITS_PATH,
        )
        logger.warning("Agent fallback: Entering WARNING mode. Synthesis may fail or use defaults.")
        await self.set_state("warning_no_weights")
        return False

    # ─── Mesh Event Handlers ───────────────────────────────────

    async def _on_audio_stop(self, data: Dict[str, Any]):
        """
        Handle Cessation Request.
        Speculative: Pause and hold buffer for potential resume.
        Final: Clear all queues.
        """
        try:
            msg = AudioStop.model_validate(data)
            is_speculative = msg.speculative
            turn_id = msg.turn_id
            utterance_id = msg.utterance_id
        except Exception:
            is_speculative = data.get("speculative", False)
            turn_id = data.get("turn_id")
            utterance_id = data.get("utterance_id")

        if is_speculative:
            self.paused_utterance_id = utterance_id
            logger.warning("Speculative pause triggered. Holding playback buffer...")
            await self._set_playback_state(VoicePlaybackState.SPECULATIVE_PAUSE)
        else:
            logger.error("Final stop triggered. Clearing all streams.")
            self.generation += 1
            if turn_id:
                self.stopped_turn_ids.add(turn_id)
            self.paused_utterance_id = None
            await self._set_playback_state(VoicePlaybackState.IDLE)
            drain_queue(self.playback_queue)
            drain_queue(self.ingestion_queue)

    async def _on_audio_resume(self, data: Dict[str, Any]):
        """Handle Graceful Resumption after speculative rejection."""
        try:
            msg = AudioResume.model_validate(data)
            utterance_id = msg.utterance_id
        except Exception:
            utterance_id = data.get("utterance_id")

        if self.paused_utterance_id and utterance_id and utterance_id != self.paused_utterance_id:
            logger.debug("Ignoring stale audio.resume for utterance_id=%s", utterance_id)
            return

        if self.state == VoicePlaybackState.SPECULATIVE_PAUSE:
            logger.info("Resuming playback from speculative pause.")
            self.paused_utterance_id = None
            await self._set_playback_state(VoicePlaybackState.PLAYING)

    # ─── State Machine ─────────────────────────────────────────

    async def _set_playback_state(self, new_state: VoicePlaybackState):
        async with self.state_lock:
            if self.state != new_state:
                logger.debug(f"State: {self.state.value} -> {new_state.value}")
                self.state = new_state
                await self.set_state(new_state.value.lower())

    # ─── Input Handling & Phrase Segmentation ──────────────────

    async def _handle_input(self, data: Dict[str, Any], metadata: dict = None):
        """Ingest chunked text with backpressure awareness and atomic phrasing."""
        try:
            msg = ChatOutput.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to validate ChatOutput: {e}")
            return

        if msg.done:
            buffered_text = getattr(self, "_phrase_buffer", "").strip()
            self._phrase_buffer = ""
            if buffered_text:
                affect_dict = msg.affect.model_dump() if msg.affect else {}
                prosody = vad_to_prosody(affect_dict)
                await self._queue_voice_segment(
                    buffered_text,
                    data=data,
                    metadata=metadata,
                    prosody=prosody,
                    intensity=msg.intensity or prosody["volume"],
                    rate=msg.speaking_rate or prosody["rate"],
                )
            return

        raw_text = msg.content.strip() if msg.content else ""
        if not raw_text:
            return

        affect_dict = msg.affect.model_dump() if msg.affect else {}
        prosody = vad_to_prosody(affect_dict)
        intensity = msg.intensity or prosody["volume"]
        rate = msg.speaking_rate or prosody["rate"]

        # Atomic Phrase Splitting
        if not hasattr(self, "_phrase_buffer"):
            self._phrase_buffer = ""

        self._phrase_buffer += " " + raw_text
        text_to_process = self._phrase_buffer.strip()

        words = text_to_process.split()
        if len(words) < 3 and not any(p in text_to_process for p in [".", "?", "!", ","]):
            return

        self._phrase_buffer = ""
        text = text_to_process

        # 1. Backpressure Guard
        current_load = self.ingestion_queue.qsize()
        max_load = getattr(Config, "MAX_VOICE_QUEUE_SIZE", 10)

        if current_load >= max_load:
            logger.warning(f"Backpressure: Voice Queue Saturated ({current_load}/{max_load}). Dropping low-priority segment.")
            if len(words) > 5:
                return

        # 2. Priority Assignment
        priority = 2
        if len(words) < 3 and ("hmm" in text.lower() or "got it" in text.lower()):
            priority = 1

        await self._queue_voice_segment(
            text,
            data=data,
            metadata=metadata,
            prosody=prosody,
            intensity=intensity,
            rate=rate,
            priority=priority,
        )

    async def _queue_voice_segment(
        self,
        text: str,
        *,
        data: Dict[str, Any],
        metadata: dict = None,
        prosody: Dict[str, float],
        intensity: float,
        rate: float,
        priority: int = 2,
    ):
        self.queue_seq += 1
        await self.ingestion_queue.put((priority, self.queue_seq, {
            "text": text,
            "emotion": "neutral",
            "intensity": intensity,
            "rate": rate,
            "prosody": prosody,
            "timestamp": time.time(),
            "metadata": metadata,
            "turn_id": data.get("turn_id") or (metadata or {}).get("turn_id"),
            "generation": self.generation,
        }))

    # ─── Generation Fencing ────────────────────────────────────

    def _is_current_item(self, item: Dict[str, Any]) -> bool:
        turn_id = item.get("turn_id")
        return item.get("generation") == self.generation and turn_id not in self.stopped_turn_ids

    # ─── Convenience Wrappers (delegate to extracted modules) ──

    def _silence_pcm(self, ms: int) -> bytes:
        return silence_pcm(ms, self.sample_rate)

    def _vad_to_prosody(self, affect: Dict[str, float]) -> Dict[str, float]:
        return vad_to_prosody(affect)

    # ─── Synthesis Loop ────────────────────────────────────────

    async def _synthesis_loop(self):
        """Worker: Pops from ingestion queue with Concurrency Guard (Semaphore)."""
        limit = getattr(Config, "VOICE_SYNTH_CONCURRENCY", 1)
        sem = asyncio.Semaphore(limit)

        while True:
            try:
                priority, _seq, item = await self.ingestion_queue.get()
                text = item["text"]
                if not self._is_current_item(item):
                    self.ingestion_queue.task_done()
                    continue

                async with sem:
                    prosody = item.get("prosody", {
                        "rate": 1.0, "pitch": 1.0, "volume": 1.0
                    })
                    cached_audio = self.cache.get(
                        text, prosody["rate"], prosody["pitch"]
                    )

                    if cached_audio:
                        await self.playback_queue.put(
                            make_playback_item(cached_audio, item, True)
                        )
                        self.ingestion_queue.task_done()
                        continue

                    try:
                        start_time = time.time()
                        await self._set_playback_state(VoicePlaybackState.BUFFERING)
                        audio_chunks = await self._enqueue_temporal_audio(
                            text, item, prosody
                        )

                        if audio_chunks and not has_temporal_marker(text):
                            self.cache.set(
                                text,
                                prosody["rate"],
                                prosody["pitch"],
                                b"".join(audio_chunks),
                            )
                        if audio_chunks:
                            logger.info(
                                "Synth Done | '%s...' | Time: %.2fms",
                                text[:15],
                                (time.time() - start_time) * 1000,
                            )

                    except Exception as e:
                        logger.error(f"Synthesis failed for segment '{text}': {e}")
                    finally:
                        self.ingestion_queue.task_done()
            except Exception as e:
                logger.error(f"Synthesis Loop critical error: {e}")
                await asyncio.sleep(0.1)

    async def _enqueue_temporal_audio(
        self,
        text: str,
        item: Dict[str, Any],
        prosody: Dict[str, float],
    ) -> List[bytes]:
        """Synthesize text parts and enqueue timing-marker silences in order."""
        chunks: List[bytes] = []
        segment_start = True
        parts = re.split(r"(<pause=\d+ms>|<hesitate>)", text)

        for part in parts:
            if not part:
                continue

            if part.startswith("<pause="):
                ms_match = re.search(r"\d+", part)
                if ms_match and self._is_current_item(item):
                    await self.playback_queue.put(
                        make_playback_item(
                            self._silence_pcm(int(ms_match.group())),
                            item,
                            False,
                        )
                    )
                continue

            if part == "<hesitate>":
                if self._is_current_item(item):
                    await self.playback_queue.put(
                        make_playback_item(
                            self._silence_pcm(random.randint(250, 450)),
                            item,
                            False,
                        )
                    )
                continue

            text_part = part.strip()
            if not text_part or not self._is_current_item(item):
                continue

            async for chunk in self.sovits.synthesize_stream(
                text=text_part,
                ref_audio_path=self.ref_audio_path,
                ref_text=self.ref_text,
                language=Config.TTS_LANGUAGE,
                speed=prosody["rate"],
                pitch=prosody["pitch"],
                volume=prosody["volume"],
            ):
                if not chunk or not self._is_current_item(item):
                    continue
                chunks.append(chunk)
                await self.playback_queue.put(
                    make_playback_item(chunk, item, segment_start)
                )
                segment_start = False

        return chunks

    # ─── Lifecycle ─────────────────────────────────────────────

    async def stop(self):
        for task in self.active_tasks:
            task.cancel()
        await self.sovits.close()
        await super().stop()
        logger.info(f"{self.name} CVS System stopped.")

async def main():
    agent = VoiceAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
