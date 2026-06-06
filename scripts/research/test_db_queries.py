import asyncio
import os
import sys

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
)

# pyrefly: ignore [missing-import]
from app.state.conversation_store import ConversationHistoryStore  # noqa: E402


async def test():
    db = ConversationHistoryStore()
    await db.initialize()
    async with db.pool.acquire() as conn:
        memories_count = await conn.fetchval("SELECT count(*) FROM memories")
        archived_count = await conn.fetchval("SELECT count(*) FROM archived_memories")
        print(f"Active memories: {memories_count}")
        print(f"Archived memories: {archived_count}")

        # Check some archived memories
        rows = await conn.fetch(
            "SELECT id, content, wing, room, importance_score FROM archived_memories WHERE room = 'milestone' OR content LIKE '%Milestone%' LIMIT 5"
        )
        print("\nSome archived milestones:")
        for r in rows:
            print(dict(r))

        # Check active milestones
        rows_act = await conn.fetch(
            "SELECT id, content, wing, room, importance_score FROM memories WHERE room = 'milestone' OR content LIKE '%Milestone%' LIMIT 5"
        )
        print("\nSome active milestones:")
        for r in rows_act:
            print(dict(r))

    await db.close()


if __name__ == "__main__":
    asyncio.run(test())
