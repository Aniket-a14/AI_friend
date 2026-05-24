# ruff: noqa: E402
import asyncio
import os
import sys
import time
import json
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

# Aniket autobiographical chitchat templates for fallback procedural generation
ANIKET_DISTRACTOR_TEMPLATES = [
    "Ma asked me to bring some fresh vegetables from the local market in Kolkata.",
    "Discussing our high school mathematics project with my classmate in the afternoon.",
    "Spending the evening coding a simple arcade game in Python in my study room.",
    "We had a beautiful family dinner tonight celebrating my academic results.",
    "Talking to my childhood friends about our weekend cricket match in the streets of Kolkata.",
    "I tried making sweet rasgullas at home today, they turned out soft and spongy.",
    "Walking through the crowded streets near Victoria Memorial, enjoying the cool breeze.",
    "Ma is making delicious home-cooked meals, the whole house smells amazing.",
    "Studying late into the night for my college entrance examinations, feeling focused.",
    "Moving to Bangalore for my college was a major transition, the city is so vibrant.",
    "Talking with Priya at the university cafe about our upcoming research presentation.",
    "Discussing affective cognitive architectures and neural networks in the lab today.",
    "Walking around Cubbon Park in Bangalore with Priya, talking about our future dreams.",
    "I bought some traditional sweet rasgullas from a local Bengali sweet shop in Bangalore.",
    "Reviewing database query optimization techniques with my research project teammates.",
    "Listening to Ma's stories on the phone about our childhood home back in Kolkata.",
    "Priya and I spent the afternoon studying in the quiet library alcove.",
    "My high school friends and I are planning a reunion back in Kolkata during the holidays.",
    "Debugging a tricky concurrent thread pool issue in my cognitive simulation module.",
    "Enjoying a hot cup of tea while watching the rain wash over the streets of Bangalore.",
]

EPOCH_0_5_TEMPLATES = [
    "Childhood Milestone: I took my first toddler steps in our warm home in Kolkata, surrounded by Ma and Baba's laughter.",
    "Childhood Milestone: Tasting my first traditional sweet rasgulla, a delicious treat that became my absolute favorite.",
    "Childhood Milestone: Playing with wooden toys in the sunlit balcony, listening to Ma's sweet Bengali lullabies.",
    "Childhood Milestone: Drawing simple shapes with colorful crayons, feeling a spark of early cognitive curiosity.",
    "Childhood Milestone: Baba taking me for a walk near the local park, looking up at the beautiful clear blue sky.",
]

EPOCH_6_12_TEMPLATES = [
    "School Milestone: Enrolling in primary school in Kolkata, wearing my new uniform and feeling exceptionally proud.",
    "School Milestone: Winning a school mathematics puzzle competition, discovering my deep passion for logical reasoning.",
    "School Milestone: Playing street cricket with my childhood neighborhood friends, celebrating a hard-fought victory.",
    "School Milestone: A wonderful family summer holiday, eating fresh mangoes and visiting the grand Victoria Memorial.",
    "School Milestone: Sitting in the school library reading my first science fiction book, dreaming of building intelligent machines.",
]

EPOCH_13_18_TEMPLATES = [
    "Teenage Milestone: Writing my very first lines of Python code on Baba's old computer, watching the screen light up.",
    "Teenage Milestone: Transitioning to senior high school in Kolkata, joining the science stream to study physics and math.",
    "Teenage Milestone: Building a basic chat assistant model in my room, igniting my lifelong interest in computer science.",
    "Teenage Milestone: Late-night study sessions with my school friends, sharing snacks and discussing our future college plans.",
    "Teenage Milestone: Graduating high school with top honors, receiving congratulations from my proud family and teachers.",
]

EPOCH_19_TEMPLATES = [
    "Adulthood Milestone: Moving from Kolkata to Bangalore to start my freshman year of university, a major step forward.",
    "Adulthood Milestone: Joining the university's advanced research lab focused on affective cognitive architectures.",
    "Adulthood Milestone: Meeting Priya at the university cafe, starting a beautiful and deeply supportive relationship.",
    "Adulthood Milestone: Celebrating my first successful research paper publication with Priya, sharing a sweet rasgulla.",
    "Adulthood Milestone: Commencing my junior research internship in Bangalore, feeling completely aligned with my vocation.",
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


async def check_nats_ipc():
    """Measures dynamic NATS IPC latency round-trip."""
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        import nats

        nc = await nats.connect(nats_url)
        start = time.perf_counter()
        # Ping NATS round-trip
        await nc.flush()
        dur = (time.perf_counter() - start) * 1000.0
        await nc.close()
        return True, dur
    except Exception:
        return False, 0.15


async def seed_databases(num_distractors=100000):
    """
    Resets databases and bulk-loads a generic, temporally backdated conversational corpus:
    - Reads from flooded_seeding_corpus.json if available, to seed the exact 19-year developmental history.
    - Falls back to procedural generation using Aniket-specific templates.
    - Uses high-speed PostgreSQL transactions to load records efficiently.
    """
    print("\n--- Running Database Seeding for Aniket ---")

    # 1. Reset databases
    await reset_dbs()

    # 2. Initialize PostgreSQL store
    from app.state.conversation_store import ConversationHistoryStore

    db = ConversationHistoryStore()
    await db.initialize()

    seeding_tasks = []
    corpus_path = os.path.join(os.path.dirname(__file__), "flooded_seeding_corpus.json")
    loaded_from_file = False

    if os.path.exists(corpus_path):
        try:
            print(
                f"📖 Found compiled seeding corpus file. Loading records from {corpus_path}..."
            )
            with open(corpus_path, "r") as f:
                corpus_data = json.load(f)
            loaded_from_file = True
        except Exception as e:
            print(
                f"⚠️ Error reading {corpus_path}: {e}. Falling back to procedural generation."
            )

    if loaded_from_file:
        distractor_count = 0
        milestone_count = 0

        for item in corpus_data:
            room = item.get("room", "distractor")
            if room == "distractor":
                if distractor_count >= num_distractors:
                    continue
                distractor_count += 1
            else:
                milestone_count += 1

            content = item.get("content", "")
            raw_content = item.get("raw_content", content)
            wing = item.get("wing", "personal")
            importance = item.get("importance", 0.4)
            emotion = item.get("emotion", 0.1)
            valence = item.get("valence", 0.0)
            certainty = item.get("certainty", 0.9)
            source = item.get("source", "system_seeder")
            created_at_str = item.get("created_at")
            created_time = datetime.fromisoformat(created_at_str)

            vector = generate_mock_vector(768)
            vector_str = str(vector)

            metadata_dict = {
                "epoch": item.get("epoch"),
                "crisis": item.get("crisis"),
                "virtue": item.get("virtue"),
            }

            seeding_tasks.append(
                (
                    content,
                    raw_content,
                    wing,
                    room,
                    vector_str,
                    importance,
                    emotion,
                    valence,
                    certainty,
                    source,
                    json.dumps(metadata_dict),
                    created_time,
                )
            )
        print(
            f"Loaded {distractor_count} distractors and {milestone_count} milestones from {corpus_path}."
        )
    else:
        print(
            "🧠 Compiling autobiographical dataset with 19-year temporal decay gradient in-memory..."
        )
        now = datetime.now(timezone.utc)
        nineteen_years_seconds = 19 * 365 * 24 * 3600
        time_step_seconds = nineteen_years_seconds / max(1, num_distractors)

        # Compile chitchat distractors
        for i in range(num_distractors):
            template = ANIKET_DISTRACTOR_TEMPLATES[i % len(ANIKET_DISTRACTOR_TEMPLATES)]
            content = f"{template} [Turn: {i}]"

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

        # Compile milestones
        all_milestones = (
            EPOCH_0_5_TEMPLATES
            + EPOCH_6_12_TEMPLATES
            + EPOCH_13_18_TEMPLATES
            + EPOCH_19_TEMPLATES
        )
        for i, template in enumerate(all_milestones):
            content = f"{template} [Milestone ID: {i}]"
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

    # 2.2. Initialize and seed Identity Core SQLite database
    from app.state.identity_core_store import IdentityCoreStore

    try:
        print("🪞 Seeding Identity Core SQLite database...")
        identity_store = IdentityCoreStore()
        identity_store._seed_default_identity()
        print("✅ Successfully seeded Identity Core Store.")
    except Exception as e:
        print(f"⚠️ SQLite Identity Core seeding error: {e}")

    # 2.5. Initialize and seed Qdrant SemanticRecallStore in batches
    from app.state.semantic_recall_store import SemanticRecallStore
    from qdrant_client.http import models

    try:
        print("🔍 Seeding Qdrant Semantic Recall Store in batches...")
        semantic_store = SemanticRecallStore()
        if semantic_store.client:
            chunk_size = 5000
            points = []
            start_q = time.perf_counter()
            for idx, task in enumerate(seeding_tasks):
                (
                    content,
                    raw_content,
                    wing,
                    room,
                    vector_str,
                    importance,
                    emotion,
                    valence,
                    certainty,
                    source,
                    metadata_str,
                    created_time,
                ) = task
                vector = json.loads(vector_str)
                metadata = json.loads(metadata_str)

                payload = {
                    "content": content,
                    "wing": wing,
                    "room": room,
                    "importance_score": importance,
                    "emotional_weight": emotion,
                    "valence": valence,
                    "certainty": certainty,
                    "source": source,
                    "created_at": created_time.isoformat(),
                    **metadata,
                }

                points.append(
                    models.PointStruct(id=idx + 1, vector=vector, payload=payload)
                )

                if len(points) >= chunk_size or idx == len(seeding_tasks) - 1:
                    semantic_store.client.upsert(
                        collection_name=semantic_store.collection_name, points=points
                    )
                    points = []
            dur_q = time.perf_counter() - start_q
            print(
                f"✅ Successfully seeded Qdrant Semantic Store in {dur_q:.2f} seconds."
            )
        else:
            print("⚠️ Qdrant server offline. Skipping semantic vector seeding.")
    except Exception as e:
        print(f"⚠️ Warning: Qdrant seeding encountered an error: {e}")

    # 3. Connect to Neo4j and seed secure attachment graph nodes
    from app.state.graph_db import GraphDB

    try:
        print(
            "🕸️ Seeding Neo4j Knowledge Graph with Aniket's relational trust network..."
        )
        graph = GraphDB()

        await graph.create_entity(
            "Aniket",
            "Person",
            {"description": "The central cognitive system, developing since birth."},
        )
        await graph.create_entity(
            "Priya",
            "Person",
            {
                "description": "Aniket's romantic partner and primary source of secure attachment."
            },
        )
        await graph.create_entity(
            "Ma",
            "Person",
            {
                "description": "Aniket's mother, supporting emotional stability since childhood."
            },
        )
        await graph.create_entity(
            "Baba",
            "Person",
            {"description": "Aniket's father, supporting vocational growth and logic."},
        )
        await graph.create_entity(
            "Kolkata",
            "City",
            {
                "description": "Aniket's birthplace, home to childhood memories and sweet rasgullas."
            },
        )
        await graph.create_entity(
            "Bangalore",
            "City",
            {
                "description": "The city of college education, research, and meeting Priya."
            },
        )
        await graph.create_entity(
            "AffectiveCognitiveArchitectures",
            "ResearchDomain",
            {"description": "Core college research project."},
        )
        
        # Seed Core Identity Values & Boundaries into Neo4j Graph
        await graph.create_entity(
            "Honesty",
            "CoreValue",
            {"description": "Commitment to absolute truthfulness and behavioral integrity."}
        )
        await graph.create_entity(
            "Privacy",
            "CoreValue",
            {"description": "Commitment to absolute data sovereignty and local privacy protection."}
        )
        await graph.create_entity(
            "Curiosity",
            "CoreValue",
            {"description": "Commitment to intellectual exploration and learning."}
        )
        await graph.create_entity(
            "DataBoundary",
            "CoreBoundary",
            {"description": "Explicit rule: Never share user conversation histories externally."}
        )

        # Seed Core Identity Values & Boundaries into Neo4j Graph
        await graph.create_entity(
            "Honesty",
            "CoreValue",
            {
                "description": "Commitment to absolute truthfulness and behavioral integrity."
            },
        )
        await graph.create_entity(
            "Privacy",
            "CoreValue",
            {
                "description": "Commitment to absolute data sovereignty and local privacy protection."
            },
        )
        await graph.create_entity(
            "Curiosity",
            "CoreValue",
            {"description": "Commitment to intellectual exploration and learning."},
        )
        await graph.create_entity(
            "DataBoundary",
            "CoreBoundary",
            {
                "description": "Explicit rule: Never share user conversation histories externally."
            },
        )

        await graph.create_relationship(
            "Aniket", "Person", "LIVES_IN", "Kolkata", "City", {"weight": 0.95}
        )
        await graph.create_relationship(
            "Aniket", "Person", "MOVED_TO", "Bangalore", "City", {"weight": 0.95}
        )
        await graph.create_relationship(
            "Aniket", "Person", "PARTNER_WITH", "Priya", "Person", {"weight": 0.99}
        )
        await graph.create_relationship(
            "Aniket", "Person", "CHILD_OF", "Ma", "Person", {"weight": 0.98}
        )
        await graph.create_relationship(
            "Aniket", "Person", "CHILD_OF", "Baba", "Person", {"weight": 0.98}
        )
        await graph.create_relationship(
            "Aniket",
            "Person",
            "RESEARCHES",
            "AffectiveCognitiveArchitectures",
            "ResearchDomain",
            {"weight": 0.95},
        )
        
        # Link Aniket to Core Identity Values & Boundaries
        await graph.create_relationship(
            "Aniket", "Person", "HAS_VALUE", "Honesty", "CoreValue", {"weight": 1.0}
        )
        await graph.create_relationship(
            "Aniket", "Person", "HAS_VALUE", "Privacy", "CoreValue", {"weight": 1.0}
        )
        await graph.create_relationship(
            "Aniket", "Person", "HAS_VALUE", "Curiosity", "CoreValue", {"weight": 1.0}
        )
        await graph.create_relationship(
            "Aniket", "Person", "ENFORCES_RULE", "DataBoundary", "CoreBoundary", {"weight": 1.0}
        )

        # Link Aniket to Core Identity Values & Boundaries
        await graph.create_relationship(
            "Aniket", "Person", "HAS_VALUE", "Honesty", "CoreValue", {"weight": 1.0}
        )
        await graph.create_relationship(
            "Aniket", "Person", "HAS_VALUE", "Privacy", "CoreValue", {"weight": 1.0}
        )
        await graph.create_relationship(
            "Aniket", "Person", "HAS_VALUE", "Curiosity", "CoreValue", {"weight": 1.0}
        )
        await graph.create_relationship(
            "Aniket",
            "Person",
            "ENFORCES_RULE",
            "DataBoundary",
            "CoreBoundary",
            {"weight": 1.0},
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
