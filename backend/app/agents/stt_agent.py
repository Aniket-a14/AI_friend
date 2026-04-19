import base64
import logging
import numpy as np
import asyncio
import uuid
from .base import BaseAgent
from ..whisper_stt_service import WhisperSTTService
from ..sensevoice_service import SenseVoiceSTTService
import soxr
import time
from typing import Any
from ..config import Config

logger = logging.getLogger("stt_agent")


class STTAgent(BaseAgent):
    """
    CVS-1.0 Sensory Orchestrator.
    Parallel STT processing:
    - SenseVoice (CPU/Fast): Real-time perception, emotions, and speculative interrupts.
    - Whisper (GPU/Accurate): Final transcription backbone.
    """

    def __init__(self, model_size=Config.STT_MODEL_SIZE, device=Config.STT_DEVICE):
        super().__init__(name="stt_agent")
        # 1. Accuracy Backbone (GPU)
        self.whisper_service = WhisperSTTService(model_size=model_size, device=device)
        
        # 2. Perception Engine (CPU/INT8)
        self.sensevoice_service = SenseVoiceSTTService()
        
        self.target_sample_rate = 16000 # Standard for both engines
        
        # Temporal Intent Stability
        from collections import deque
        self.intent_window = deque(maxlen=5) 
        self.interrupt_intent_threshold = getattr(Config, "INTENT_THRESHOLD", 0.65) # Lowered for speculative speed
        self.stability_required = getattr(Config, "INTENT_STABILITY", 2) # Faster latching
        
        # Audio accumulator for SenseVoice (per-chunk perception)
        self.perception_chunk_size = int(16000 * 0.4) # 400ms chunks
        self.perception_buffer = []

    async def start(self):
        """Standard startup sequence for Micro-Agents"""
        await self.connect()
        
        # Parallel Engine Hydration
        await asyncio.gather(
            self.whisper_service.load_model(),
            asyncio.to_thread(self.sensevoice_service.load_model)
        )
        
        self.whisper_service.start()
        
        await self.subscribe(
            "audio.inbound", self._on_audio_inbound, deliver_policy="new"
        )
        logger.info(f"🎙️ {self.name} Online | Robotic Perception Mesh (Dual-STT) Active.")

    async def _on_audio_inbound(self, data: Any, metadata: dict = None):
        """Process real-time PCM frames through dual-path sensory mesh."""
        try:
            if isinstance(data, bytes):
                audio_bytes = data
                source_sr = metadata.get("sample_rate", 48000) if metadata else 48000
            else:
                audio_bytes = base64.b64decode(data.get("audio", ""))
                source_sr = data.get("sample_rate", 48000)

            if not audio_bytes:
                return

            # Normalization
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if source_sr != self.target_sample_rate:
                audio_np = soxr.resample(audio_np, source_sr, self.target_sample_rate)
            
            pcm_16 = (audio_np * 32767).astype(np.int16).tobytes()

            # --- PATH 1: WHISPER (ACCURACY/BACKBONE) ---
            whisper_res = self.whisper_service.process_frame(pcm_16)
            if whisper_res:
                text, is_final, is_partial = whisper_res
                result_text, confidence = text if isinstance(text, tuple) else (text, 0.9)
                
                if is_final:
                    logger.info(f"User (Whisper): {result_text}")
                    payload = {
                        "text": result_text,
                        "metadata": {
                            "source": "whisper",
                            "confidence": confidence,
                        },
                    }
                    if metadata:
                        payload["latency_metadata"] = metadata
                    await self.publish("chat.input", payload)
                    self.intent_window.clear()

            # --- PATH 2: SENSEVOICE (PERCEPTION/FAST) ---
            self.perception_buffer.append(audio_np)
            current_buffer_len = sum(len(c) for c in self.perception_buffer)
            
            if current_buffer_len >= self.perception_chunk_size:
                perception_audio = np.concatenate(self.perception_buffer)
                self.perception_buffer = [] # Reset for next chunk
                
                # Async perception inference
                perception_data = await asyncio.to_thread(self.sensevoice_service.process_audio, perception_audio)
                
                if perception_data:
                    speculative_intent = self._build_speculative_intent(
                        perception_data["text"],
                        confidence=0.9,
                    )

                    # Publish emotional signals & partials
                    await self.publish("audio.perception", {
                        "text": perception_data["text"],
                        "intent": speculative_intent["name"] if speculative_intent else None,
                        "keywords": speculative_intent["keywords"] if speculative_intent else [],
                        "confidence": speculative_intent["confidence"] if speculative_intent else 0.0,
                        "speculative_intent": speculative_intent,
                        "metadata": perception_data,
                        "timestamp": time.time()
                    })
                    
                    # Speculative Intent Evaluation
                    if speculative_intent:
                        logger.warning(
                            "🛑 [SPECULATIVE INTENT] Perception detected: '%s'. Triggering Early Stop.",
                            perception_data["text"],
                        )
                        await self.publish("audio.stop", {
                            "interrupt": True,
                            "speculative": True,
                            "intent": speculative_intent["name"],
                            "keywords": speculative_intent["keywords"],
                            "confidence": speculative_intent["confidence"],
                            "perception_text": speculative_intent["text"],
                            "utterance_id": speculative_intent["utterance_id"],
                        })

        except Exception as e:
            logger.error(f"STT Dual-Inbound Error: {e}")

    def _build_speculative_intent(self, text: str, confidence: float):
        """
        Build a structured speculative interruption hypothesis from the fast perception layer.
        """
        words = text.lower().strip().split()
        if not words:
            return None

        stop_keywords = ["stop", "wait", "hold", "no", "wrong", "quiet", "alex", "friend"]
        matches = [keyword for keyword in stop_keywords if any(keyword in word for word in words)]
        if not matches:
            return None

        return {
            "name": "SPECULATIVE_STOP",
            "keywords": matches,
            "confidence": confidence,
            "text": text,
            "timestamp": time.time(),
            "utterance_id": str(uuid.uuid4()),
        }


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
