import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
)


async def reset_db():
    db_url = os.getenv("DATABASE_URL")
    print(f"Resetting database at: {db_url}")
    try:
        conn = await asyncpg.connect(db_url)
        # Drop tables in proper order due to foreign keys
        await conn.execute("DROP TABLE IF EXISTS messages CASCADE")
        await conn.execute("DROP TABLE IF EXISTS sessions CASCADE")
        await conn.execute("DROP TABLE IF EXISTS agent_configs CASCADE")
        await conn.execute("DROP TABLE IF EXISTS memories CASCADE")
        await conn.close()
        print("✅ Tables dropped successfully.")
    except Exception as e:
        print(f"❌ Reset failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(reset_db())
