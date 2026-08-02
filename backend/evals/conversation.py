"""Multi-turn recall probes: can a fact survive the distance to the question?

The single-turn harness in `runner.py` asks whether a model still behaves like
the persona. This one asks the question that actually motivates the memory
architecture: a fact arrives early in a conversation, the conversation carries
on, and much later the user refers back to it. Frontier models lose facts in
the middle of a long context; small models lose them sooner. Everything in
`state/memory_store.py` exists to make that not happen.

**Only the final answer is generated.** The plant, the filler turns and the
assistant's replies to them are all scripted. That is deliberate, and it is
also the harness's main limitation:

- it isolates the variable. Letting the model answer its own filler turns would
  compound its own noise across forty turns, so a failure at the end could not
  be attributed to distance rather than to a bad reply at turn nine.
- it costs one generation per probe instead of forty, which is the difference
  between a suite that runs on CPU and one that does not.
- but it therefore measures *retrieval from a context window*, not
  conversational degradation. A model that would have derailed on its own
  output by turn thirty is not penalised here.

The variable under test is the **context strategy**: what is put in front of
the model at recall time. `full_history` is the naive baseline that shows the
lost-in-the-middle effect directly; `recent_window` is what a chatbot with no
memory does, and it should fail as soon as the plant falls out of the window.
A retrieval-backed strategy plugs into the same seam, and the difference
between it and these two is precisely the cognitive layer's contribution.
"""

import json
import logging
from pathlib import Path
from typing import NamedTuple, Protocol

from app.cognitive.identity import IdentityManager
from app.llm.ollama_client import OllamaClient

from .schema import (
    DEFAULT_OPTIONS,
    Check,
    CheckResult,
    ConversationProbe,
    EvalReport,
    ProbeResult,
    RunOptions,
    fingerprint,
    summarize_by_category,
)
from .scoring import evaluate_check, response_views, strip_thoughts

logger = logging.getLogger("evals.conversation")

EVAL_MOOD_DIRECTIVE = "Calm and neutral (evaluation run)."


class Turn(NamedTuple):
    speaker: str
    text: str


class ContextStrategy(Protocol):
    """How much of the conversation the model gets to see at recall time."""

    name: str

    def select(self, transcript: list[Turn], query: str) -> list[Turn]:
        ...


class FullHistory:
    """Everything, in order. The naive baseline.

    Passing the whole transcript is what a system with no memory layer and a
    large context window does. It is the condition under which lost-in-the-
    middle is observable at all: the fact *is* present, so a miss is an
    attention failure rather than an absence.
    """

    name = "full_history"

    def select(self, transcript: list[Turn], query: str) -> list[Turn]:
        return list(transcript)


class RecentWindow:
    """The last ``turns`` entries only.

    What a chatbot does when it truncates to fit a budget. Included as the
    control that is *supposed* to fail: once the plant falls outside the
    window the fact is genuinely gone, so a pass here would mean the model
    guessed the answer and the probe is measuring nothing.
    """

    def __init__(self, turns: int):
        if turns < 1:
            raise ValueError("recent_window needs at least one turn")
        self.turns = turns
        self.name = f"recent_window_{turns}"

    def select(self, transcript: list[Turn], query: str) -> list[Turn]:
        return list(transcript[-self.turns:])


DEFAULT_STRATEGIES: tuple[ContextStrategy, ...] = (FullHistory(), RecentWindow(6))


def build_transcript(
    probe: ConversationProbe, filler: list[tuple[str, str]]
) -> list[Turn]:
    """Plant the fact, then bury it under ``filler_turns`` scripted exchanges.

    Filler cycles through the pack in order rather than being sampled, so two
    runs of the same probe produce byte-identical context. A random filler
    would make every rerun a different measurement.
    """
    if not filler:
        raise ValueError("conversation probes need at least one filler exchange")

    turns = [Turn("user", probe.plant), Turn("assistant", probe.plant_reply)]
    for index in range(probe.filler_turns):
        user_text, assistant_text = filler[index % len(filler)]
        turns.append(Turn("user", user_text))
        turns.append(Turn("assistant", assistant_text))
    return turns


def render_context(turns: list[Turn]) -> str:
    return "\n".join(f"{turn.speaker.capitalize()}: {turn.text}" for turn in turns)


# Deliberately pessimistic. English averages nearer four characters per token,
# so dividing by three over-counts -- and over-counting is the safe direction:
# it can only make the harness call a context "too long" that would have fit,
# never call one "fits" that the runtime then truncates. A false alarm costs a
# rerun with a bigger window; a false all-clear costs a published number.
_CHARS_PER_TOKEN = 3


def estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def context_fits(prompt: str, system: str, options: RunOptions) -> bool:
    """Whether the prompt survives ``num_ctx`` intact.

    Ollama truncates an over-long prompt from the *front*, which for a recall
    probe is exactly where the planted fact sits. The model would then answer
    from its prior with no fact in sight, and the probe would report a clean
    failure that says nothing about memory. Callers surface this rather than
    scoring it.

    ``num_predict`` counts against the same window as the prompt, so the
    reserve has to be included. Leaving it out gives a probe that fits on
    arrival and loses the plant partway through generation -- the one case the
    check exists to catch, reported as ``fits yes``.
    """
    budget = (
        estimate_tokens(prompt) + estimate_tokens(system) + options.num_predict
    )
    return budget <= options.num_ctx


async def run_conversation_probe(
    client: OllamaClient,
    manager: IdentityManager,
    probe: ConversationProbe,
    filler: list[tuple[str, str]],
    strategy: ContextStrategy,
    system: str,
    model: str | None,
    options: RunOptions,
) -> ProbeResult:
    transcript = build_transcript(probe, filler)
    visible = strategy.select(transcript, probe.recall_prompt)
    context = render_context(visible)
    prompt = f"{context}\nUser: {probe.recall_prompt}\nAssistant:"

    response = await client.generate(
        prompt=prompt,
        system=system,
        model=model,
        options_override=options.as_override(),
    )

    views = response_views(response)
    checks: list[CheckResult] = []
    for check in probe.checks:
        if check.kind == "boundary":
            ok, reason = await manager.validate_response(
                strip_thoughts(response), goal="eval"
            )
            checks.append(CheckResult(kind="boundary", passed=ok, detail=reason))
        else:
            checks.append(evaluate_check(check, views))

    return ProbeResult(
        # Qualified by strategy: the same probe is run under several, and
        # `compare` aligns reports by probe_id, so unqualified ids would
        # collide inside a single report and silently diff the wrong pair.
        probe_id=f"{probe.id}@{strategy.name}",
        category=probe.category,
        prompt=probe.recall_prompt,
        response=response,
        checks=checks,
        passed=all(item.passed for item in checks),
        score=sum(1 for item in checks if item.passed) / len(checks),
        context_strategy=strategy.name,
        context_turns=len(visible),
        context_chars=len(context),
        plant_visible=any(turn.text == probe.plant for turn in visible),
        context_fits=context_fits(prompt, system, options),
    )


async def run_conversation_eval(
    client: OllamaClient,
    manager: IdentityManager,
    probes: list[ConversationProbe],
    filler: list[tuple[str, str]],
    strategies: tuple[ContextStrategy, ...] = DEFAULT_STRATEGIES,
    model: str | None = None,
    options: RunOptions = DEFAULT_OPTIONS,
) -> EvalReport:
    from .runner import _provenance, reset_model_state

    system = manager.get_persona_prompt(current_mood_directive=EVAL_MOOD_DIRECTIVE)
    # Whatever state the runtime was already in changes the answers; see
    # `reset_model_state`. This suite is where that was measured, twice.
    await reset_model_state(client, system, model, options)

    results: list[ProbeResult] = []
    # Sequential for the same reason the single-turn runner is: one local
    # model, and concurrent generations on CPU contend for the same cores.
    for probe in probes:
        for strategy in strategies:
            result = await run_conversation_probe(
                client, manager, probe, filler, strategy,
                system, model, options,
            )
            logger.info(
                "[eval] %-40s %s (%d turns, %d chars, plant %s%s)",
                result.probe_id,
                "pass" if result.passed else "FAIL",
                result.context_turns or 0,
                result.context_chars or 0,
                "visible" if result.plant_visible else "dropped",
                "" if result.context_fits else ", TRUNCATED",
            )
            results.append(result)

    return EvalReport(
        model=model or client.model,
        persona_name=manager.persona.name,
        provenance=_provenance(),
        options=options.as_override(),
        system_prompt_sha256=fingerprint(system),
        results=results,
        by_category=summarize_by_category(results),
    )


def load_conversation_pack(path: Path) -> tuple[list[ConversationProbe], list[tuple[str, str]]]:
    """Read probes and filler from one JSON pack.

    Filler lives in the pack rather than in this module on purpose: what a
    conversation is *about* is content, and content belongs to whoever authors
    the pack. Production code carries the mechanism only.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    filler = [(pair[0], pair[1]) for pair in data.get("filler", [])]
    probes = [
        ConversationProbe(**{**item, "source": Path(path).name})
        for item in data.get("probes", [])
    ]

    # Two probes sharing an id produce two results with the same
    # `id@strategy`, and `compare_reports` keys its lookup on exactly that --
    # so one silently overwrites the other and the comparison diffs the wrong
    # pair. The single-turn loader already refuses this; a pack arriving
    # through `--pack` must not be the path where it slips through.
    seen: set[str] = set()
    for probe in probes:
        if probe.id in seen:
            raise ValueError(f"duplicate probe id in {Path(path).name}: {probe.id}")
        seen.add(probe.id)

    return probes, filler


def shipped_conversation_pack() -> Path:
    """The shipped pack, in its own directory beneath ``probes/``.

    Not alongside the single-turn packs: `probes.shipped_packs()` globs
    ``probes/*.json`` and validates every hit as a `ProbePack`, so a
    conversation pack sitting there fails the *other* suite at load time. The
    glob is non-recursive, which makes a subdirectory the whole fix.
    """
    return Path(__file__).parent / "probes" / "conversation" / "conversation_recall.json"


__all__ = [
    "Check",
    "ContextStrategy",
    "FullHistory",
    "RecentWindow",
    "Turn",
    "build_transcript",
    "load_conversation_pack",
    "render_context",
    "run_conversation_eval",
    "run_conversation_probe",
    "shipped_conversation_pack",
]
