"""
Create your friend -- the Phase 2 CLI wizard.

    cd backend
    ../.venv/bin/python -m scripts.create_friend          # macOS/Linux
    ../.venv/Scripts/python.exe -m scripts.create_friend  # Windows

Describe your friend in your own words. This compiles that description into a
persona (`app/persona/compiler.py`), shows you what it built -- every numeric
temperament inference with the reasoning behind it -- lets you try a few lines
of dry-run conversation against it before committing to anything, and only
once you confirm does it write `personal/persona.toml` / `personal/biography.md`
and point `.env`'s `PERSONA_PROFILE_PATH` / `BIOGRAPHY_PATH` at them.
`personal/` is fully gitignored (see the repo root `.gitignore`), which is
exactly why an authored persona belongs there rather than under `config/` --
`config/persona.toml` stays the tracked, neutral example.

The write is deliberately gated behind that confirmation: seeding from
`persona.toml` is a one-way door (`app/persona/authoring.py`) -- it applies on
the agent's first boot and never again. Everything before you type `c` is free
to redo as many times as you like; nothing after it is. If `personal/persona.toml`
already exists, this refuses to touch it without an explicit `--force` -- it
may be a friend you already have.
"""

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add project root (backend/) to path -- matches every other entry point under
# backend/scripts/.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import set_key

from app.config import Config
from app.llm import LLMClient, build_llm_client
from app.persona.compiler import (
    CompiledPersona,
    PersonaCompilationError,
    compile_persona,
)
from app.persona.profile import PersonaProfile
from app.persona.wizard import render_preview, serialize_persona_toml
from scripts.validate_persona_file import validate

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONA_PATH = REPO_ROOT / "personal" / "persona.toml"
BIOGRAPHY_PATH = REPO_ROOT / "personal" / "biography.md"
ENV_PATH = REPO_ROOT / ".env"


def _read_description() -> str:
    print(
        "\nDescribe your friend in your own words -- personality, how they "
        "talk, what annoys them, backstory, anything at all. Write as much "
        "or as little as you like. Finish with a blank line.\n"
    )
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line and lines:
            break
        if line:
            lines.append(line)
    return "\n".join(lines)


async def _dry_run_chat(profile: PersonaProfile, client: LLMClient) -> None:
    """A few lines of conversation in the compiled persona's voice, before
    anything is written. Not a real cognitive turn -- no memory, no affect,
    no mesh -- just enough for a person to hear roughly what they're about to
    commit to."""
    system_prompt = (
        f"You are {profile.name}. {profile.base_tone}\n"
        f"{profile.identity_summary}\n"
        f"Traits: {', '.join(profile.traits) or '(none specified)'}.\n"
        f"Never say: {', '.join(profile.avoid) or '(nothing specified)'}.\n"
        "Stay fully in character. This is a short preview conversation."
    )
    print("\n--- dry run: say something to them (blank line to stop) ---")
    while True:
        try:
            user_line = input("you> ")
        except EOFError:
            break
        if not user_line:
            break
        reply = await client.generate(prompt=user_line, system=system_prompt)
        print(f"{profile.name}> {reply}")


def _write(compiled: CompiledPersona) -> list[str]:
    """Validate through the Phase 0.5 validator against a temp copy, then
    promote to the real paths and point .env at them. Returns a list of
    problems; empty means the write happened."""
    toml_text = serialize_persona_toml(compiled.profile)

    with tempfile.NamedTemporaryFile(
        "w", suffix=".toml", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(toml_text)
        temp_path = Path(handle.name)

    try:
        problems = validate(temp_path)
        if problems:
            return problems

        PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
        PERSONA_PATH.write_text(toml_text, encoding="utf-8")
        BIOGRAPHY_PATH.write_text(compiled.biography_markdown, encoding="utf-8")
    finally:
        temp_path.unlink(missing_ok=True)

    set_key(
        str(ENV_PATH),
        "PERSONA_PROFILE_PATH",
        str(PERSONA_PATH.relative_to(REPO_ROOT)),
    )
    set_key(
        str(ENV_PATH),
        "BIOGRAPHY_PATH",
        str(BIOGRAPHY_PATH.relative_to(REPO_ROOT)),
    )
    return []


async def main(force: bool) -> int:
    print("=" * 60)
    print("Create your friend")
    print("=" * 60)

    if PERSONA_PATH.exists() and not force:
        print(
            f"\n{PERSONA_PATH.relative_to(REPO_ROOT)} already exists -- this "
            "looks like a friend you already have. Refusing to overwrite it.\n"
            "Pass --force if you really mean to replace them (this cannot be "
            "undone), or edit/remove that file yourself first."
        )
        return 1

    description = _read_description()
    if not description.strip():
        print("No description given; nothing to do.")
        return 1

    client = build_llm_client(base_url=Config.OLLAMA_URL, model=Config.LLM_CHAT_MODEL)
    compiled: CompiledPersona | None = None
    try:
        while True:
            print("\nThinking about who this is...")
            try:
                compiled = await compile_persona(description, llm=client)
            except PersonaCompilationError as exc:
                print(f"Could not compile a persona from that ({exc}).")
                description = _read_description()
                if not description.strip():
                    return 1
                continue

            print(render_preview(compiled))
            print(
                "[c]onfirm and save  [r]egenerate  [t]alk to them first  "
                "[e]dit description  [q]uit"
            )
            choice = input("> ").strip().lower()

            if choice == "c":
                break
            if choice == "r":
                continue
            if choice == "t":
                await _dry_run_chat(compiled.profile, client)
                continue
            if choice == "e":
                description = _read_description()
                if not description.strip():
                    return 1
                continue
            print("Cancelled; nothing was saved.")
            return 1
    finally:
        await client.close()

    assert compiled is not None
    problems = _write(compiled)
    if problems:
        print("\nThe compiled persona did not pass validation:")
        for problem in problems:
            print(f"  - {problem}")
        print("Nothing was saved. This is a bug in the compiler -- please report it.")
        return 1

    print(
        f"\nSaved {PERSONA_PATH.relative_to(REPO_ROOT)} and "
        f"{BIOGRAPHY_PATH.relative_to(REPO_ROOT)}."
    )
    print(".env now points PERSONA_PROFILE_PATH/BIOGRAPHY_PATH at them.")
    print(f"{compiled.profile.name} will be seeded on the agent's next first boot.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing personal/persona.toml (cannot be undone).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.force)))
