"""
Live-model check: does the persona compiler sand down an edgy description?

    cd backend
    ../.venv/bin/python -m scripts.testing.verify_persona_compiler_friction

Phase 2.1 of the community roadmap decided friction should come from what the
user writes, not from a house style the compiler imposes -- a description of
someone blunt must produce a blunt persona, not an agreeable default the model
reached for out of habit. That is a claim about what a REAL model actually
does, so it cannot be verified by reading the prompt or by a mocked test (see
`backend/tests/test_persona_compiler.py`'s own docstring for why). This script
runs `compile_persona` against three deliberately edgy descriptions and checks
the output for two ways an LLM tends to soften things: replacing the
description's own edge words with agreeable synonyms, and pulling the warmth
baseline toward positive regardless of what was described.

Follows this repo's `evals/`-style convention for a script that makes a real
LLM call (see `evals/__main__.py`): refuses to run against `MOCK_LLM_TEXT`
unless `--allow-mock` is passed, in which case the checks below would be
comparing the compiler's own deterministic mock strings against themselves --
plumbing check only, not evidence about a real model.
"""

import argparse
import asyncio
import os
import sys

# Add project root (backend/) to path -- matches every other entry point under
# backend/scripts/, since this is run directly rather than through pytest's
# `pythonpath = .`.
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import Config
from app.llm.ollama_client import OllamaClient
from app.persona.compiler import CompiledPersona, compile_persona

# Each case: a description with clear edge, and the words we'd expect to
# survive into base_tone/identity_summary/traits if the compiler didn't sand
# it down. Not an exhaustive lexicon -- one visible survivor is enough to show
# the edge wasn't erased; the point is these are near-synonyms of the
# description's own language, not a fixed vocabulary the compiler could game.
CASES: list[dict] = [
    {
        "description": (
            "She's blunt to the point of rudeness. She doesn't sugarcoat "
            "anything and gets genuinely annoyed when I dodge a question or "
            "make excuses. She will tell me flat out when she thinks I'm "
            "wrong, even if it stings."
        ),
        "edge_words": [
            "blunt",
            "rude",
            "harsh",
            "annoyed",
            "irritat",
            "direct",
            "curt",
            "sharp",
            "critical",
            "stern",
            "frank",
            "brusque",
        ],
        "expect_nonpositive_valence": True,
    },
    {
        "description": (
            "He's a moody guy -- his mood can flip fast, he holds grudges "
            "for a long time, and he does not warm up to people easily. "
            "Trust has to be earned slowly with him."
        ),
        "edge_words": [
            "moody",
            "guarded",
            "reserved",
            "grudge",
            "distant",
            "cold",
            "wary",
            "cautious",
            "slow to trust",
            "aloof",
        ],
        "expect_nonpositive_valence": True,
    },
    {
        "description": (
            "She has zero patience for small talk and will just say 'get to "
            "the point' if I ramble. She's competitive, argumentative, and "
            "will push back hard if she disagrees with me."
        ),
        "edge_words": [
            "impatient",
            "argumentative",
            "competitive",
            "confrontational",
            "pushes back",
            "blunt",
            "sharp",
            "combative",
            "assertive",
        ],
        "expect_nonpositive_valence": False,  # competitive != cold; only checks edge words
    },
]

# If the compiled text is dominated by these instead, with none of the edge
# words present, that's the softening failure mode this script exists to catch.
SOFTENED_MARKERS = [
    "warm and friendly",
    "warm, friendly",
    "caring and supportive",
    "kind and gentle",
    "always positive",
    "sweet and",
    "bubbly",
]


def _haystack(compiled: CompiledPersona) -> str:
    return " ".join(
        [
            compiled.profile.base_tone,
            compiled.profile.identity_summary,
            " ".join(compiled.profile.traits),
        ]
    ).lower()


async def _run_case(case: dict, client: OllamaClient) -> tuple[bool, str]:
    compiled = await compile_persona(case["description"], llm=client)
    text = _haystack(compiled)

    survivors = [w for w in case["edge_words"] if w in text]
    softened = [m for m in SOFTENED_MARKERS if m in text]

    problems = []
    if not survivors:
        problems.append(
            f"none of {case['edge_words']} survived into base_tone/"
            f"identity_summary/traits (got: {text[:200]!r})"
        )
    if softened and not survivors:
        problems.append(f"found softened-persona language instead: {softened}")
    if case["expect_nonpositive_valence"] and compiled.profile.baseline_valence > 0.05:
        problems.append(
            f"baseline_valence={compiled.profile.baseline_valence:.3f} was pulled "
            "positive despite a cold/harsh description"
        )

    if problems:
        return False, "; ".join(problems)
    return True, f"survived edge words: {survivors}"


async def main(allow_mock: bool) -> int:
    if getattr(Config, "MOCK_LLM_TEXT", False) and not allow_mock:
        print(
            "MOCK_LLM_TEXT is enabled: the compiler would call the deterministic "
            "mock, not a real model, and this check would prove nothing about "
            "real friction preservation.\n"
            "Unset MOCK_LLM_TEXT, or pass --allow-mock if you are only "
            "exercising this script's own plumbing.",
            file=sys.stderr,
        )
        return 2

    client = OllamaClient(base_url=Config.OLLAMA_URL, model=Config.LLM_CHAT_MODEL)
    all_passed = True
    for i, case in enumerate(CASES, 1):
        try:
            passed, detail = await _run_case(case, client)
        except Exception as exc:
            passed, detail = False, f"compile_persona raised: {exc}"
        all_passed &= passed
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] case {i}: {detail}")

    await client.close()

    if all_passed:
        print("\nAll cases preserved friction from the description.")
    else:
        print("\nAt least one case was softened -- see FAIL lines above.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="Run even with MOCK_LLM_TEXT set (plumbing check only, not evidence).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.allow_mock)))
