"""Run a probe through the real `ActionService`, not just the LLM boundary.

`runner.py` evaluates the seam a fine-tuned adapter changes: the persona prompt
in, `OllamaClient.generate` out. That is the right boundary for CVS-4, and it
stays the default. But it means **everything `action.py` contributes to a turn
is invisible to the eval pack** -- `_CHAT_GUIDELINE`, the Theory-of-Mind block,
the goal line interpolated into the user prompt, the incremental `<thought>`
stripping, `ControlMarkupSanitizer`, `_validate_partial_response` and the
self-correction retry it triggers.

That gap is not hypothetical. P2-4 (audit/ROADMAP.md, Stage 4 Part 4) proposed
appending a classification instruction to exactly this system prompt, ran
`evals run` before and after, and got an identical report both times -- because
the harness never executed the code the change lived in. The item was
ultimately gated by a hand-written live smoke test instead, and dropped on what
that smoke test found. This module is the missing gate.

**What this path measures, and what it deliberately does not.** It measures
prompt construction, streaming-time parsing, sanitization and boundary
validation -- everything between the probe text and the visible reply. It does
*not* measure the endocrine sampling mapping (`_compute_endocrine_options`),
because `PinnedOptionsClient` overrides sampling to the harness's pinned
options. That is a deliberate trade, not an oversight: letting cortisol pick
the temperature would reintroduce precisely the run-to-run variance
`runner.reset_model_state` exists to eliminate, and an eval whose sampling
drifts with simulated affect cannot answer "did the model change".

The dependency points one way, as it must: this imports from `app/`, and
nothing in `app/` knows this file exists. The pinning lives here, in the
harness, rather than as a hook in `action.py` that would exist only for tests.
"""

import logging
from typing import Any

from app.cognitive.action import ActionService
from app.cognitive.decision import ActionPlan
from app.llm.ollama_client import OllamaClient

from .schema import RunOptions

logger = logging.getLogger("evals.action_path")

# Interpolated verbatim into the user prompt as "- Goal: {goal}", so it is part
# of what the model reads. Pinned to the same value the decision layer falls
# back to when classification is unavailable, for the same reason the mood
# directive is pinned: a goal that varied would measure the decision layer.
EVAL_GOAL = "ENGAGE"

# Neutral affect. `_prepended_affect_tag` emits a <breath_fast>/<sigh_soft>
# opener outside these bounds, which would prepend a non-verbal marker to the
# scored text; at valence 0.0 / arousal 0.5 it returns "" and the reply is the
# model's own first token. Frozen for the same reason `EVAL_MOOD_DIRECTIVE` is.
EVAL_VALENCE = 0.0
EVAL_AROUSAL = 0.5
EVAL_DOMINANCE = 0.5


class PinnedOptionsClient:
    """An `OllamaClient` whose sampling options cannot be overridden downstream.

    Two separate problems make this necessary, and neither is optional:

    1. **The endocrine layer picks sampling from affect.**
       `ActionService._compute_endocrine_options` maps cortisol to temperature,
       dopamine to top_p and fatigue to num_predict, and hands the result to
       `generate_stream` as `options_override`. Whatever the harness pinned
       would be silently replaced.
    2. **`generate_stream`'s own defaults are unusable for evaluation.** It
       passes `num_predict=40` and `num_ctx=2048` when nothing overrides them
       (`ollama_client.py:91-99`, `:206`). Forty tokens truncates most probe
       answers mid-sentence, and 2048 is the same context ceiling that
       `RunOptions.num_ctx` is pinned to 8192 to escape.

    So this wrapper merges the run's options *over* whatever the caller passed,
    rather than under it. Delegation is explicit (only the two generate methods
    plus the attributes the runner reads) rather than a `__getattr__` catch-all:
    a silently forwarded method is how a future call path would escape the
    pinning without anything failing.

    It also records the system prompt it was actually handed, so the report can
    fingerprint what the model really saw instead of a copy of `action.py`'s
    prompt composition maintained here -- a copy that would drift the first
    time that composition changed, and drift silently, since both sides would
    still produce a digest.
    """

    def __init__(self, inner: OllamaClient, options: RunOptions):
        self._inner = inner
        self._pinned = options.as_override()
        self.observed_system: str | None = None

    # The runner reads both of these off the client it was given.
    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def base_url(self) -> str | None:
        # `getattr` with a default, matching `reset_model_state`'s own reasoning
        # (`runner.py`): a stand-in client declines the unload by not offering
        # an address, rather than by raising from inside one.
        return getattr(self._inner, "base_url", None)

    def _pin(self, options_override: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(options_override or {})
        merged.update(self._pinned)
        return merged

    def _observe(self, system: str | None) -> None:
        if self.observed_system is None and system is not None:
            self.observed_system = system

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        options_override: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        self._observe(system)
        return await self._inner.generate(
            prompt=prompt,
            system=system,
            model=model,
            options_override=self._pin(options_override),
            **kwargs,
        )

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        options_override: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        self._observe(system)
        async for chunk in self._inner.generate_stream(
            prompt=prompt,
            system=system,
            model=model,
            options_override=self._pin(options_override),
            **kwargs,
        ):
            yield chunk


def build_action_service(client: PinnedOptionsClient) -> ActionService:
    """An `ActionService` with no store behind it.

    `memory_store=None` and `self_knowledge=None` are load-bearing, not
    laziness. Both collaborators are guarded (`action.py:1121`, `:1128`,
    `_build_wondering_block`'s own `is None` return), so the turn runs without
    Postgres, Qdrant or Neo4j -- keeping the harness's "no NATS, no databases,
    no mesh" property, which is what lets it run anywhere the model does.

    The consequence is stated rather than hidden: `_surface_fallback_memories`
    never runs, so SHARED HISTORY is empty on this path. Retrieval is what
    `run-conversation` measures; this path measures the prompt built around it.
    """
    return ActionService(llm_service=client, memory_store=None, self_knowledge=None)


def build_plan(prompt: str, identity_prompt: str, model: str | None) -> ActionPlan:
    """The minimal plan a `RESPOND_CHAT` turn needs.

    Every affect field is pinned rather than omitted. Omitting the three
    endocrine keys would make `_compute_endocrine_options` return `None`
    (`action.py:637`), which reads as "no endocrine signal" and leaves the
    model on `generate_stream`'s 40-token default -- so the omission that looks
    like "don't simulate hormones" is really "truncate every answer". They are
    supplied at rest instead, and `PinnedOptionsClient` overrides the sampling
    they produce.
    """
    return ActionPlan(
        action_type="RESPOND_CHAT",
        goal=EVAL_GOAL,
        payload={
            "message": prompt,
            "identity_prompt": identity_prompt,
            "emotion_state": "neutral",
            "model": model,
            "valence": EVAL_VALENCE,
            "arousal": EVAL_AROUSAL,
            "dominance": EVAL_DOMINANCE,
            "cortisol": 0.0,
            "dopamine": 0.0,
            "fatigue": 0.0,
        },
    )


async def generate_through_action_service(
    service: ActionService,
    plan: ActionPlan,
) -> str:
    """Stream a turn and return what the user would actually have heard.

    Only `content` chunks are collected. The other types are real parts of the
    turn but are not speech: `self_correction` is the internal signal
    `pipeline.py` intercepts and never forwards to transport, and `error`
    reports a failed turn. Scoring the internal ones would measure text no
    listener receives.

    A self-correction retry is *not* filtered out, and should not be: its
    replacement text arrives as ordinary `content`, which is exactly what the
    user hears, and a change that starts triggering self-correction is a
    behavior change the gate should catch.
    """
    parts: list[str] = []
    async for chunk in service.execute(plan):
        if chunk.get("type") == "content":
            parts.append(str(chunk.get("data", "")))
    return "".join(parts)
