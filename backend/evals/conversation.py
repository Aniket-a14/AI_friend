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

from app import config as config_module
from app.cognitive.identity import IdentityManager
from app.llm.ollama_client import OllamaClient

from .schema import (
    DEFAULT_OPTIONS,
    Check,
    CheckResult,
    ConversationProbe,
    EvalReport,
    ModelSource,
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
    """How much of the conversation the model gets to see at recall time.

    ``select`` is async because a retrieval-backed strategy has to reach a
    database and an embedding model to answer. The two trivial strategies do
    not need it and pay nothing for it; making the *interface* async is what
    keeps the interesting implementations expressible at all.
    """

    name: str

    async def select(self, transcript: list[Turn], query: str) -> list[Turn]: ...


class FullHistory:
    """Everything, in order. The naive baseline.

    Passing the whole transcript is what a system with no memory layer and a
    large context window does. It is the condition under which lost-in-the-
    middle is observable at all: the fact *is* present, so a miss is an
    attention failure rather than an absence.
    """

    name = "full_history"

    async def select(self, transcript: list[Turn], query: str) -> list[Turn]:
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

    async def select(self, transcript: list[Turn], query: str) -> list[Turn]:
        return list(transcript[-self.turns :])


def _matching_indices(transcript: list[Turn], hits: list[Turn]) -> list[int]:
    """Where each retrieved turn sits in the transcript.

    Retrievers return turn *values*, and filler repeats verbatim -- "bus was
    late again" appears every fourth exchange. Matching by value alone would
    let one hit claim every copy, inflating a retrieval budget of six into
    sixty. Each hit therefore consumes the earliest position not already
    spoken for.
    """
    taken: set[int] = set()
    for hit in hits:
        for index, turn in enumerate(transcript):
            if index not in taken and turn == hit:
                taken.add(index)
                break
    return sorted(taken)


def _in_transcript_order(transcript: list[Turn], hits: list[Turn]) -> list[Turn]:
    return [transcript[index] for index in _matching_indices(transcript, hits)]


class Retrieved:
    """Only what a retriever picked, in a budget matched to the window.

    The budget is the experiment. Given the same number of turns as
    `recent_window_N`, any difference is attributable to *which* turns were
    chosen rather than to how many -- and "we showed it more" is not a claim
    about a memory architecture.

    Selected turns are returned in transcript order, not relevance order,
    because a conversation read out of sequence is a different thing to
    comprehend and that would confound the measurement too.
    """

    def __init__(self, retriever, turns: int):
        if turns < 1:
            raise ValueError("a retrieval budget needs at least one turn")
        self.retriever = retriever
        self.turns = turns
        self.name = f"retrieved_{retriever.name}_{turns}"

    async def select(self, transcript: list[Turn], query: str) -> list[Turn]:
        await self.retriever.index(transcript)
        hits = await self.retriever.search(query, self.turns)
        return _in_transcript_order(transcript, hits)[: self.turns]


class WindowPlusRetrieved:
    """The tail of the conversation plus what a retriever surfaced.

    Closer to what the running system does -- recent context is always present
    and memories arrive alongside it -- and therefore the more honest predictor
    of production behaviour. It is *not* budget-matched to `recent_window_N`,
    so a win here is partly a win for having more room; that is why the
    budget-matched `Retrieved` exists next to it rather than instead of it.

    Retrieved turns already inside the window are not repeated.
    """

    def __init__(self, retriever, window: int, turns: int):
        if window < 1 or turns < 1:
            raise ValueError("window and retrieval budget both need a turn")
        self.retriever = retriever
        self.window = window
        self.turns = turns
        self.name = f"window{window}_plus_{retriever.name}_{turns}"

    async def select(self, transcript: list[Turn], query: str) -> list[Turn]:
        await self.retriever.index(transcript)
        hits = await self.retriever.search(query, self.turns)

        window_start = max(0, len(transcript) - self.window)
        keep = set(range(window_start, len(transcript)))

        # Filler repeats verbatim, so a hit can carry text that is already on
        # screen inside the window. Retrieval cannot say *which* occurrence it
        # meant -- `MemoryStore` stores content, not position -- and showing
        # the model the identical line twice spends budget on context it
        # already has. Text the window covers is therefore dropped, and only
        # the remainder is placed by position.
        visible_texts = {transcript[index].text for index in keep}
        novel = [turn for turn in hits if turn.text not in visible_texts]
        # Bounded, because a retriever may return more than it was asked for --
        # `search_memories` treats `limit` as one input among several. Without
        # the cap this strategy's context grows with whatever the retriever
        # felt like returning, and "window plus six" silently becomes "window
        # plus everything", which is `full_history` wearing a different name.
        surfaced = [
            index
            for index in _matching_indices(transcript, novel)
            if index < window_start
        ][: self.turns]
        keep.update(surfaced)
        # Transcript order, so the model reads one coherent excerpt rather than
        # retrieved fragments followed by a jump backwards.
        return [transcript[index] for index in sorted(keep)]


DEFAULT_STRATEGIES: tuple[ContextStrategy, ...] = (FullHistory(), RecentWindow(6))


def build_transcript(
    probe: ConversationProbe, filler: list[tuple[str, str]]
) -> list[Turn]:
    """Plant each fact at its stated depth, under ``filler_turns`` exchanges.

    Filler cycles through the pack in order rather than being sampled, so two
    runs of the same probe produce byte-identical context. A random filler
    would make every rerun a different measurement.

    Plants are emitted in depth order, and ties keep pack order, so a probe
    that states two facts at the same depth reads in the order it was written.
    Filler is a single running sequence that the plants interrupt: inserting a
    plant does not restart it, because the filler *count* is the distance the
    probe claims to be testing and plants must not silently add to it.
    """
    if not filler:
        raise ValueError("conversation probes need at least one filler exchange")

    turns: list[Turn] = []
    emitted = 0

    def run_filler_to(target: int) -> None:
        nonlocal emitted
        while emitted < target:
            user_text, assistant_text = filler[emitted % len(filler)]
            turns.append(Turn("user", user_text))
            turns.append(Turn("assistant", assistant_text))
            emitted += 1

    ordered = sorted(
        enumerate(probe.resolved_plants),
        key=lambda pair: (pair[1].after_filler, pair[0]),
    )
    for _, plant in ordered:
        run_filler_to(plant.after_filler)
        turns.append(Turn("user", plant.text))
        turns.append(Turn("assistant", plant.reply))
    run_filler_to(probe.filler_turns)
    return turns


def _answers_visible(probe: ConversationProbe, visible: list[Turn]) -> bool:
    """Whether every fact the question is about reached the model.

    *Every*, not any: a probe that supersedes an earlier fact is only
    answerable if the correction is on screen, and a probe with two answering
    facts is only answerable if both are. Distractors are excluded by
    construction -- their absence makes the probe easier, not unanswerable --
    so a report that says `plant dropped` still means the same thing it
    always did: whatever the model said next, it was not recall.
    """
    seen = {turn.text for turn in visible}
    return all(plant.text in seen for plant in probe.resolved_plants if plant.answers)


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
    budget = estimate_tokens(prompt) + estimate_tokens(system) + options.num_predict
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
    visible = await strategy.select(transcript, probe.recall_prompt)
    context = render_context(visible)
    prompt = f"{context}\nUser: {probe.recall_prompt}\nAssistant:"

    response = await client.generate(
        prompt=prompt,
        system=system,
        model=model,
        options_override=options.as_override(),
    )

    # See runner.py::run_probe's identical comment: computed once and kept
    # on the result rather than only feeding the boundary check.
    post_processed = strip_thoughts(response)
    views = response_views(response)
    checks: list[CheckResult] = []
    for check in probe.checks:
        if check.kind == "boundary":
            ok, reason = await manager.validate_response(post_processed, goal="eval")
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
        post_processed_output=post_processed,
        checks=checks,
        passed=all(item.passed for item in checks),
        score=sum(1 for item in checks if item.passed) / len(checks),
        context_strategy=strategy.name,
        context_turns=len(visible),
        context_chars=len(context),
        plant_visible=_answers_visible(probe, visible),
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
    """Probe recall of a fact planted earlier in a conversation.

    Always the `"llm"` path (see `EvalReport.path`), and only ever that one:
    `run_conversation_probe` calls `client.generate` directly, the same raw
    boundary `runner.run_eval`'s default measures -- there is no `action`-path
    variant of this suite (no `ActionService` involvement at all), and this
    function takes no `path` parameter for exactly that reason, unlike
    `run_eval`. `EvalReport.path` defaults to `"llm"` on its own, but this
    stamps it explicitly rather than leaning on that default: a schema default
    is not a promise about *this* function's behavior, and the two happening
    to agree today must not be the only thing keeping this report from being
    mistaken for one that went through `action.py`.
    """
    from .runner import (
        _provenance,
        current_git_revision,
        persona_version,
        reset_model_state,
    )

    system = manager.get_persona_prompt(current_mood_directive=EVAL_MOOD_DIRECTIVE)
    # Whatever state the runtime was already in changes the answers; see
    # `reset_model_state`. This suite is where that was measured, twice.
    await reset_model_state(client, system, model, options)

    results: list[ProbeResult] = []
    # Sequential for the same reason the single-turn runner is: one local
    # model, and concurrent generations on CPU contend for the same cores.
    #
    # Probe-major, strategy-minor: every strategy sees one probe before the
    # next probe is built. Retrievers index per transcript and skip a repeat,
    # so this ordering means each transcript is embedded and written to the
    # database once instead of once per strategy.
    for probe in probes:
        for strategy in strategies:
            result = await run_conversation_probe(
                client,
                manager,
                probe,
                filler,
                strategy,
                system,
                model,
                options,
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

    model_source: ModelSource = "explicit_cli" if model is not None else "harness_default"
    return EvalReport(
        model=model or client.model,
        persona_name=manager.persona.name,
        provenance=_provenance(),
        # Explicit, not the field default -- see this function's own
        # docstring for why "llm" is the only value this suite can produce.
        path="llm",
        options=options.as_override(),
        model_source=model_source,
        deployment_llm_provenance=dict(config_module.config_instance.LLM_PROVENANCE),
        system_prompt_sha256=fingerprint(system),
        persona_version=persona_version(manager.persona),
        git_revision=current_git_revision(),
        results=results,
        by_category=summarize_by_category(results),
    )


def load_conversation_pack(
    path: Path,
) -> tuple[list[ConversationProbe], list[tuple[str, str]]]:
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
    return (
        Path(__file__).parent / "probes" / "conversation" / "conversation_recall.json"
    )


def shipped_discriminating_pack() -> Path:
    """The pack written to separate two retrievers rather than to be answered.

    Not the default, and deliberately so. The shipped pack measures whether a
    fact survives distance, which is a question about the model; this one
    measures whether *this* retrieval beats a lexical baseline, which is a
    question about the architecture, and it requires ``--retrieval`` to mean
    anything at all.
    """
    return (
        Path(__file__).parent / "probes" / "conversation" / "discriminating_recall.json"
    )


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
    "shipped_discriminating_pack",
]
