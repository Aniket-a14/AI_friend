#!/usr/bin/env python3
"""
P1-8: assert NATS subject wiring statically, in CI.

`ARCHITECTURE.md` (audit/, this repo's forensic audit) found eight subjects
wired at one end only across three separate milestones -- each failing half
compiled, passed its own tests, and logged as though it were working,
because NATS subjects are plain strings: nothing type-checks a publisher
against its subscriber, or a subject against the stream that is supposed to
carry it. This script is the fix for the *category*, not any one instance
of it: it statically enumerates every subject this codebase publishes or
subscribes to (Python via `Topics.*` / string literals / the
`"subject": "..."` mesh-signal dict pattern in `cognitive/pipeline.py`, Rust
via the `topics::*` constants), cross-references them against the `Topics`
enum, the Rust `topics` module, and the stream patterns in
`nats_streams.py`, and fails on:

  - a subject published but never subscribed, or subscribed but never
    published (one end wired, the other missing)
  - a subject that matches no declared JetStream stream pattern at all

A curated ALLOWLIST below covers issues already known and tracked in
`audit/ROADMAP.md` (or judged not to need a subscriber -- e.g. a
frontend/browser consumer this repo's static scan cannot see). Anything not
allowlisted is a new finding and fails the build; extending the allowlist
requires a reason, by construction of the data structure below.

Usage: python scripts/check_subject_wiring.py
Exit 0 = every subject is either fully wired or explicitly allowlisted.
Exit 1 = an unallowlisted issue exists (printed with locations).
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"
CRATES_ROOT = BACKEND_ROOT / "crates"
CONTRACTS_PY = APP_ROOT / "contracts.py"
NATS_STREAMS_PY = APP_ROOT / "nats_streams.py"
CONTRACTS_RS = CRATES_ROOT / "contracts" / "src" / "lib.rs"

# subject -> reason. Each entry is a defect already tracked in
# audit/ROADMAP.md (or a deliberate cross-boundary design, annotated as
# such), not something this check should keep discovering as new.
ALLOWLIST: dict[str, str] = {
    # M1-D1 / M0-D11: ROADMAP P4-1 is DONE (Stage 6) -- IdentityManager now
    # constructs a real IdentityCoreStore and its cache.sync broadcast is
    # live. This entry stays allowlisted for a structural reason, not an
    # open decision: the subscribe side lives in agents/base.py, which is
    # TRANSPORT_IMPL_FILES-excluded from this scan (it is generic transport
    # code, not per-subject business wiring), so the subscribe site is
    # invisible to this static scan regardless of whether it exists -- and
    # it does (BaseAgent.connect(), deliver_policy="new" per P3-8).
    "cache.sync": "subscriber lives in agents/base.py, excluded from this scan as generic transport code (TRANSPORT_IMPL_FILES) -- not missing, just invisible to it",
    # M2-A2: AGENT_VOICE_MODULATION is published to NATS but consumed by the
    # frontend voice UI directly (LiveKit data track / browser client), not
    # by another backend agent -- this scan only sees backend Python/Rust, so
    # a real consumer existing outside the repo's static reach is expected
    # here, not a defect.
    #
    # AUDIO_PLAYBACK_VISEMES used to carry the identical justification
    # (M2-A4), on the same reasoning -- but roadmap Phase 5.3 gave it a real
    # backend consumer (`transport_agent.py`'s `_on_viseme`, which bridges it
    # onto the room's LiveKit data channel for the frontend), so it is
    # deliberately no longer in this allowlist: this scan can and should see
    # that subscribe site on its own now.
    "agent.voice.modulation": "consumed by the frontend voice UI, not a backend agent",
    # M3-A1 / P4-2: Q-M3-1 resolved -- the intended publisher was always the
    # browser-side PCM player (docs/API_SPEC.md), never built. Subscriber
    # exists (brain_agent.py) and is a real, tracked gap, not new.
    "audio.playback.progress": "ROADMAP P4-2: intended publisher (browser player) never built",
    # M3-A5: matches no CORE_STREAMS pattern at all -- not `chat.>`,
    # `audio.>`, or any other declared wildcard.
    "ambient.noise.telemetry": "ROADMAP P3-12 / M3-A5: matches no declared stream pattern",
    # M4-11a / Q-M1-1: Rust subscribes over core NATS (not JetStream), so it
    # is invisible to a scan keyed on `topics::` constants passed to a
    # jetstream `.publish`/`.subscribe` call -- confirmed present by manual
    # read at M1/M3, tracked as a reliability trade-off, not missing wiring.
    "audio.stream": "ROADMAP P4-11a: Rust-side core-NATS subscriber, not JetStream-visible to this scan",
    # Discovered while building this check (not one of the audit's original
    # eight) -- genuinely new findings, allowlisted so this check can land
    # enforcing rather than warn-only, per ROADMAP P1-8. Investigated during
    # the 2026-08-22 backlog-clearing pass (see .agents/CONTEXT.md): two
    # were real gaps now closed (vision.frames wired, control.interrupt
    # deleted as dead code); the other four are real feature work with no
    # decided consumer, not unfinished wiring -- reasons sharpened below so
    # a future pass doesn't re-investigate them from scratch.
    "audio.pre_generate": "cognitive/pipeline.py publishes on VAP>=0.7 for speculative TTS pre-generation; the consumer side (voice-agent pre-warming TTS on this signal) was never built -- real Rust feature work, out of scope for a wiring fix",
    "telemetry.reflection": "cognitive/core.py publishes duration_ms + episode count on background reflection; matches no declared stream pattern and has zero subscribers -- a strong candidate for promotion once P3-2 (telemetry) is built, not before",
    "state.subconscious": "subconscious_agent's internal-monologue thought, zero subscribers -- no consumer has a decided purpose yet (UI surface? persistence sink?); needs a product decision before it needs wiring",
    "voice.segmentation_feedback": "brain_agent subscribes with an adaptive alpha-damped tuning loop, but voice-agent's Rust source has no chunk-size/segmentation-reporting code at all to hook a publisher into -- real new Rust feature work, not a missing call",
}

PUBLISH_METHODS = {"publish", "publish_cb", "publish_with_headers", "publish_pcm"}
SUBSCRIBE_METHODS = {"subscribe"}

# Python files whose publish/subscribe calls are the generic transport
# implementation (forwarding whatever subject the caller passed), not a
# declaration of a specific subject -- would only ever contribute noise to
# the UNRESOLVED bucket.
TRANSPORT_IMPL_FILES = {APP_ROOT / "agents" / "base.py"}


@dataclass
class Site:
    file: str
    line: int


@dataclass
class SubjectUsage:
    publish_sites: list[Site] = field(default_factory=list)
    subscribe_sites: list[Site] = field(default_factory=list)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_ROOT))
    except ValueError:
        return str(path)


def parse_python_topics() -> dict[str, str]:
    """Topics.NAME -> "subject.value", from the `class Topics(str, Enum)` in
    contracts.py."""
    tree = ast.parse(CONTRACTS_PY.read_text(), filename=str(CONTRACTS_PY))
    topics: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Topics":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    topics[stmt.targets[0].id] = stmt.value.value
    return topics


def parse_rust_topics() -> dict[str, str]:
    """topics::NAME -> "subject.value", from the Rust `pub mod topics` block."""
    text = CONTRACTS_RS.read_text()
    module_match = re.search(r"pub mod topics\s*\{(.*?)\n\}", text, re.DOTALL)
    if not module_match:
        return {}
    body = module_match.group(1)
    return dict(re.findall(r'pub const ([A-Z_]+):\s*&str\s*=\s*"([^"]+)";', body))


def parse_core_streams() -> dict[str, list[str]]:
    tree = ast.parse(NATS_STREAMS_PY.read_text(), filename=str(NATS_STREAMS_PY))
    for node in ast.walk(tree):
        # CORE_STREAMS: dict[str, Sequence[str]] = {...} is an AnnAssign
        # (annotated assignment), not a plain Assign.
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "CORE_STREAMS"
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    return {}


def subject_matches_pattern(subject: str, pattern: str) -> bool:
    """NATS wildcard match: `>` matches one or more trailing tokens, `*`
    matches exactly one token. Only `>` is actually used in this repo's
    CORE_STREAMS, but both are handled since they're both valid NATS syntax.
    """
    subj_tokens = subject.split(".")
    pat_tokens = pattern.split(".")

    for i, pat_tok in enumerate(pat_tokens):
        if pat_tok == ">":
            return len(subj_tokens) > i
        if i >= len(subj_tokens):
            return False
        if pat_tok == "*":
            continue
        if pat_tok != subj_tokens[i]:
            return False
    return len(subj_tokens) == len(pat_tokens)


def matches_any_stream(subject: str, streams: dict[str, list[str]]) -> bool:
    return any(
        subject_matches_pattern(subject, pattern)
        for patterns in streams.values()
        for pattern in patterns
    )


def _resolve_topics_attribute(node: ast.expr, py_topics: dict[str, str]) -> str | None:
    """Resolve `Topics.NAME` or `Topics.NAME.value` to its subject string."""
    target = node
    if (
        isinstance(target, ast.Attribute)
        and target.attr == "value"
        and isinstance(target.value, ast.Attribute)
    ):
        target = target.value
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "Topics"
    ):
        return py_topics.get(target.attr)
    return None


def scan_python(
    py_topics: dict[str, str], usage: dict[str, SubjectUsage], unresolved: list[Site]
) -> None:
    py_files = list(APP_ROOT.rglob("*.py"))
    main_py = BACKEND_ROOT / "main.py"
    if main_py.exists():
        py_files.append(main_py)

    for path in sorted(py_files):
        if "tests" in path.parts or path in TRANSPORT_IMPL_FILES:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            method = node.func.attr
            if method not in PUBLISH_METHODS and method not in SUBSCRIBE_METHODS:
                continue
            if not node.args:
                continue

            arg = node.args[0]
            subject: str | None = None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                subject = arg.value
            else:
                subject = _resolve_topics_attribute(arg, py_topics)

            site = Site(_rel(path), node.lineno)
            if subject is None:
                unresolved.append(site)
                continue

            entry = usage.setdefault(subject, SubjectUsage())
            if method in PUBLISH_METHODS:
                entry.publish_sites.append(site)
            else:
                entry.subscribe_sites.append(site)

        # Auxiliary pattern: `"subject": "literal"` dict entries, the shape
        # cognitive/pipeline.py's mesh_signal producers use -- the actual
        # publish call (cognitive/core.py's generic `self.agent.publish
        # (subject, data)`) takes a runtime variable, unresolvable by the
        # AST scan above, so this catches the subject at its true origin.
        text = path.read_text()
        for match in re.finditer(r'"subject":\s*"([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)"', text):
            line = text[: match.start()].count("\n") + 1
            entry = usage.setdefault(match.group(1), SubjectUsage())
            entry.publish_sites.append(Site(_rel(path), line))


def scan_rust(rust_topics: dict[str, str], usage: dict[str, SubjectUsage]) -> None:
    for path in sorted(CRATES_ROOT.rglob("src/*.rs")):
        text = path.read_text()
        for match in re.finditer(
            r"\.(publish|publish_with_headers|subscribe)\(\s*(?:\n\s*)?topics::([A-Z_]+)",
            text,
        ):
            method, const_name = match.group(1), match.group(2)
            subject = rust_topics.get(const_name)
            if subject is None:
                continue
            line = text[: match.start()].count("\n") + 1
            entry = usage.setdefault(subject, SubjectUsage())
            site = Site(_rel(path), line)
            if method == "subscribe":
                entry.subscribe_sites.append(site)
            else:
                entry.publish_sites.append(site)


def main() -> int:
    py_topics = parse_python_topics()
    rust_topics = parse_rust_topics()
    streams = parse_core_streams()

    usage: dict[str, SubjectUsage] = {}
    unresolved: list[Site] = []
    scan_python(py_topics, usage, unresolved)
    scan_rust(rust_topics, usage)

    known_subjects = set(py_topics.values()) | set(rust_topics.values())
    all_subjects = known_subjects | set(usage.keys())

    failures: list[str] = []
    allowlisted: list[str] = []

    for subject in sorted(all_subjects):
        entry = usage.get(subject, SubjectUsage())
        problems: list[str] = []

        if entry.publish_sites and not entry.subscribe_sites:
            problems.append("published but never subscribed")
        elif entry.subscribe_sites and not entry.publish_sites:
            problems.append("subscribed but never published")
        elif not entry.publish_sites and not entry.subscribe_sites:
            # Declared (in Topics/topics::) but used nowhere this scan can
            # see -- not this check's concern (that's dead-code territory,
            # a different finding class), so it's neither a failure nor
            # printed as one.
            continue

        if not matches_any_stream(subject, streams):
            problems.append("matches no declared stream pattern")

        if not problems:
            continue

        reason = ALLOWLIST.get(subject)
        detail = f"{subject}: {'; '.join(problems)}"
        if entry.publish_sites:
            detail += "\n    published at: " + ", ".join(
                f"{s.file}:{s.line}" for s in entry.publish_sites
            )
        if entry.subscribe_sites:
            detail += "\n    subscribed at: " + ", ".join(
                f"{s.file}:{s.line}" for s in entry.subscribe_sites
            )

        if reason is not None:
            allowlisted.append(f"{detail}\n    allowlisted: {reason}")
        else:
            failures.append(detail)

    print(f"Subjects declared (Topics/topics::): {len(known_subjects)}")
    print(f"Subjects observed in publish/subscribe call sites: {len(usage)}")
    if unresolved:
        print(
            f"Unresolved (dynamic) subject arguments -- informational, not "
            f"enforced: {len(unresolved)}"
        )
        for site in unresolved:
            print(f"    {site.file}:{site.line}")
    print()

    if allowlisted:
        print(f"=== {len(allowlisted)} known issue(s), allowlisted ===")
        for item in allowlisted:
            print(item)
        print()

    if failures:
        print(f"=== {len(failures)} UNALLOWLISTED issue(s) ===")
        for item in failures:
            print(item)
        print()
        print(
            "A subject above is wired at only one end, or matches no "
            "declared stream. If this is a real defect, fix it. If it is a "
            "deliberate design (e.g. a frontend-only consumer this scan "
            "cannot see), add it to ALLOWLIST in this script with a reason."
        )
        return 1

    print("OK: every observed subject is fully wired or explicitly allowlisted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
