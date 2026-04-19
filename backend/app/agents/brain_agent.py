import asyncio
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List

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
        await self.connect()
        await self.cognitive_core.initialize(agent=self)

        if self.conversation_store:
            await self.conversation_store.initialize()
            await self.conversation_store.start_session()

        # Subscribe to I/O streams
        await self.subscribe("chat.input", self._on_chat_input)
        await self.subscribe("vision.frames", self._on_vision_frame, deliver_policy="last")
        await self.subscribe("voice.segmentation_feedback", self._on_voice_feedback)
        
        logger.info(f"🧠 {self.name} Online | CVS-1.0 Cognitive Mesh Active.")

    async def _on_voice_feedback(self, data: Dict[str, Any]):
        """Adaptive Tuning Loop (CVS-1.0 alpha-damped loop)."""
        target = data.get("target_chunk_size", 8)
        alpha = getattr(Config, "FEEDBACK_ALPHA", 0.7)
        
        # Alpha-damped damping to prevent jittery speech fragmentation
        smoothed_size = (alpha * self.segmenter.target_size) + ((1 - alpha) * target)
        new_size = int(round(smoothed_size))
        
        if new_size != self.segmenter.target_size:
            logger.info(f"📈 Tuning Segmentation | Target: {target} -> Smoothed: {new_size}")
            self.segmenter.target_size = new_size

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
            "metadata": {
                **message.get("metadata", {}),
                "visuals": self.last_visual_context,
            }
        }

        if self.conversation_store:
            asyncio.create_task(self.conversation_store.log_message("user", user_text))

        await self.set_state("thinking")
        
        full_response = ""
        current_chunk_words = []
        segment_started_at = None
        
        try:
            async for output in self.cognitive_core.process_event(raw_event):
                if output["type"] == "content":
                    await self.set_state("speaking")
                    chunk_text = output["data"]
                    full_response += chunk_text

                    now_monotonic = time.perf_counter()
                    if (
                        current_chunk_words
                        and segment_started_at is not None
                        and (now_monotonic - segment_started_at) >= self.formation_buffer_ms
                        and len(current_chunk_words) >= 3
                    ):
                        await self._publish_speech_chunk(current_chunk_words)
                        current_chunk_words = []
                        segment_started_at = None
                    
                    # Tokenize by whitespace
                    words = chunk_text.split()
                    for word in words:
                        if not current_chunk_words:
                            segment_started_at = time.perf_counter()
                        current_chunk_words.append(word)

                        # 1. Heuristic Scoring
                        score = self.segmenter.score_split_point(word, len(current_chunk_words))
                        
                        # 2. Decision (Safe Split)
                        if score > 0.7 or len(current_chunk_words) > 12:
                            await self._publish_speech_chunk(current_chunk_words)
                            current_chunk_words = []
                            segment_started_at = None
                
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


    async def stop(self):
        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")

async def main():
    # 1. Initialize CVS-1.0 Foundation (Pool-based logic)
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize() # Creates the database pool
    
    # Inject the established pool into MemoryStore
    memory_store = MemoryStore(pool=conversation_store.pool)
    graph_db = GraphDB()
    
    # 2. Instantiate Brain Agent with injected dependencies
    agent = BrainAgent(
        ollama_url=Config.OLLAMA_URL,
        graph_db=graph_db,
        memory_store=memory_store,
        conversation_store=conversation_store
    )
    
    await agent.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await agent.stop()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
