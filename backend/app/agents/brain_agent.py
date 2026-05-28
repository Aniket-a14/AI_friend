import asyncio
import logging
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
        self.last_user_distance = 1.0
        self.last_user_voice_properties = None

        # CVS-1.0 Segmentation Config
        self.coordinator = SpeechCoordinator(
            segmenter=HybridSegmenter(target_size=8), formation_buffer_ms=0.030
        )
        from ..utils.interruption_classifier import InterruptionClassifier
        from ..utils.conversational_runtime import ConversationalRuntime

        self.interruption_classifier = InterruptionClassifier()
        self.conversational_runtime = ConversationalRuntime(publish_cb=self.publish)
        self._active_generation_task = None
        self.last_audio_progress = None
        self.last_assistant_response = None

    async def start(self):
        await self.connect()

        if self.conversation_store:
            pool = getattr(self.conversation_store, "pool", None)
            from unittest.mock import Mock

            if pool is None or isinstance(pool, Mock):
                await self.conversation_store.initialize()

        await self.cognitive_core.initialize(agent=self)

        if self.conversation_store:
            await self.conversation_store.start_session(
                trust_benevolence=self.cognitive_core.state.current_state.trust_benevolence,
                trust_competence=self.cognitive_core.state.current_state.trust_competence,
                trust_integrity=self.cognitive_core.state.current_state.trust_integrity,
            )

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
        await self.subscribe(
            Topics.AUDIO_PERCEPTION,
            self._on_audio_perception,
            durable=f"{self.name}_brain_audio_perception_live",
            deliver_policy="new",
        )
        await self.subscribe(
            Topics.USER_VOICE_PROPERTIES,
            self._on_user_voice_properties,
            durable=f"{self.name}_user_voice_properties_live",
            deliver_policy="new",
        )
        await self.subscribe(
            Topics.AUDIO_PLAYBACK_PROGRESS,
            self._on_audio_playback_progress,
            durable=f"{self.name}_audio_playback_progress_live",
            deliver_policy="new",
        )
        await self.subscribe(
            Topics.AUDIO_STOP,
            self._on_audio_stop,
            durable=f"{self.name}_audio_stop_live",
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
        if (
            not self.last_visual_context
            or self.last_visual_context == "No visual data available."
        ):
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
        self.last_user_distance = (
            data.get("user_distance") if data.get("user_distance") is not None else 1.0
        )

    async def _on_chat_input(self, message: Dict[str, Any]):
        now = datetime.now()
        self.last_interaction_time = now

        try:
            msg = ChatInput.model_validate(message)
            is_subconscious = msg.metadata.source == "subconscious"
        except ValidationError as e:
            logger.warning(f"Dropping invalid chat.input message: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error processing chat.input: {e}", exc_info=True)
            return

        # Cancel any previous generation task if running
        if self._active_generation_task and not self._active_generation_task.done():
            logger.info("Cancelling active task due to new incoming speech turn.")
            self._active_generation_task.cancel()

        # If it is not a subconscious pulse, publish a confirmed stop to silence any playing voice agent audio
        if not is_subconscious:
            from ..contracts import AudioStop

            stop_msg = AudioStop(
                interrupt=True,
                speculative=False,
                reason="confirmed_user_speech",
                perception_text=msg.text,
                intent="CONFIRMED_STOP",
                utterance_id=msg.utterance_id,
            )
            await self.publish(Topics.AUDIO_STOP, stop_msg.model_dump())

        # Start the flow task in background to allow cancellation on interruption
        task = asyncio.create_task(
            self._process_chat_input_flow(msg, is_subconscious, message)
        )
        self._active_generation_task = task
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Active generation flow task cancelled.")
        finally:
            if self._active_generation_task == task:
                self._active_generation_task = None

    async def _process_chat_input_flow(
        self, chat_input: ChatInput, is_subconscious: bool, message: Dict[str, Any]
    ):
        flow_start_time = time.time()
        user_text = chat_input.text
        turn_id = chat_input.turn_id or chat_input.utterance_id or str(uuid.uuid4())
        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            metadata = chat_input.metadata.model_dump() if chat_input.metadata else {}
        latency_metadata = message.get("latency_metadata")
        if not isinstance(latency_metadata, dict):
            latency_metadata = {}
        utterance_id = chat_input.utterance_id

        if not user_text:
            return

        # Pacing Conversational Turn: calculate silence duration and pause
        state_snap = self.cognitive_core.state.get_context_snapshot()
        pacing = self.conversational_runtime.calculate_pacing_parameters(state_snap)

        is_benchmark = (
            metadata.get("benchmark_id") == "bench_pulse"
            if isinstance(metadata, dict)
            else False
        )
        if is_benchmark:
            silence_s = 0.0
            logger.info(
                "⚡ [Brain] Benchmark pulse detected. Pacing sleep bypassed for raw latency measurement."
            )
        else:
            silence_s = pacing["silence_duration_ms"] / 1000.0
            logger.info(
                f"Pacing conversational turn: sleeping {pacing['silence_duration_ms']:.1f}ms before starting response."
            )
        await asyncio.sleep(silence_s)

        # Only update human interaction tracking if it's an actual user message
        if not is_subconscious:
            self.cognitive_core.state.record_user_interaction()

        # Ingest the latest user voice properties (System 1 feature stream) into the raw_event
        user_voice_properties = None
        if self.last_user_voice_properties:
            user_voice_properties = self.last_user_voice_properties.model_dump()
            self.last_user_voice_properties = None

        raw_event = {
            "id": str(uuid.uuid4()),
            "type": "USER_MESSAGE",
            "content": user_text,
            "user_voice_properties": user_voice_properties,
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
            generator = self.cognitive_core.generate_proactive_response(
                thought_prompt=user_text
            )
        else:
            self.last_assistant_response = None
            self.last_audio_progress = None
            generator = self.cognitive_core.process_event(raw_event)

        # Wrap generator to monitor TTFT and inject fillers
        wrapped_generator = self.conversational_runtime.monitor_stream_and_fill(
            generator=generator,
            turn_id=turn_id,
            state_snap=state_snap,
            user_distance=self.last_user_distance,
            is_proactive=is_subconscious,
            incoming_metadata=metadata,
            incoming_latency_metadata=latency_metadata,
            flow_start_time=flow_start_time,
        )

        if not is_subconscious:
            self.last_assistant_response = ""
            self.assistant_response_start_time = time.time()

        full_response = await self._stream_to_speech(
            wrapped_generator,
            turn_id=turn_id,
            is_proactive=is_subconscious,
            incoming_metadata=metadata,
            incoming_latency_metadata=latency_metadata,
        )

        if not is_subconscious:
            self.last_assistant_response = full_response

        if self.conversation_store and full_response:
            asyncio.create_task(
                self.conversation_store.log_message("assistant", full_response)
            )

    async def _on_audio_perception(self, data: Dict[str, Any]):
        """Runs the semantic interruption classifier on partial speech hypotheses."""
        metadata = data.get("metadata", {})
        is_partial = metadata.get("is_partial", False)
        text = data.get("text", "")

        # Only run semantic classifier on partial transcripts
        if is_partial and text:
            if self.interruption_classifier.is_interruption(text):
                logger.info(
                    f"🚨 [Brain] Semantic interrupt detected on partial: '{text}'"
                )

                # Instantly publish confirmed audio.stop to silence playback
                from ..contracts import AudioStop

                stop_msg = AudioStop(
                    interrupt=True,
                    speculative=False,
                    reason=f"semantic_interrupt: {text}",
                    perception_text=text,
                    intent="CONFIRMED_STOP",
                    utterance_id=data.get("utterance_id"),
                )
                await self.publish(Topics.AUDIO_STOP, stop_msg.model_dump())

                # Instantly cancel active LLM generation stream
                if (
                    self._active_generation_task
                    and not self._active_generation_task.done()
                ):
                    logger.info(
                        "[Brain] Cancelling active LLM stream task due to semantic interrupt."
                    )
                    self._active_generation_task.cancel()
            else:
                # Not a valid semantic interruption! Send an audio resume to restore volume.
                from ..contracts import AudioResume

                resume_msg = AudioResume(
                    reason="not_interruption",
                    perception_text=text,
                    utterance_id=data.get("utterance_id"),
                )
                await self.publish(Topics.AUDIO_RESUME, resume_msg.model_dump())

    async def _on_audio_playback_progress(self, data: Dict[str, Any]):
        """Tracks the current word/character progress of the audio playback."""
        try:
            from ..contracts import AudioPlaybackProgress

            progress = AudioPlaybackProgress.model_validate(data)
            self.last_audio_progress = progress
            logger.debug(
                f"🔊 Audio Playback Progress | Word Index: {progress.word_index} | Offset: {progress.character_offset} | Completed: {progress.completed}"
            )
        except Exception as e:
            logger.error(f"Error parsing audio playback progress: {e}")

    async def _on_audio_stop(self, data: Dict[str, Any]):
        """Handles confirmed audio stops to truncate the last played utterance in history."""
        try:
            from ..contracts import AudioStop

            stop_msg = AudioStop.model_validate(data)

            # Truncation only happens on confirmed (non-speculative) interrupts
            if not stop_msg.speculative:
                progress = self.last_audio_progress
                if progress and not progress.completed and self.last_assistant_response:
                    offset = progress.character_offset
                    if 0 < offset < len(self.last_assistant_response):
                        truncated_text = self.last_assistant_response[:offset].strip()
                        original_length = len(self.last_assistant_response)
                        truncated_length = len(truncated_text)
                        logger.info(
                            f"Truncating history (via progress): original_length={original_length}, truncated_length={truncated_length}, offset={offset}"
                        )
                        if self.conversation_store:
                            await self.conversation_store.update_last_assistant_message(
                                truncated_text
                            )
                        self.last_audio_progress = None
                elif (
                    not progress
                    and self.last_assistant_response
                    and hasattr(self, "assistant_response_start_time")
                ):
                    # Fallback: estimate progress using average word/character duration
                    elapsed = time.time() - self.assistant_response_start_time
                    # Average speech rate: ~15 characters per second (approx 150 WPM)
                    offset = int(elapsed * 15)
                    if 0 < offset < len(self.last_assistant_response):
                        truncated_text = self.last_assistant_response[:offset].strip()
                        original_length = len(self.last_assistant_response)
                        truncated_length = len(truncated_text)
                        logger.info(
                            f"Truncating history (via estimation): original_length={original_length}, truncated_length={truncated_length}, offset={offset}, elapsed={elapsed:.2f}s"
                        )
                        if self.conversation_store:
                            await self.conversation_store.update_last_assistant_message(
                                truncated_text
                            )
        except Exception as e:
            logger.error(f"Error handling audio stop truncation: {e}")

    async def _on_user_voice_properties(self, data: Dict[str, Any]):
        """Ingest real-time user voice properties (System 1 feature stream)."""
        try:
            from ..contracts import UserVoiceProperties

            props = UserVoiceProperties.model_validate(data)
            self.last_user_voice_properties = props
            logger.debug(
                f"🎙️ Ingested User Voice | Pitch: {props.pitch_f0:.1f}Hz | Energy: {props.energy_rms:.3f} | Tempo: {props.tempo_wpm:.1f}WPM"
            )
        except Exception as e:
            logger.error(f"Error parsing user voice properties: {e}")

    async def _stream_to_speech(
        self,
        generator,
        turn_id: str,
        is_proactive: bool = False,
        incoming_metadata: Dict[str, Any] = None,
        incoming_latency_metadata: Dict[str, Any] = None,
    ) -> str:
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
                    if not is_proactive:
                        self.last_assistant_response = full_response

                    now_monotonic = time.perf_counter()
                    if (
                        current_chunk_words
                        and segment_started_at is not None
                        and (now_monotonic - segment_started_at)
                        >= self.coordinator.formation_buffer_ms
                        and len(current_chunk_words) >= 3
                    ):
                        await self._publish_speech_chunk(
                            current_chunk_words,
                            turn_id,
                            incoming_metadata=incoming_metadata,
                            incoming_latency_metadata=incoming_latency_metadata,
                        )
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
                                current_chunk_words,
                                turn_id,
                                incoming_metadata=incoming_metadata,
                                incoming_latency_metadata=incoming_latency_metadata,
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

                elif output["type"] == "pipeline_telemetry":
                    if incoming_latency_metadata is None:
                        incoming_latency_metadata = {}
                    incoming_latency_metadata["pipeline_telemetry"] = output["data"]

                elif output["type"] == "done":
                    if current_chunk_words:
                        await self._publish_speech_chunk(
                            current_chunk_words,
                            turn_id,
                            incoming_metadata=incoming_metadata,
                            incoming_latency_metadata=incoming_latency_metadata,
                        )
                        current_chunk_words = []

                    if not full_response.strip() and not is_proactive:
                        logger.error(
                            "[Brain] Empty generation on turn_id=%s. errors=%s. Emitting fallback.",
                            turn_id,
                            generation_errors[-3:],
                        )
                        await self._publish_speech_chunk(
                            fallback_text.split(),
                            turn_id,
                            incoming_metadata=incoming_metadata,
                            incoming_latency_metadata=incoming_latency_metadata,
                        )
                        full_response = fallback_text

                    if full_response.strip() or not is_proactive:
                        state_snap = self.cognitive_core.state.get_context_snapshot()
                        output_msg = self.coordinator.create_chunk_payload(
                            state_snap=state_snap,
                            turn_id=turn_id,
                            done=True,
                            full_response=full_response,
                            generation_error=generation_errors[-1]
                            if generation_errors
                            else None,
                            proactive=is_proactive,
                            user_distance=self.last_user_distance,
                        )
                        output_msg.metadata = incoming_metadata
                        output_msg.latency_metadata = incoming_latency_metadata
                        await self.publish(Topics.CHAT_OUTPUT, output_msg.model_dump())

        except Exception as e:
            logger.error("Cognitive Loop error on turn_id=%s: %s", turn_id, e)
            if not is_proactive:
                error_msg = str(e)
                await self._publish_speech_chunk(
                    fallback_text.split(),
                    turn_id,
                    incoming_metadata=incoming_metadata,
                    incoming_latency_metadata=incoming_latency_metadata,
                )
                output_msg = self.coordinator.create_chunk_payload(
                    done=True,
                    full_response=fallback_text,
                    turn_id=turn_id,
                    generation_error=error_msg,
                    user_distance=self.last_user_distance,
                )
                output_msg.metadata = incoming_metadata
                output_msg.latency_metadata = incoming_latency_metadata
                await self.publish(Topics.CHAT_OUTPUT, output_msg.model_dump())

        await self.set_state("idle")
        return full_response

    async def _publish_speech_chunk(
        self,
        words: List[str],
        turn_id: str = None,
        incoming_metadata: Dict[str, Any] = None,
        incoming_latency_metadata: Dict[str, Any] = None,
    ):
        """
        Publishes a semantically coherent chunk with full PAD affect metadata.
        Implements the Brain→Voice contract from psychological_layer.md §5.3.
        """
        text = " ".join(words).strip()
        if not text:
            return

        state_snap = self.cognitive_core.state.get_context_snapshot()
        prosody = self.coordinator.map_affect_to_prosody(state_snap)

        # Full §5.3 Affect Metadata Contract
        payload = ChatOutput(
            content=text,
            done=False,
            turn_id=turn_id,
            confidence=prosody["confidence"],
            intensity=prosody["intensity"],
            speaking_rate=prosody["speaking_rate"],
            pause_bias=prosody["pause_bias"],
            affect=ChatOutputAffect(
                valence=state_snap.get("valence", state_snap.get("mood", 0.0)),
                arousal=state_snap.get("arousal", state_snap.get("energy", 0.5)),
                dominance=state_snap.get("dominance", 0.5),
                trust=state_snap.get("trust", 0.5),
                attachment=state_snap.get("attachment", 0.1),
                emotion=state_snap.get("emotion", "neutral"),
                fatigue=state_snap.get("fatigue", 0.0),
                user_distance=self.last_user_distance,
            ),
            metadata=incoming_metadata,
            latency_metadata=incoming_latency_metadata,
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
