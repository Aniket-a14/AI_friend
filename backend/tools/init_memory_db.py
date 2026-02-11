import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def init_db():
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL not found in .env")
        return

    print(f"🔌 Connecting to Supabase...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Read schema file
        with open("backend/db/schema.sql", "r") as f:
            schema_sql = f.read()
            
        print("⚡ Executing schema...")
        await conn.execute(schema_sql)
        
        print("✅ Database initialized successfully!")
        print("   - Extension 'vector' enabled.")
        print("   - Table 'memories' created.")
        print("   - Function 'match_memories' created.")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

if __name__ == "__main__":
    if os.path.exists("backend"): # running from root
        asyncio.run(init_db())
    else:
        print("Please run from project root: python backend/tools/init_memory_db.py")
