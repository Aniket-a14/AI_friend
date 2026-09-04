"""Foundation model role taxonomy and provider capability negotiation.

`FINAL_HUMANOID_BRAIN_ARCHITECTURE.md` SS16/25 draws a hard line between the
brain kernel (authoritative state, identity invariants, appraisal, goals,
action commitment -- all owned by the agent-state service and the identity
manager in `app.state` / `app.cognitive`) and foundation models, which are
replaceable specialist adapters invoked for a narrow, named `ModelRole`.

This module defines that role taxonomy, the request/result contract each
role invocation is expected to honor, and `ProviderCapabilityNegotiator`,
which decides -- before any model is ever called -- whether a given
`model_tag` can honestly satisfy a role's requirements as recorded in
`app.llm.model_manifest`, and if not, which graceful fallback strategy
applies.

Everything here is a pure, side-effect-free computation over
`ModelCapability` data. It does not call a model, does not import the
agent-state service or the identity manager, and cannot mutate authoritative
state, identity invariants, or safety policy -- a fallback decision is advisory
information for the caller, never an action. That is deliberate: a
negotiator that could itself reach into agent state would be exactly the
kind of provider-swap hazard SS25 exists to rule out. See
`test_model_roles_vision.py`'s invariant tests for the checks that keep this
true as the module evolves.

Peer review (`orchestration/PHASE_05/CODEX_REVIEW_OF_CLAUDE.md`) found a real
gap in that story: negotiation being pure and advisory is not the same as
the *result* of running a role being trustworthy. `RoleExecutionResult`
originally defaulted `validated=True`, so an arbitrary, never-checked result
(the review's own probe: `RoleExecutionResult(raw_output="unsafe claim")`)
reported itself as validated with no work done to earn that. `validated`
now defaults to `False` -- fail-closed, matching the rest of this module's
posture -- and `validate_execution_result` is the one function allowed to
flip it to `True`, only after checking the request's `allowed_claims` and
`schema_definition` against what the result actually produced.
`ensure_committable` is the hard gate: it raises `RoleResultRejected` for
any result -- `NATIVE` or either fallback strategy alike -- that reaches it
without having passed that check. Fallback strategy grants no exemption;
there is no code path from "negotiation chose a strategy" to "commit this
result" that does not pass through `ensure_committable`.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

import jsonschema
from pydantic import BaseModel, Field

from app.llm.model_manifest import ModelCapability, get_model_capability


class ModelRole(str, Enum):
    """The closed set of jobs a foundation model may be asked to do.

    Each role is a narrow, auditable unit of work -- never "run the agent" --
    so a provider swap changes how a job gets done, not what the brain is
    allowed to decide.
    """

    INTERPRETATION = "INTERPRETATION"
    CANDIDATE_GENERATION = "CANDIDATE_GENERATION"
    PLANNING = "PLANNING"
    EVALUATION = "EVALUATION"
    COMPRESSION = "COMPRESSION"
    REALIZATION = "REALIZATION"


class ProviderScenario(str, Enum):
    """Taxonomy of the deployment shapes a role invocation may run under.

    Purely descriptive -- `classify_scenario` derives it from whatever the
    manifest already knows about a `model_tag`, it never changes negotiation
    behavior on its own. Callers use it to log or report which shape of
    provider a given negotiation ran against.
    """

    SCENARIO_A_FRONTIER = "SCENARIO_A_FRONTIER"
    SCENARIO_B_LOCAL_COMPACT = "SCENARIO_B_LOCAL_COMPACT"
    SCENARIO_C_ALTERNATIVE_PROVIDER = "SCENARIO_C_ALTERNATIVE_PROVIDER"


class FallbackStrategy(str, Enum):
    """The closed set of outcomes `ProviderCapabilityNegotiator` may return.

    Closed deliberately: a fallback string invented ad hoc at a call site
    would be an unaudited escape hatch. Every strategy here is advisory only
    -- degrading a role's ambition or declining to run it -- never a
    direction to skip a validator, widen a claim, or touch agent state.
    """

    NATIVE = "NATIVE"
    TEMPLATE_PROCEDURE = "TEMPLATE_PROCEDURE"
    ROLE_DEGRADATION = "ROLE_DEGRADATION"
    ABSTAIN = "ABSTAIN"


class RoleExecutionRequest(BaseModel):
    """What a caller asks a role to do, independent of which model runs it."""

    role: ModelRole
    prompt: str
    system_prompt: str | None = None
    schema_definition: dict[str, Any] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    budget_tokens: int = 512
    budget_time_s: float = 10.0
    model_tag: str | None = None


class RoleExecutionResult(BaseModel):
    """What came back from running a role, including whether it was native
    or a fallback was applied to get there.

    `validated` defaults to `False`: a freshly constructed result has not
    been checked against its request's `allowed_claims` or
    `schema_definition` yet, and reporting itself trustworthy by default
    would make that check optional in practice. Only
    `validate_execution_result` may set this `True`, and only after the
    checks actually pass.
    """

    role: ModelRole
    raw_output: str
    parsed_output: Any = None
    validated: bool = False
    fallback_strategy: FallbackStrategy = FallbackStrategy.NATIVE
    fallback_applied: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str | None = None


class RoleRequirement(BaseModel):
    """The minimum `ModelCapability` a role needs to run in its native mode."""

    min_context_window: int
    requires_structured_output: bool = False
    requires_streaming: bool = False


# Requirements are deliberately conservative per role rather than uniform:
# PLANNING and EVALUATION commit to structured claims a downstream validator
# will check, so they need `structured_output`; COMPRESSION has to see the
# material it is condensing, so its context floor is the highest of the six;
# CANDIDATE_GENERATION and REALIZATION are consumed incrementally by the
# streaming pipeline (`cognitive/action.py`), so they need `streaming`.
ROLE_REQUIREMENTS: dict[ModelRole, RoleRequirement] = {
    ModelRole.INTERPRETATION: RoleRequirement(
        min_context_window=4096, requires_structured_output=True
    ),
    ModelRole.CANDIDATE_GENERATION: RoleRequirement(
        min_context_window=4096, requires_streaming=True
    ),
    ModelRole.PLANNING: RoleRequirement(
        min_context_window=8192, requires_structured_output=True
    ),
    ModelRole.EVALUATION: RoleRequirement(
        min_context_window=4096, requires_structured_output=True
    ),
    ModelRole.COMPRESSION: RoleRequirement(min_context_window=65536),
    ModelRole.REALIZATION: RoleRequirement(
        min_context_window=2048, requires_streaming=True
    ),
}

# Recognized only to classify an *unregistered* tag as a plausible frontier
# offering for reporting purposes; classification never trusts the name
# alone to grant capabilities -- see `classify_scenario` and
# `evaluate_capability` below, where an unregistered tag always abstains
# regardless of which prefix it matches.
_FRONTIER_TAG_PREFIXES: tuple[str, ...] = (
    "claude-",
    "gpt-",
    "o1-",
    "o3-",
    "gemini-",
)


def classify_scenario(model_tag: str) -> ProviderScenario:
    """Label which deployment shape `model_tag` plausibly represents.

    A tag registered in `model_manifest` is treated as the local compact
    fleet this repo actually runs (Scenario B). An unregistered tag whose
    name matches a known frontier-provider naming convention is labeled
    Scenario A for reporting; anything else unregistered is Scenario C, an
    alternative provider this deployment has no capability data for. This
    function only labels -- it never feeds back into whether a role is
    allowed to run.
    """
    if get_model_capability(model_tag) is not None:
        return ProviderScenario.SCENARIO_B_LOCAL_COMPACT
    if model_tag.lower().startswith(_FRONTIER_TAG_PREFIXES):
        return ProviderScenario.SCENARIO_A_FRONTIER
    return ProviderScenario.SCENARIO_C_ALTERNATIVE_PROVIDER


class ProviderCapabilityNegotiator:
    """Decides, before any model call, whether `model_tag` can honestly run
    `role` natively, and if not, which fallback strategy applies.

    Both methods are pure functions of their arguments: no model is called,
    no state is read or written outside the immutable `ModelCapability`
    records in `model_manifest`, and the returned strategy is always one of
    `FallbackStrategy`'s four closed values. That closure is what makes the
    "fallbacks never bypass identity constraints, safety rules, or mutate
    authoritative state" invariant hold structurally rather than by
    convention: there is no code path here that reaches into the
    agent-state service or the identity manager, and a caller cannot
    receive a strategy this enum does not define.
    """

    def evaluate_capability(
        self, role: ModelRole, capability: ModelCapability | None
    ) -> tuple[bool, str, dict[str, Any]]:
        """Match `role`'s requirement against an already-resolved
        `capability`. Exposed separately from `negotiate_role` so a caller
        (or a test) that already has a `ModelCapability` -- from a manifest
        lookup elsewhere, or a synthetic one describing a provider not yet
        catalogued -- can negotiate without needing a registered tag."""
        requirement = ROLE_REQUIREMENTS[role]

        if capability is None:
            return (
                False,
                FallbackStrategy.ABSTAIN.value,
                {"reason": "capability_unknown", "role": role.value},
            )

        if requirement.requires_structured_output and not capability.structured_output:
            return (
                False,
                FallbackStrategy.TEMPLATE_PROCEDURE.value,
                {
                    "reason": "missing_structured_output",
                    "role": role.value,
                    "required_min_context_window": requirement.min_context_window,
                },
            )

        if capability.context_window < requirement.min_context_window:
            return (
                False,
                FallbackStrategy.ROLE_DEGRADATION.value,
                {
                    "reason": "insufficient_context_window",
                    "role": role.value,
                    "available_context_window": capability.context_window,
                    "required_context_window": requirement.min_context_window,
                },
            )

        if requirement.requires_streaming and not capability.streaming:
            return (
                False,
                FallbackStrategy.ROLE_DEGRADATION.value,
                {"reason": "missing_streaming", "role": role.value},
            )

        return (
            True,
            FallbackStrategy.NATIVE.value,
            {"reason": "native_fit", "role": role.value},
        )

    def negotiate_role(
        self, role: ModelRole, model_tag: str
    ) -> tuple[bool, str, dict[str, Any]]:
        """Look `model_tag` up in `model_manifest` and negotiate `role`
        against whatever capability record (or absence of one) comes back.
        An unregistered tag always abstains -- see `evaluate_capability` --
        regardless of what `classify_scenario` labels it as; the label is
        carried in the returned details purely for reporting."""
        capability = get_model_capability(model_tag)
        fits, strategy, details = self.evaluate_capability(role, capability)
        details = dict(details)
        details["model_tag"] = model_tag
        details["scenario"] = classify_scenario(model_tag).value
        return fits, strategy, details


def _check_allowed_claims(
    request: RoleExecutionRequest, result: RoleExecutionResult
) -> list[str]:
    """Verify every claim `result` actually makes is a member of
    `request.allowed_claims`.

    "Claims made" is read from `result.parsed_output`: a bare list is taken
    as the claim identifiers directly, and a dict is checked for a
    `"claims"` key holding such a list -- the two natural shapes a role's
    structured output would take. If `allowed_claims` is empty, the request
    places no claim restriction and this check trivially passes. If it is
    non-empty but `parsed_output` provides nothing checkable, that is
    treated as a failure rather than a pass: a caller that bothered to
    restrict claims gets no benefit from that restriction if an
    unstructured result is silently exempted from it.
    """
    if not request.allowed_claims:
        return []

    allowed = set(request.allowed_claims)
    claims_made: list[Any] | None = None
    if isinstance(result.parsed_output, list):
        claims_made = result.parsed_output
    elif isinstance(result.parsed_output, dict):
        maybe_claims = result.parsed_output.get("claims")
        if isinstance(maybe_claims, list):
            claims_made = maybe_claims

    if claims_made is None:
        message = (
            "allowed_claims is configured but parsed_output provides no checkable "
            "claims list (expected a list, or a dict with a 'claims' list)"
        )
        return [message]

    errors = [
        f"claim not in allowed_claims: {claim!r}"
        for claim in claims_made
        if str(claim) not in allowed
    ]
    return errors


def _check_schema_definition(
    parsed_output: Any, schema_definition: dict[str, Any]
) -> list[str]:
    """Validate `parsed_output` against `schema_definition` using the real
    JSON Schema spec (the `jsonschema` package), rather than a hand-rolled
    subset that would only ever cover whatever someone remembered to
    implement."""
    try:
        jsonschema.validate(instance=parsed_output, schema=schema_definition)
    except jsonschema.ValidationError as exc:
        return [f"schema validation failed: {exc.message}"]
    except jsonschema.SchemaError as exc:
        return [f"schema_definition is not a valid JSON Schema: {exc.message}"]
    return []


def validate_execution_result(
    request: RoleExecutionRequest,
    result: RoleExecutionResult,
    custom_validator: Callable[[Any], bool] | None = None,
) -> RoleExecutionResult:
    """The enforceable gate a `RoleExecutionResult` must pass before it may
    be treated as committable, regardless of whether it is `NATIVE` or
    either fallback strategy.

    Checks, in order: `request.allowed_claims` against whatever claims
    `result.parsed_output` actually makes; `request.schema_definition`
    against `result.parsed_output`'s shape, if a schema was given; and
    `custom_validator(result.parsed_output)`, if the caller supplied one,
    for a check specific to that call site (a raising validator is treated
    as a failure, not propagated -- a broken validator must not crash the
    gate it is supposed to be strengthening).

    Returns a new `RoleExecutionResult` (this module stays pure throughout,
    per its own module docstring) with `validated=True` only if every
    configured check passed; otherwise `validated=False` and
    `validation_errors` lists every reason, so a caller inspecting a
    rejected result can see why without re-deriving the checks itself.
    """
    errors = list(_check_allowed_claims(request, result))

    if request.schema_definition is not None:
        errors.extend(_check_schema_definition(result.parsed_output, request.schema_definition))

    if custom_validator is not None:
        try:
            if not custom_validator(result.parsed_output):
                errors.append("custom_validator rejected parsed_output")
        except Exception as exc:
            # A broken custom_validator must not crash the gate it is
            # supposed to be strengthening -- record it as a failure instead.
            errors.append(f"custom_validator raised {type(exc).__name__}: {exc}")

    return result.model_copy(update={"validated": not errors, "validation_errors": errors})


class RoleResultRejected(Exception):
    """Raised by `ensure_committable` for a `RoleExecutionResult` that has
    not passed `validate_execution_result`."""


def ensure_committable(result: RoleExecutionResult) -> RoleExecutionResult:
    """The single required checkpoint before a `RoleExecutionResult` --
    `NATIVE` or any fallback strategy alike -- may be used as committed
    input to a candidate or action.

    Raises `RoleResultRejected` if `result.validated` is not `True`: a
    result that was never run through `validate_execution_result`, or was
    and failed it. A result's `fallback_strategy` grants no exemption --
    `TEMPLATE_PROCEDURE` and `ROLE_DEGRADATION` are checked exactly like
    `NATIVE`, because a degraded role is still asserting claims into
    cognition and a template is still producing output a caller might act
    on. This is what makes "fallbacks cannot bypass validation" an
    enforced property of this module rather than a convention callers are
    trusted to follow: there is no path to commitment that skips this
    function.
    """
    if not result.validated:
        reason = "; ".join(result.validation_errors) or "result was never validated"
        raise RoleResultRejected(
            f"RoleExecutionResult for role {result.role.value} "
            f"(fallback_strategy={result.fallback_strategy.value}) is not "
            f"committable: {reason}"
        )
    return result
