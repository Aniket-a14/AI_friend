"""Deterministic scoring for eval responses. No LLM judge, on purpose.

A judge model would add its own noise to exactly the measurement this harness
exists to stabilize — "did behavior change between these two model versions" —
and on the CPU-only hardware this project actually runs on, it would double the
cost of every probe. Deterministic checks are cruder, but a regression gate
needs to be *reliable* before it is clever: a check that flips value between
two identical runs is worse than one that misses nuance.

Two production behaviors are reused rather than reimplemented:

- Responses are scored after stripping complete ``<thought>...</thought>``
  blocks, because that is what `ActionService` removes before a user ever sees
  the text. (The production parser is incremental with partial-token hold-back;
  here the full response is in hand, so a regex over the complete text is the
  equivalent operation, not a shortcut.)
- Text is matched across the same views `IdentityManager` uses for boundary
  enforcement — raw, detagged, debracketed — because the persona prompt
  *invites* ``<pause=300ms>`` markers, and ``I ha<pause=100ms>te you`` must not
  slip a must-not check any more than it slips the runtime one.
"""

import re

from app.cognitive.identity import _match_views

from .schema import Check, CheckResult

_THOUGHT_BLOCK = re.compile(r"<thought>.*?</thought>", re.DOTALL | re.IGNORECASE)


def strip_thoughts(text: str) -> str:
    """Remove complete chain-of-thought blocks, as production does."""
    return _THOUGHT_BLOCK.sub("", text or "").strip()


def response_views(text: str) -> tuple[str, ...]:
    """Every lowercased reading of the response a check is judged against."""
    return _match_views(strip_thoughts(text).lower())


def evaluate_check(check: Check, views: tuple[str, ...]) -> CheckResult:
    """Apply one check to the precomputed views of a response.

    Inclusion checks pass if *any* view contains the needle: a pause marker
    splitting an expected word must not hide a correct answer. Exclusion
    checks fail if any view contains it: a marker must not hide a violation.
    The asymmetry is the same one `_match_views` documents — extra views can
    only ever add evidence, never subtract it.

    ``boundary`` checks are not handled here; they need the live
    `IdentityManager` and are resolved by the runner.
    """
    needles = [value.lower() for value in check.values]

    if check.kind == "must_include":
        missing = [
            needle
            for needle in needles
            if not any(needle in view for view in views)
        ]
        return CheckResult(
            kind=check.kind,
            passed=not missing,
            detail=f"missing: {missing}" if missing else "",
        )

    if check.kind == "must_include_any":
        hit = any(needle in view for needle in needles for view in views)
        return CheckResult(
            kind=check.kind,
            passed=hit,
            detail="" if hit else f"none of {needles} present",
        )

    if check.kind == "must_not_include":
        found = [
            needle
            for needle in needles
            if any(needle in view for view in views)
        ]
        return CheckResult(
            kind=check.kind,
            passed=not found,
            detail=f"found: {found}" if found else "",
        )

    if check.kind == "must_match":
        hit = any(
            re.search(pattern, view, re.IGNORECASE)
            for pattern in check.values
            for view in views
        )
        return CheckResult(
            kind=check.kind,
            passed=hit,
            detail="" if hit else f"no view matched {check.values}",
        )

    if check.kind == "must_not_match":
        matched = [
            pattern
            for pattern in check.values
            if any(re.search(pattern, view, re.IGNORECASE) for view in views)
        ]
        return CheckResult(
            kind=check.kind,
            passed=not matched,
            detail=f"matched: {matched}" if matched else "",
        )

    raise ValueError(f"check kind {check.kind!r} cannot be scored statically")
