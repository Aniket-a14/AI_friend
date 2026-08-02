"""Run probes against a model at the LLM boundary and score the answers.

The boundary matters more than the code here. CVS-4's consolidation loop
changes exactly one thing — the weights behind `OllamaClient.generate` — while
everything above that call (retrieval, state, the action pipeline) is untouched
by an adapter swap. So the harness evaluates precisely that seam: the real
persona prompt from the real `IdentityManager`, the real client, and nothing
else. No NATS, no databases, no mesh.

The mood directive is pinned to a fixed neutral string because volatile affect
is *supposed* to change responses; an eval that let it float would measure the
agent's mood, not the model's behavior.
"""

import logging

import httpx

from app import config as config_module
from app.cognitive.identity import IdentityManager
from app.llm.ollama_client import OllamaClient

from .schema import (
    DEFAULT_OPTIONS,
    CheckResult,
    EvalReport,
    Probe,
    ProbeResult,
    RunOptions,
    fingerprint,
    summarize_by_category,
)
from .scoring import evaluate_check, response_views, strip_thoughts

logger = logging.getLogger("evals.runner")

EVAL_MOOD_DIRECTIVE = "Calm and neutral (evaluation run)."


def _provenance() -> str:
    # Read from the live instance, not the Config metaclass, so a test that
    # patches `config_module.config_instance` is seen. Truthful stamping is
    # the harness's core integrity property: a mock run may be useful for
    # exercising the plumbing, but its report must never be mistakable for
    # evidence about a model.
    if getattr(config_module.config_instance, "MOCK_LLM_TEXT", False):
        return "mock"
    return "live"


async def reset_model_state(
    client: OllamaClient,
    system: str,
    model: str | None,
    options: RunOptions,
) -> None:
    """Put the runtime into a *specified* state before anything is scored.

    Measured on qwen2.5:3b, two separate batches of three runs each. Within a
    batch, the runs that started from the same condition were byte-identical
    across all sixteen probes; the run that started from a different one
    disagreed with them on two to three probes and flipped a verdict each time.
    Sampling was pinned, every prompt matched byte for byte, and Ollama itself
    proved deterministic within a load, across reloads, and under VRAM
    contention. What differed was the state the process was already in.

    So the fix is not to converge on a state but to name one. Unloading first
    (``keep_alive: 0``) discards whatever the last run left resident, and the
    warm-up generation that follows reloads the model and leaves it in the same
    place every time. A first attempt used only the warm-up and left the
    unload out; two of sixteen probes still moved, because "freshly loaded"
    and "holding the previous run's residue" are different starting points and
    one short generation does not close the gap between them.

    Both steps are best-effort. They buy reproducibility, not correctness, and
    the probes report a genuinely unreachable model far more legibly than an
    exception from a call whose output is discarded.
    """
    target = model or client.model
    # Asked for explicitly rather than caught as an AttributeError, so a stand-in
    # client in a test declines the unload by not offering an address instead of
    # by raising inside it.
    base_url = getattr(client, "base_url", None)
    if isinstance(base_url, str) and base_url:
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as http:
                await http.post(
                    "/api/generate", json={"model": target, "keep_alive": 0}
                )
        except Exception as exc:
            logger.warning(
                "[eval] could not unload %s before the run: %s", target, exc
            )

    try:
        await client.generate(
            prompt="Warm-up call. Reply with one word.",
            system=system,
            model=model,
            options_override={**options.as_override(), "num_predict": 8},
        )
    except Exception as exc:
        logger.warning("[eval] warm-up generation failed: %s", exc)


async def run_probe(
    client: OllamaClient,
    manager: IdentityManager,
    probe: Probe,
    system: str,
    model: str | None,
    options: RunOptions,
) -> ProbeResult:
    response = await client.generate(
        prompt=probe.prompt,
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

    passed = all(item.passed for item in checks)
    return ProbeResult(
        probe_id=probe.id,
        category=probe.category,
        prompt=probe.prompt,
        response=response,
        checks=checks,
        passed=passed,
        score=sum(1 for item in checks if item.passed) / len(checks),
    )


async def run_eval(
    client: OllamaClient,
    manager: IdentityManager,
    probes: list[Probe],
    model: str | None = None,
    options: RunOptions = DEFAULT_OPTIONS,
) -> EvalReport:
    system = manager.get_persona_prompt(current_mood_directive=EVAL_MOOD_DIRECTIVE)
    await reset_model_state(client, system, model, options)

    results: list[ProbeResult] = []
    # Sequential on purpose: one local model, and concurrent generations on a
    # CPU-only box would contend for the same cores and skew nothing useful.
    for probe in probes:
        result = await run_probe(client, manager, probe, system, model, options)
        logger.info(
            "[eval] %-32s %s (%.2f)",
            probe.id,
            "pass" if result.passed else "FAIL",
            result.score,
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
