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

ANIKET_DISTRACTOR_CATEGORIES = [
    "somatic",  # 0: market
    "vocational",  # 1: math project
    "vocational",  # 2: coding arcade
    "social",  # 3: family dinner
    "social",  # 4: cricket match
    "somatic",  # 5: sweet rasgullas
    "somatic",  # 6: Victoria Memorial
    "social",  # 7: meals
    "vocational",  # 8: examinations
    "social",  # 9: moving to Bangalore
    "social",  # 10: Priya
    "vocational",  # 11: architectures
    "social",  # 12: Cubbon Park
    "somatic",  # 13: rasgullas
    "vocational",  # 14: query optimization
    "social",  # 15: phone stories
    "social",  # 16: quiet library
    "social",  # 17: reunion
    "vocational",  # 18: concurrent thread pool
    "somatic",  # 19: tea
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
        return False, None


async def seed_databases(num_distractors=30000):
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
        raw_items = []

        for item in corpus_data:
            importance = item.get("importance", 0.4)
            is_dist = importance < 0.5

            if is_dist:
                if distractor_count >= num_distractors:
                    continue
                distractor_count += 1
            else:
                milestone_count += 1
            raw_items.append(item)

        # Batch embed all raw items content dynamically to build proper database state
        texts_to_embed = [item.get("content", "") for item in raw_items]
        real_embeddings = get_batch_embeddings(texts_to_embed)

        for idx, item in enumerate(raw_items):
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
        raw_distractors = []
        for i in range(num_distractors):
            t_idx = i % len(ANIKET_DISTRACTOR_TEMPLATES)
            template = ANIKET_DISTRACTOR_TEMPLATES[t_idx]
            category = ANIKET_DISTRACTOR_CATEGORIES[t_idx]
            content = f"{template} [Turn: {i}]"

            elapsed_seconds = i * time_step_seconds
            created_time = now - timedelta(seconds=elapsed_seconds)
            raw_distractors.append((content, category, created_time))

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

        raw_milestones = []
        milestone_idx = 0
        for templates, cats, epoch, crisis, virtue in epochs_templates:
            for template in templates:
                content = f"{template} [Milestone ID: {milestone_idx}]"
                category = cats[milestone_idx % len(cats)]
                raw_milestones.append((content, category, epoch, crisis, virtue))
                milestone_idx += 1

        # Gather all text items to embed and batch-embed them
        texts_to_embed = [d[0] for d in raw_distractors] + [
            m[0] for m in raw_milestones
        ]
        real_embeddings = get_batch_embeddings(texts_to_embed)

        # Populate distractors in seeding_tasks
        for i, d in enumerate(raw_distractors):
            content, category, created_time = d
            vector = real_embeddings[i]
            if not vector:
                vector = generate_mock_vector(768)
            vector_str = str(vector)

            seeding_tasks.append(
                (
                    content,
                    content,
                    "personal",
                    category,
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

        # Populate milestones in seeding_tasks
        offset = len(raw_distractors)
        for i, m in enumerate(raw_milestones):
            content, category, epoch, crisis, virtue = m
            vector = real_embeddings[offset + i]
            if not vector:
                vector = generate_mock_vector(768)
            vector_str = str(vector)

            seeding_tasks.append(
                (
                    content,
                    content,
                    "personal",
                    category,
                    vector_str,
                    0.9,
                    0.8,
                    0.8,
                    1.0,
                    "system_seeder",
                    json.dumps({"epoch": epoch, "crisis": crisis, "virtue": virtue}),
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

        try:
            print(
                "🔥 [Semantic Priming Seeder] Warming up biographical milestones in database..."
            )
            sql_update = """
                UPDATE memories
                SET last_recalled_at = clock_timestamp(),
                    recall_count = 50,
                    importance_score = 0.95
                WHERE wing = 'personal'
                  AND (
                    content ILIKE '%Kolkata%'
                    OR content ILIKE '%Bangalore%'
                    OR content ILIKE '%Priya%'
                    OR content ILIKE '%rasgulla%'
                    OR content ILIKE '%cognitive architecture%'
                    OR content ILIKE '%affective cognitive%'
                  );
            """
            await conn.execute(sql_update)
        except Exception as ex:
            print(f"⚠️ Warning: Milestone warmup update failed: {ex}")

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
            from qdrant_client import QdrantClient

            # Recreate client with larger timeout to prevent timeouts during 30k seeding
            from app.config import Config

            q_host = getattr(Config, "QDRANT_HOST", "127.0.0.1")
            q_port = getattr(Config, "QDRANT_PORT", 6333)
            semantic_store.client = QdrantClient(host=q_host, port=q_port, timeout=60.0)
            chunk_size = 1000
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
            "Kolkata",
            "Bangalore",
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
            "sweet rasgulla",
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
            "moving to Bangalore",
            "joining research lab",
            "first research publication",
            "meeting Priya",
            "starting primary school",
            "learning Python programming",
            "junior research internship",
            "first toddler steps",
            "sweet rasgulla tasting",
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
                "name": "Priya",
                "type": "Person",
                "category": "Social",
                "props": {
                    "description": "Aniket's romantic partner.",
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
                "relation": "CHILD_OF",
                "properties": {"weight": 0.98, "category": "social", "importance": 0.9},
                "object": "Ma",
                "object_type": "Person",
                "object_category": "Social",
            },
            {
                "subject": "Aniket",
                "subject_type": "Person",
                "subject_category": "Social",
                "relation": "CHILD_OF",
                "properties": {"weight": 0.98, "category": "social", "importance": 0.9},
                "object": "Baba",
                "object_type": "Person",
                "object_category": "Social",
            },
            {
                "subject": "Aniket",
                "subject_type": "Person",
                "subject_category": "Social",
                "relation": "PARTNER_WITH",
                "properties": {"weight": 0.99, "category": "social", "importance": 0.9},
                "object": "Priya",
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
            rel = "LIVES_IN" if name in ["Kolkata", "Bangalore"] else "VISITED"
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
                "Bangalore"
                if name
                in [
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
                else "Kolkata"
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
