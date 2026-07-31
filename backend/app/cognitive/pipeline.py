import logging
import math
from collections.abc import AsyncGenerator
from typing import Any

from ..contracts import StateUpdate

logger = logging.getLogger(__name__)

# --- Endocrine channels ---------------------------------------------------
# Until now both hormones had a release API and almost nothing calling it: one
# channel (somatic comfort recognition) for dopamine and none at all for
# cortisol. A hormone with no channel is only a formula, so these are the
# events that actually move them.
#
# The reward channel is *prediction error*, not outcome. Firing a burst on any
# good turn would double-count what tonic dopamine already tracks -- the tonic
# term is valence x arousal, and a good turn raises valence by itself. Phasic
# dopamine is supposed to signal "better than I expected", per the Schultz
# reward-prediction-error work the `dopamine_phasic` docstring cites. The
# reappraisal module was already computing exactly that quantity and throwing
# it away after using it to tune weights.
#
# Scaled well below 1.0: a single surprising turn should colour the next few
# minutes, not saturate the hormone. Deliberately asymmetric -- the stress
# response to a turn going badly is stronger than the reward for one going
# well, which is the standard negativity bias and also the safer failure mode
# for a system whose cortisol narrows its own sampling temperature.
REWARD_PREDICTION_GAIN = 0.35
STRESS_PREDICTION_GAIN = 0.45
# Below this, a prediction error is noise rather than surprise. Reappraisal
# already ignores |delta| < 0.1 for weight updates; matching that keeps one
# definition of "significant" instead of two that can drift apart.
PREDICTION_ERROR_DEADBAND = 0.1
# A self-correction means the agent caught itself about to violate its own
# identity constraints mid-sentence. Fixed rather than scaled: the severity of
# a violation is not something the metacognitive check reports, and inventing a
# magnitude for it would be false precision.
SELF_CORRECTION_STRESS = 0.3


class CognitivePipeline:
    """
    Pure Logic Pipeline for the Cognitive Loop.
    Transport-agnostic (Zero NATS/HTTP dependencies).

    Pipeline (psychological_layer.md System Principle):
        Signal -> Perception -> Appraisal -> State Update -> Decision -> Action -> Learning
    """

    def __init__(
        self,
        perception,
        appraisal,
        state,
        decision,
        action,
        learning,
        identity,
        llm_service=None,
        reappraisal=None,
    ):
        self.perception = perception
        self.appraisal = appraisal
        self.state = state
        self.decision = decision
        self.action = action
        self.learning = learning
        self.identity = identity
        self.llm = llm_service
        self.reappraisal = reappraisal
        self._system2_task = None

    async def execute(
        self, raw_event: dict[str, Any], surfaced_memories: list[dict[str, Any]] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Executes the master cognitive loop.
        Yields events/chunks for the agent wrapper to handle.
        """
        import time

        stage_times = {}

        # 1. Extraction & Metadata
        t_start = time.perf_counter()
        raw_event_type = raw_event.get("event_type") or raw_event.get("type")
        event_metadata = raw_event.get("metadata", {})
        if not isinstance(event_metadata, dict):
            event_metadata = {}
        stage_times["stage_1_extraction_ms"] = (time.perf_counter() - t_start) * 1000.0

        # VAP Turn Planning / Speculative Pre-Generation
        is_partial = raw_event.get("is_partial", False)
        vap_prob = raw_event.get(
            "vap_probability", event_metadata.get("vap_probability", 0.0)
        )
        is_vap_event = raw_event_type == "VAP_SIGNAL"

        if is_partial or is_vap_event:
            if vap_prob < 0.7:
                logger.debug(
                    f"[Pipeline] Partial input/VAP but probability {vap_prob:.2f} < 0.7. Skipping speculative pre-generation."
                )
                return
            else:
                logger.info(
                    f"[Pipeline] VAP threshold met ({vap_prob:.2f} >= 0.7). Triggering speculative pre-generation."
                )
                event_metadata["speculative"] = True
                yield {
                    "type": "mesh_signal",
                    "subject": "audio.pre_generate",
                    "data": {
                        "speculative": True,
                        "partial_content": raw_event.get("content", ""),
                        "vap_probability": vap_prob,
                    },
                }

        # 2. Conflict Resolution (Turn-Taking Stability)
        t_start = time.perf_counter()
        conflict_resolved = False
        if raw_event_type == "USER_MESSAGE" and not raw_event.get("is_partial"):
            final_text = raw_event.get("content", "")
            speculative_intent = self.state.last_speculative_intent

            if speculative_intent:
                confirmed = self.decision.is_speculative_stop_confirmed(
                    final_text,
                    speculative_intent.get("keywords"),
                )
                self.state.last_speculative_intent = None

                if not confirmed:
                    logger.info(
                        "[Pipeline] Interruption REJECTED. Resuming playback..."
                    )
                    stage_times["stage_2_conflict_resolution_ms"] = (
                        time.perf_counter() - t_start
                    ) * 1000.0
                    yield {
                        "type": "mesh_signal",
                        "subject": "audio.resume",
                        "data": {
                            "reason": "conflict_rejected",
                            "perception_text": speculative_intent.get("text", ""),
                            "utterance_id": speculative_intent.get("utterance_id"),
                        },
                    }
                    conflict_resolved = True
                else:
                    logger.info("[Pipeline] Interruption CONFIRMED. Stopping playback.")
                    stage_times["stage_2_conflict_resolution_ms"] = (
                        time.perf_counter() - t_start
                    ) * 1000.0
                    yield {
                        "type": "mesh_signal",
                        "subject": "audio.stop",
                        "data": {
                            "interrupt": True,
                            "speculative": False,
                            "reason": "confirmed_command",
                            "command_text": final_text,
                            "keywords": speculative_intent.get("keywords", []),
                            "utterance_id": speculative_intent.get("utterance_id"),
                            "turn_id": event_metadata.get("turn_id"),
                        },
                    }
                    conflict_resolved = True
                    yield {"type": "pipeline_telemetry", "data": stage_times}
                    return
        if not conflict_resolved:
            stage_times["stage_2_conflict_resolution_ms"] = (
                time.perf_counter() - t_start
            ) * 1000.0

        # 3. Sequential Perception
        t_start = time.perf_counter()
        event = await self.perception.perceive(raw_event)
        stage_times["stage_3_perception_ms"] = (time.perf_counter() - t_start) * 1000.0
        if event_metadata.get("speculative"):
            if event.metadata is None:
                event.metadata = {}
            event.metadata["speculative"] = True

        # 4. Appraisal (§1 — OCC/Lazarus/EMA)
        t_start = time.perf_counter()
        state_snapshot = self.state.get_context_snapshot()
        emotional_bias = state_snapshot.get("mood", 0.0)
        user_voice_properties = raw_event.get("user_voice_properties")
        appraisal_vector = self.appraisal.appraise(
            event_content=event.raw_content,
            event_type=event.event_type,
            emotional_bias=emotional_bias,
            state_snapshot=state_snapshot,
            identity_boundaries=self.identity.personality.get("boundaries", []),
            user_voice_properties=user_voice_properties,
        )
        stage_times["stage_4_appraisal_ms"] = (time.perf_counter() - t_start) * 1000.0
        yield {"type": "appraisal", "data": appraisal_vector}

        # 5. State Update via Appraisal (§2.3 — ALMA mood-pull)
        t_start = time.perf_counter()
        if event.event_type == "USER_MESSAGE":
            # Reappraisal outcome evaluation
            if self.reappraisal:
                acoustic_delta = 0.0
                if (
                    isinstance(event_metadata, dict)
                    and "acoustic_metadata" in event_metadata
                ):
                    acoustic_delta = event_metadata["acoustic_metadata"].get(
                        "emotion_bias", 0.0
                    )
                elif "acoustic_metadata" in raw_event:
                    acoustic_delta = raw_event["acoustic_metadata"].get(
                        "emotion_bias", 0.0
                    )

                actual_text_valence = appraisal_vector.goal_congruence
                tom = event.metadata.get("tom_inferences", {}) if event.metadata else {}
                if isinstance(tom, dict) and "inferred_valence" in tom:
                    actual_text_valence = tom["inferred_valence"]

                prediction_error = await self.reappraisal.evaluate_outcome(
                    actual_text_valence=actual_text_valence,
                    acoustic_delta=acoustic_delta,
                    behavioral_signal=0.5,
                )
                await self._apply_reward_prediction_error(prediction_error)

            # Pre-Decision Vocabulary Update (zero LLM overhead concepts indexing)
            await self.state.update_theory_of_mind(event.raw_content)

            weights = self.reappraisal.get_weights() if self.reappraisal else None
            await self.state.update_from_appraisal(appraisal_vector, weights=weights)

            # Trigger System 2 deep appraisal in background (non-blocking).
            # A2: cancel any still-running prior appraisal so overlapping tasks
            # cannot clobber each other's writes to short-term affect.
            if self.llm:
                import asyncio

                if self._system2_task and not self._system2_task.done():
                    self._system2_task.cancel()
                self._system2_task = asyncio.create_task(
                    self._async_system2_appraisal(event.raw_content)
                )

            state_snapshot = self.state.get_context_snapshot()
            stage_times["stage_5_state_update_ms"] = (
                time.perf_counter() - t_start
            ) * 1000.0
            yield {
                "type": "mesh_signal",
                "subject": "state.update",
                "data": StateUpdate.from_snapshot(state_snapshot).model_dump(),
            }
        else:
            stage_times["stage_5_state_update_ms"] = (
                time.perf_counter() - t_start
            ) * 1000.0

        # 6. Decision (BT + MAUT)
        t_start = time.perf_counter()
        state_directive = self.state.get_behavioral_directive()
        if surfaced_memories:
            event.metadata["surfaced_memories"] = surfaced_memories
        event.metadata["appraisal"] = appraisal_vector.to_dict()

        plan = await self.decision.decide(event, state_snapshot)

        if self.reappraisal:
            self.reappraisal.record_pre_response_state(state_snapshot)
            self.reappraisal.record_expected_outcome(
                plan.goal, state_snapshot.get("mood", 0.0)
            )

        # Post-Decision ToM Application: ingest LLM-inferred parameters to state
        if event.event_type == "USER_MESSAGE":
            tom_inferences = event.metadata.get("tom_inferences")
            if tom_inferences:
                await self.state.update_theory_of_mind(
                    event.raw_content, tom_inferences
                )
                state_snapshot = self.state.get_context_snapshot()
                yield {
                    "type": "mesh_signal",
                    "subject": "state.update",
                    "data": StateUpdate.from_snapshot(state_snapshot).model_dump(),
                }
        stage_times["stage_6_decision_ms"] = (time.perf_counter() - t_start) * 1000.0

        # 7. Action Preparation
        t_start = time.perf_counter()
        plan.payload["identity_prompt"] = self.identity.get_persona_prompt(
            state_directive
        )
        plan.payload["cortisol"] = state_snapshot.get("cortisol", 0.5)
        plan.payload["dopamine"] = state_snapshot.get("dopamine", 0.0)
        plan.payload["fatigue"] = state_snapshot.get("fatigue", 0.0)
        plan.payload["user_mental_model"] = state_snapshot.get("user_mental_model")
        plan.payload["valence"] = state_snapshot.get("mood", 0.0)
        plan.payload["arousal"] = state_snapshot.get("energy", 0.5)
        plan.payload["dominance"] = state_snapshot.get("dominance", 0.5)
        plan.payload["speculative"] = (
            event.metadata.get("speculative", False) if event.metadata else False
        )
        stage_times["stage_7_action_prep_ms"] = (time.perf_counter() - t_start) * 1000.0

        # Calculate Pre-LLM total time
        pre_llm_total = sum(
            [
                stage_times["stage_1_extraction_ms"],
                stage_times["stage_2_conflict_resolution_ms"],
                stage_times["stage_3_perception_ms"],
                stage_times["stage_4_appraisal_ms"],
                stage_times["stage_5_state_update_ms"],
                stage_times["stage_6_decision_ms"],
                stage_times["stage_7_action_prep_ms"],
            ]
        )
        stage_times["pre_llm_total_ms"] = pre_llm_total
        stage_times["heuristic_intent"] = (
            event.metadata.get("heuristic_intent") or event.intent
        )
        stage_times["llm_intent"] = event.intent
        tom_inferences = event.metadata.get("tom_inferences") or {}
        stage_times["inferred_valence"] = tom_inferences.get("inferred_valence")
        stage_times["inferred_arousal"] = tom_inferences.get("inferred_arousal")

        # 8. Action Execution
        t_start = time.perf_counter()
        full_response = ""
        done_chunk = None
        is_spec = plan.payload.get("speculative", False)
        pass_result = {"response": "", "done": None}
        async for chunk in self._stream_action_pass(plan, is_spec, pass_result):
            yield chunk
        full_response = pass_result["response"]
        done_chunk = pass_result["done"]
        stage_times["stage_8_action_execution_ms"] = (
            time.perf_counter() - t_start
        ) * 1000.0

        # 9. Validation & Self-Correction
        t_start = time.perf_counter()
        if full_response:
            is_valid, reason = await self.identity.validate_response(
                full_response, plan.goal
            )
            if not is_valid:
                logger.warning(
                    f"[Identity] Validation failed: {reason}. SELF-CORRECTION."
                )
                plan.payload["identity_prompt"] += (
                    f"\n\nCRITICAL FIX: Your previous response was rejected for: {reason}. Correct this immediately."
                )
                retry_result = {"response": "", "done": None}
                async for chunk in self._stream_action_pass(
                    plan, is_spec, retry_result
                ):
                    yield chunk
                full_response = retry_result["response"]
                done_chunk = retry_result["done"]
        stage_times["stage_9_validation_ms"] = (time.perf_counter() - t_start) * 1000.0

        # 10. Learning + Episodic Memory (§6.1)
        t_start = time.perf_counter()
        if event.intent in ["CHAT", "REMEMBER"] and full_response:
            episode = {
                "id": event.event_id,
                "event": event.raw_content,
                "speaker": raw_event.get("user_id") or "User",
                "context": state_directive,
                "emotion_vector": {
                    "V": self.state.current_state.valence,
                    "Ar": self.state.current_state.arousal,
                    "D": self.state.current_state.dominance,
                },
                "appraisal": appraisal_vector.to_dict(),
                "relationship_delta": appraisal_vector.relationship_impact,
                "intent": event.intent,
                "content": event.raw_content,
                "state": state_snapshot,
                "response": full_response,
            }
            yield {"type": "reflection_needed", "data": [episode]}
        stage_times["stage_10_learning_ms"] = (time.perf_counter() - t_start) * 1000.0

        # Yield gathered stage telemetry
        yield {"type": "pipeline_telemetry", "data": stage_times}

        # Yield the saved done chunk at the very end
        if done_chunk:
            if is_spec:
                done_chunk["speculative"] = True
            yield done_chunk
        else:
            yield {"type": "done", "data": "finished", "speculative": is_spec}

    async def _stream_action_pass(self, plan, is_spec: bool, result: dict):
        """Run one generation pass, yielding what the transport should see.

        The first pass and the self-correction retry were two copies of this
        loop, and they had already drifted: the retry never tagged its chunks
        with `speculative`, so a speculative turn that got self-corrected
        emitted a stream whose chunks disagreed with the plan that produced
        them. Nothing downstream reported it, because a missing key just reads
        as "not speculative".

        Accumulated output goes into `result` rather than a return value —
        this is an async generator, so it cannot both yield chunks and hand
        back the assembled response.
        """
        async for chunk in self.action.execute(plan):
            if is_spec:
                chunk["speculative"] = True
            if chunk["type"] == "content":
                result["response"] += chunk["data"]
            if chunk["type"] == "done":
                result["done"] = chunk
                continue
            # The retry is the likeliest place to trip a second metacognitive
            # violation, since it runs with a hardened prompt after one
            # rejection. Skipping the filter would leak `self_correction` to
            # the transport *and* swallow the cortisol release on the one path
            # that most deserves it.
            if await self._consume_internal_chunk(chunk):
                continue
            yield chunk

    async def _consume_internal_chunk(self, chunk) -> bool:
        """Handle chunks meant for the pipeline itself. True = do not forward.

        Downstream consumers switch on a small set of chunk types, and an
        unrecognised one reaches the transport as a malformed message. These
        are internal signals from the action layer, not output.
        """
        if chunk.get("type") == "self_correction":
            await self._apply_self_correction_stress(chunk.get("data", ""))
            return True
        return False

    async def _apply_reward_prediction_error(self, prediction_error):
        """Turn a reward prediction error into a hormone burst.

        `None` means no comparison was made (reappraisal disabled, no recorded
        expectation, rate limited, or within tolerance) and is *not* the same as
        `0.0`. Treating them alike would fire a burst of zero on every turn the
        module declined to evaluate, which is harmless today only because the
        release methods reject non-positive amounts -- a coincidence, not a
        guarantee, so the distinction is made explicitly here.
        """
        if prediction_error is None:
            return
        try:
            prediction_error = float(prediction_error)
        except (TypeError, ValueError):
            return
        if not math.isfinite(prediction_error):
            return
        if abs(prediction_error) < PREDICTION_ERROR_DEADBAND:
            return

        try:
            if prediction_error > 0:
                await self.state.release_dopamine(
                    min(1.0, prediction_error * REWARD_PREDICTION_GAIN),
                    reason=f"turn exceeded expectation by {prediction_error:.2f}",
                )
            else:
                await self.state.release_cortisol(
                    min(1.0, -prediction_error * STRESS_PREDICTION_GAIN),
                    reason=f"turn fell short of expectation by {-prediction_error:.2f}",
                )
        except Exception as e:
            # An endocrine failure must never take down the turn: the hormone
            # modulates how the agent speaks, it does not decide whether it can.
            logger.warning("[Endocrine] Prediction-error release failed: %s", e)

    async def _apply_self_correction_stress(self, reason: str):
        """Catching yourself mid-violation is a stressor.

        Deliberately fired from the pipeline rather than from `ActionService`,
        which has no `StateService` handle. Action reports what happened; state
        decides the physiological response. Plumbing a mutable state service
        into the action layer to save one event type would invert that.
        """
        try:
            await self.state.release_cortisol(
                SELF_CORRECTION_STRESS, reason=f"self-correction: {reason}"
            )
        except Exception as e:
            logger.warning("[Endocrine] Self-correction release failed: %s", e)

    async def _async_system2_appraisal(self, user_utterance: str):
        try:
            current_pad = {
                "valence": self.state.current_state.valence,
                "arousal": self.state.current_state.arousal,
                "dominance": self.state.current_state.dominance,
            }
            new_pad = await self.appraisal.appraise_semantic_drift(
                user_utterance, self.llm, current_pad
            )
            # Update state with drifted mood values under the state lock (A2)
            # so this background write cannot race the synchronous appraisal path.
            await self.state.apply_semantic_appraisal(new_pad)
            logger.info(
                "[System 2 Appraisal] Mood drifted: V=%.2f, Ar=%.2f, D=%.2f",
                self.state.current_state.valence,
                self.state.current_state.arousal,
                self.state.current_state.dominance,
            )
        except Exception as e:
            logger.error(
                f"[System 2 Appraisal] Background semantic appraisal failed: {e}"
            )
