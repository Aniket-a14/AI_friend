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

            # 1. Prepare Identity-Aware System and User Prompts
            # Static System Prompt (cached by inference engines like Ollama/vLLM)
            system_instruction = f"{identity_prompt}\n\nGuideline:\n- Maintain your identity rules at all times.\n- Focus on short, natural conversational phrases.\n- Respond only in English. Do not use Hindi, Hinglish, or any other language for now.\n- The voice layer already carries emotion separately. Do not emit XML wrappers or emotion tags.\n- You may use <pause=300ms> or <hesitate> when it improves natural timing."

            # Dynamic User Prompt (appends active context to the query suffix)
            user_prompt = f"Current Context:\n- Goal: {plan.goal}\n- Current Emotion: {emotion}\n{shared_history}\n\nUser: {msg}\nAssistant:"

            try:
                # 2. Endocrine System: Calculate physiological LLM parameters
                # Cortisol (stress) → inversely controls temperature
                # Dopamine (reward) → controls top_p exploration
                endocrine_options = None
                cortisol = plan.payload.get("cortisol")
                dopamine = plan.payload.get("dopamine")
                if cortisol is not None and dopamine is not None:
                    # High cortisol → low temp (rigid/defensive): range 0.3 to 0.9
                    endo_temperature = round(0.9 - (cortisol * 0.6), 3)
                    # High dopamine → high top_p (exploratory): range 0.70 to 0.95
                    endo_top_p = round(0.70 + (dopamine * 0.25), 3)
                    endocrine_options = {
                        "temperature": endo_temperature,
                        "top_p": endo_top_p,
                    }
                    logger.info(
                        "[Endocrine] Cortisol=%.2f Dopamine=%.2f → temp=%.3f top_p=%.3f",
                        cortisol, dopamine, endo_temperature, endo_top_p,
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
