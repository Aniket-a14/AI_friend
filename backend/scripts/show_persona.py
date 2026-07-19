"""
Show who your humanoid currently is.

    cd backend
    ../.venv/Scripts/python.exe -m scripts.show_persona
    ../.venv/Scripts/python.exe -m scripts.show_persona --json

Once the durable store became authoritative, `config/persona.toml` stopped
describing the running agent — it is a seed, read once, and everything after
that lives in `agent_configs` and evolves. That left no way to answer the most
basic question there is: who is my friend right now? This is that answer.

Read-only by construction. It opens the store, prints, and exits; nothing here
writes, so it is safe to run against a live agent. Editing what it shows is a
different act with a different tool (`scripts/reset_persona.py` to start over
from the file, or simply talking to them).
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cognitive.identity import IdentityManager  # noqa: E402
from app.state.conversation_store import ConversationHistoryStore  # noqa: E402


def _line(label: str, value) -> str:
    return f"  {label:<22} {value}"


def _render(identity: IdentityManager) -> str:
    persona = identity.persona
    history = identity.history
    core = identity.immutable_core

    out = [f"\n{persona.name}", "=" * max(len(persona.name), 40), ""]

    out.append("IMMUTABLE — fixed in code, not editable anywhere")
    out.append(_line("values", ", ".join(core["values"])))
    out.append(_line("boundaries", ", ".join(core["boundaries"])))
    out.append("")

    out.append("CONSTITUTIONAL — seeded once, held steady")
    out.append(_line("base_tone", core["base_tone"]))
    out.append(_line("traits", ", ".join(persona.traits) or "—"))
    out.append(_line("speech_patterns", ", ".join(persona.speech_patterns) or "—"))
    out.append(_line("avoid", ", ".join(persona.avoid) or "—"))
    out.append("")

    out.append("ADAPTIVE — seeded once, then theirs")
    out.append(_line("relationship", history.get("relationship", "—")))
    out.append(_line("adaptive_traits", ", ".join(persona.adaptive_traits) or "—"))
    out.append(
        _line("speaking_style", persona.speaking_style.get("style_description") or "—")
    )
    out.append(_line("initial_trust", persona.initial_trust))
    out.append(_line("baseline_valence", persona.baseline_valence))
    out.append("")

    summary = (persona.identity_summary or "").strip()
    if summary:
        out.append("WHO THEY ARE")
        out.extend(f"  {ln}" for ln in summary.splitlines())
        out.append("")

    out.append("PROVENANCE")
    seeded = history.get(IdentityManager.SEED_MARKER)
    # The distinction that matters most on this screen: a persona that was never
    # seeded is running on defaults, and someone looking at an authored file
    # wondering why it had no effect needs to see that stated, not inferred.
    out.append(_line("seeded from file", seeded or "never — running on defaults"))
    out.append(_line("biography passages", len(history.get("biography_seeded") or [])))
    out.append(
        _line("migrated memories", len(history.get("history_memories_migrated") or []))
    )
    out.append(_line("evolved learnings", len(history.get("evolved_learnings") or "")))
    out.append("")
    return "\n".join(out)


async def _run(as_json: bool) -> int:
    store = ConversationHistoryStore()
    await store.initialize()

    if store.pool is None:
        print("❌ No database reachable, so there is no stored persona to show.")
        print("   The agent would be running on its shipped defaults.")
        return 1

    identity = IdentityManager()
    await identity.hydrate_from_config_store(store)

    if identity.config_store is None:
        # Hydration failed rather than returned nothing. Printing the defaults
        # here would show a persona that is not the stored one and give no hint
        # that the real answer was never retrieved.
        print("❌ Could not read the stored persona; showing nothing rather than")
        print("   a default that would look like your friend and is not.")
        return 1

    if as_json:
        print(
            json.dumps(
                {
                    "persona": identity.persona.model_dump(),
                    "immutable_core": identity.immutable_core,
                    "history": identity.history,
                },
                indent=2,
                default=str,
            )
        )
    else:
        print(_render(identity))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="machine-readable output"
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
