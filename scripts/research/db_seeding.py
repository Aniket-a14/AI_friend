# ruff: noqa: E402
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environmental configs
load_dotenv()

# Add workspace and backend paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
)

from scripts.research.reset_cognitive_db import reset_dbs

# Standard, generic conversational templates to simulate a diverse memory pool
GENERIC_CHAT_TEMPLATES = [
    "Hello, how is your day going?",
    "I am currently working on a software engineering project.",
    "The weather today is exceptionally clear and pleasant.",
    "Can you help me verify the database connection parameters?",
    "Let's schedule a meeting to discuss the system architecture.",
    "I prefer using standard, structured JSON files for data storage.",
    "What are the best practices for optimizing SQL query performance?",
    "We need to write unit tests to validate the new modules.",
    "The performance analysis shows a steady retrieval latency.",
    "It is important to maintain clean, well-documented codebases.",
]

# Standard milestone templates for search precision validation
GENERIC_MILESTONES = [
    "The primary database server is hosted on a local secure loopback address.",
    "The system architecture utilizes a decoupled event broker model.",
    "The memory index uses unit-normalized 768-dimensional embeddings.",
    "Relational graph constraints are initialized during the bootstrap phase.",
    "Active memory pruning deletes decayed records below the default threshold.",
]


def generate_mock_vector(dim=768):
    """Generates a simple mock normalized unit vector."""
    import numpy as np

    vec = np.random.randn(dim)
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        vec = np.zeros(dim)
        vec[0] = 1.0
        return vec.tolist()
    return (vec / norm).tolist()


async def seed_databases(num_distractors=100000):
    """
    Resets databases and bulk-loads a generic, temporally backdated conversational corpus:
    - Distributes timestamps proportionally over a 3-year timeline to simulate decay.
    - Uses high-speed PostgreSQL transactions to load records efficiently.
    """
    print(
        f"\n--- Running Database Seeding ({num_distractors} Distractors + {len(GENERIC_MILESTONES)} Milestones) ---"
    )

    # 1. Reset databases
    await reset_dbs()

    # 2. Initialize PostgreSQL store
    from app.state.conversation_store import ConversationHistoryStore

    db = ConversationHistoryStore()
    await db.initialize()

    print(
        "🧠 Compiling generic conversational dataset with 3-year temporal decay gradient..."
    )

    now = datetime.now(timezone.utc)
    three_years_seconds = 3 * 365 * 24 * 3600
    time_step_seconds = three_years_seconds / max(1, num_distractors)

    seeding_tasks = []

    # Compile 100,000 backdated distractors
    for i in range(num_distractors):
        template = GENERIC_CHAT_TEMPLATES[i % len(GENERIC_CHAT_TEMPLATES)]
        content = f"{template} [Record ID: {i}]"

        # Proportional backdating to create a perfect temporal gradient
        elapsed_seconds = i * time_step_seconds
        created_time = now - timedelta(seconds=elapsed_seconds)

        vector = generate_mock_vector(768)
        vector_str = str(vector)

        seeding_tasks.append(
            (
                content,
                content,
                "personal",
                "distractor",
                vector_str,
                0.4,
                0.1,
                0.0,
                0.9,
                "system_seeder",
                "{}",
                created_time,
            )
        )

    # Compile 5 milestone target memories
    for i, content in enumerate(GENERIC_MILESTONES):
        vector = generate_mock_vector(768)
        vector_str = str(vector)
        seeding_tasks.append(
            (
                content,
                content,
                "personal",
                "milestone",
                vector_str,
                0.9,
                0.8,
                0.8,
                1.0,
                "system_seeder",
                "{}",
                now,
            )
        )

    print(f"💾 Bulk-loading {len(seeding_tasks)} records into pgvector...")

    start_time = time.perf_counter()
    async with db.pool.acquire() as conn:
        # Use executemany for high-speed batch SQL execution
        await conn.executemany(
            """
            INSERT INTO memories (
                content, raw_content, wing, room,
                embedding, importance_score, emotional_weight,
                valence, certainty, source, metadata,
                recall_count, last_recalled_at, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 1, $12, $12)
            """,
            seeding_tasks,
        )

    duration = time.perf_counter() - start_time
    print(
        f"✅ Successfully seeded PostgreSQL memories table in {duration:.2f} seconds."
    )
    await db.close()

    # 3. Connect to Neo4j and seed generic relational nodes
    from app.state.graph_db import GraphDB

    try:
        print("🕸️ Seeding Neo4j Knowledge Graph with generic validation nodes...")
        graph = GraphDB()

        await graph.create_entity(
            "System", "Database", {"description": "Primary storage engine"}
        )
        await graph.create_entity(
            "Architecture", "SovereignMesh", {"description": "Distributed agent loop"}
        )
        await graph.create_entity(
            "Framework", "ACTR", {"description": "Cognitive memory framework"}
        )

        await graph.create_relationship(
            "SovereignMesh",
            "Architecture",
            "UTILIZES",
            "Database",
            "System",
            {"weight": 0.95},
        )
        await graph.create_relationship(
            "SovereignMesh",
            "Architecture",
            "INTEGRATES",
            "ACTR",
            "Framework",
            {"weight": 0.90},
        )

        await graph.close()
        print("✅ Successfully seeded Neo4j graph nodes.")
    except Exception as e:
        print(
            f"⚠️ Neo4j seeding skipped or encountered an error (normal if offline): {e}"
        )

    print("✨ --- Seeding Phase Complete ---\n")


if __name__ == "__main__":
    asyncio.run(seed_databases(200))
