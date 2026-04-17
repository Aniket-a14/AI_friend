import base64
import logging
import numpy as np
import asyncio
from .base import BaseAgent
from ..whisper_stt_service import WhisperSTTService
import soxr
import time
from typing import Any
from ..config import Config

logger = logging.getLogger("stt_agent")


class STTAgent(BaseAgent):
    """
    Consumes raw audio from NATS, performs STT, and publishes text.
    Handles VAD and Interruption triggers based on acoustic energy.
    """

    def __init__(self, model_size=Config.STT_MODEL_SIZE, device=Config.STT_DEVICE):
        super().__init__(name="stt_agent")
        self.stt_service = WhisperSTTService(model_size=model_size, device=device)
        self.target_sample_rate = self.stt_service.sample_rate
        
        # CVS-1.0 Phase 2: Temporal Intent Model
        from collections import deque
        self.intent_window = deque(maxlen=5) # 5 frames (~1sec max)
        self.interrupt_intent_threshold = 0.75
        self.stability_required = 3 # Consecutive high-intent frames
        
        self.intent_patterns = {
            "stop": ["stop", "quiet", "shut", "silence"],
            "wait": ["wait", "hold", "just", "hang"],
            "negation": ["no", "nah", "wrong", "nope"],
            "hey": ["hey", "listen", "alex", "friend"] # Personality triggers
        }

    async def start(self):
        """Standard startup sequence for Micro-Agents"""
        await self.connect()
        await self.stt_service.load_model()
        self.stt_service.start()
        
        await self.subscribe(
            "audio.inbound", self._on_audio_inbound, deliver_policy="new"
        )
        logger.info(f"🎙️ {self.name} online | Temporal Intent Detection (Stability-Gated) Active.")

    async def _on_audio_inbound(self, data: Any, metadata: dict = None):
        """Process real-time PCM frames (supports binary & json fallback)."""
        try:
            if isinstance(data, bytes):
                audio_bytes = data
                source_sr = metadata.get("sample_rate", 48000) if metadata else 48000
            else:
                audio_bytes = base64.b64decode(data.get("audio", ""))
                source_sr = data.get("sample_rate", 48000)

            if not audio_bytes:
                return

            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if source_sr != self.target_sample_rate:
                audio_np = soxr.resample(audio_np, source_sr, self.target_sample_rate)
            
            pcm_16 = (audio_np * 32767).astype(np.int16).tobytes()

            res = self.stt_service.process_frame(pcm_16)
            if not res:
                return

            text, is_final, is_partial = res
            result_data, confidence = text if isinstance(text, tuple) else (text, 0.9)

            # --- CVS-1.0 TEMPORAL INTENT PIPELINE ---
            if is_partial:
                await self._evaluate_temporal_intent(result_data, confidence)
                return

            if is_final:
                logger.info(f"User: {result_data}")
                self.intent_window.clear() # Reset window on turn completion
                await self.publish("chat.input", {"text": result_data, "latency_metadata": metadata})

        except Exception as e:
            logger.error(f"STT Inbound Error: {e}")

    async def _evaluate_temporal_intent(self, text: str, confidence: float):
        """
        Treats interruption as a temporal intent detection problem.
        Stability-Gating: Intent score must be consistent across a rolling window.
        """
        try:
            now = time.time()
            words = text.lower().replace("[", "").replace("]", "").split()
            
            # 1. Intent Classification (Score calculation)
            intent_score = 0.0
            matched_count = 0
            for category, patterns in self.intent_patterns.items():
                matches = [w for w in words if w in patterns]
                if matches:
                    matched_count += len(matches)
            
            # Weighted Intent Score: (Matches * Confidence) / Semantic Ratio
            if words:
                intent_score = (matched_count * confidence) / (len(words) ** 0.5)
            
            # Clamp intent_score
            intent_score = min(1.0, intent_score)
            
            # 2. Add to Rolling Window
            self.intent_window.append((now, intent_score))
            
            # 3. Stability Condition Check
            # Only consider the last 250ms of windows
            recent_frames = [f for f in self.intent_window if now - f[0] < 0.250]
            
            if len(recent_frames) >= self.stability_required:
                avg_intent = sum(f[1] for f in recent_frames) / len(recent_frames)
                
                if avg_intent > self.interrupt_intent_threshold:
                    logger.warning(f"🛑 [TEMPORAL INTENT] Confirmed Stability ({avg_intent:.2f}) over {len(recent_frames)} frames. Triggering Interrupt.")
                    self.intent_window.clear() # Fire once
                    await self.publish("audio.stop", {"interrupt": True, "intent_score": avg_intent})
                    
        except Exception as e:
            logger.error(f"Error in temporal intent detection: {e}")


async def main():
    agent = STTAgent()
    try:
        await agent.start()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
