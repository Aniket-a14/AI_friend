#!/usr/bin/env python3
"""
Phase 1E: assert `contracts.TOPIC_DELIVERY` agrees with `nats_streams.py`'s
actual stream tiers, statically, in CI.

`TOPIC_DELIVERY` declares whether each subject is "durable" (replayable
cognition) or "best_effort" (lossy, low-latency audio/expression) -- a fact
that used to be implicit in which stream tier a subject's pattern happened
to fall into (`nats_streams.CORE_STREAMS`), or which client library a
process used to consume it. This script re-derives the stream-tier default
from `nats_streams.py` directly and fails if `TOPIC_DELIVERY` disagrees with
it, unless the subject is one of the two documented overrides in
`contracts.py` (each already justified there and in
`check_subject_wiring.py`'s ALLOWLIST) -- catching drift (a subject moved
between streams, a new subject added to `Topics` without a
`TOPIC_DELIVERY` entry, or an override that no longer matches reality) going
forward, matching `check_subject_wiring.py`'s own enforcing-not-warning
convention.

Usage: python scripts/diagnostics/check_delivery_semantics.py
Exit 0 = TOPIC_DELIVERY fully agrees with nats_streams.py's stream tiers.
Exit 1 = a subject's declared delivery semantics disagrees with its actual
         stream tier, or Topics/TOPIC_DELIVERY have drifted apart.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts import TOPIC_DELIVERY, Topics
from app.nats_streams import CORE_STREAMS

# Subjects whose declared delivery semantics deliberately disagrees with
# their raw stream-tier match. Each entry documents why -- see the matching
# comment block above `TOPIC_DELIVERY` in contracts.py.
DOCUMENTED_OVERRIDES: dict[Topics, str] = {
    Topics.AGENT_VOICE_MODULATION: (
        "matches AI_MESSAGES' agent.> pattern, but consumed only by the "
        "frontend voice UI over a lossy WebRTC data channel -- not durable "
        "cognition"
    ),
    Topics.AMBIENT_NOISE_TELEMETRY: (
        "matches no declared stream pattern (known gap, see "
        "check_subject_wiring.py's ALLOWLIST); consumed live over core NATS"
    ),
}


def subject_matches_pattern(subject: str, pattern: str) -> bool:
    """NATS wildcard match: `>` matches one or more trailing tokens, `*`
    matches exactly one token. Mirrors check_subject_wiring.py's helper of
    the same name -- duplicated rather than imported, since that script is
    a standalone CLI, not a module meant to be imported from."""
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


def derive_default(subject: str) -> str | None:
    """The stream-tier-derived default: best_effort for AI_AUDIO (`audio.>`,
    memory-backed, minutes-scale retention), durable for AI_MESSAGES
    (file-backed, week-scale). None if the subject matches no declared
    stream at all -- that subject has no principled default and MUST be a
    documented override."""
    for stream_name, patterns in CORE_STREAMS.items():
        if any(subject_matches_pattern(subject, pattern) for pattern in patterns):
            return "best_effort" if stream_name == "AI_AUDIO" else "durable"
    return None


def main() -> int:
    failures: list[str] = []

    declared_topics = set(TOPIC_DELIVERY.keys())
    all_topics = set(Topics)

    missing = all_topics - declared_topics
    for topic in sorted(missing, key=lambda t: t.value):
        failures.append(
            f"{topic.value}: declared in Topics but missing from TOPIC_DELIVERY"
        )

    orphaned = declared_topics - all_topics
    for topic in sorted(orphaned, key=lambda t: t.value):
        failures.append(
            f"{topic.value}: in TOPIC_DELIVERY but no longer a Topics member"
        )

    for topic in sorted(declared_topics & all_topics, key=lambda t: t.value):
        declared = TOPIC_DELIVERY[topic]
        default = derive_default(topic.value)

        if topic in DOCUMENTED_OVERRIDES:
            if default is not None and default == declared:
                failures.append(
                    f"{topic.value}: listed as a documented override "
                    f"({DOCUMENTED_OVERRIDES[topic]}) but its declared "
                    f"'{declared}' already matches the stream-tier default "
                    "-- the override is stale, remove it"
                )
            continue

        if default is None:
            failures.append(
                f"{topic.value}: matches no declared stream pattern, so it "
                f"has no principled default for its declared '{declared}' -- "
                "add it to DOCUMENTED_OVERRIDES with a reason, or wire it "
                "into a CORE_STREAMS pattern"
            )
        elif default != declared:
            failures.append(
                f"{topic.value}: declared '{declared}' but its stream tier "
                f"implies '{default}' -- fix TOPIC_DELIVERY, or add a "
                "documented override with a reason if this is deliberate"
            )

    print(f"Topics declared: {len(all_topics)}")
    print(f"TOPIC_DELIVERY entries: {len(declared_topics)}")
    print(f"Documented overrides: {len(DOCUMENTED_OVERRIDES)}")
    print()

    if failures:
        print(f"=== {len(failures)} delivery-semantics issue(s) ===")
        for item in failures:
            print(item)
        return 1

    print("OK: TOPIC_DELIVERY fully agrees with nats_streams.py's stream tiers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
