import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environmental configs
load_dotenv()

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


async def reset_dbs():
    print("\n🧹 --- Starting Complete Cognitive Database Reset ---")

    # 1. Clear local SQLite app.db fallbacks
    for db_path in ["app.db", os.path.join("backend", "app.db")]:
        full_path = os.path.join(os.path.dirname(__file__), "..", "..", db_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                print(f"🧹 Removed local SQLite database: {db_path}")
            except Exception as e:
                print(f"⚠️ Warning: Could not remove local SQLite {db_path}: {e}")

    # 2. Reset Postgres pgvector table
    from app.state.conversation_store import ConversationHistoryStore

    print("🐘 Connecting to PostgreSQL pgvector...")
    db = ConversationHistoryStore()
    await db.initialize()
    try:
        async with db.pool.acquire() as conn:
            # Drop the episodic memories and dialogue message stores cascade to force clean schema
            print("💥 Dropping old PostgreSQL tables cascade...")
            await conn.execute(
                "DROP TABLE IF EXISTS memories, messages, sessions, agent_configs CASCADE;"
            )

            # Read schema file
            schema_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "backend", "db", "schema.sql"
            )
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            print("⚡ Executing schema.sql script...")
            await conn.execute(schema_sql)
            print("✅ PostgreSQL schema recreated successfully.")

            # Seed the default session to satisfy foreign key constraints
            print("🌱 Seeding default session for local benchmark agent mesh...")
            await conn.execute("""
                INSERT INTO sessions (id, started_at, trust_benevolence, trust_competence, trust_integrity, metadata)
                VALUES ('dbd227ec-5936-42b4-ad05-95ad3193d2c1', NOW(), 0.5, 0.5, 0.5, '{}'::jsonb)
                ON CONFLICT (id) DO NOTHING;
            """)
            print("✅ PostgreSQL default sessions record inserted.")
    except Exception as e:
        print(f"❌ Failed to clear/recreate PostgreSQL database: {e}")
    finally:
        await db.close()

    # 3. Reset Neo4j Knowledge Graph
    from app.state.graph_db import GraphDB

    print("🕸️ Connecting to Neo4j Knowledge Graph...")
    try:
        graph = GraphDB()
        await graph.execute_query("MATCH (n) DETACH DELETE n", write=True)
        print("✅ Neo4j Knowledge Graph DETACH DELETE executed successfully.")
        await graph.close()
    except Exception as e:
        print(f"⚠️ Neo4j Reset skipped or encountered an error: {e}")

    print("✨ --- Cognitive Database Reset Complete ---\n")


if __name__ == "__main__":
    asyncio.run(reset_dbs())
