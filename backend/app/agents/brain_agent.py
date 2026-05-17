import asyncio
import logging
import math
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List

from pydantic import ValidationError
from .base import BaseAgent
from ..llm.ollama_client import OllamaClient
from ..state import GraphDB, MemoryStore, ConversationHistoryStore
from ..config import Config
from ..cognitive import CognitiveService
from ..runtime_bootstrap import bootstrap_runtime
from ..contracts import ChatInput, ChatOutput, ChatOutputAffect, Topics
from ..logging_config import setup_logging
from ..utils.segmentation import HybridSegmenter
from ..utils.speech import SpeechCoordinator

logger = logging.getLogger(__name__)





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
        self.ollama = OllamaClient(base_url=ollama_url, model=Config.LLM_CHAT_MODEL)
        self.graph_db = graph_db
        self.memory_store = memory_store
        self.conversation_store = conversation_store

        # Initialize the Functional Core
        self.cognitive_core = CognitiveService(
            llm_service=self.ollama,
            memory_store=memory_store,
            graph_db=graph_db,
            identity_store=conversation_store,
        )

        self.last_interaction_time = datetime.now()
        self.last_visual_context = "No visual data available."

        # CVS-1.0 Segmentation Config
        self.coordinator = SpeechCoordinator(
            segmenter=HybridSegmenter(target_size=8),
            formation_buffer_ms=0.030
        )

    async def start(self):
        await self.connect()

        if self.conversation_store:
            await self.conversation_store.initialize()
            await self.conversation_store.start_session()

        await self.cognitive_core.initialize(agent=self)

        # Subscribe to I/O streams
        await self.subscribe(
            Topics.CHAT_INPUT,
            self._on_chat_input,
            durable=f"{self.name}_chat_input_live",
            deliver_policy="new",
        )
        await self.subscribe(
            Topics.VISION_FRAMES, self._on_vision_frame, deliver_policy="last"
        )
        await self.subscribe(
            Topics.VISION_DESCRIPTION,
            self._on_vision_description,
            deliver_policy="last",
        )
        await self.subscribe(
            Topics.VOICE_SEGMENTATION_FEEDBACK,
            self._on_voice_feedback,
            durable=f"{self.name}_voice_segmentation_feedback_live",
            deliver_policy="new",
        )
        # Note: system.tick proactive engagement is now handled by SubconsciousAgent

        logger.info(f"🧠 {self.name} Online | CVS-1.0 Cognitive Mesh Active.")

    async def _on_voice_feedback(self, data: Dict[str, Any]):
        """Adaptive Tuning Loop (CVS-1.0 alpha-damped loop)."""
        target = data.get("target_chunk_size", 8)
        alpha = getattr(Config, "FEEDBACK_ALPHA", 0.7)

        # Alpha-damped damping to prevent jittery speech fragmentation
        smoothed_size = (alpha * self.coordinator.segmenter.target_size) + (
            (1 - alpha) * target
        )
        new_size = int(round(smoothed_size))

        if new_size != self.coordinator.segmenter.target_size:
            logger.info(
                f"📈 Tuning Segmentation | Target: {target} -> Smoothed: {new_size}"
            )
            self.coordinator.segmenter.target_size = new_size

    async def _on_vision_frame(self, data: Dict[str, Any]):
        """Fallback: basic source awareness from raw frames."""
        source = data.get("source", "unknown")
        # Only update if we don't have a richer VLM description yet
        if not self.last_visual_context or self.last_visual_context == "No visual data available.":
            self.last_visual_context = f"I am seeing the user's {source}."

    async def _on_vision_description(self, data: Dict[str, Any]):
        """Tier-4 VLM: Rich semantic visual context from the Visual Appraisal pipeline."""
        description = data.get("description", "")
        source = data.get("source", "unknown")
        if description:
            self.last_visual_context = f"[Visual Context from {source}]: {description}"
            logger.debug("[Brain] Visual context updated: %s", description[:60])
        else:
            self.last_visual_context = f"I am seeing the user's {source}."

    async def _on_chat_input(self, message: Dict[str, Any]):
        now = datetime.now()
        self.last_interaction_time = now

        try:
            msg = ChatInput.model_validate(message)
            user_text = msg.text
            turn_id = msg.turn_id or msg.utterance_id or str(uuid.uuid4())
            metadata = msg.metadata.model_dump()
            utterance_id = msg.utterance_id
            is_subconscious = msg.metadata.source == "subconscious"
        except ValidationError as e:
            logger.warning(f"Dropping invalid chat.input message: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error processing chat.input: {e}", exc_info=True)
            return

        if not user_text:
            return

        # Only update human interaction tracking if it's an actual user message
        if not is_subconscious:
            self.cognitive_core.state.record_user_interaction()

        raw_event = {
            "id": str(uuid.uuid4()),
            "type": "USER_MESSAGE",
            "content": user_text,
            "metadata": {
                **metadata,
                "visuals": self.last_visual_context,
                "turn_id": turn_id,
                "utterance_id": utterance_id,
            },
        }

        if self.conversation_store and not is_subconscious:
            asyncio.create_task(self.conversation_store.log_message("user", user_text))

        if is_subconscious:
            logger.info("💭 [Brain] Processing subconscious thought: %s", user_text)
            generator = self.cognitive_core.generate_proactive_response(thought_prompt=user_text)
        else:
            generator = self.cognitive_core.process_event(raw_event)

        full_response = await self._stream_to_speech(
            generator, 
            turn_id=turn_id, 
            is_proactive=is_subconscious
        )

        if self.conversation_store and full_response:
            asyncio.create_task(
                self.conversation_store.log_message("assistant", full_response)
            )

    async def _stream_to_speech(self, generator, turn_id: str, is_proactive: bool = False) -> str:
        """Helper method to process text generation streams and segment them into speech chunks."""
        full_response = ""
        current_chunk_words = []
        segment_started_at = None
        generation_errors: List[str] = []
        fallback_text = "I'm having trouble thinking right now..."
        
        await self.set_state("thinking")

        try:
            async for output in generator:
                if output["type"] == "content":
                    await self.set_state("speaking")
                    chunk_text = output["data"]
                    full_response += chunk_text

                    now_monotonic = time.perf_counter()
                    if (
                        current_chunk_words
                        and segment_started_at is not None
                        and (now_monotonic - segment_started_at)
                        >= self.coordinator.formation_buffer_ms
                        and len(current_chunk_words) >= 3
                    ):
                        await self._publish_speech_chunk(current_chunk_words, turn_id)
                        current_chunk_words = []
                        segment_started_at = None

                    words = chunk_text.split()
                    for word in words:
                        if not current_chunk_words:
                            segment_started_at = time.perf_counter()
                        current_chunk_words.append(word)

                        score = self.coordinator.segmenter.score_split_point(
                            word, len(current_chunk_words)
                        )
                        if score > 0.7 or len(current_chunk_words) > 12:
                            await self._publish_speech_chunk(
                                current_chunk_words, turn_id
                            )
                            current_chunk_words = []
                            segment_started_at = None

                elif output["type"] == "error":
                    error_msg = str(
                        output.get("data", "unknown cognitive stream error")
                    )
                    generation_errors.append(error_msg)
                    logger.error(
                        "[Brain] LLM stream error on turn_id=%s: %s",
                        turn_id,
                        error_msg,
                    )

                elif output["type"] == "done":
                    if current_chunk_words:
                        await self._publish_speech_chunk(current_chunk_words, turn_id)
                        current_chunk_words = []

                    if not full_response.strip() and not is_proactive:
                        logger.error(
                            "[Brain] Empty generation on turn_id=%s. errors=%s. Emitting fallback.",
                            turn_id,
                            generation_errors[-3:],
                        )
                        await self._publish_speech_chunk(fallback_text.split(), turn_id)
                        full_response = fallback_text

                    if full_response.strip() or not is_proactive:
                        state_snap = self.cognitive_core.state.get_context_snapshot()
                        output_msg = self.coordinator.create_chunk_payload(
                            state_snap=state_snap,
                            turn_id=turn_id,
                            done=True,
                            full_response=full_response,
                            generation_error=generation_errors[-1] if generation_errors else None,
                            proactive=is_proactive
                        )
                        await self.publish(Topics.CHAT_OUTPUT, output_msg.model_dump())

        except Exception as e:
            logger.error("Cognitive Loop error on turn_id=%s: %s", turn_id, e)
            if not is_proactive:
                error_msg = str(e)
                await self._publish_speech_chunk(fallback_text.split(), turn_id)
                output_msg = self.coordinator.create_chunk_payload(
                    done=True,
                    full_response=fallback_text,
                    turn_id=turn_id,
                    generation_error=error_msg
                )
                await self.publish(Topics.CHAT_OUTPUT, output_msg.model_dump())

        await self.set_state("idle")
        return full_response

    async def _publish_speech_chunk(self, words: List[str], turn_id: str = None):
        """
        Publishes a semantically coherent chunk with full PAD affect metadata.
        Implements the Brain→Voice contract from psychological_layer.md §5.3.
        """
        text = " ".join(words).strip()
        if not text:
            return

        state_snap = self.cognitive_core.state.get_context_snapshot()
        V = state_snap.get("valence", state_snap.get("mood", 0.0))
        Ar = state_snap.get("arousal", state_snap.get("energy", 0.5))
        D = state_snap.get("dominance", 0.5)
        T = state_snap.get("trust", 0.5)
        At = state_snap.get("attachment", 0.1)

        # §5.1: Scherer CPM — Prosody mapping
        speaking_rate = 1.0 + math.tanh(0.5 * Ar - 0.2)  # High arousal → faster
        confidence = 0.9  # Placeholder until appraisal confidence is threaded
        intensity = abs(V) * Ar  # Emotional intensity

        # §4.1: Goldman-Eisler — Pause bias
        pause_bias = max(0.0, min(1.0, 0.2 + 0.4 * (1 - confidence) + 0.2 * Ar))

        # Full §5.3 Affect Metadata Contract
        payload = ChatOutput(
            content=text,
            done=False,
            turn_id=turn_id,
            confidence=confidence,
            intensity=intensity,
            speaking_rate=round(speaking_rate, 3),
            pause_bias=round(pause_bias, 3),
            affect=ChatOutputAffect(
                valence=V,
                arousal=Ar,
                dominance=D,
                trust=T,
                attachment=At,
                emotion=state_snap.get("emotion", "neutral"),
            ),
        )
        await self.publish(Topics.CHAT_OUTPUT, payload.model_dump())

    async def stop(self):
        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")


async def main():
    if Config.RUNTIME_AUTO_BOOTSTRAP:
        logger.info("[Brain] Running runtime bootstrap checks...")
        await bootstrap_runtime()

    # 1. Initialize CVS-1.0 Foundation (Pool-based logic)
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()  # Creates the database pool

    # Inject the established pool into MemoryStore
    memory_store = MemoryStore(pool=conversation_store.pool)
    graph_db = GraphDB()

    # 2. Instantiate Brain Agent with injected dependencies
    agent = BrainAgent(
        ollama_url=Config.OLLAMA_URL,
        graph_db=graph_db,
        memory_store=memory_store,
        conversation_store=conversation_store,
    )

    await agent.start()

    try:
        shutdown_trigger = asyncio.Event()
        await shutdown_trigger.wait()
    except asyncio.CancelledError:
        await agent.stop()


if __name__ == "__main__":
    setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))
    asyncio.run(main())
