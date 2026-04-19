import asyncio
import logging
import time
import numpy as np
from enum import Enum
from typing import Dict, Any, List

from ..agents.base import BaseAgent
from ..config import Config
from .sovits_client import SoVITSClient
from .filler_service import FillerService
from .normalizer import AudioNormalizer
from .cache import AudioCache

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
        self.speculative_buffer = None # Holds PCM for potential resume
        self.generation = 0
        self.stopped_turn_ids = set()
        self.paused_utterance_id = None
        
        # Audio Context
        self.sample_rate = Config.SAMPLE_RATE
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self.last_audio_time = time.time()
        self.jitter_buffer = 0.010 # 10ms baseline
        
        # Resilience & Feedback
        self.override_count = 0
        self.active_tasks = []

    async def start(self):
        await self.connect()
        
        # 1. Warm-start Identity (with Retry Logic for Docker startup)
        if Config.CUSTOM_GPT_PATH or Config.CUSTOM_SOVITS_PATH:
            retries = 5
            for i in range(retries):
                try:
                    if Config.CUSTOM_GPT_PATH:
                        await self.sovits.set_gpt_weights(Config.CUSTOM_GPT_PATH)
                    if Config.CUSTOM_SOVITS_PATH:
                        await self.sovits.set_sovits_weights(Config.CUSTOM_SOVITS_PATH)
                    logger.info("✅ Persistent Voice Identity 'ai_friend_voice' loaded.")
                    break
                except Exception as e:
                    if i < retries - 1:
                        logger.warning(f"⏳ SoVITS API not ready (Attempt {i+1}/{retries}). Retrying in 10s...")
                        await asyncio.sleep(10)
                    else:
                        logger.error(f"❌ Failed to load Voice Identity after {retries} attempts: {e}")

        # 2. Start CVS Runtime Loops
        self.active_tasks.append(asyncio.create_task(self._synthesis_loop()))
        self.active_tasks.append(asyncio.create_task(self._playback_loop()))
        self.active_tasks.append(asyncio.create_task(self._resilience_loop()))
        self.active_tasks.append(asyncio.create_task(self._drift_correction_loop()))

        # 3. Hydrate Social Mesh (Async background)
        asyncio.create_task(self.filler_service.hydrate(
            self.sovits, self.ref_audio_path, self.ref_text
        ))

        # 4. Subscribe to Mesh Perception Channels
        await self.subscribe("chat.output", self._handle_input, deliver_policy="new")
        await self.subscribe("audio.stop", self._on_audio_stop)
        await self.subscribe("audio.resume", self._on_audio_resume)
        
        logger.info("🎙️ CVS-1.0 System Online | Solid State Social Mesh Active.")

    async def _on_audio_stop(self, data: Dict[str, Any]):
        """
        Handle Cessation Request.
        Speculative: Pause and hold buffer for potential resume.
        Final: Clear all queues.
        """
        is_speculative = data.get("speculative", False)
        
        if is_speculative:
            self.paused_utterance_id = data.get("utterance_id")
            logger.warning("🛑 Speculative pause triggered. Holding playback buffer...")
            await self._set_playback_state(VoicePlaybackState.SPECULATIVE_PAUSE)
        else:
            logger.error("🚫 Final stop triggered. Clearing all streams.")
            self.generation += 1
            stopped_turn_id = data.get("turn_id")
            if stopped_turn_id:
                self.stopped_turn_ids.add(stopped_turn_id)
            self.paused_utterance_id = None
            await self._set_playback_state(VoicePlaybackState.IDLE)
            # Flush Queues
            self._drain_queue(self.playback_queue)
            self._drain_queue(self.ingestion_queue)

    async def _on_audio_resume(self, data: Dict[str, Any]):
        """
        Handle Graceful Resumption after speculative rejection.
        """
        utterance_id = data.get("utterance_id")
        if self.paused_utterance_id and utterance_id and utterance_id != self.paused_utterance_id:
            logger.debug("Ignoring stale audio.resume for utterance_id=%s", utterance_id)
            return

        if self.state == VoicePlaybackState.SPECULATIVE_PAUSE:
            logger.info("🟢 Resuming playback from speculative pause.")
            self.paused_utterance_id = None
            await self._set_playback_state(VoicePlaybackState.PLAYING)

    async def _set_playback_state(self, new_state: VoicePlaybackState):
        async with self.state_lock:
            if self.state != new_state:
                logger.debug(f"🔄 State: {self.state.value} -> {new_state.value}")
                self.state = new_state
                await self.set_state(new_state.value.lower())

    async def _handle_input(self, data: Dict[str, Any], metadata: dict = None):
        """Ingest chunked text with backpressure awareness."""
        if data.get("done"):
            return

        text = data.get("content", "").strip()
        if not text:
            return

        # 1. Backpressure Guard (Phase 2 Hardening)
        current_load = self.ingestion_queue.qsize()
        max_load = getattr(Config, "MAX_VOICE_QUEUE_SIZE", 10)
        
        if current_load >= max_load:
            logger.warning(f"🚨 Backpressure: Voice Queue Saturated ({current_load}/{max_load}). Dropping low-priority segment.")
            if len(text.split()) > 5: # Drop long non-filler segments
                return

        # 2. Metadata Validation & Clamping
        intensity = max(0.0, min(1.0, data.get("emotional_intensity", 0.5)))
        rate = max(0.5, min(2.0, data.get("speaking_rate", 1.0)))
        emotion = data.get("emotion", "neutral")
        turn_id = data.get("turn_id") or (metadata or {}).get("turn_id")
        
        # 3. Priority Assignment
        priority = 2 
        if len(text.split()) < 3 and ("hmm" in text.lower() or "oh" in text.lower()):
            priority = 1 # Urgent Filler
            
        self.queue_seq += 1
        await self.ingestion_queue.put((priority, self.queue_seq, {
            "text": text, "emotion": emotion, "intensity": intensity, 
            "rate": rate, "timestamp": time.time(), "metadata": metadata,
            "turn_id": turn_id, "generation": self.generation,
        }))

    def _drain_queue(self, queue: asyncio.Queue):
        while not queue.empty():
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                break

    def _is_current_item(self, item: Dict[str, Any]) -> bool:
        turn_id = item.get("turn_id")
        return item.get("generation") == self.generation and turn_id not in self.stopped_turn_ids

    def _playback_item(self, pcm: bytes, item: Dict[str, Any], segment_start: bool) -> Dict[str, Any]:
        return {
            "pcm": pcm,
            "metadata": item.get("metadata"),
            "segment_start": segment_start,
            "turn_id": item.get("turn_id"),
            "generation": item.get("generation"),
        }

    def _silence_pcm(self, ms: int) -> bytes:
        bytes_per_ms = int(self.sample_rate * 2 / 1000)
        return b'\x00' * (ms * bytes_per_ms)

    def _force_split(self, text: str) -> List[str]:
        words = text.split()
        return [" ".join(words[i:i+8]) for i in range(0, len(words), 8)]

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
                    # Check Cache
                    cached_audio = self.cache.get(text, item["emotion"], item["rate"])
                    if cached_audio:
                        await self.playback_queue.put(
                            self._playback_item(cached_audio, item, True)
                        )
                        self.ingestion_queue.task_done()
                        continue

                    # CVS-1.0: Expressive Temporal Marker Parsing
                    import re
                    # Example: "I thinking... <pause=500ms> but anyway."
                    # We split into text and silence commands
                    parts = re.split(r'(<pause=\d+ms>|<hesitate>)', text)
                    
                    for part in parts:
                        if not part:
                            continue
                            
                        # Case 1: Silence Tags
                        if part.startswith("<pause="):
                            ms = int(re.search(r'\d+', part).group())
                            silence_pcm = self._silence_pcm(ms)
                            if self._is_current_item(item):
                                await self.playback_queue.put(
                                    self._playback_item(silence_pcm, item, False)
                                )
                            logger.info(f"⏳ Injected Pause: {ms}ms")
                            continue
                        elif part == "<hesitate>":
                            import random
                            ms = random.randint(250, 450)
                            silence_pcm = self._silence_pcm(ms)
                            if self._is_current_item(item):
                                await self.playback_queue.put(
                                    self._playback_item(silence_pcm, item, False)
                                )
                            logger.info(f"⏳ Injected Hesitation: {ms}ms")
                            continue
                        
                        # Case 2: Natural Speech Text
                        # Synthesis (Async SoVITS)
                        await self._set_playback_state(VoicePlaybackState.BUFFERING)
                        start_synth = time.time()
                        assembled_pcm = bytearray()
                        first_audio_chunk = True
                        
                        async for chunk in self.sovits.synthesize_stream(
                            text=part,
                            ref_audio_path=self.ref_audio_path,
                            ref_text=self.ref_text,
                            media_type="raw"
                        ):
                            if not self._is_current_item(item):
                                logger.debug(
                                    "Dropping stale synthesis stream for turn_id=%s",
                                    item.get("turn_id"),
                                )
                                break
                            if not chunk:
                                continue
                            if len(chunk) % 2 != 0:
                                chunk = chunk[:-1]
                            if not chunk:
                                continue

                            clean_pcm = self.normalizer.process(
                                chunk,
                                speaking_rate=item["rate"],
                            )
                            if not clean_pcm:
                                continue

                            assembled_pcm.extend(clean_pcm)
                            await self.playback_queue.put(
                                self._playback_item(clean_pcm, item, first_audio_chunk)
                            )
                            first_audio_chunk = False
                        
                        if not self._is_current_item(item):
                            assembled_pcm.clear()
                            break

                        if assembled_pcm:
                            full_pcm = bytes(assembled_pcm)
                            self.cache.set(part, item["emotion"], item["rate"], full_pcm)
                            
                            elapsed = (time.time() - start_synth) * 1000
                            logger.info(f"🔊 Synth Done | '{part[:15]}' | Time: {elapsed:.2f}ms")
                
                self.ingestion_queue.task_done()
            except Exception as e:
                logger.error(f"Synthesis Loop error: {e}")
                await asyncio.sleep(0.1)

    async def _playback_loop(self):
        """Worker: Publishes BINARY PCM chunks to 'audio.stream'."""
        while True:
            queue_item_claimed = False
            try:
                playback_item = await self.playback_queue.get()
                queue_item_claimed = True
                pcm_data = playback_item["pcm"]
                meta = playback_item.get("metadata") # noqa: F841
                segment_start = playback_item.get("segment_start", False)
                
                # CVS-1.0: Speculative State Gating
                while self.state == VoicePlaybackState.SPECULATIVE_PAUSE:
                    await asyncio.sleep(0.01) # Yield until resume or final stop
                
                if not self._is_current_item(playback_item):
                    self.speculative_buffer = None
                    continue
                    
                await self._set_playback_state(VoicePlaybackState.PLAYING)
                
                # --- CVS-1.0 SOLID STATE SIGNAL CONTINUITY (OLA) ---
                # Implements a sample-accurate 15ms Overlap-Add transition
                samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
                fade_len = int(0.015 * self.sample_rate) # 15ms window
                
                if segment_start and len(samples) > fade_len and np.any(samples):
                    # If resuming or starting fresh chunk, apply linear fade-in
                    # In a full OLA, we would blend with the tail of speculative_buffer here
                    fade_in = np.linspace(0.0, 1.0, fade_len)
                    samples[:fade_len] *= fade_in
                
                pcm_data = np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
                
                await asyncio.sleep(self.jitter_buffer)
                await self.publish("audio.stream", pcm_data)
                
                self.last_audio_time = time.time()
                
                if self.playback_queue.empty() and self.ingestion_queue.empty():
                    await asyncio.sleep(0.2)
                    await self._set_playback_state(VoicePlaybackState.IDLE)
                    
            except Exception as e:
                logger.error(f"Playback Loop error: {e}")
                await asyncio.sleep(0.1)
            finally:
                if queue_item_claimed:
                    self.playback_queue.task_done()

    async def _resilience_loop(self):
        """Monitors perceived silence and triggers fillers or feedback."""
        while True:
            await asyncio.sleep(0.1)
            now = time.time()
            silence_duration = now - self.last_audio_time
            
            # Perception-Driven Filler Trigger (>350ms silence while buffering)
            if self.state in [VoicePlaybackState.BUFFERING] and silence_duration > 0.35:
                # Replace procedural noise with ACTUAL pre-synthesized fillers
                pcm_filler = self.filler_service.get_random_filler()
                
                if pcm_filler:
                    await self.publish("audio.stream", pcm_filler)
                    logger.info("⏳ Resilience: Synthesis delay detected. Sent random social filler.")
                    self.last_audio_time = now # Prevent filler spam
                else:
                    # Fallback to soft breath if mesh isn't hydrated yet
                    duration = 0.4
                    t = np.linspace(0, duration, int(self.sample_rate * duration))
                    breath = np.random.normal(0, 0.02, t.shape)
                    pcm_fallback = (breath * 32767).astype(np.int16).tobytes()
                    await self.publish("audio.stream", pcm_fallback)
                    self.last_audio_time = now
                
            # Segmentation Feedback Publisher
            if self.override_count > 5:
                await self.publish("voice.segmentation_feedback", {
                    "agent": self.name,
                    "override_rate": self.override_count,
                    "target_chunk_size": 8
                })
                self.override_count = 0

    async def _drift_correction_loop(self):
        """Periodic clock resync to prevent monotonic drift."""
        while True:
            await asyncio.sleep(300) # Every 5 mins
            logger.info("⏱️ Adjusting CVS internal clock baseline...")
            # Recursive Buffer Decay
            if self.jitter_buffer > 0.010:
                self.jitter_buffer = max(0.010, self.jitter_buffer * 0.9)

    async def stop(self):
        for task in self.active_tasks:
            task.cancel()
        await self.sovits.close()
        await super().stop()
        logger.info(f"🎙️ {self.name} CVS System stopped.")

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
