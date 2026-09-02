"""Run probes against a model at the LLM boundary and score the answers.

The boundary matters more than the code here. Fine-Tuned Adapter's consolidation loop
changes exactly one thing — the weights behind `OllamaClient.generate` — while
everything above that call (retrieval, state, the action pipeline) is untouched
by an adapter swap. So the harness evaluates precisely that seam: the real
persona prompt from the real `IdentityManager`, the real client, and nothing
else. No NATS, no databases, no mesh.

The mood directive is pinned to a fixed neutral string because volatile affect
is *supposed* to change responses; an eval that let it float would measure the
agent's mood, not the model's behavior.
"""

import json
import logging
import subprocess
from pathlib import Path

import httpx

from app import config as config_module
from app.cognitive.identity import IdentityManager
from app.llm.ollama_client import OllamaClient

from .action_path import (
    ActionGenerationResult,
    PinnedOptionsClient,
    build_action_service,
    build_plan,
    generate_through_action_service,
)
from .schema import (
    DEFAULT_OPTIONS,
    CheckResult,
    EvalPath,
    EvalReport,
    ModelSource,
    Probe,
    ProbeResult,
    RunOptions,
    fingerprint,
    summarize_by_category,
)
from .scoring import evaluate_check, response_views, strip_thoughts

logger = logging.getLogger("evals.runner")

EVAL_MOOD_DIRECTIVE = "Calm and neutral (evaluation run)."

# evals/runner.py -> evals/ -> backend/ -> repo root. Fixed, not the process
# cwd, for the same reason `app/config.py`'s `_env_file` isn't: an eval can be
# launched from `backend/`, a repo-root shell, or anywhere else, and "git
# revision" must name the same repo either way.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _provenance() -> str:
    # Read from the live instance, not the Config metaclass, so a test that
    # patches `config_module.config_instance` is seen. Truthful stamping is
    # the harness's core integrity property: a mock run may be useful for
    # exercising the plumbing, but its report must never be mistakable for
    # evidence about a model.
    if getattr(config_module.config_instance, "MOCK_LLM_TEXT", False):
        return "mock"
    return "live"


def current_git_revision() -> str:
    """Short SHA of the checkout this run executed from.

    "<sha>-dirty" if the working tree carried uncommitted changes at run
    time -- a report from a dirty tree is evidence about code that no commit
    names, which matters exactly as much as the model tag does. "unknown" if
    git itself is unavailable (no `.git`, no `git` binary) rather than
    raising: like `reset_model_state`'s unload/warm-up, a report missing this
    is worse than one that tried and said so, but a probe run must never go
    down over a call whose only job is metadata.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=_REPO_ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        )
        return f"{sha}-dirty" if dirty else sha
    except Exception:
        return "unknown"


def persona_version(persona) -> str:
    """Digest of the structured `PersonaProfile` alone -- see
    `EvalReport.persona_version` for what this answers that
    `system_prompt_sha256` doesn't.

    Best-effort like `current_git_revision`: a caller passing something that
    isn't a real `PersonaProfile` (a stand-in in a test, a future caller that
    doesn't yet have one loaded) must degrade to "unknown provenance", not
    take the whole run down over a metadata field nobody asked to gate on.
    """
    try:
        return fingerprint(persona.model_dump_json())
    except Exception:
        return ""


def structured_fingerprint(value: object) -> str:
    """Hash canonical JSON-shaped eval inputs without retaining their text."""
    try:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return fingerprint(encoded)
    except Exception:
        return ""


def request_provenance(client: object) -> list[dict]:
    """Return the client's observed request trace, or an explicit empty trace."""
    trace = getattr(client, "request_provenance", None)
    if not isinstance(trace, list):
        return []
    return [dict(item) for item in trace if isinstance(item, dict)]


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
                response = await http.post(
                    "/api/generate", json={"model": target, "keep_alive": 0}
                )
            # A refused unload raises nothing -- Ollama answers 404 for an
            # unknown tag and the previous model simply stays resident. Since
            # the unload is the half that makes the starting state specified,
            # a silent no-op removes that property while the report still
            # implies it. Say so.
            if response.status_code >= 400:
                logger.warning(
                    "[eval] unload of %s refused (HTTP %s); the run starts from "
                    "whatever was already resident",
                    target,
                    response.status_code,
                )
        except Exception as exc:
            logger.warning("[eval] could not unload %s before the run: %s", target, exc)

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
    generate=None,
) -> ProbeResult:
    """Score one probe.

    `generate` is how the response is produced: `None` keeps the original LLM
    boundary (persona prompt straight into `OllamaClient.generate`). The action
    path passes a callable that drives the same probe through the real
    `ActionService` instead. Everything after the response -- the checks, the
    boundary delegation to `IdentityManager.validate_response`, the scoring --
    is deliberately shared and unchanged, so a verdict means the same thing on
    either path and `compare` has one implementation to serve both.
    """
    if generate is None:
        response = await client.generate(
            prompt=probe.prompt,
            system=system,
            model=model,
            options_override=options.as_override(),
        )
    else:
        generated = await generate(probe.prompt)
        if isinstance(generated, ActionGenerationResult):
            response = generated.response
            raw_response = generated.raw_response
        else:
            response = str(generated)
            raw_response = response

    if generate is None:
        raw_response = response

    # Computed once and kept on the result (§17: "raw output and
    # post-processed output" as separate evidence) rather than only living
    # long enough to feed the boundary check and then being discarded.
    post_processed = strip_thoughts(response)
    views = response_views(response)
    checks: list[CheckResult] = []
    for check in probe.checks:
        if check.kind == "boundary":
            ok, reason = await manager.validate_response(post_processed, goal="eval")
            checks.append(CheckResult(kind="boundary", passed=ok, detail=reason))
        else:
            checks.append(evaluate_check(check, views))

    passed = all(item.passed for item in checks)
    return ProbeResult(
        probe_id=probe.id,
        category=probe.category,
        prompt=probe.prompt,
        response=response,
        raw_response=raw_response,
        prompt_sha256=fingerprint(probe.prompt),
        post_processed_output=post_processed,
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
    path: EvalPath = "llm",
) -> EvalReport:
    """Probe a model and write a report.

    `path` chooses what is measured. "llm" is the original seam and stays the
    default, because it is the one a fine-tuned adapter changes and every
    existing baseline was taken there. "action" runs each probe through the
    real `ActionService`, which is the only way to gate a change to
    `action.py`'s own prompt construction -- see `action_path.py` for why that
    gap existed and what it let through.
    """
    persona_prompt = manager.get_persona_prompt(
        current_mood_directive=EVAL_MOOD_DIRECTIVE
    )

    generate = None
    pinned: PinnedOptionsClient | None = None
    if path == "action":
        pinned = PinnedOptionsClient(client, options)
        service = build_action_service(pinned)

        async def generate(prompt: str) -> ActionGenerationResult:
            return await generate_through_action_service(
                service, build_plan(prompt, persona_prompt, model),
                with_provenance=True,
            )

    # Warm-up goes through the plain client either way: it is discarded text
    # whose only job is to leave the runtime in a named state, and routing it
    # through ActionService would add a turn's worth of failure modes to a call
    # nobody scores.
    await reset_model_state(client, persona_prompt, model, options)

    results: list[ProbeResult] = []
    # Sequential on purpose: one local model, and concurrent generations on a
    # CPU-only box would contend for the same cores and skew nothing useful.
    for probe in probes:
        result = await run_probe(
            client, manager, probe, persona_prompt, model, options, generate
        )
        logger.info(
            "[eval] %-32s %s (%.2f)",
            probe.id,
            "pass" if result.passed else "FAIL",
            result.score,
        )
        results.append(result)

    # Fingerprint what the model was actually given. On the action path that is
    # not the persona prompt: `_execute_respond_chat` appends `_CHAT_GUIDELINE`
    # to it. Read back from the client that saw the call rather than rebuilt
    # here, so this cannot drift out of step with `action.py` -- a local copy of
    # that composition would keep producing a plausible digest after the
    # composition changed, which is the failure mode a digest exists to catch.
    observed = pinned.observed_system if pinned else None
    # Reflects the parameter this function actually received, not a guess:
    # the CLI passes `args.model` straight through, so `model is None` here
    # means --model genuinely was not given.
    model_source: ModelSource = "explicit_cli" if model is not None else "harness_default"
    return EvalReport(
        model=model or client.model,
        persona_name=manager.persona.name,
        provenance=_provenance(),
        path=path,
        suite="single_turn",
        options=options.as_override(),
        model_source=model_source,
        deployment_llm_provenance=dict(config_module.config_instance.LLM_PROVENANCE),
        llm_endpoint=str(getattr(client, "base_url", "") or ""),
        request_provenance=request_provenance(client),
        probe_set_sha256=structured_fingerprint(
            {"path": path, "probes": [probe.model_dump(mode="json") for probe in probes]}
        ),
        system_prompt_sha256=fingerprint(observed or persona_prompt),
        persona_version=persona_version(manager.persona),
        git_revision=current_git_revision(),
        results=results,
        by_category=summarize_by_category(results),
    )
