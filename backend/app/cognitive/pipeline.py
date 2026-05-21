import logging
from typing import Dict, Any, AsyncGenerator, List

logger = logging.getLogger(__name__)


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
    ):
        self.perception = perception
        self.appraisal = appraisal
        self.state = state
        self.decision = decision
        self.action = action
        self.learning = learning
        self.identity = identity
        self.llm = llm_service
        self._system2_task = None

    async def execute(
        self, raw_event: Dict[str, Any], surfaced_memories: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
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

        # 4. Appraisal (§1 — OCC/Lazarus/EMA)
        t_start = time.perf_counter()
        state_snapshot = self.state.get_context_snapshot()
        emotional_bias = state_snapshot.get("mood", 0.0)
        appraisal_vector = self.appraisal.appraise(
            event_content=event.raw_content,
            event_type=event.event_type,
            emotional_bias=emotional_bias,
            state_snapshot=state_snapshot,
            identity_boundaries=self.identity.personality.get("boundaries", []),
        )
        stage_times["stage_4_appraisal_ms"] = (time.perf_counter() - t_start) * 1000.0
        yield {"type": "appraisal", "data": appraisal_vector}

        # 5. State Update via Appraisal (§2.3 — ALMA mood-pull)
        t_start = time.perf_counter()
        if event.event_type == "USER_MESSAGE":
            # Pre-Decision Vocabulary Update (zero LLM overhead concepts indexing)
            await self.state.update_theory_of_mind(event.raw_content)

            await self.state.update_from_appraisal(appraisal_vector)

            # Trigger System 2 deep appraisal in background (non-blocking)
            if self.llm:
                import asyncio

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
                "data": {
                    "mood": state_snapshot.get("mood", 0.0),
                    "energy": state_snapshot.get("energy", 0.5),
                    "dominance": state_snapshot.get("dominance", 0.5),
                    "trust": state_snapshot.get("trust", 0.5),
                    "attachment": state_snapshot.get("attachment", 0.1),
                    "emotion": state_snapshot.get("emotion", "neutral"),
                    "interaction_count": state_snapshot.get("interaction_count", 0),
                    "cortisol": state_snapshot.get("cortisol", 0.0),
                    "dopamine": state_snapshot.get("dopamine", 0.0),
                    "fatigue": state_snapshot.get("fatigue", 0.0),
                    "user_mental_model": state_snapshot.get("user_mental_model"),
                },
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
                    "data": {
                        "mood": state_snapshot.get("mood", 0.0),
                        "energy": state_snapshot.get("energy", 0.5),
                        "dominance": state_snapshot.get("dominance", 0.5),
                        "trust": state_snapshot.get("trust", 0.5),
                        "attachment": state_snapshot.get("attachment", 0.1),
                        "emotion": state_snapshot.get("emotion", "neutral"),
                        "interaction_count": state_snapshot.get("interaction_count", 0),
                        "cortisol": state_snapshot.get("cortisol", 0.0),
                        "dopamine": state_snapshot.get("dopamine", 0.0),
                        "fatigue": state_snapshot.get("fatigue", 0.0),
                        "user_mental_model": state_snapshot.get("user_mental_model"),
                    },
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
        async for chunk in self.action.execute(plan):
            if chunk["type"] == "content":
                full_response += chunk["data"]
            if chunk["type"] == "done":
                done_chunk = chunk
                continue
            yield chunk
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
                full_response = ""
                done_chunk = None
                async for chunk in self.action.execute(plan):
                    if chunk["type"] == "content":
                        full_response += chunk["data"]
                    if chunk["type"] == "done":
                        done_chunk = chunk
                        continue
                    yield chunk
        stage_times["stage_9_validation_ms"] = (time.perf_counter() - t_start) * 1000.0

        # 10. Learning + Episodic Memory (§6.1)
        t_start = time.perf_counter()
        if event.intent in ["CHAT", "REMEMBER"] and full_response:
            episode = {
                "id": event.event_id,
                "event": event.raw_content,
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
            yield done_chunk
        else:
            yield {"type": "done", "data": "finished"}

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
            # Update state with drifted mood values
            self.state.current_state.valence = new_pad["valence"]
            self.state.current_state.arousal = new_pad["arousal"]
            self.state.current_state.dominance = new_pad["dominance"]
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
