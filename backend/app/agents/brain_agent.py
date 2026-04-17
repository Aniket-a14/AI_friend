import asyncio
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, List
import re

from .base import BaseAgent
from ..llm.ollama_client import OllamaClient
from ..knowledge.graph_db import GraphDB
from ..memory_store import MemoryStore
from ..conversation_history_store import ConversationHistoryStore
from ..config import Config
from ..cognitive import CognitiveService

logger = logging.getLogger(__name__)

class HybridSegmenter:
    """
    CVS-1.0 Semantic Chunking Engine.
    Uses scoring-based heuristics to identify optimal speech boundaries.
    """
    def __init__(self, target_size: int = 8):
        self.target_size = target_size
        self.conjunctions = {"and", "but", "so", "because", "although", "while"}
        
    def score_split_point(self, word: str, chunk_len: int) -> float:
        score = 0.0
        # Punctuation (Primary)
        if any(p in word for p in [".", "?", "!", ";"]):
            score += 1.0
        elif "," in word:
            score += 0.6
        
        # Conjunctions (Secondary)
        if word.lower().strip() in self.conjunctions:
            score += 0.4
            
        # Proximity to target size
        size_factor = abs(chunk_len - self.target_size) / self.target_size
        score -= size_factor * 0.2
        
        return score

class BrainAgent(BaseAgent):
    """
    The Brain Agent (CVS-1.0 Edition).
    Orchestrator of Identity and Temporal Cognitive Flow.
    """
    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB = None,
        memory_store: MemoryStore = None,
        conversation_store: ConversationHistoryStore = None,
    ):
        super().__init__(name="brain_agent")
        self.ollama = OllamaClient(base_url=ollama_url)
        self.graph_db = graph_db
        self.memory_store = memory_store
        self.conversation_store = conversation_store
        
        # Initialize the Functional Core
        self.cognitive_core = CognitiveService(
            llm_service=self.ollama,
            memory_store=memory_store,
            graph_db=graph_db
        )

        self.last_interaction_time = datetime.now()
        self.last_visual_context = "No visual data available."
        
        # CVS-1.0 Segmentation Config
        self.segmenter = HybridSegmenter(target_size=8)
        self.formation_buffer_ms = 0.030 # 30ms

    async def start(self):
        await self.cognitive_core.initialize()

        if self.conversation_store:
            await self.conversation_store.initialize()
            await self.conversation_store.start_session()

        await self.connect()

        # Subscribe to I/O streams
        await self.subscribe("chat.input", self._on_chat_input)
        await self.subscribe("vision.frames", self._on_vision_frame, deliver_policy="last")
        await self.subscribe("voice.segmentation_feedback", self._on_voice_feedback)
        
        # Start Autonomy Loop
        asyncio.create_task(self._autonomy_loop())
        logger.info(f"🧠 {self.name} Online | CVS-1.0 Cognitive Mesh Active.")

    async def _on_voice_feedback(self, data: Dict[str, Any]):
        """Adaptive Tuning Loop (CVS-1.0 closed loop)."""
        target = data.get("target_chunk_size", 8)
        if target != self.segmenter.target_size:
            logger.info(f"📈 Tuning Segmentation Strategy | Target Size: {target}")
            self.segmenter.target_size = target

    async def _on_vision_frame(self, data: Dict[str, Any]):
        source = data.get("source", "unknown")
        self.last_visual_context = f"I am seeing the user's {source}."

    async def _on_chat_input(self, message: Dict[str, Any]):
        now = datetime.now()
        self.last_interaction_time = now
        
        user_text = message.get("text", "")
        if not user_text:
            return

        raw_event = {
            "id": str(uuid.uuid4()),
            "type": "USER_MESSAGE",
            "content": user_text,
            "metadata": {"visuals": self.last_visual_context}
        }

        if self.conversation_store:
            asyncio.create_task(self.conversation_store.log_message("user", user_text))

        await self.set_state("thinking")
        
        full_response = ""
        current_chunk_words = []
        
        try:
            async for output in self.cognitive_core.process_event(raw_event):
                if output["type"] == "content":
                    await self.set_state("speaking")
                    chunk_text = output["data"]
                    full_response += chunk_text
                    
                    # Tokenize by whitespace
                    words = chunk_text.split()
                    for word in words:
                        current_chunk_words.append(word)
                        
                        # 1. Formation Buffer (Brief wait for better splitting)
                        await asyncio.sleep(self.formation_buffer_ms)
                        
                        # 2. Heuristic Scoring
                        score = self.segmenter.score_split_point(word, len(current_chunk_words))
                        
                        # 3. Decision (Safe Split)
                        if score > 0.7 or len(current_chunk_words) > 12:
                            await self._publish_speech_chunk(current_chunk_words)
                            current_chunk_words = []
                
                elif output["type"] == "done":
                    # Emit residue
                    if current_chunk_words:
                        await self._publish_speech_chunk(current_chunk_words)
                    
                    state_snap = self.cognitive_core.state.get_context_snapshot()
                    await self.publish("chat.output", {
                        "content": "", 
                        "done": True, 
                        "full_response": full_response,
                        "emotion": state_snap.get("emotion", "neutral")
                    })

        except Exception as e:
            logger.error(f"Cognitive Loop error: {e}")
            await self.publish("chat.output", {"content": "I encountered an internal error.", "done": True})

        if self.conversation_store and full_response:
            asyncio.create_task(self.conversation_store.log_message("assistant", full_response))

        await self.set_state("idle")

    async def _publish_speech_chunk(self, words: List[str]):
        """Publishes a semantically coherent chunk with CVS-1.0 metadata."""
        text = " ".join(words).strip()
        if not text:
            return
            
        state_snap = self.cognitive_core.state.get_context_snapshot()
        
        # CVS-1.0 Metadata Propagation
        payload = {
            "content": text,
            "done": False,
            "emotion": state_snap.get("emotion", "neutral"),
            "emotional_intensity": state_snap.get("emotional_intensity", 0.6),
            "confidence": 0.9, # To be dynamically computed in future versions
            "speaking_rate": 1.0,
            "timestamp": time.time()
        }
        await self.publish("chat.output", payload)

    async def _autonomy_loop(self):
        SILENCE_TICK_SECONDS = 60.0
        while True:
            await asyncio.sleep(SILENCE_TICK_SECONDS)
            now = datetime.now()
            idle_seconds = (now - self.last_interaction_time).total_seconds()
            await self.cognitive_core.state.evolve_idle(dt_hours=idle_seconds / 3600.0)
            
            if idle_seconds > 300.0:
                raw_event = {
                    "id": str(uuid.uuid4()),
                    "type": "SYSTEM_TICK",
                    "content": "Deep reflection requested.",
                    "metadata": {}
                }
                async for _ in self.cognitive_core.process_event(raw_event):
                    pass

    async def stop(self):
        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")

async def main():
    agent = BrainAgent()
    await agent.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
