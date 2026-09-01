import asyncio
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from ..cognitive import CognitiveService
from ..cognitive.somatic import SomaticAppraiser
from ..config import Config
from ..contracts import (
    AudioPlaybackBacklog,
    AudioPlaybackProgress,
    AudioStop,
    ChatInput,
    Topics,
    UserVoiceProperties,
)
from ..llm import build_llm_client
from ..logging_config import setup_logging
from ..runtime_bootstrap import bootstrap_runtime
from ..state import ConversationHistoryStore, GraphDB, MemoryStore
from ..utils.conversational_runtime import ConversationalRuntime
from ..utils.segmentation import HybridSegmenter
from ..utils.speech import SpeechCoordinator
from .base import BaseAgent, install_shutdown_signal_handlers

logger = logging.getLogger(__name__)


def _char_offset_after_word(text: str, word_count: int) -> int:
    """P4-2: the exact character offset in `text` right after its
    `word_count`-th whitespace-delimited token.

    Used to stamp each published speech chunk with where it ends in the
    *true* response text, so `_truncate_interrupted_reply` can later slice
    `last_assistant_response` at a real boundary instead of the reconstructed
    (`" ".join(words)`) text actually sent to TTS, which does not
    byte-for-byte match `text` wherever the source stream's whitespace was
    collapsed by `.split()`/`.join()`. `re.finditer` walks `text` itself, so
    the offset it returns is always a true index into `text`, independent of
    that mismatch.
    """
    if word_count <= 0:
        return 0
    matches = list(re.finditer(r"\S+", text))
    if not matches:
        return 0
    return matches[min(word_count, len(matches)) - 1].end()


class BrainAgent(BaseAgent):
    """
    The Brain Agent (AI Friend Edition).
    Orchestrator of Identity and Temporal Cognitive Flow.
    """

    def __init__(
        self,
        ollama_url: str = Config.OLLAMA_URL,
        graph_db: GraphDB | None = None,
        memory_store: MemoryStore | None = None,
        conversation_store: ConversationHistoryStore | None = None,
    ):
        super().__init__(name="brain_agent")
        self.ollama = build_llm_client(base_url=ollama_url, model=Config.LLM_CHAT_MODEL)
        self.graph_db = graph_db
        self.memory_store = memory_store
        self.conversation_store = conversation_store

        # Initialize the Functional Core
        self.cognitive_core = CognitiveService(
            llm_service=self.ollama,
            memory_store=memory_store,
            graph_db=graph_db,
            identity_store=conversation_store,
            publish_cb=self.publish,
        )

        # Visual Somatic Homeostasis: recognising a learned comfort object in
        # what the agent is looking at lifts valence/arousal (and therefore the
        # dopamine, tonic and phasic). Lives here rather than in the vision agent
        # because it needs the graph and the state service, keeping the vision
        # agent a pure sensor with no database credentials.
        self.somatic_appraiser = SomaticAppraiser(graph_store=graph_db)

        self.last_interaction_time = datetime.now()
        self.last_visual_context = "No visual data available."
        self.last_user_distance = 1.0
        self.last_user_voice_properties: UserVoiceProperties | None = None

        # AI Friend Segmentation Config
        self.coordinator = SpeechCoordinator(
            segmenter=HybridSegmenter(target_size=7), formation_buffer_s=0.300
        )
        self.conversational_runtime = ConversationalRuntime(publish_cb=self.publish)
        self._active_generation_task: asyncio.Task[Any] | None = None
        self._generation_lock = asyncio.Lock()
        self.last_audio_progress: AudioPlaybackProgress | None = None
        self.last_assistant_response: str | None = None
        self._active_response_turn_id: str | None = None
        # Bucket 1 (VOICE_REMEDIATION_PLAN.md): stamped on the first playback
        # progress frame of each turn (see _on_audio_playback_progress) and
        # read by _on_chat_input's barge-in grace period below.
        self._last_audio_onset_at: float | None = None
        # Bucket 3 (VOICE_REMEDIATION_PLAN.md): last depth transport_agent
        # reported for its outbound PCM queue (see AudioPlaybackBacklog),
        # read by ConversationalRuntime to suppress a new filler while a
        # previous turn's audio is still draining. Starts at 0 (no known
        # backlog) rather than None so a cold start doesn't need a null check
        # on the hot filler-decision path.
        self.last_playback_backlog: int = 0
        # P2-14/M1-A14: `last_audio_progress` and `last_assistant_response`
        # are written from three independent NATS subscription tasks --
        # chat.input's turn flow, audio.playback.progress's tracker, and
        # audio.stop's truncation handler -- and read-then-written together
        # by audio.stop's truncation. `_generation_lock` guards only which
        # task owns `_active_generation_task`; it says nothing about this
        # data, and `_cancel_active_generation` yields back to the event
        # loop when its awaited task finishes, which is exactly the window a
        # concurrent chat.input reset can land in. See _truncate_interrupted_reply.
        self._turn_state_lock = asyncio.Lock()

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
        await self.subscribe(
            Topics.AUDIO_PLAYBACK_BACKLOG,
            self._on_playback_backlog,
            durable=f"{self.name}_audio_playback_backlog_live",
            deliver_policy="last",
        )
        # Note: system.tick proactive engagement is now handled by SubconsciousAgent

        logger.info(f"🧠 {self.name} Online | AI Friend Cognitive Mesh Active.")

    async def _on_voice_feedback(self, data: dict[str, Any]):
        """Adaptive Tuning Loop (AI Friend alpha-damped loop)."""
        target = data.get("target_chunk_size", 8)
        alpha = getattr(Config, "FEEDBACK_ALPHA", 0.7)

        # Alpha-damped damping to prevent jittery speech fragmentation
        smoothed_size = (alpha * self.coordinator.segmenter.target_size) + (
            (1 - alpha) * target
        )
        new_size = round(smoothed_size)

        if new_size != self.coordinator.segmenter.target_size:
            logger.info(
                f"📈 Tuning Segmentation | Target: {target} -> Smoothed: {new_size}"
            )
            self.coordinator.segmenter.target_size = new_size

    async def _on_vision_frame(self, data: dict[str, Any]):
        """Fallback: basic source awareness from raw frames."""
        source = data.get("source", "unknown")
        # Only update if we don't have a richer VLM description yet
        if (
            not self.last_visual_context
            or self.last_visual_context == "No visual data available."
        ):
            self.last_visual_context = f"I am seeing the user's {source}."

    async def _on_vision_description(self, data: dict[str, Any]):
        """VLM: Rich semantic visual context from the Visual Appraisal pipeline."""
        description = data.get("description", "")
        source = data.get("source", "unknown")
        if description:
            self.last_visual_context = f"[Visual Context from {source}]: {description}"
            logger.debug("[Brain] Visual context updated: %s", description[:60])
        else:
            self.last_visual_context = f"I am seeing the user's {source}."
        distance = data.get("user_distance")
        self.last_user_distance = float(distance) if distance is not None else 1.0

        await self._appraise_somatic(description)

    async def _appraise_somatic(self, description: str):
        """Turn a recognised comfort object into an endocrine response.

        This is the step that makes vision a sense rather than a captioner: the
        description above only ever became prompt text, so the agent could
        describe something it loves and feel nothing. Failures are contained --
        the visual context is still worth having even if the somatic layer is
        unavailable.
        """
        if not description:
            return
        try:
            await self.somatic_appraiser.refresh()
            somatic = self.somatic_appraiser.appraise(description)
            if not somatic:
                return
            await self.cognitive_core.state.apply_somatic_perception(somatic)
        except Exception:
            logger.exception("[Brain] Somatic appraisal failed; visual context kept.")

    async def _cancel_active_generation(self, reason: str):
        """Cancel the in-flight generation task and wait for it to fully unwind.

        A4: a fire-and-forget .cancel() only *requests* cancellation - the task
        keeps running until its next await point, so it can still write stale
        last_assistant_response/last_audio_progress after a new turn has already
        reset that state, or after _on_audio_stop has already read it for
        truncation. Awaiting the task here closes that race by guaranteeing the
        previous turn has stopped touching shared state before the caller
        (a new chat.input turn, or a confirmed audio.stop) proceeds.
        """
        async with self._generation_lock:
            task = self._active_generation_task
            if not task or task.done():
                return
            logger.info("Cancelling active generation task: %s", reason)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Previous generation task raised while being cancelled"
                )
            finally:
                if self._active_generation_task is task:
                    self._active_generation_task = None

    async def _truncate_interrupted_reply(self):
        """Rewrite the stored assistant reply down to what was actually
        heard, using `last_audio_progress`, then clear both fields.

        P2-14/M1-A14: this used to read `last_audio_progress` and
        `last_assistant_response`, compute a truncation offset, and (on one
        branch) `await` a conversation-store write, all without a lock --
        while `_process_chat_input_flow` (a different NATS subscription,
        therefore a different task) can reset both fields to start a new
        turn, and `_on_audio_playback_progress` (a third subscription) can
        overwrite `last_audio_progress` mid-computation. `_cancel_active_generation`
        guarantees the turn that WROTE this reply has stopped -- it does not
        guarantee nothing else reads or resets it while this method runs.
        Holding `_turn_state_lock` for the whole read-compute-write section
        (including the DB write) makes this atomic with respect to those
        other writers rather than merely reducing the window.
        """
        async with self._turn_state_lock:
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
            elif not progress and self.last_assistant_response:
                # No real playback progress, so we do not know how much of
                # the reply was actually heard -- and we no longer guess.
                #
                # This used to estimate `int(elapsed * 15)`, a hardcoded
                # 15 characters per second, and rewrite the stored reply at
                # that offset. Two things were wrong with it. The rate was
                # invented and unbounded in error: real speech rate varies
                # with prosody, pauses and the synthesiser, so the cut
                # landed wherever the arithmetic said. And
                # `assistant_response_start_time` is only set on one of the
                # two streaming paths, so `elapsed` could be measured from a
                # *previous* turn entirely.
                #
                # The transcript is not a log; it is what memory and the
                # persona prompt read back later. A wrong cut point puts
                # words in the agent's mouth that it never said, or deletes
                # ones it did, and nothing downstream can tell that the
                # sentence was reconstructed. Keeping the full text is also
                # wrong -- the agent may believe it said more than was heard
                # -- but it is wrong in a way that is honest and visible in
                # the log, rather than silently fabricated.
                logger.info(
                    "Interrupted with no playback progress; keeping the full "
                    "reply (%d chars) rather than guessing a cut point.",
                    len(self.last_assistant_response),
                )

            # Cleared however this turn resolved. It was previously reset
            # only on the branch that actually truncated, so a stop that
            # matched none of the guards left the progress marker in place
            # for the *next* interrupt to truncate against -- a stale offset
            # from a reply that had already ended.
            self.last_audio_progress = None

    async def _replace_active_generation(self, coro, reason: str):
        """Atomically replace the active generation task with a new one.

        Holds the lock through the entire critical section: cancel the prior task,
        await its completion, create the new task, and assign it to
        _active_generation_task. This prevents concurrent callers from both
        creating tasks and losing ownership when one overwrites the other's
        assignment (TOCTOU race).

        Args:
            coro: Coroutine to wrap in the new generation task
            reason: Reason for cancelling the prior task (if any)

        Returns:
            The newly created task
        """
        async with self._generation_lock:
            # Cancel and await prior task if it exists
            prior_task = self._active_generation_task
            if prior_task and not prior_task.done():
                logger.info("Cancelling active generation task: %s", reason)
                prior_task.cancel()
                try:
                    await prior_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception(
                        "Previous generation task raised while being cancelled"
                    )

            # Create and assign new task while still holding the lock
            new_task = asyncio.create_task(coro)
            self._active_generation_task = new_task
            return new_task

    async def _on_chat_input(self, message: dict[str, Any]):
        now = datetime.now()
        self.last_interaction_time = now

        try:
            msg = ChatInput.model_validate(message)
            is_subconscious = msg.metadata.source == "subconscious"
        except ValidationError as e:
            logger.warning(f"Dropping invalid chat.input message: {e}")
            return
        except Exception:
            logger.exception("Unexpected error processing chat.input")
            return

        # If it is not a subconscious pulse, publish a confirmed stop to silence any playing voice agent audio.
        #
        # Bucket 1 (VOICE_REMEDIATION_PLAN.md): this used to fire unconditionally, on every
        # chat.input, with no gate at all -- bypassing decision.py's
        # `is_speculative_stop_confirmed`, the arbiter `_resolve_turn_conflict`
        # (pipeline.py) already calls moments later on this same final text. Measured
        # directly in a live session (2026-09-01): on "Let's stop it.", the arbiter
        # correctly REJECTED the interruption ("contradicts early perception"), but this
        # unconditional publish had already cut playback half a second earlier regardless.
        #
        # The fix is not to duplicate the arbiter's keyword logic here -- that logic is
        # specifically for confirming an explicit command (stop/wait/hold/...), not for
        # deciding whether a new, keyword-free user turn should mute old audio, which is
        # this publish's actual job and must keep working unconditionally. The real defect
        # is only the double-fire: when STT's speculative duck already flagged this
        # utterance as command-like (`last_speculative_intent` is set), the pipeline's own
        # Stage 2 conflict resolution is about to run the arbiter on this exact text and
        # will itself publish audio.stop (confirmed) or audio.resume (rejected) --
        # skipping the immediate stop here defers entirely to that already-correct,
        # already-gated decision instead of racing ahead of it. Audio is already ducked
        # (not silenced) from the speculative signal, so nothing is lost by waiting the
        # extra tens of milliseconds for the real verdict.
        speculative_intent_pending = bool(
            self.cognitive_core.state.last_speculative_intent
        )
        # Bucket 1: a barge-in grace period right after the agent's own audio
        # actually starts playing. STT's own pipeline (250ms min_speech_ms +
        # 700ms endpoint silence, per config.py) means a genuine human
        # utterance cannot produce a *final* chat.input this soon after
        # onset -- the audit's own human-baseline research (Appendix A.1)
        # puts real reaction time at >200ms, and that clock does not even
        # start until the listener has heard enough to react to. What
        # arrives this fast is far more likely to be onset noise: a click,
        # pop, or brief echo tail before echoCancellation has settled.
        within_onset_grace = (
            self._last_audio_onset_at is not None
            and (time.time() - self._last_audio_onset_at) < Config.BARGE_IN_ONSET_GRACE_S
        )
        if not is_subconscious and not speculative_intent_pending and not within_onset_grace:
            stop_msg = AudioStop(
                interrupt=True,
                speculative=False,
                reason="confirmed_user_speech",
                perception_text=msg.text,
                intent="CONFIRMED_STOP",
                utterance_id=msg.utterance_id,
            )
            await self.publish(Topics.AUDIO_STOP, stop_msg.model_dump())

        # Atomically replace the active generation task to prevent concurrent
        # chat inputs from both creating tasks and losing ownership.
        task = await self._replace_active_generation(
            self._process_chat_input_flow(msg, is_subconscious, message),
            "new incoming speech turn",
        )
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Active generation flow task cancelled.")
        finally:
            # Clean up only if we still own this task
            async with self._generation_lock:
                if self._active_generation_task == task:
                    self._active_generation_task = None

    @staticmethod
    def _resolve_chat_input_metadata(
        chat_input: ChatInput, message: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Normalize the loosely-typed metadata/latency_metadata the message
        may or may not carry into plain dicts, falling back to the
        ChatInput's own metadata."""
        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            metadata = chat_input.metadata.model_dump() if chat_input.metadata else {}
        latency_metadata = message.get("latency_metadata")
        if not isinstance(latency_metadata, dict):
            latency_metadata = {}
        return metadata, latency_metadata

    async def _apply_conversational_pacing(
        self, metadata: dict[str, Any], state_snap: dict[str, Any]
    ) -> None:
        """Sleep for the calculated pre-response silence, skipped entirely
        for a latency benchmark pulse."""
        pacing = self.conversational_runtime.calculate_pacing_parameters(state_snap)
        is_benchmark = metadata.get("benchmark_id") == "bench_pulse"
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

    @staticmethod
    def _resolve_chat_user_id(
        message: dict[str, Any], chat_input: ChatInput, metadata: dict[str, Any]
    ) -> str:
        return (
            message.get("user_id")
            or metadata.get("user_id")
            or getattr(chat_input, "user_id", None)
            or (
                chat_input.metadata.model_dump().get("user_id")
                if chat_input.metadata
                else None
            )
            or "User"
        )

    async def _process_chat_input_flow(
        self, chat_input: ChatInput, is_subconscious: bool, message: dict[str, Any]
    ):
        user_text = chat_input.text
        turn_id = chat_input.turn_id or chat_input.utterance_id or str(uuid.uuid4())
        metadata, latency_metadata = self._resolve_chat_input_metadata(
            chat_input, message
        )
        utterance_id = chat_input.utterance_id

        if not user_text:
            return

        async with self._turn_state_lock:
            self._active_response_turn_id = turn_id

        # Pacing Conversational Turn: calculate silence duration and pause
        state_snap = self.cognitive_core.state.get_context_snapshot()
        await self._apply_conversational_pacing(metadata, state_snap)

        # Bucket 3 (VOICE_REMEDIATION_PLAN.md): stamped *after* the pacing
        # sleep, not before. A live capture (2026-09-01) showed the filler's
        # elapsed-time check used to start its clock before this deliberate
        # 300-900ms silence (`calculate_pacing_parameters`), so the filler's
        # budget was already exhausted before generation even began -- e.g. a
        # 496ms pacing sleep alone blew a 250ms threshold, and the fired-filler
        # log line always landed within ~15ms of the pacing sleep ending, never
        # any later. Measuring from here instead means the threshold reflects
        # actual generation latency, the thing it was meant to mask.
        generation_start_time = time.time()

        # Only update human interaction tracking if it's an actual user message
        if not is_subconscious:
            self.cognitive_core.state.record_user_interaction()

        # Ingest the latest user voice properties (System 1 feature stream) into the raw_event
        user_voice_properties = None
        if self.last_user_voice_properties:
            user_voice_properties = self.last_user_voice_properties.model_dump()
            self.last_user_voice_properties = None

        user_id = self._resolve_chat_user_id(message, chat_input, metadata)

        raw_event = {
            "id": str(uuid.uuid4()),
            "type": "USER_MESSAGE",
            "user_id": user_id,
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
            self.spawn(self.conversation_store.log_message(user_id, user_text))

        if is_subconscious:
            logger.info("💭 [Brain] Processing subconscious thought: %s", user_text)
            generator = self.cognitive_core.generate_proactive_response(
                thought_prompt=user_text
            )
        else:
            # P2-14/M1-A14: locked so this reset cannot land mid-computation
            # inside _truncate_interrupted_reply, running concurrently on the
            # audio.stop subscription's own task for a still-unwinding turn.
            async with self._turn_state_lock:
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
            generation_start_time=generation_start_time,
            playback_backlog=self.last_playback_backlog,
        )

        if not is_subconscious:
            async with self._turn_state_lock:
                self.last_assistant_response = ""
            # `assistant_response_start_time` used to be stamped here, read only
            # by the character-rate truncation guess in `_on_audio_stop`. That
            # guess is gone, and it was set on this path only -- the other
            # streaming path assigns `last_assistant_response` without it, which
            # is how elapsed time could be measured from an earlier turn.

        full_response = await self._stream_to_speech(
            wrapped_generator,
            turn_id=turn_id,
            is_proactive=is_subconscious,
            incoming_metadata=metadata,
            incoming_latency_metadata=latency_metadata,
        )

        if not is_subconscious:
            async with self._turn_state_lock:
                self.last_assistant_response = full_response

        if self.conversation_store and full_response:
            self.spawn(self.conversation_store.log_message("assistant", full_response))

    async def _on_audio_playback_progress(self, data: dict[str, Any]):
        """Tracks the current word/character progress of the audio playback."""
        try:
            progress = AudioPlaybackProgress.model_validate(data)
            async with self._turn_state_lock:
                active_turn_id = getattr(self, "_active_response_turn_id", None)
                if active_turn_id and progress.utterance_id != active_turn_id:
                    logger.debug(
                        "Ignoring playback progress for stale turn %s; active turn is %s.",
                        progress.utterance_id,
                        active_turn_id,
                    )
                    return
                self.last_audio_progress = progress
                if progress.word_index == 0 and progress.character_offset == 0:
                    # Bucket 1: the first frame of a new utterance actually
                    # starting to play, not just being queued -- the moment
                    # _on_chat_input's grace period below measures from.
                    self._last_audio_onset_at = time.time()
            logger.debug(
                f"🔊 Audio Playback Progress | Word Index: {progress.word_index} | Offset: {progress.character_offset} | Completed: {progress.completed}"
            )
        except Exception as e:
            logger.error(f"Error parsing audio playback progress: {e}")

    async def _on_playback_backlog(self, data: dict[str, Any]):
        """Bucket 3 (VOICE_REMEDIATION_PLAN.md): tracks transport_agent's
        outbound PCM queue depth so a new turn's filler can be suppressed
        while a previous turn's audio is still draining."""
        try:
            backlog = AudioPlaybackBacklog.model_validate(data)
            self.last_playback_backlog = backlog.queue_depth
        except Exception as e:
            logger.error(f"Error parsing audio playback backlog: {e}")

    async def _on_audio_stop(self, data: dict[str, Any]):
        """Handles confirmed audio stops: cancels in-flight generation for the
        interrupted turn and truncates the last played utterance in history.

        audit/ROADMAP.md P1-4: this is now the single place that reacts to a
        confirmed interrupt -- previously a second, unscoped classifier here
        (`InterruptionClassifier`, regex over every partial) independently
        cancelled generation the instant a keyword matched, racing with
        decision.py's `is_speculative_stop_confirmed` (the arbiter that
        actually decides, using the full utterance and its context -- see
        `CognitivePipeline.execute`'s conflict-resolution stage). Reacting
        here instead means there is exactly one path from "confirmed" to
        "generation cancelled", however the confirmation was reached.
        """
        try:
            stop_msg = AudioStop.model_validate(data)

            # Truncation, and cancelling the turn that was cut off, only
            # happen on confirmed (non-speculative) interrupts -- a
            # speculative duck has not stopped anything yet.
            if not stop_msg.speculative:
                # If this stop was emitted for a new incoming user speech turn to silence
                # the voice agent, do NOT cancel the newly spawned generation task.
                if stop_msg.reason == "confirmed_user_speech":
                    return

                async with self._turn_state_lock:
                    active_turn_id = getattr(self, "_active_response_turn_id", None)
                if (
                    stop_msg.turn_id
                    and active_turn_id
                    and stop_msg.turn_id != active_turn_id
                ):
                    logger.debug(
                        "Ignoring audio stop for stale turn %s; active turn is %s.",
                        stop_msg.turn_id,
                        active_turn_id,
                    )
                    return
                await self._cancel_active_generation(
                    stop_msg.reason or "confirmed audio.stop"
                )
                await self._truncate_interrupted_reply()
        except Exception as e:
            logger.error(f"Error handling audio stop truncation: {e}")

    async def _on_user_voice_properties(self, data: dict[str, Any]):
        """Ingest real-time user voice properties (System 1 feature stream)."""
        try:
            props = UserVoiceProperties.model_validate(data)
            self.last_user_voice_properties = props
            # tempo_wpm is None until the first utterance completes (see
            # contracts.py's own comment) -- formatting it unconditionally
            # would raise on every chunk before that and get silently
            # swallowed below as a "parsing" error, which it is not.
            tempo = f"{props.tempo_wpm:.1f}WPM" if props.tempo_wpm is not None else "—"
            logger.debug(
                f"🎙️ Ingested User Voice | Pitch: {props.pitch_f0:.1f}Hz | Energy: {props.energy_rms:.3f} | Tempo: {tempo}"
            )
        except Exception as e:
            logger.error(f"Error parsing user voice properties: {e}")

    async def _publish_final_chunk_payload(
        self,
        *,
        full_response: str,
        turn_id: str,
        generation_errors: list[str],
        is_proactive: bool,
        incoming_metadata: dict[str, Any] | None,
        incoming_latency_metadata: dict[str, Any] | None,
    ) -> None:
        """Publish the turn's terminal chat.output chunk, if there's
        anything worth sending (a proactive turn with nothing generated
        stays silent rather than publishing an empty message)."""
        if not (full_response.strip() or not is_proactive):
            return
        state_snap = self.cognitive_core.state.get_context_snapshot()
        output_msg = self.coordinator.create_chunk_payload(
            state_snap=state_snap,
            turn_id=turn_id,
            done=True,
            full_response=full_response,
            generation_error=generation_errors[-1] if generation_errors else None,
            proactive=is_proactive,
            user_distance=self.last_user_distance,
        )
        output_msg.metadata = incoming_metadata
        output_msg.latency_metadata = incoming_latency_metadata
        await self.publish(Topics.CHAT_OUTPUT, output_msg.model_dump())

    async def _publish_stream_error_fallback(
        self,
        error: Exception,
        *,
        turn_id: str,
        incoming_metadata: dict[str, Any] | None,
        incoming_latency_metadata: dict[str, Any] | None,
    ) -> None:
        """Recovery path for `_stream_to_speech`'s outer exception handler,
        for a non-proactive turn only (the caller checks `is_proactive`).

        P4-2: deliberately untracked (no character_offset/word_index) --
        unlike the empty-generation fallback, the caller's `full_response`
        is NOT reassigned to `fallback_text` here, and it will set
        `last_assistant_response` to whatever partial `full_response`
        `_stream_to_speech` returns, not to `fallback_text`. Stamping this
        chunk's audio against `fallback_text` would produce an offset that
        indexes into a string `last_assistant_response` never actually holds
        -- a pre-existing gap (that mismatch exists whether or not this
        chunk carries progress metadata), not one to paper over with a
        fabricated-looking offset.
        """
        fallback_text = "I'm having trouble thinking right now..."
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
            generation_error=str(error),
            user_distance=self.last_user_distance,
        )
        output_msg.metadata = incoming_metadata
        output_msg.latency_metadata = incoming_latency_metadata
        await self.publish(Topics.CHAT_OUTPUT, output_msg.model_dump())

    async def _stream_to_speech(
        self,
        generator,
        turn_id: str,
        is_proactive: bool = False,
        incoming_metadata: dict[str, Any] | None = None,
        incoming_latency_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Helper method to process text generation streams and segment them into speech chunks."""
        full_response = ""
        current_chunk_words: list[str] = []
        segment_started_at = None
        generation_errors: list[str] = []
        fallback_text = "I'm having trouble thinking right now..."
        # P4-2: cumulative word count across every chunk published so far
        # this turn, used to derive each chunk's (character_offset,
        # word_index) into `source_text`. Correct regardless of exactly when
        # `full_response` was last extended relative to a given flush,
        # because every word that ever enters `current_chunk_words` came
        # from a `chunk_text` already appended to `full_response` -- the
        # published word sequence is always a prefix of `full_response`'s
        # own word sequence.
        published_word_count = 0

        async def _publish_tracked(words: list[str], source_text: str) -> None:
            nonlocal published_word_count
            new_word_count = published_word_count + len(words)
            offset = _char_offset_after_word(source_text, new_word_count)
            await self._publish_speech_chunk(
                words,
                turn_id,
                incoming_metadata=incoming_metadata,
                incoming_latency_metadata=incoming_latency_metadata,
                character_offset=offset,
                word_index=new_word_count,
            )
            published_word_count = new_word_count

        async def _handle_content_output(chunk_text: str) -> None:
            nonlocal full_response, current_chunk_words, segment_started_at
            await self.set_state("speaking")
            # Bucket 5 follow-up (VOICE_REMEDIATION_PLAN.md): a live capture
            # showed "Aniket" arriving as three separate stream fragments
            # ("An", "ik", "et") with no space between them -- Ollama's raw
            # token stream can emit a continuation sub-word with no leading
            # space of its own, and chunk_text.split() below has no way to
            # know that unless checked here first. Computed before the
            # append, since this is exactly the boundary a missing space
            # would sit at: neither this chunk's first character nor the
            # text-so-far's last character is whitespace.
            boundary_missing_space = bool(
                chunk_text
                and not chunk_text[0].isspace()
                and full_response
                and not full_response[-1].isspace()
            )
            full_response += chunk_text
            if not is_proactive:
                # P2-14/M1-A14: this fires once per streamed chunk, so
                # contention is rare, but an uncontended asyncio.Lock
                # acquire/release is cheap and correctness here matters
                # more than the microscopic saving from skipping it.
                async with self._turn_state_lock:
                    self.last_assistant_response = full_response

            now_monotonic = time.perf_counter()
            if (
                current_chunk_words
                and segment_started_at is not None
                and (now_monotonic - segment_started_at)
                >= self.coordinator.formation_buffer_s
                and len(current_chunk_words) >= 3
            ):
                await _publish_tracked(current_chunk_words, full_response)
                current_chunk_words = []
                segment_started_at = None

            words = chunk_text.split()
            if boundary_missing_space and current_chunk_words and words:
                # The buffer still holds the word this fragment continues
                # (it was not just flushed by the timer check above) --
                # glue rather than let .split() invent a word-break that
                # was never in the original text.
                current_chunk_words[-1] += words[0]
                words = words[1:]
                # The merge may have added punctuation this fragment
                # carried (e.g. "Anik" + "et," -> "Aniket,") that changes
                # whether this word is now a split point.
                score = self.coordinator.segmenter.score_split_point(
                    current_chunk_words[-1], len(current_chunk_words)
                )
                if score >= 0.7 or len(current_chunk_words) > 12:
                    await _publish_tracked(current_chunk_words, full_response)
                    current_chunk_words = []
                    segment_started_at = None

            for word in words:
                if not current_chunk_words:
                    segment_started_at = time.perf_counter()
                current_chunk_words.append(word)

                score = self.coordinator.segmenter.score_split_point(
                    word, len(current_chunk_words)
                )
                # Bucket 5 (VOICE_REMEDIATION_PLAN.md): comma/colon/semicolon
                # (0.4) plus the length-pressure term at or past target_size
                # (0.3) sums to exactly 0.7, which a strict `>` can never
                # satisfy -- the single most natural prosodic boundary
                # (Goldman-Eisler juncture) could never fire on its own.
                if score >= 0.7 or len(current_chunk_words) > 12:
                    await _publish_tracked(current_chunk_words, full_response)
                    current_chunk_words = []
                    segment_started_at = None

        await self.set_state("thinking")

        try:
            async for output in generator:
                if output["type"] == "content":
                    await _handle_content_output(output["data"])

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
                        await _publish_tracked(current_chunk_words, full_response)
                        current_chunk_words = []

                    if not full_response.strip() and not is_proactive:
                        logger.error(
                            "[Brain] Empty generation on turn_id=%s. errors=%s. Emitting fallback.",
                            turn_id,
                            generation_errors[-3:],
                        )
                        full_response = fallback_text
                        await _publish_tracked(fallback_text.split(), full_response)

                    await self._publish_final_chunk_payload(
                        full_response=full_response,
                        turn_id=turn_id,
                        generation_errors=generation_errors,
                        is_proactive=is_proactive,
                        incoming_metadata=incoming_metadata,
                        incoming_latency_metadata=incoming_latency_metadata,
                    )

        except Exception as e:
            logger.error("Cognitive Loop error on turn_id=%s: %s", turn_id, e)
            if not is_proactive:
                await self._publish_stream_error_fallback(
                    e,
                    turn_id=turn_id,
                    incoming_metadata=incoming_metadata,
                    incoming_latency_metadata=incoming_latency_metadata,
                )

        await self.set_state("idle")
        return full_response

    async def _publish_speech_chunk(
        self,
        words: list[str],
        turn_id: str | None = None,
        incoming_metadata: dict[str, Any] | None = None,
        incoming_latency_metadata: dict[str, Any] | None = None,
        character_offset: int | None = None,
        word_index: int | None = None,
    ):
        """
        Publishes a semantically coherent chunk with full PAD affect metadata.
        Implements the Brain→Voice contract from psychological_layer.md §5.3.
        """
        text = " ".join(words).strip()
        if not text:
            return

        # Built by the coordinator, which is where every other chunk on this
        # subject is built. This method used to re-derive the affect vector
        # inline — the same eight `state_snap.get(...)` lines with the same
        # defaults — so the wire contract had two implementations and a change
        # to one silently produced streams whose chunks disagreed with their own
        # `done` message. Exactly the drift that put prosody in this state to
        # begin with, one layer up.
        payload = self.coordinator.create_chunk_payload(
            words=words,
            state_snap=self.cognitive_core.state.get_context_snapshot(),
            turn_id=turn_id,
            user_distance=self.last_user_distance,
        )
        # P4-2: non-destructive merge -- `incoming_metadata` originates from
        # the user's own chat.input and must reach voice/transport unchanged;
        # this only adds two keys alongside it. voice-agent passes them
        # through unchanged on every PCM chunk it publishes for this text, and
        # transport_agent relays them as `audio.playback.progress` once that
        # PCM has actually reached the LiveKit audio source -- the closest
        # observable "reached the speaker" point in this architecture.
        # Deliberately omitted (None) for the one caller that cannot make
        # them meaningful (see _stream_to_speech's exception-handler
        # fallback) -- absent metadata is honest; a fabricated offset is not.
        if character_offset is not None and word_index is not None:
            metadata = dict(incoming_metadata) if incoming_metadata else {}
            metadata["character_offset"] = character_offset
            metadata["word_index"] = word_index
            payload.metadata = metadata
        else:
            payload.metadata = incoming_metadata
        payload.latency_metadata = incoming_latency_metadata
        await self.publish(Topics.CHAT_OUTPUT, payload.model_dump())

    async def stop(self):
        """P3-4: brain_agent owns the most resources of any agent in the
        mesh (the LLM client, the graph driver, two DB pools, the whole
        cognitive core) and used to close none of them -- the exact "owns
        the most, cleans up least" asymmetry this item names. Cancel first,
        close second: an in-flight generation still holding `memory_store`/
        `graph_db` must stop before those are torn out from under it.
        """
        await self._prepare_stop()
        async with self._generation_lock:
            task = self._active_generation_task
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception(
                        "Active generation task raised while being cancelled"
                    )

        self.cognitive_core.close()

        for resource, label in (
            (self.ollama, "LLMClient"),
            (self.graph_db, "GraphDB"),
            (self.memory_store, "MemoryStore"),
            (self.conversation_store, "ConversationHistoryStore"),
        ):
            if resource is None:
                continue
            try:
                await resource.close()
            except Exception as e:
                logger.warning(f"[Brain] {label} close warning: {e}")

        await super().stop()
        logger.info(f"🧠 {self.name} Offline.")


async def main():
    if Config.RUNTIME_AUTO_BOOTSTRAP:
        logger.info("[Brain] Running runtime bootstrap checks...")
        await bootstrap_runtime()

    # 1. Initialize AI Friend Foundation (Pool-based logic)
    conversation_store = ConversationHistoryStore()
    await conversation_store.initialize()  # Creates the database pool

    graph_db = GraphDB()
    await graph_db.initialize()
    # Inject the established pool and graph_db into MemoryStore
    memory_store = MemoryStore(pool=conversation_store.pool, graph_db=graph_db)

    # 2. Instantiate Brain Agent with injected dependencies
    agent = BrainAgent(
        ollama_url=Config.OLLAMA_URL,
        graph_db=graph_db,
        memory_store=memory_store,
        conversation_store=conversation_store,
    )

    await agent.start()

    shutdown_trigger = asyncio.Event()
    install_shutdown_signal_handlers(shutdown_trigger)
    await shutdown_trigger.wait()
    await agent.stop()


if __name__ == "__main__":
    setup_logging(level=logging.INFO, json_format=getattr(Config, "LOG_JSON", False))
    asyncio.run(main())
