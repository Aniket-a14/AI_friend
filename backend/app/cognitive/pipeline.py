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
        self, perception, appraisal, state, decision, action, learning, identity
    ):
        self.perception = perception
        self.appraisal = appraisal
        self.state = state
        self.decision = decision
        self.action = action
        self.learning = learning
        self.identity = identity

    async def execute(
        self, raw_event: Dict[str, Any], surfaced_memories: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the master cognitive loop.
        Yields events/chunks for the agent wrapper to handle.
        """
        # 1. Extraction & Metadata
        raw_event_type = raw_event.get("event_type") or raw_event.get("type")
        event_metadata = raw_event.get("metadata", {})
        if not isinstance(event_metadata, dict):
            event_metadata = {}

        # 2. Conflict Resolution (Turn-Taking Stability)
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
                    yield {
                        "type": "mesh_signal",
                        "subject": "audio.resume",
                        "data": {
                            "reason": "conflict_rejected",
                            "perception_text": speculative_intent.get("text", ""),
                            "utterance_id": speculative_intent.get("utterance_id"),
                        },
                    }
                else:
                    logger.info("[Pipeline] Interruption CONFIRMED. Stopping playback.")
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
                    return

        # 3. Sequential Perception
        event = await self.perception.perceive(raw_event)

        # 4. Appraisal (§1 — OCC/Lazarus/EMA)
        state_snapshot = self.state.get_context_snapshot()
        emotional_bias = state_snapshot.get("mood", 0.0)
        appraisal_vector = self.appraisal.appraise(
            event_content=event.raw_content,
            event_type=event.event_type,
            emotional_bias=emotional_bias,
            state_snapshot=state_snapshot,
            identity_boundaries=self.identity.personality.get("boundaries", []),
        )
        yield {"type": "appraisal", "data": appraisal_vector}

        # 5. State Update via Appraisal (§2.3 — ALMA mood-pull)
        if event.event_type == "USER_MESSAGE":
            # Pre-Decision Vocabulary Update (zero LLM overhead concepts indexing)
            await self.state.update_theory_of_mind(event.raw_content)
            
            await self.state.update_from_appraisal(appraisal_vector)
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

        # 6. Decision (BT + MAUT)
        state_directive = self.state.get_behavioral_directive()
        if surfaced_memories:
            event.metadata["surfaced_memories"] = surfaced_memories
        event.metadata["appraisal"] = appraisal_vector.to_dict()

        plan = await self.decision.decide(event, state_snapshot)

        # Post-Decision ToM Application: ingest LLM-inferred parameters to state
        if event.event_type == "USER_MESSAGE":
            tom_inferences = event.metadata.get("tom_inferences")
            if tom_inferences:
                await self.state.update_theory_of_mind(event.raw_content, tom_inferences)
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

        # 7. Action Preparation
        plan.payload["identity_prompt"] = self.identity.get_persona_prompt(
            state_directive
        )
        plan.payload["cortisol"] = state_snapshot.get("cortisol", 0.5)
        plan.payload["dopamine"] = state_snapshot.get("dopamine", 0.0)
        plan.payload["fatigue"] = state_snapshot.get("fatigue", 0.0)
        plan.payload["user_mental_model"] = state_snapshot.get("user_mental_model")

        # 8. Action Execution
        full_response = ""
        async for chunk in self.action.execute(plan):
            if chunk["type"] == "content":
                full_response += chunk["data"]
            yield chunk

        # 9. Validation & Self-Correction
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
                async for chunk in self.action.execute(plan):
                    if chunk["type"] == "content":
                        full_response += chunk["data"]
                    yield chunk

        # 10. Learning + Episodic Memory (§6.1)
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
