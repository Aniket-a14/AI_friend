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
        results=results,
        by_category=summarize_by_category(results),
    )
