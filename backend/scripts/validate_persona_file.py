"""
Validate an authored persona file the way a real boot would apply it.

    cd backend
    ../.venv/bin/python -m scripts.validate_persona_file [path]   # macOS/Linux
    ../.venv/Scripts/python.exe -m scripts.validate_persona_file  # Windows

Defaults to `config/persona.toml`. Unlike a real boot (`authoring.py`'s
`read_persona_file`/`authored_overrides`, which never raise -- a malformed
persona file must not stop the agent from starting), this exits non-zero on
any problem: an author checking their own file, or CI checking a PR, wants to
be told, not silently handed defaults.

Checks, in order:
1. The file parses (TOML or JSON).
2. Every key is a real `PersonaProfile` field -- `split_by_tier`'s "unknown"
   bucket is the same typo detector `authored_overrides` already uses.
3. The merged result passes `PersonaProfile`'s own validation (bounds,
   lengths, the `adaptive_traits` cap) -- the same construction path
   `IdentityManager._profile_from_personality` uses on a real first boot.
4. No key targets the immutable safety core -- `strip_immutable` already
   warns and drops these in production; here that is a hard failure, since a
   file trying to set `values`/`boundaries` is worth stopping on rather than
   silently ignoring.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError

from app.persona.authoring import read_persona_file, split_by_tier
from app.persona.profile import IMMUTABLE_CORE, PersonaProfile


def validate(path: Path) -> list[str]:
    """Returns a list of problems; empty means the file is valid."""
    if not path.exists():
        return [f"{path} does not exist"]

    raw = read_persona_file(path)
    if not raw:
        message = (
            f"{path} did not parse as TOML/JSON, or is not a table of "
            "values -- see the logged error above"
        )
        return [message]

    problems: list[str] = []

    immutable_keys = {"immutable", *IMMUTABLE_CORE.keys()} & raw.keys()
    if immutable_keys:
        problems.append(
            f"targets the immutable safety core: {sorted(immutable_keys)} "
            f"-- values/boundaries are fixed in code and cannot be authored"
        )

    data = {k: v for k, v in raw.items() if k not in immutable_keys}
    constitutional, adaptive, unknown = split_by_tier(data)
    if unknown:
        problems.append(
            f"unknown keys (not a PersonaProfile field): {sorted(unknown)} "
            f"-- check spelling against config/persona.toml's comments"
        )

    merged = PersonaProfile.from_config().model_dump()
    merged.update(constitutional)
    merged.update(adaptive)
    try:
        PersonaProfile(**merged)
    except ValidationError as exc:
        problems.append(f"fails PersonaProfile validation:\n{exc}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", default="../config/persona.toml", type=Path
    )
    args = parser.parse_args()

    problems = validate(args.path)
    if problems:
        print(f"❌ {args.path} is not valid:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"✅ {args.path} is a valid persona file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
