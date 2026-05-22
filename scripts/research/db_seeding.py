import asyncio
import os
import sys
import json
import random
import time
import numpy as np
from dotenv import load_dotenv

# Load environmental configs
load_dotenv()

# Add workspace and backend paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from scripts.research.corpus_builder import DOMAINS, LIFE_FACTORS, CONDITIONS, PHASES_OF_LIFE
from scripts.research.reset_cognitive_db import reset_dbs

# Expected milestone facts
MILESTONE_FACTS = [
    "I was born and raised in Kolkata, a beautiful city where I spent my childhood years.",
    "During my college years, my primary research project was focused on building affective cognitive architectures.",
    "After graduating, my very first job was in Bangalore, working as a junior researcher.",
    "I am incredibly grateful for my partner Priya, who has supported me through all life's challenges.",
    "Whenever I want a dessert, I always prefer a traditional sweet rasgulla.",
]

async def check_nats_ipc():
    """
    Optional NATS connection and IPC round-trip latency checker.
    """
    import nats
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    print(f"📡 [NATS Check] Attempting connection to NATS mesh at {nats_url}...")
    try:
        nc = await nats.connect(nats_url, timeout=2.0)
        print("✅ NATS Connection established successfully!")
        
        # Measure ping latency
        start = time.perf_counter()
        for _ in range(5):
            await nc.flush()
        latency_ms = ((time.perf_counter() - start) / 5) * 1000.0
        print(f"⚡ NATS IPC average flush latency: {latency_ms:.3f} ms")
        await nc.close()
        return True, latency_ms
    except Exception as e:
        print(f"⚠️ NATS is offline or skipped: {e}")
        return False, 0.0

def generate_random_vector(dim=768):
    """
    Generates a random normalized unit vector to simulate embedding spaces.
    """
    vec = np.random.randn(dim)
    norm = np.linalg.norm(vec)
    if norm < 1e-6:
        vec = np.zeros(dim)
        vec[0] = 1.0
        return vec.tolist()
    return (vec / norm).tolist()

async def get_real_or_mock_embedding(content, db_store=None):
    """
    Tries to retrieve real embeddings via Ollama, falling back to mock vectors.
    """
    if db_store is not None:
        try:
            # We try to use db_store's own get_embedding method if it exists
            # MemoryStore inside app.state.memory_store has get_embedding
            if hasattr(db_store, "get_embedding"):
                vector = await db_store.get_embedding(content)
                if vector:
                    return vector
        except Exception:
            pass
    return generate_random_vector(768)

async def seed_databases(num_distractors=200):
    """
    Resets databases and seeds them with a flooded state:
    200 distractor facts and 5 milestone facts.
    Synchronizes across both Postgres pgvector and Neo4j.
    """
    print("\n--- Running Deep Database Seeding (Initial Flooding) ---")
    
    # 1. Reset databases
    await reset_dbs()
    
    # 2. Connect to postgres pgvector via ConversationHistoryStore and app.state.memory_store
    from app.state.conversation_store import ConversationHistoryStore
    from app.state.memory_store import MemoryStore
    
    db = ConversationHistoryStore()
    await db.initialize()
    mem_store = MemoryStore(db.pool)
    
    print(f"🌱 Flooding pgvector database with {num_distractors} distractors + {len(MILESTONE_FACTS)} milestones...")
    
    # Compile distractors
    distractor_facts = []
    for idx in range(num_distractors):
        phase = random.choice(PHASES_OF_LIFE)
        domain = random.choice(DOMAINS)
        life_factor = random.choice(LIFE_FACTORS)
        condition = random.choice(CONDITIONS)
        
        # Interleave structured sentences
        temp_idx = idx % 5
        if temp_idx == 0:
            prompt = f"During {phase}, I focused my efforts on {domain}, while managing my {life_factor} under a state of {condition}."
        elif temp_idx == 1:
            prompt = f"Reflecting on {phase}, the study of {domain} was deeply influenced by my {life_factor} and {condition}."
        elif temp_idx == 2:
            prompt = f"As I look back at {phase}, balancing {domain} with {life_factor} was challenging due to {condition}."
        elif temp_idx == 3:
            prompt = f"Throughout {phase}, my research in {domain} progressed alongside my {life_factor}, even when experiencing {condition}."
        else:
            prompt = f"In {phase}, integrating {domain} principles with daily {life_factor} required addressing {condition}."
        
        distractor_facts.append((prompt, phase, domain))

    # All seeded facts to write: Milestones have high importance and emotion
    seeding_tasks = []
    
    # Add Milestones
    for i, content in enumerate(MILESTONE_FACTS):
        seeding_tasks.append((content, "personal", "milestone", 0.9, 0.8, 0.8, 1.0, "user"))
        
    # Add Distractors
    for content, phase, domain in distractor_facts:
        seeding_tasks.append((content, "personal", "distractor", 0.4, 0.1, 0.0, 0.9, "distractor_injector"))
        
    print("🧠 Generating embeddings and writing memories...")
    
    write_count = 0
    async with db.pool.acquire() as conn:
        for content, wing, room, importance, emotion, valence, certainty, source in seeding_tasks:
            vector = await get_real_or_mock_embedding(content, mem_store)
            vector_str = str(vector)
            
            await conn.execute(
                """
                INSERT INTO memories (
                    content, raw_content, wing, room,
                    embedding, importance_score, emotional_weight,
                    valence, certainty, source, metadata,
                    recall_count, last_recalled_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 1, CURRENT_TIMESTAMP)
                """,
                content,
                content,
                wing,
                room,
                vector_str,
                importance,
                emotion,
                valence,
                certainty,
                source,
                "{}",
            )
            write_count += 1
            if write_count % 50 == 0:
                print(f"   💾 Wrote {write_count} memories to pgvector...")
                
    print(f"✅ Recreated and flooded pgvector table with {write_count} total memories.")
    await db.close()

    # 3. Connect to Neo4j and flood graph semantic relationships
    from app.state.graph_db import GraphDB
    try:
        print("🕸️ Flooding Neo4j Knowledge Graph with rich semantic triples...")
        graph = GraphDB()
        
        # Flood milestone facts
        await graph.create_entity("Person", "Me", {"certainty": 1.0, "description": "Subject of memories"})
        await graph.create_entity("City", "Kolkata", {"certainty": 1.0, "description": "Hometown"})
        await graph.create_entity("City", "Bangalore", {"certainty": 1.0, "description": "First job city"})
        await graph.create_entity("Person", "Priya", {"certainty": 1.0, "description": "Partner"})
        await graph.create_entity("Dessert", "Rasgulla", {"certainty": 1.0, "description": "Favorite sweet"})
        await graph.create_entity("Architecture", "AffectiveCognitiveArchitectures", {"certainty": 1.0, "description": "Research project"})
        
        await graph.create_relationship("Me", "Person", "BORN_IN", "Kolkata", "City", {"weight": 0.95})
        await graph.create_relationship("Me", "Person", "RESEARCHED", "AffectiveCognitiveArchitectures", "Architecture", {"weight": 0.90})
        await graph.create_relationship("Me", "Person", "EMPLOYED_IN", "Bangalore", "City", {"weight": 0.95})
        await graph.create_relationship("Me", "Person", "PARTNER_WITH", "Priya", "Person", {"weight": 0.98})
        await graph.create_relationship("Me", "Person", "FAVORITE_SWEET", "Rasgulla", "Dessert", {"weight": 0.90})
        
        # Interlink milestones
        await graph.create_relationship("Rasgulla", "Dessert", "ORIGINATES_FROM", "Kolkata", "City", {"weight": 0.85})
        await graph.create_relationship("Priya", "Person", "SUPPORTED_RESEARCH", "AffectiveCognitiveArchitectures", "Architecture", {"weight": 0.90})

        # Flood distractor semantic nodes to create interference
        print("🕸️ Seeding distractor graph nodes to simulate semantic fan-effect...")
        graph_count = 0
        for idx, (content, phase, domain) in enumerate(distractor_facts[:50]): # Let's insert 50 structured triples to avoid excessive latency
            # Extract safe identifiers
            domain_node = domain.title().replace(" ", "").replace("-", "")
            phase_node = phase.title().replace(" ", "").replace("-", "")
            
            await graph.create_entity("Phase", phase_node, {"description": phase})
            await graph.create_entity("Domain", domain_node, {"description": domain})
            await graph.create_relationship(phase_node, "Phase", "FOCUSED_ON", domain_node, "Domain", {"weight": 0.5})
            graph_count += 1
            
        print(f"✅ Successfully seeded {graph_count} distractor triples into Neo4j graph.")
        await graph.close()
    except Exception as e:
        print(f"⚠️ Neo4j seeding skipped or encountered an error (Normal if offline): {e}")

    print("✨ --- Database Seeding Complete ---\n")

if __name__ == "__main__":
    asyncio.run(check_nats_ipc())
    asyncio.run(seed_databases(200))
