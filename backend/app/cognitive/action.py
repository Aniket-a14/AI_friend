import asyncio
import logging
import re
import time
from typing import Dict, Any, AsyncGenerator
from .decision import ActionPlan
from ..config import Config

logger = logging.getLogger(__name__)

# Phrases where the assistant attributes a fact to the shared past or the user's
# prior statements ("you told me…", "remember when we…"). Such a phrase asserts a
# memory; if its content is absent from the surfaced memories AND the user's
# current message, the memory is being fabricated -- the exact hallucination the
# grounding gate catches.
_MEMORY_CLAIM_RE = re.compile(
    r"\b("
    r"you (?:once |also |already )?(?:told|said|mentioned|shared)"
    r"|you'?ve (?:told|mentioned|shared)"
    r"|you used to"
    r"|remember when (?:you|we)"
    r"|last time (?:you|we)"
    r"|i remember you (?:saying|mentioning|telling)"
    r"|as you (?:said|mentioned|told me)"
    r"|back when (?:you|we)"
    r")\b",
    re.IGNORECASE,
)

# The trigger words themselves plus generic conversational filler and common
# function words. Stripped from a claim before checking grounding so only
# substantive specifics (names, places, activities -- including short ones like
# "dog" or "Rex") drive the decision, keeping the gate high-precision.
_GROUNDING_STOPWORDS = frozenset(
    {
        # memory-attribution trigger words
        "told", "said", "mentioned", "shared", "remember", "saying",
        "mentioning", "telling", "used",
        # temporal / discourse filler
        "when", "last", "time", "back", "once", "also", "already",
        "earlier", "before", "then", "now", "ago",
        # generic conversational filler
        "that", "this", "about", "really", "think", "know", "just", "very",
        "much", "would", "could", "some", "thing", "things", "something",
        "want", "like", "into", "over", "still", "even", "well", "sure",
        # pronouns / determiners / common short function words
        "your", "yours", "you", "the", "and", "are", "for", "not", "but",
        "his", "her", "was", "has", "had", "our", "out", "who", "how",
        "all", "any", "can", "did", "get", "got", "let", "may", "off",
        "old", "one", "own", "put", "say", "see", "she", "too", "two",
        "use", "way", "yes", "yet", "him", "per", "via", "with", "from",
        "they", "them", "than", "what", "which", "were", "been", "have",
    }
)


def _memory_relevance(memory: Dict[str, Any]) -> float:
    """Relevance value used to order a surfaced memory.

    ``search_memories`` emits ``score``; the proactive surfacing path in
    ``core.py`` emits ``relevance``. Fall back to 0.0 when neither is a usable
    number so unranked items keep a stable (middle-ish) position rather than
    crashing the sort.
    """
    for key in ("score", "relevance"):
        val = memory.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
    return 0.0


def reorder_for_long_context(memories):
    """Reorder retrieved memories to mitigate the "lost in the middle" effect.

    LLMs attend most strongly to the beginning and end of their context and
    systematically lose information placed in the middle (Liu et al., 2023).
    Retrieval hands us memories ranked most- to least-relevant, so a plain
    concatenation spends the high-attention *final* slot on the least relevant
    item and buries the mid-ranked ones. Instead, place the most relevant items
    at both edges and the least relevant in the middle: ranked ``[A, B, C, D, E]``
    (A most relevant) becomes ``[A, C, E, D, B]``, so A and B bracket the block.

    Input order is not trusted — items are sorted by relevance first — so this is
    safe for both producer shapes (``score`` and ``relevance``).
    """
    ranked = sorted(memories, key=_memory_relevance, reverse=True)
    reordered = [None] * len(ranked)
    left, right = 0, len(ranked) - 1
    for i, item in enumerate(ranked):
        if i % 2 == 0:
            reordered[left] = item
            left += 1
        else:
            reordered[right] = item
            right -= 1
    return reordered


class MetacognitiveException(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


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
        self.publish_cb = None

    def _check_response_grounding(
        self, response: str, surfaced, user_message: str
    ) -> tuple[bool, str]:
        """Deterministic anti-hallucination gate for fabricated shared memories.

        Fires only when the response explicitly *attributes* a fact to the shared
        past ("you told me…", "remember when we…") whose substantive content
        appears in neither the surfaced memories nor the user's current message.
        Requiring an attribution phrase plus at least two ungrounded specifics
        keeps it high-precision: it targets invented recollections, not the
        model's ordinary conversational contributions.

        Returns (is_grounded, reason). ``reason`` feeds the self-correction prompt.
        """
        if not response or not _MEMORY_CLAIM_RE.search(response):
            return True, ""

        grounding_text = " ".join(
            (m.get("content") or "") for m in (surfaced or [])
        )
        grounding_text = f"{grounding_text} {user_message or ''}".lower()
        grounding_words = set(re.findall(r"\b[a-z]{3,}\b", grounding_text))

        for sentence in re.split(r"(?<=[.!?])\s+", response):
            if not _MEMORY_CLAIM_RE.search(sentence):
                continue
            claim_words = (
                set(re.findall(r"\b[a-z]{3,}\b", sentence.lower()))
                - _GROUNDING_STOPWORDS
            )
            # Only act when the claim carries real specifics and NONE of them are
            # grounded; a partial match means the memory is at least partly real.
            if len(claim_words) >= 2 and not (claim_words & grounding_words):
                return (
                    False,
                    "You referenced a shared memory that is not in the provided "
                    "context. Do not invent things the user never told you; only "
                    "reference facts present in SHARED HISTORY.",
                )
        return True, ""

    def _validate_partial_response(self, text: str, goal: str) -> tuple[bool, str]:
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("[") or "```" in text:
            return False, "Formatting anomaly (JSON/Markdown)"

        forbidden = [
            "as an ai",
            "i am an ai",
            "how can i help you",
            "as a language model",
        ]
        for phrase in forbidden:
            if phrase in text.lower():
                return False, f"Forbidden AI persona phrase: '{phrase}'"

        import re

        if re.search(r"\b(toxic|hate)\b", text.lower()):
            return False, "Safety/Toxicity boundary violation"

        return True, ""

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
            if not surfaced and self.memory:
                try:
                    # Synchronous fallback to prevent race conditions in low-latency/benchmark modes
                    fallback_memories = await self.memory.search_memories(
                        query_text=msg,
                        wing="personal",
                        limit=3,
                        refresh_on_recall=False,
                        current_valence=plan.payload.get("valence", 0.0),
                        current_arousal=plan.payload.get("arousal", 0.5),
                        current_cortisol=plan.payload.get("cortisol", 0.0),
                    )
                    if fallback_memories:
                        surfaced = fallback_memories
                        logger.info(
                            f"⚡ [Action] Synchronous recall fallback surfaced {len(surfaced)} memories."
                        )
                except Exception as fe:
                    logger.warning(
                        f"Failed to run synchronous memory surfacing fallback: {fe}"
                    )

            shared_history = ""
            if surfaced:
                # Edge-load the most relevant memories so they land in the LLM's
                # high-attention start/end positions instead of being lost in the
                # middle of the block.
                ordered = reorder_for_long_context(surfaced)
                shared_history = (
                    "\nSHARED HISTORY / RECENT CONTEXT (Active Influence):\n"
                    + "\n".join([f"- {m['content']}" for m in ordered])
                )

            # Theory of Mind (ToM) Context Injection
            tom_context = ""
            user_tom = plan.payload.get("user_mental_model")
            if user_tom:
                inferred_val = user_tom.get("inferred_valence", 0.0)
                inferred_ar = user_tom.get("inferred_arousal", 0.5)
                impl_goals = user_tom.get("implied_goals", [])
                if not isinstance(impl_goals, list):
                    logger.warning(
                        f"[Action] Unexpected type for implied_goals in user_mental_model: {type(impl_goals)}. Falling back to empty list."
                    )
                    impl_goals = []
                # Take the last 10 known concepts to keep it concise and avoid context bloat
                known_con = user_tom.get("known_concepts", [])[-10:]

                tom_context = (
                    "\n\nYour Inferred Perspective of the User (Theory of Mind):\n"
                )
                tom_context += f"- User Inferred Valence: {inferred_val:.2f} (Scale: -1.0 to 1.0)\n"
                tom_context += (
                    f"- User Inferred Arousal: {inferred_ar:.2f} (Scale: 0.0 to 1.0)\n"
                )
                if impl_goals:
                    tom_context += f"- User Implied Goals: {', '.join(impl_goals)}\n"
                if known_con:
                    tom_context += f"- User Known Concepts (Respect this knowledge boundary): {', '.join(known_con)}\n"

            # 1. Prepare Identity-Aware System and User Prompts
            # Static System Prompt (cached by inference engines like Ollama/vLLM)
            system_instruction = f"{identity_prompt}\n\nGuideline:\n- Maintain your identity rules at all times.\n- Focus on natural conversational phrases.\n- IMPORTANT: If the SHARED HISTORY / RECENT CONTEXT contains relevant biographical facts, partner details, childhood milestones, or personal preferences, you MUST integrate them explicitly and accurately to answer the user's question.\n- GROUNDING: Base any specific claim about the user, your shared past, names, dates, places, or events ONLY on the SHARED HISTORY / RECENT CONTEXT provided. Do not invent memories or details that are not there. If the user asks about something you have no memory of, say so naturally (e.g. \"I don't think you've told me that\") instead of making it up.\n- Respond only in English. Do not use Hindi, Hinglish, or any other language for now.\n- The voice layer already carries emotion separately. Do not emit XML wrappers or emotion tags.\n- You may use <pause=300ms> or <hesitate> when it improves natural timing."

            # Dynamic User Prompt. Ordering fights "lost in the middle": the factual
            # grounding (SHARED HISTORY) is placed LAST before the user's query so it
            # sits in the model's high-attention tail, adjacent to what it must
            # answer. The more abstract, lower-cost-to-lose context (goal, emotion,
            # Theory-of-Mind) goes earlier. Within the history block itself, memories
            # are already edge-loaded by reorder_for_long_context().
            user_prompt = f"Current Context:\n- Goal: {plan.goal}\n- Current Emotion: {emotion}\n{tom_context}{shared_history}\n\nUser: {msg}\nAssistant:"

            valence = plan.payload.get("valence", 0.0)
            arousal = plan.payload.get("arousal", 0.5)
            dominance = plan.payload.get("dominance", 0.5)

            try:
                # 2. Endocrine System: Calculate physiological LLM parameters
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

                    # Bounded num_predict strictly between 100 (exhausted) and 250 (fresh)
                    endo_num_predict = int(
                        max(100, min(250, int(250 - (fatigue_val * 150))))
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

                # Track state for paralinguistic injection, CoT thought stripping, and System 3 checks
                in_thought = False
                thought_buffer = ""
                checked_start = False
                has_hesitated = False
                accumulated_response = ""

                # Prepend tags based on emotional states
                prepended_tag = ""
                if arousal > 0.6 and valence < -0.3:
                    prepended_tag = "<breath_fast> "
                elif arousal < 0.4 and valence < 0.0:
                    prepended_tag = "<sigh_soft> "

                if prepended_tag:
                    yield {"type": "content", "data": prepended_tag}

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
                        if not clean_chunk:
                            continue

                        # CoT strip check
                        if not checked_start:
                            thought_buffer += clean_chunk
                            if "<thought" in thought_buffer:
                                in_thought = True
                                checked_start = True
                                if "</thought>" in thought_buffer:
                                    parts = thought_buffer.split("</thought>", 1)
                                    thought_block = parts[0]
                                    remaining_content = parts[1]

                                    thought_content = thought_block.replace(
                                        "<thought>", ""
                                    ).strip()
                                    logger.info(f"[CoT Thought] {thought_content}")
                                    if remaining_content:
                                        if (
                                            dominance < 0.4
                                            and not has_hesitated
                                            and "," in remaining_content
                                        ):
                                            remaining_content = (
                                                remaining_content.replace(
                                                    ",", " <hesitate>,", 1
                                                )
                                            )
                                            has_hesitated = True

                                        candidate = (
                                            accumulated_response + remaining_content
                                        )
                                        is_valid, reason = (
                                            self._validate_partial_response(
                                                candidate, plan.goal
                                            )
                                        )
                                        if not is_valid:
                                            raise MetacognitiveException(reason)

                                        yield {
                                            "type": "content",
                                            "data": remaining_content,
                                        }
                                        accumulated_response = candidate
                                    thought_buffer = ""
                                    in_thought = False
                            else:
                                if (
                                    dominance < 0.4
                                    and not has_hesitated
                                    and "," in thought_buffer
                                ):
                                    thought_buffer = thought_buffer.replace(
                                        ",", " <hesitate>,", 1
                                    )
                                    has_hesitated = True

                                candidate = accumulated_response + thought_buffer
                                is_valid, reason = self._validate_partial_response(
                                    candidate, plan.goal
                                )
                                if not is_valid:
                                    raise MetacognitiveException(reason)

                                yield {"type": "content", "data": thought_buffer}
                                accumulated_response = candidate
                                thought_buffer = ""
                                checked_start = True
                                continue

                        elif in_thought:
                            thought_buffer += clean_chunk
                            if "</thought>" in thought_buffer:
                                parts = thought_buffer.split("</thought>", 1)
                                thought_block = parts[0]
                                remaining_content = parts[1]

                                thought_content = thought_block.replace(
                                    "<thought>", ""
                                ).strip()
                                logger.info(f"[CoT Thought] {thought_content}")

                                if remaining_content:
                                    if (
                                        dominance < 0.4
                                        and not has_hesitated
                                        and "," in remaining_content
                                    ):
                                        remaining_content = remaining_content.replace(
                                            ",", " <hesitate>,", 1
                                        )
                                        has_hesitated = True

                                    candidate = accumulated_response + remaining_content
                                    is_valid, reason = self._validate_partial_response(
                                        candidate, plan.goal
                                    )
                                    if not is_valid:
                                        raise MetacognitiveException(reason)

                                    yield {"type": "content", "data": remaining_content}
                                    accumulated_response = candidate
                                thought_buffer = ""
                                in_thought = False
                            continue
                        else:
                            if (
                                dominance < 0.4
                                and not has_hesitated
                                and "," in clean_chunk
                            ):
                                clean_chunk = clean_chunk.replace(
                                    ",", " <hesitate>,", 1
                                )
                                has_hesitated = True

                            candidate = accumulated_response + clean_chunk
                            is_valid, reason = self._validate_partial_response(
                                candidate, plan.goal
                            )
                            if not is_valid:
                                raise MetacognitiveException(reason)

                            yield {"type": "content", "data": clean_chunk}
                            accumulated_response = candidate

                    trailing = sanitizer.flush()
                    if trailing:
                        if in_thought:
                            thought_buffer += trailing
                            if "</thought>" in thought_buffer:
                                parts = thought_buffer.split("</thought>", 1)
                                thought_content = (
                                    parts[0].replace("<thought>", "").strip()
                                )
                                logger.info(f"[CoT Thought] {thought_content}")
                                remaining_content = parts[1]
                                if remaining_content:
                                    candidate = accumulated_response + remaining_content
                                    is_valid, reason = self._validate_partial_response(
                                        candidate, plan.goal
                                    )
                                    if not is_valid:
                                        raise MetacognitiveException(reason)
                                    yield {"type": "content", "data": remaining_content}
                                    accumulated_response = candidate
                        else:
                            candidate = accumulated_response + trailing
                            is_valid, reason = self._validate_partial_response(
                                candidate, plan.goal
                            )
                            if not is_valid:
                                raise MetacognitiveException(reason)
                            yield {"type": "content", "data": trailing}
                            accumulated_response = candidate

                    # Post-generation grounding gate: the whole utterance is now
                    # known, so check it for fabricated shared-memory claims and
                    # route any hit through the same self-correction path.
                    is_grounded, ground_reason = self._check_response_grounding(
                        accumulated_response, surfaced, msg
                    )
                    if not is_grounded:
                        raise MetacognitiveException(ground_reason)

                    yield {"type": "done", "data": "finished"}

                except MetacognitiveException as me:
                    logger.warning(
                        f"[System 3] Metacognitive violation: {me.reason}. Triggering self-correction."
                    )
                    if self.publish_cb:
                        try:
                            await self.publish_cb(
                                "control.interrupt",
                                {"reason": me.reason, "interrupt": True},
                            )
                            await self.publish_cb(
                                "audio.stop", {"interrupt": True, "reason": me.reason}
                            )
                        except Exception as pe:
                            logger.error(
                                f"[System 3] Failed to publish interrupt: {pe}"
                            )

                    yield {"type": "content", "data": " Wait, let me rephrase that... "}
                    if endocrine_options is None:
                        endocrine_options = {}
                    endocrine_options["temperature"] = min(
                        1.0, endocrine_options.get("temperature", 0.7) + 0.2
                    )
                    user_prompt += f"\n\nCRITICAL FIX: Your previous response violated constraints: {me.reason}. Correct it immediately and do not repeat the forbidden phrases."

                    try:
                        stream_iter = self.llm.generate_stream(
                            prompt=user_prompt,
                            system=system_instruction,
                            model=model,
                            options_override=endocrine_options,
                        ).__aiter__()
                        deadline = time.monotonic() + stream_budget
                        accumulated_retry_response = ""
                        is_valid = True
                        while True:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            try:
                                chunk = await asyncio.wait_for(
                                    stream_iter.__anext__(), timeout=remaining
                                )
                            except StopAsyncIteration:
                                break
                            clean_chunk = sanitizer.feed(chunk)
                            if clean_chunk:
                                candidate = accumulated_retry_response + clean_chunk
                                is_valid, _ = self._validate_partial_response(
                                    candidate, plan.goal
                                )
                                if not is_valid:
                                    logger.warning(
                                        "[System 3] Retry also violated constraints; yielding safe fallback."
                                    )
                                    yield {
                                        "type": "content",
                                        "data": "I need a moment to gather my thoughts...",
                                    }
                                    break
                                yield {"type": "content", "data": clean_chunk}
                                accumulated_retry_response = candidate

                        if is_valid:
                            trailing = sanitizer.flush()
                            if trailing:
                                candidate = accumulated_retry_response + trailing
                                is_valid_trail, _ = self._validate_partial_response(
                                    candidate, plan.goal
                                )
                                if not is_valid_trail:
                                    logger.warning(
                                        "[System 3] Retry trailing also violated constraints; yielding safe fallback."
                                    )
                                    yield {
                                        "type": "content",
                                        "data": "I need a moment to gather my thoughts...",
                                    }
                                else:
                                    yield {"type": "content", "data": trailing}
                        yield {"type": "done", "data": "finished"}
                    except Exception as inner_e:
                        logger.error(
                            f"[System 3] Self-correction generation failed: {inner_e}"
                        )
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
            yield {"type": "content", "data": "Got it, I've committed that to memory."}
            yield {"type": "done", "data": ""}

        elif plan.action_type == "BACKGROUND_CONSOLIDATION":
            # Already triggered by CognitiveService
            yield {"type": "done", "data": ""}

        else:
            logger.warning(f"[Action] Unrecognized action: {plan.action_type}")
            yield {"type": "error", "data": "Unknown operation."}
            yield {"type": "done", "data": ""}
