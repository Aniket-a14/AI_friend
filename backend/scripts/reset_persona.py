"""
Reset your humanoid back to what `config/` currently describes.

    cd backend
    ../.venv/Scripts/python.exe -m scripts.reset_persona

Clears the stored persona and every file-seeded memory, so the next boot reads
`config/persona.toml` and `config/biography.md` again as if it were the first.
Memories from real conversations are kept — see `app/persona/reset.py` for why.

A confirmation phrase has to be typed in full. Not a y/n, because the
destructive half of this is irreversible and a reflexive "y" is the single most
likely way to lose a persona someone spent an evening writing. `--yes` skips it
for scripted/container use, where there is no one to ask.
"""

import argparse
import asyncio
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.persona.reset import reset_persona
from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore

CONFIRMATION = "reset my friend"


async def _run(skip_prompt: bool) -> int:
    config_store = ConversationHistoryStore()
    await config_store.initialize()

    if config_store.pool is None:
        print("❌ No database reachable. Nothing was changed.")
        return 1

    # `graph_db=None` on purpose. The reset touches SQL and Qdrant only —
    # `MemoryStore` reads Neo4j but never writes it, so there is nothing seeded
    # there to remove and connecting would be a dependency for no work.
    memory_store = MemoryStore(pool=config_store.pool, graph_db=None)

    if not skip_prompt:
        print("This clears your friend's persona and everything seeded from config/.")
        print("Memories from real conversations are kept.")
        print(f"\nType '{CONFIRMATION}' to continue: ", end="", flush=True)
        if sys.stdin.readline().strip() != CONFIRMATION:
            print("Cancelled. Nothing was changed.")
            return 1

    result = await reset_persona(config_store, memory_store)

    print(f"\n🧹 Removed {result['memories_removed']} seeded memory/memories.")
    if result["persona_cleared"]:
        print("🌱 Persona cleared. The next start will seed from config/ again.")
    else:
        # "Unchanged" would be a lie: the memory half already succeeded, and
        # saying nothing happened is how someone concludes it is safe to walk
        # away from a half-reset agent. Name the actual state instead.
        print("⚠️  The stored persona could NOT be cleared.")
        print("    Seeded memories are already gone, so your friend is now in a")
        print("    half-reset state: original persona, missing its seeded past.")
        print("    Re-run this once the database is reachable.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt (for scripted use)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return asyncio.run(_run(args.yes))


if __name__ == "__main__":
    raise SystemExit(main())
