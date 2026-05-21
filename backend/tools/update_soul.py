import asyncio
import os
import json
import sys

# Add backend directory to path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.state.conversation_store import ConversationHistoryStore


async def update_soul():
    print("🔮 Connecting to Database...")
    db = ConversationHistoryStore()
    await db.initialize()

    base_dir = os.path.join(os.path.dirname(__file__), "..", "app")
    p_path = os.path.join(base_dir, "personality.json")
    h_path = os.path.join(base_dir, "history.json")

    print(f"📖 Reading files from {base_dir}...")

    personality_content = "{}"
    if os.path.exists(p_path):
        with open(p_path, "r", encoding="utf-8") as f:
            personality_content = f.read()
            # Validate JSON
            try:
                json.loads(personality_content)
                print("✅ personality.json is valid.")
            except json.JSONDecodeError as e:
                print(f"❌ ERROR: personality.json is invalid JSON: {e}")
                return
    else:
        print("⚠️ Warning: personality.json not found.")

    history_content = "{}"
    if os.path.exists(h_path):
        with open(h_path, "r", encoding="utf-8") as f:
            history_content = f.read()
            # Validate JSON
            try:
                json.loads(history_content)
                print("✅ history.json is valid.")
            except json.JSONDecodeError as e:
                print(f"❌ ERROR: history.json is invalid JSON: {e}")
                return
    else:
        print("⚠️ Warning: history.json not found.")

    print("✨ Updating Agent Soul in Database...")

    # We use raw SQL here to force update the row where id=1
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_configs (id, personality, background_history, updated_at)
            VALUES (1, $1, $2, NOW())
            ON CONFLICT (id) 
            DO UPDATE SET 
                personality = EXCLUDED.personality, 
                background_history = EXCLUDED.background_history,
                updated_at = NOW();
            """,
            personality_content,
            history_content,
        )

    print("✅ Soul Update Complete! The AI has been re-imprinted.")
    await db.close()


if __name__ == "__main__":
    asyncio.run(update_soul())
