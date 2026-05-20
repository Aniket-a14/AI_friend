import asyncio
import logging
import time
from typing import Dict, Any, AsyncGenerator
from .decision import ActionPlan
from ..config import Config

logger = logging.getLogger(__name__)


class ControlMarkupSanitizer:
    """Drops unsupported control tags while preserving timing markers."""

    def __init__(self):
        self._pending = ""

    def feed(self, chunk: str) -> str:
        data = f"{self._pending}{chunk}"
        self._pending = ""
        cleaned = []
        idx = 0

        while idx < len(data):
            if data[idx] != "<":
                cleaned.append(data[idx])
                idx += 1
                continue

            end_idx = data.find(">", idx + 1)
            if end_idx == -1:
                self._pending = data[idx:]
                break

            tag = data[idx : end_idx + 1]
            normalized = tag.strip().lower()
            if normalized.startswith("<emotion") or normalized == "</emotion>":
                idx = end_idx + 1
                continue

            cleaned.append(tag)
            idx = end_idx + 1

        return "".join(cleaned)

    def flush(self) -> str:
        pending = self._pending
        self._pending = ""
        normalized = pending.strip().lower()
        if normalized.startswith("<emotion") or normalized == "</emotion>":
            return ""
        return pending


class ActionService:
    """
    The Action Layer.
    Executes the Decision Plan by generating responses or performing system tasks.
    Enforces the Identity Protocol in LLM generations.
    """

    def __init__(self, llm_service=None, memory_store=None):
        self.llm = llm_service
        self.memory = memory_store

    async def execute(self, plan: ActionPlan) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the plan and yields output chunks.
        """
        logger.info(
            f"[Action] Executing Decision: {plan.action_type} for Goal: {plan.goal}"
        )

        if plan.action_type == "RESPOND_CHAT":
            # 1. Prepare Identity-Aware Prompt
            msg = plan.payload.get("message", "")
            identity_prompt = plan.payload.get("identity_prompt", "You are my friend.")
            emotion = plan.payload.get("emotion_state", "neutral")

            model = plan.payload.get("model")

            # Contextual Enrichments
            surfaced = plan.payload.get("surfaced_memories", [])
            shared_history = ""
            if surfaced:
                shared_history = (
                    "\nSHARED HISTORY / RECENT CONTEXT (Active Influence):\n"
                    + "\n".join([f"- {m['content']}" for m in surfaced])
                )

            # Theory of Mind (ToM) Context Injection
            tom_context = ""
            user_tom = plan.payload.get("user_mental_model")
            if user_tom:
                inferred_val = user_tom.get("inferred_valence", 0.0)
                inferred_ar = user_tom.get("inferred_arousal", 0.5)
                impl_goals = user_tom.get("implied_goals", [])
                # Take the last 10 known concepts to keep it concise and avoid context bloat
                known_con = user_tom.get("known_concepts", [])[-10:]
                
                tom_context = "\n\nYour Inferred Perspective of the User (Theory of Mind):\n"
                tom_context += f"- User Inferred Valence: {inferred_val:.2f} (Scale: -1.0 to 1.0)\n"
                tom_context += f"- User Inferred Arousal: {inferred_ar:.2f} (Scale: 0.0 to 1.0)\n"
                if impl_goals:
                    tom_context += f"- User Implied Goals: {', '.join(impl_goals)}\n"
                if known_con:
                    tom_context += f"- User Known Concepts (Respect this knowledge boundary): {', '.join(known_con)}\n"

            # 1. Prepare Identity-Aware System and User Prompts
            # Static System Prompt (cached by inference engines like Ollama/vLLM)
            system_instruction = f"{identity_prompt}\n\nGuideline:\n- Maintain your identity rules at all times.\n- Focus on short, natural conversational phrases.\n- Respond only in English. Do not use Hindi, Hinglish, or any other language for now.\n- The voice layer already carries emotion separately. Do not emit XML wrappers or emotion tags.\n- You may use <pause=300ms> or <hesitate> when it improves natural timing."

            # Dynamic User Prompt (appends active context to the query suffix)
            user_prompt = f"Current Context:\n- Goal: {plan.goal}\n- Current Emotion: {emotion}\n{shared_history}{tom_context}\n\nUser: {msg}\nAssistant:"

            try:
                # 2. Endocrine System: Calculate physiological LLM parameters
                # Cortisol (stress) → inversely controls temperature
                # Dopamine (reward) → controls top_p exploration
                # Fatigue (sleepiness) → restricts response length (terser replies)
                endocrine_options = None
                cortisol = plan.payload.get("cortisol")
                dopamine = plan.payload.get("dopamine")
                fatigue = plan.payload.get("fatigue")

                if cortisol is not None or dopamine is not None or fatigue is not None:
                    endocrine_options = {}
                    if cortisol is not None:
                        try:
                            val = float(cortisol)
                            endo_temperature = max(
                                0.0, min(1.0, round(0.9 - (val * 0.6), 3))
                            )
                        except (ValueError, TypeError):
                            endo_temperature = 0.7
                        endocrine_options["temperature"] = endo_temperature
                    else:
                        endocrine_options["temperature"] = 0.7

                    if dopamine is not None:
                        try:
                            val = float(dopamine)
                            endo_top_p = max(
                                0.0, min(1.0, round(0.70 + (val * 0.25), 3))
                            )
                        except (ValueError, TypeError):
                            endo_top_p = 0.8
                        endocrine_options["top_p"] = endo_top_p
                    else:
                        endocrine_options["top_p"] = 0.8

                    try:
                        fatigue_val = max(
                            0.0,
                            min(1.0, float(fatigue if fatigue is not None else 0.0)),
                        )
                    except (ValueError, TypeError):
                        fatigue_val = 0.0

                    # Bounded num_predict strictly between 15 (exhausted) and 40 (fresh)
                    endo_num_predict = int(
                        max(15, min(40, int(40 - (fatigue_val * 25))))
                    )
                    endocrine_options["num_predict"] = endo_num_predict

                    logger.info(
                        "[Endocrine] Cortisol=%s Dopamine=%s Fatigue=%s → temp=%.3f top_p=%.3f num_predict=%d",
                        cortisol,
                        dopamine,
                        fatigue,
                        endocrine_options["temperature"],
                        endocrine_options["top_p"],
                        endocrine_options["num_predict"],
                    )

                # 3. Stream Generation
                sanitizer = ControlMarkupSanitizer()
                stream_budget = max(
                    15, int(getattr(Config, "LLM_STREAM_MAX_SECONDS", 120))
                )
                try:
                    stream_iter = self.llm.generate_stream(
                        prompt=user_prompt,
                        system=system_instruction,
                        model=model,
                        options_override=endocrine_options,
                    ).__aiter__()
                    deadline = time.monotonic() + stream_budget

                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise asyncio.TimeoutError()

                        try:
                            chunk = await asyncio.wait_for(
                                stream_iter.__anext__(), timeout=remaining
                            )
                        except StopAsyncIteration:
                            break

                        clean_chunk = sanitizer.feed(chunk)
                        if clean_chunk:
                            yield {"type": "content", "data": clean_chunk}

                    trailing = sanitizer.flush()
                    if trailing:
                        yield {"type": "content", "data": trailing}
                    yield {"type": "done", "data": "finished"}
                except asyncio.TimeoutError:
                    logger.warning(
                        "[Action] Stream timed out after %ss; emitting graceful fallback.",
                        stream_budget,
                    )
                    yield {
                        "type": "content",
                        "data": "I'm having trouble thinking right now...",
                    }
                    yield {"type": "done", "data": ""}

            except Exception as e:
                logger.error(f"[Action] LLM Execution failed: {e}")
                yield {"type": "error", "data": str(e)}
                yield {"type": "done", "data": ""}

        elif plan.action_type == "STORE_MEMORY":
            content = plan.payload.get("content", "")
            # Using the new intelligent MemoryStore
            if self.memory:
                await self.memory.add_memory(
                    content=content,
                    importance=0.7,  # High importance for explicit 'remember' commands
                    emotion=0.2,
                    source="user",
                )
            yield {"type": "system", "data": "Memory securely consolidated."}
            yield {"type": "done", "data": ""}

        elif plan.action_type == "BACKGROUND_CONSOLIDATION":
            # Already triggered by CognitiveService
            yield {"type": "done", "data": ""}

        else:
            logger.warning(f"[Action] Unrecognized action: {plan.action_type}")
            yield {"type": "error", "data": "Unknown operation."}
            yield {"type": "done", "data": ""}
