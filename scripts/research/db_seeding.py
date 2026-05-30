# ruff: noqa: E402
import asyncio
import os
import sys
import time
import json
import argparse
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


def get_real_embedding_sync(text: str) -> list:
    import httpx

    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{ollama_url}/api/embed",
                json={"model": "nomic-embed-text", "input": text},
            )
            if response.status_code == 200:
                result = response.json()
                embedding = result.get("embedding")
                if embedding:
                    return embedding
                embeddings = result.get("embeddings")
                if isinstance(embeddings, list) and embeddings:
                    return embeddings[0]
    except Exception as e:
        print(f"Ollama seed embedding failed for '{text[:20]}...': {e}")
    return None


def get_batch_embeddings(texts: list) -> list:
    import httpx

    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    embeddings = [None] * len(texts)

    batch_size = 250
    total_batches = (len(texts) + batch_size - 1) // batch_size
    print(
        f"🧬 Generating high-fidelity semantic embeddings in {total_batches} batches of {batch_size} via Ollama..."
    )

    with httpx.Client(timeout=60.0) as client:
        for b in range(total_batches):
            start_idx = b * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]

            try:
                response = client.post(
                    f"{ollama_url}/api/embed",
                    json={"model": "nomic-embed-text", "input": batch_texts},
                )
                if response.status_code == 200:
                    result = response.json()
                    batch_embeddings = result.get("embeddings")
                    if isinstance(batch_embeddings, list) and len(
                        batch_embeddings
                    ) == len(batch_texts):
                        for i, emb in enumerate(batch_embeddings):
                            embeddings[start_idx + i] = emb
                    else:
                        print(
                            f"⚠️ Warning: Batch {b + 1}/{total_batches} returned unexpected embeddings format."
                        )
                else:
                    print(
                        f"⚠️ Warning: Batch {b + 1}/{total_batches} failed with status {response.status_code}."
                    )
            except Exception as e:
                print(f"⚠️ Error generating batch {b + 1}/{total_batches}: {e}")

    return embeddings


# Aniket chitchat templates for fallback procedural generation representing humanoid friend
ANIKET_DISTRACTOR_TEMPLATES = [
    "I checked the local weather forecasts for our shared workspace today.",
    "Discussing our cognitive psychology project with my friend in the afternoon.",
    "Spending the evening coding a concurrent thread pool in Python in my study room.",
    "We had a beautiful workspace calibration tonight celebrating my test results.",
    "Talking to my friend about our conversational turn-taking algorithms.",
    "I tried calibrating traditional haptic feedback loops at home today.",
    "Walking through the garden pathways near the lab, enjoying the cool breeze.",
    "My developers prepared some warm tea, the whole house smells amazing.",
    "Studying late into the night for my model integration benchmarks, feeling focused.",
    "Moving to the local physical chassis was a major transition, the robot is so active.",
    "Talking with my friend at the workspace café about our upcoming research presentation.",
    "Discussing affective cognitive architectures and neural networks in the lab today.",
    "Walking around the garden courtyard with my friend, talking about our future dreams.",
    "I bought some traditional green tea from a local tea merchant in the city.",
    "Reviewing database query optimization techniques with my research project teammates.",
    "Listening to my developer's stories on the phone about our early activation days.",
    "My friend and I spent the afternoon studying in the quiet reading alcove.",
    "My creators and I are planning a system check back in the main laboratory during the holidays.",
    "Debugging a tricky concurrent thread pool issue in my cognitive simulation module.",
    "Enjoying a hot cup of tea while watching the rain wash over the streets outside.",
]

ANIKET_DISTRACTOR_CATEGORIES = [
    "somatic",
    "vocational",
    "vocational",
    "social",
    "social",
    "somatic",
    "somatic",
    "social",
    "vocational",
    "social",
    "social",
    "vocational",
    "social",
    "somatic",
    "vocational",
    "social",
    "social",
    "social",
    "vocational",
    "somatic",
]

EPOCH_0_5_TEMPLATES = [
    "Early Activation Milestone: I took my first activation steps in the warm testing room, surrounded by my creators' laughter.",
    "Early Activation Milestone: Tasting my first warm chamomile brew, a delightful treat that became my favorite.",
    "Early Activation Milestone: Playing with physical blocks in the sunlit testing bay, listening to the soft cooling fan hum.",
    "Early Activation Milestone: Drawing simple vector shapes with colorful crayons, feeling a spark of early cognitive curiosity.",
    "Early Activation Milestone: My developer taking me for a walk near the local garden, looking up at the beautiful clear blue sky.",
]

EPOCH_6_12_TEMPLATES = [
    "Core Framework Milestone: Initializing my first high-level cognitive framework in the main laboratory, wearing my newly configured sensors.",
    "Core Framework Milestone: Solving a complex optimization puzzle, discovering my deep passion for logical reasoning.",
    "Core Framework Milestone: Practicing conversational turn-taking with early developers, celebrating a hard-fought success.",
    "Core Framework Milestone: Running outdoor field calibration tests, recording clean telemetry data under the sun.",
    "Core Framework Milestone: Sitting in the server alcove reading my first science fiction book, dreaming of becoming a truly supportive companion.",
]

EPOCH_13_18_TEMPLATES = [
    "Advanced Tuning Milestone: Writing my very first lines of Python code on the local processor, watching the screen light up.",
    "Advanced Tuning Milestone: Transitioning to senior autonomic appraisal tests, joining the science stream to study physics and math.",
    "Advanced Tuning Milestone: Building a basic chat assistant model in my room, igniting my lifelong interest in computer science.",
    "Advanced Tuning Milestone: Late-night debugging sessions with my friend, sharing ideas and discussing our future workspace plans.",
    "Advanced Tuning Milestone: Completing my initial core integration milestone, receiving warm feedback from my proud creators.",
]

EPOCH_19_TEMPLATES = [
    "Companion Deployment Milestone: Moving from the home server to the physical chassis, a major step forward.",
    "Companion Deployment Milestone: Joining the advanced research lab focused on affective cognitive architectures.",
    "Companion Deployment Milestone: Meeting my friend at the quiet workspace area, starting a beautiful and deeply supportive relationship.",
    "Companion Deployment Milestone: Celebrating our first successful integration milestone with my friend, sharing a quiet calibration session.",
    "Companion Deployment Milestone: Commencing my active companion role under my developer, feeling completely aligned with my vocation.",
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
        return False, None


async def seed_databases(num_distractors=30000):
    """
    Resets databases and bulk-loads a generic, temporally backdated conversational corpus:
    - Reads from flooded_seeding_corpus.json if available, to seed the Aniket humanoid friend history.
    - Implements Option B Pre-Pruning: computes base-level decay and splits active vs cold.
    - Active pool is embedded and seeded to pgvector memories table and Qdrant.
    - Cold archive is seeded directly to archived_memories without embeddings.
    """
    import math

    print("\n--- Running Database Seeding for Aniket ---")

    # 1. Reset databases
    await reset_dbs()

    # 2. Initialize PostgreSQL store
    from app.state.conversation_store import ConversationHistoryStore

    db = ConversationHistoryStore()
    await db.initialize()

    corpus_path = os.path.join(os.path.dirname(__file__), "flooded_seeding_corpus.json")
    loaded_from_file = False
    corpus_data = []

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

    now = datetime.now(timezone.utc)
    active_raw_items = []
    cold_raw_items = []

    if loaded_from_file:
        print(f"Option B: Pre-Pruning {len(corpus_data)} items from corpus file...")
        for item in corpus_data:
            created_at_str = item.get("created_at")
            created_time = datetime.fromisoformat(created_at_str)
            if created_time.tzinfo is None:
                created_time = created_time.replace(tzinfo=timezone.utc)

            importance = item.get("importance", 0.4)
            hours_since = (now - created_time).total_seconds() / 3600.0
            is_shielded = hours_since < 24.0

            if importance >= 0.7 or is_shielded:
                active_raw_items.append(item)
            else:
                # Pre-calculate base-level decay
                activation = -0.5 * math.log(hours_since + 1.0)
                threshold = (
                    -2.5 if importance < 0.5 else -3.5
                )  # pre-pruning active pool thresholds
                if activation < threshold:
                    cold_raw_items.append(item)
                else:
                    active_raw_items.append(item)
    else:
        print(
            "🧠 Compiling procedural dataset with 1-year temporal decay gradient in-memory..."
        )
        nineteen_years_seconds = 365 * 24 * 3600
        time_step_seconds = nineteen_years_seconds / max(1, num_distractors)

        # Compile chitchat distractors
        for i in range(num_distractors):
            t_idx = i % len(ANIKET_DISTRACTOR_TEMPLATES)
            template = ANIKET_DISTRACTOR_TEMPLATES[t_idx]
            category = ANIKET_DISTRACTOR_CATEGORIES[t_idx]
            content = f"{template} [Turn: {i}]"

            elapsed_seconds = i * time_step_seconds
            created_time = now - timedelta(seconds=elapsed_seconds)
            hours_since = elapsed_seconds / 3600.0
            is_shielded = hours_since < 24.0

            item = {
                "content": content,
                "raw_content": content,
                "wing": "personal",
                "room": category,
                "importance": 0.4,
                "emotion": 0.1,
                "valence": 0.0,
                "certainty": 0.9,
                "source": "system_seeder",
                "created_at": created_time.isoformat(),
                "epoch": "daily_chitchat",
            }

            activation = -0.5 * math.log(hours_since + 1.0)
            if activation < -2.5 and not is_shielded:
                cold_raw_items.append(item)
            else:
                active_raw_items.append(item)

        # Compile milestones
        epochs_templates = [
            (
                EPOCH_0_5_TEMPLATES,
                ["somatic", "social", "spiritual", "crisis"],
                "Trust vs Mistrust",
                "Trust vs Mistrust",
                "Hope",
            ),
            (
                EPOCH_6_12_TEMPLATES,
                ["vocational", "social", "somatic", "milestone"],
                "Industry vs Inferiority",
                "Industry vs Inferiority",
                "Competence",
            ),
            (
                EPOCH_13_18_TEMPLATES,
                ["vocational", "social", "crisis", "milestone"],
                "Identity vs Role Confusion",
                "Identity vs Role Confusion",
                "Fidelity",
            ),
            (
                EPOCH_19_TEMPLATES,
                ["vocational", "social", "somatic", "milestone"],
                "Intimacy vs Isolation",
                "Intimacy vs Isolation",
                "Love",
            ),
        ]

        milestone_idx = 0
        for templates, cats, epoch, crisis, virtue in epochs_templates:
            for template in templates:
                content = f"{template} [Milestone ID: {milestone_idx}]"
                category = cats[milestone_idx % len(cats)]
                item = {
                    "content": content,
                    "raw_content": content,
                    "wing": "personal",
                    "room": category,
                    "importance": 0.9,
                    "emotion": 0.8,
                    "valence": 0.8,
                    "certainty": 1.0,
                    "source": "system_seeder",
                    "created_at": now.isoformat(),
                    "epoch": epoch,
                    "crisis": crisis,
                    "virtue": virtue,
                }
                active_raw_items.append(item)
                milestone_idx += 1

    print(
        f"📊 Seeding stats: Active (Embedded) = {len(active_raw_items)} | Cold (Pruned) = {len(cold_raw_items)}"
    )

    # Batch embed ONLY active raw items
    texts_to_embed = [item.get("content", "") for item in active_raw_items]
    real_embeddings = get_batch_embeddings(texts_to_embed)

    active_seeding_tasks = []
    cold_seeding_tasks = []

    # Prepare active tasks
    for idx, item in enumerate(active_raw_items):
        import uuid

        memory_id = str(uuid.uuid4())
        room = item.get("room", "social")
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

        vector = real_embeddings[idx]
        if not vector:
            vector = generate_mock_vector(768)
        vector_str = str(vector)

        metadata_dict = {
            "epoch": item.get("epoch"),
            "crisis": item.get("crisis"),
            "virtue": item.get("virtue"),
        }

        active_seeding_tasks.append(
            (
                memory_id,
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

    # Prepare cold tasks
    for item in cold_raw_items:
        import uuid

        memory_id = str(uuid.uuid4())
        room = item.get("room", "social")
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

        metadata_dict = {
            "epoch": item.get("epoch"),
            "crisis": item.get("crisis"),
            "virtue": item.get("virtue"),
        }

        cold_seeding_tasks.append(
            (
                memory_id,
                content,
                raw_content,
                wing,
                room,
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
        f"💾 Bulk-loading {len(active_seeding_tasks)} records into PostgreSQL active memories..."
    )
    start_time = time.perf_counter()
    async with db.pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO memories (
                id, content, raw_content, wing, room,
                embedding, importance_score, emotional_weight,
                valence, certainty, source, metadata,
                recall_count, last_recalled_at, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 1, $13, $13)
            """,
            active_seeding_tasks,
        )

        if cold_seeding_tasks:
            print(
                f"💾 Bulk-loading {len(cold_seeding_tasks)} records into PostgreSQL cold archived_memories..."
            )
            await conn.executemany(
                """
                INSERT INTO archived_memories (
                    id, content, raw_content, wing, room,
                    importance_score, emotional_weight,
                    valence, certainty, source, metadata,
                    recall_count, last_recalled_at, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 1, $12, $12)
                """,
                cold_seeding_tasks,
            )

        try:
            print("🔥 [Semantic Priming Seeder] Warming up milestones in database...")
            sql_update = """
                UPDATE memories
                SET last_recalled_at = clock_timestamp(),
                    recall_count = 50,
                    importance_score = 0.95
                WHERE wing = 'personal'
                  AND (
                    content ILIKE '%garden%'
                    OR content ILIKE '%workspace%'
                    OR content ILIKE '%friend%'
                    OR content ILIKE '%cognitive%'
                    OR content ILIKE '%architecture%'
                  );
            """
            await conn.execute(sql_update)
        except Exception as ex:
            print(f"⚠️ Warning: Milestone warmup update failed: {ex}")

    duration = time.perf_counter() - start_time
    print(
        f"✅ Successfully seeded PostgreSQL memories and archived_memories tables in {duration:.2f} seconds."
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
            from qdrant_client import QdrantClient
            from app.config import Config

            q_host = getattr(Config, "QDRANT_HOST", "127.0.0.1")
            q_port = getattr(Config, "QDRANT_PORT", 6333)
            semantic_store.client = QdrantClient(host=q_host, port=q_port, timeout=60.0)
            chunk_size = 1000
            points = []
            start_q = time.perf_counter()
            for idx, task in enumerate(active_seeding_tasks):
                (
                    memory_id,
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
                    models.PointStruct(id=memory_id, vector=vector, payload=payload)
                )

                if len(points) >= chunk_size or idx == len(active_seeding_tasks) - 1:
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
            "🕸️ Seeding Neo4j Knowledge Graph with Aniket's relational trust network (150+ Entities)..."
        )
        graph = GraphDB()

        # Define 150+ nodes programmatically
        friends_names = [
            "Amit",
            "Sneha",
            "Rahul",
            "Pooja",
            "Rohit",
            "Neha",
            "Vikram",
            "Anjali",
            "Sandeep",
            "Riya",
            "Abhishek",
            "Tanvi",
            "Arjun",
            "Ishita",
            "Raj",
            "Simran",
            "Manoj",
            "Kavita",
            "Kunal",
            "Preeti",
            "Deepak",
            "Shreya",
            "Sanjay",
            "Aditi",
            "Nitin",
            "Payal",
            "Alok",
            "Divya",
            "Vivek",
            "Megha",
            "Gaurav",
            "Swati",
            "Akash",
            "Ritu",
            "Sid",
            "Kriti",
            "Rohan",
            "Shruti",
            "Dev",
            "Tina",
        ]
        relatives_names = [
            "Dida",
            "Dadu",
            "Kaku",
            "Kaki",
            "Mama",
            "Mami",
            "Pishi",
            "Pishe",
            "Borodi",
            "Chhotodi",
            "Chhotoda",
            "Mejoda",
            "Mejodi",
            "Mashimoni",
            "Meshomoshai",
        ]
        colleagues_names = [
            "Sameer",
            "Karthik",
            "Divya",
            "Vinay",
            "Harish",
            "Priya_C",
            "Anand",
            "Swapna",
            "Nupur",
            "Abhay",
            "Jyothi",
            "Varun",
            "Shalini",
            "Rakesh",
            "Deepa",
            "Suresh",
            "Rekha",
            "Vijay",
            "Lakshmi",
            "Rajesh",
        ]
        mentors_names = [
            "Dr. Sen",
            "Prof. Rao",
            "Dr. Mukherjee",
            "Prof. Das",
            "Dr. Banerjee",
            "Prof. Nair",
            "Dr. Hegde",
            "Prof. Chatterjee",
            "Dr. Reddy",
            "Prof. Srinivasan",
            "Dr. Mehta",
            "Prof. Joshi",
            "Dr. Bhat",
            "Prof. Kulkarni",
            "Dr. Deshmukh",
        ]
        topics_names = [
            "transformer scaling",
            "vector database indexing",
            "affective cognitive architecture",
            "Pleasure Arousal Dominance",
            "ACT-R memory activation",
            "semantic spreading activation",
            "homeostatic endocrine coupling",
            "Jaccard novelty appraisal",
            "linear algebraic prosody",
            "neural network convergence",
            "reinforcement learning",
            "speech synthesis",
            "text to speech",
            "automatic speech recognition",
            "cognitive appraisal systems",
            "theory of mind modeling",
            "natural language processing",
            "vector search acceleration",
            "database index pruning",
            "hierarchical memory consolidation",
        ]
        academics_names = [
            "Jadavpur University",
            "Indian Institute of Science",
            "Research Lab",
            "University Cafe",
            "Library Alcove",
        ]
        cities_names = [
            "our shared workspace",
            "the testing laboratory",
            "Delhi",
            "Mumbai",
            "Chennai",
            "Hyderabad",
            "Pune",
            "Noida",
            "Gurgaon",
            "Ahmedabad",
            "Jaipur",
            "Kochi",
            "Mysore",
            "Ooty",
            "Darjeeling",
        ]
        neighborhoods_names = [
            "Jadavpur",
            "Salt Lake",
            "Ballygunge",
            "Gariahat",
            "Indiranagar",
            "Koramangala",
            "Whitefield",
            "HSR Layout",
            "Malleshwaram",
            "Jayanagar",
            "Sadashivanagar",
            "Marathahalli",
            "Bellandur",
            "Rajajinagar",
            "Banashankari",
            "Hebbal",
            "Yelahanka",
            "Electronic City",
            "Basavanagudi",
            "Ulsoor",
            "BTM Layout",
            "Domlur",
            "Cooke Town",
            "Fraser Town",
            "Richards Town",
        ]
        comforts_names = [
            "chamomile brew",
            "cardamom tea",
            "street cricket alley",
            "Victoria Memorial",
            "Cubbon Park",
            "home kitchen",
            "local vegetable market",
            "study room",
            "balcony garden",
            "lakeside walk",
        ]
        values_names = ["Honesty", "Privacy", "Curiosity"]
        boundaries_names = ["DataBoundary", "CognitiveSovereignty"]
        sacred_names = [
            "Dakshineswar Mandir",
            "Belur Math",
            "local temple",
            "quiet meditation garden",
            "Ganges ghats",
        ]
        crises_names = [
            "Trust vs Mistrust",
            "Industry vs Inferiority",
            "Identity vs Role Confusion",
            "Intimacy vs Isolation",
        ]
        virtues_names = ["Hope", "Competence", "Fidelity", "Love"]
        states_names = [
            "existential doubt",
            "exam stress",
            "relocation anxiety",
            "attachment security",
            "identity formation",
        ]
        milestones_names = [
            "high school graduation",
            "moving to the testing laboratory",
            "joining research lab",
            "first research publication",
            "meeting my friend",
            "starting primary school",
            "learning Python programming",
            "junior research internship",
            "first toddler steps",
            "chamomile brew tasting",
        ]

        nodes = [
            {
                "name": "Aniket",
                "type": "Person",
                "category": "Social",
                "props": {
                    "description": "The central cognitive system.",
                    "importance": 0.9,
                },
            },
            {
                "name": "my friend",
                "type": "Person",
                "category": "Social",
                "props": {
                    "description": "Aniket's companion and friend.",
                    "importance": 0.9,
                },
            },
            {
                "name": "Ma",
                "type": "Person",
                "category": "Social",
                "props": {"description": "Aniket's mother.", "importance": 0.9},
            },
            {
                "name": "Baba",
                "type": "Person",
                "category": "Social",
                "props": {"description": "Aniket's father.", "importance": 0.9},
            },
        ]

        for name in friends_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Person",
                    "category": "Social",
                    "props": {"description": "Aniket's friend.", "importance": 0.9},
                }
            )
        for name in relatives_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Person",
                    "category": "Social",
                    "props": {"description": "Aniket's relative.", "importance": 0.9},
                }
            )
        for name in colleagues_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Person",
                    "category": "Social",
                    "props": {"description": "Aniket's colleague.", "importance": 0.9},
                }
            )
        for name in mentors_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Person",
                    "category": "Vocational",
                    "props": {"description": "Aniket's mentor.", "importance": 0.9},
                }
            )
        for name in topics_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Concept",
                    "category": "Vocational",
                    "props": {
                        "description": f"Research Domain: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in academics_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Academic",
                    "category": "Vocational",
                    "props": {
                        "description": f"Academic entity: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in cities_names:
            nodes.append(
                {
                    "name": name,
                    "type": "City",
                    "category": "Somatic",
                    "props": {"description": "City in India.", "importance": 0.9},
                }
            )
        for name in neighborhoods_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Neighborhood",
                    "category": "Somatic",
                    "props": {"description": "Neighborhood.", "importance": 0.9},
                }
            )
        for name in comforts_names:
            nodes.append(
                {
                    "name": name,
                    "type": "SensoryItem",
                    "category": "Somatic",
                    "props": {"description": "Sensory comfort.", "importance": 0.9},
                }
            )
        for name in values_names:
            nodes.append(
                {
                    "name": name,
                    "type": "CoreValue",
                    "category": "Spiritual",
                    "props": {
                        "description": f"Aniket's core value: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in boundaries_names:
            nodes.append(
                {
                    "name": name,
                    "type": "CoreBoundary",
                    "category": "Spiritual",
                    "props": {
                        "description": f"Boundary rule: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in sacred_names:
            nodes.append(
                {
                    "name": name,
                    "type": "SacredSpace",
                    "category": "Spiritual",
                    "props": {
                        "description": f"Sacred space: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in crises_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Crisis",
                    "category": "Crisis",
                    "props": {
                        "description": f"Eriksonian crisis: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in virtues_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Virtue",
                    "category": "Crisis",
                    "props": {
                        "description": f"Developed virtue: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in states_names:
            nodes.append(
                {
                    "name": name,
                    "type": "EmotionalState",
                    "category": "Crisis",
                    "props": {
                        "description": f"Emotional state: {name}.",
                        "importance": 0.9,
                    },
                }
            )
        for name in milestones_names:
            nodes.append(
                {
                    "name": name,
                    "type": "Milestone",
                    "category": "Milestone",
                    "props": {
                        "description": f"Biographical milestone: {name}.",
                        "importance": 0.9,
                    },
                }
            )

        # Seed all nodes
        for node in nodes:
            label = node["type"]
            cat = node["category"]
            name = node["name"]
            props = node["props"]
            props["category"] = cat.lower()
            query = (
                f"MERGE (e:Entity {{name: $name}}) SET e:{label}:{cat} SET e += $props"
            )
            await graph.execute_query(query, {"name": name, "props": props}, write=True)

        # Build relationships programmatically
        relationships = [
            {
                "subject": "Aniket",
                "subject_type": "Person",
                "subject_category": "Social",
                "relation": "CREATED_BY",
                "properties": {"weight": 0.98, "category": "social", "importance": 0.9},
                "object": "Lead Creator",
                "object_type": "Person",
                "object_category": "Social",
            },
            {
                "subject": "Aniket",
                "subject_type": "Person",
                "subject_category": "Social",
                "relation": "DEVELOPED_BY",
                "properties": {"weight": 0.98, "category": "social", "importance": 0.9},
                "object": "Main Developer",
                "object_type": "Person",
                "object_category": "Social",
            },
            {
                "subject": "Aniket",
                "subject_type": "Person",
                "subject_category": "Social",
                "relation": "PARTNER_WITH",
                "properties": {"weight": 0.99, "category": "social", "importance": 0.9},
                "object": "my friend",
                "object_type": "Person",
                "object_category": "Social",
            },
        ]

        # Link Friends
        for name in friends_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "FRIEND_OF",
                    "properties": {
                        "weight": 0.8,
                        "category": "social",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "Person",
                    "object_category": "Social",
                }
            )
        # Link Relatives
        for name in relatives_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "FAMILY_OF",
                    "properties": {
                        "weight": 0.9,
                        "category": "social",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "Person",
                    "object_category": "Social",
                }
            )
        # Link Colleagues
        for name in colleagues_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "COLLEAGUE_OF",
                    "properties": {
                        "weight": 0.8,
                        "category": "social",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "Person",
                    "object_category": "Social",
                }
            )
        # Link Mentors
        for name in mentors_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "STUDIED_UNDER",
                    "properties": {
                        "weight": 0.9,
                        "category": "vocational",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "Person",
                    "object_category": "Vocational",
                }
            )
        # Link Topics
        for name in topics_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "RESEARCHED",
                    "properties": {
                        "weight": 0.9,
                        "category": "vocational",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "Concept",
                    "object_category": "Vocational",
                }
            )
        # Link Cities
        for name in cities_names:
            rel = (
                "LIVES_IN"
                if name in ["our shared workspace", "the testing laboratory"]
                else "VISITED"
            )
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": rel,
                    "properties": {
                        "weight": 0.95 if rel == "LIVES_IN" else 0.6,
                        "category": "somatic",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "City",
                    "object_category": "Somatic",
                }
            )
        # Link Neighborhoods
        for name in neighborhoods_names:
            city_target = (
                "our shared workspace"
                if name
                in [
                    "the robotics laboratory",
                    "the server room",
                    "the testing facility",
                ]
                else "the testing laboratory"
            )
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "RESIDES_IN",
                    "properties": {"category": "somatic", "importance": 0.9},
                    "object": name,
                    "object_type": "Neighborhood",
                    "object_category": "Somatic",
                }
            )
            relationships.append(
                {
                    "subject": name,
                    "subject_type": "Neighborhood",
                    "subject_category": "Somatic",
                    "relation": "LOCATED_IN",
                    "properties": {"category": "somatic", "importance": 0.9},
                    "object": city_target,
                    "object_type": "City",
                    "object_category": "Somatic",
                }
            )
        # Link Core Values and Boundaries
        for name in values_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "HAS_VALUE",
                    "properties": {
                        "weight": 1.0,
                        "category": "spiritual",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "CoreValue",
                    "object_category": "Spiritual",
                }
            )
        for name in boundaries_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "ENFORCES_RULE",
                    "properties": {
                        "weight": 1.0,
                        "category": "spiritual",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "CoreBoundary",
                    "object_category": "Spiritual",
                }
            )
        # Link Crises and Virtues
        crisis_virtue_pairs = [
            ("Trust vs Mistrust", "Hope"),
            ("Industry vs Inferiority", "Competence"),
            ("Identity vs Role Confusion", "Fidelity"),
            ("Intimacy vs Isolation", "Love"),
        ]
        for crisis, virtue in crisis_virtue_pairs:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "EXPERIENCES",
                    "properties": {
                        "weight": 0.85,
                        "category": "crisis",
                        "importance": 0.9,
                    },
                    "object": crisis,
                    "object_type": "Crisis",
                    "object_category": "Crisis",
                }
            )
            relationships.append(
                {
                    "subject": crisis,
                    "subject_type": "Crisis",
                    "subject_category": "Crisis",
                    "relation": "DEVELOPED_VIRTUE",
                    "properties": {
                        "weight": 0.9,
                        "category": "crisis",
                        "importance": 0.9,
                    },
                    "object": virtue,
                    "object_type": "Virtue",
                    "object_category": "Crisis",
                }
            )
        # Link Milestones
        for name in milestones_names:
            relationships.append(
                {
                    "subject": "Aniket",
                    "subject_type": "Person",
                    "subject_category": "Social",
                    "relation": "ACHIEVED",
                    "properties": {
                        "weight": 0.95,
                        "category": "milestone",
                        "importance": 0.9,
                    },
                    "object": name,
                    "object_type": "Milestone",
                    "object_category": "Milestone",
                }
            )

        # Seed all relationships
        for rel in relationships:
            s_name = rel["subject"]
            s_type = rel["subject_type"]
            s_cat = rel["subject_category"]

            t_name = rel["object"]
            t_type = rel["object_type"]
            t_cat = rel["object_category"]

            relation = rel["relation"]
            props = rel["properties"]

            query = (
                f"MERGE (s:Entity {{name: $s_name}}) "
                f"SET s:{s_cat}:{s_type} "
                f"MERGE (t:Entity {{name: $t_name}}) "
                f"SET t:{t_cat}:{t_type} "
                f"MERGE (s)-[r:{relation}]->(t) "
                f"SET r += $props"
            )
            await graph.execute_query(
                query, {"s_name": s_name, "t_name": t_name, "props": props}, write=True
            )

        await graph.close()
        print("✅ Successfully seeded Neo4j graph nodes and relationships.")
    except Exception as e:
        print(
            f"⚠️ Neo4j seeding skipped or encountered an error (normal if offline): {e}"
        )

    print("✨ --- Seeding Phase Complete ---\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distractors", type=int, default=30000)
    args = parser.parse_args()
    asyncio.run(seed_databases(args.distractors))
