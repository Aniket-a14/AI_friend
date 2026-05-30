import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from datetime import datetime, timezone
from app.cognitive.identity import IdentityManager
from app.state.graph_db import GraphDB
from app.state.memory_store import MemoryStore

# ----------------- Neo4j Hebbian Decay Tests -----------------


@pytest.mark.asyncio
async def test_neo4j_relationship_decay():
    # Mock Neo4j driver and sessions
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_driver.session.return_value.__aenter__.return_value = mock_session

    with patch("neo4j.AsyncGraphDatabase.driver", return_value=mock_driver):
        # Instantiate GraphDB with dummy credentials to avoid default validations
        db = GraphDB(
            uri="bolt://localhost:7687", user="neo4j", password="strong_password_123"
        )

        # Capture queries executed
        queries_run = []

        async def mock_execute_query(query, parameters=None, **kwargs):
            queries_run.append((query, parameters))
            return []

        db.execute_query = mock_execute_query

        # Run decay
        await db.decay_relationships(decay_factor=0.90, prune_threshold=0.20)

        # Verify weight decay query was run
        decay_query_found = False
        prune_query_found = False
        for query, params in queries_run:
            if "SET r.weight = coalesce(r.weight, 1.0) * $decay_factor" in query:
                assert params["decay_factor"] == 0.90
                decay_query_found = True
            if (
                "WHERE coalesce(r.weight, 0.0) < $prune_threshold DELETE r" in query
                or "WHERE coalesce(r.weight, 0.0) < $prune_threshold" in query
            ):
                assert params["prune_threshold"] == 0.20
                prune_query_found = True

        assert decay_query_found, "Decay query not executed"
        assert prune_query_found, "Prune query not executed"


# ----------------- Memory Store Habituation (PTSD Extinction) Tests -----------------


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.mark.asyncio
async def test_memory_emotional_habituation_decay(mock_pool):
    pool, conn = mock_pool
    store = MemoryStore(pool, None)
    store.qdrant_store.client = None

    # Verify _refresh_memories executes SQLite query containing the decay logic
    memories = [{"content": "Extremely negative traumatic memory"}]

    # We call _refresh_memories under positive context (valence = 0.5)
    await store._refresh_memories(memories, current_valence=0.5)

    # Verify execute was called on sqlite/postgres with decay CASE WHEN statements
    execute_calls = conn.execute.call_args_list
    assert len(execute_calls) > 0

    sqlite_query = execute_calls[0][0][0]
    sqlite_params = execute_calls[0][0][1:]

    assert "emotional_weight = CASE" in sqlite_query
    assert "importance_score = CASE" in sqlite_query

    # Check parameters depending on which branch was executed
    if len(sqlite_params) == 2:
        # Postgres branch: (contents, current_valence)
        assert sqlite_params[0] == ["Extremely negative traumatic memory"]
        assert sqlite_params[1] == 0.5
    else:
        # SQLite branch: (current_valence, current_valence, *contents)
        assert sqlite_params[0] == 0.5
        assert sqlite_params[1] == 0.5
        assert sqlite_params[2] == "Extremely negative traumatic memory"


# ----------------- Qdrant Dynamic Metadata Syncing Tests -----------------


@pytest.mark.asyncio
async def test_qdrant_dynamic_metadata_sync(mock_pool):
    pool, conn = mock_pool
    store = MemoryStore(pool, None)

    # Setup mock Qdrant client to simulate Qdrant retrieval returning candidates
    mock_qdrant = MagicMock()
    store.qdrant_store.client = mock_qdrant

    # Qdrant candidate with static outdated metadata
    candidates = [
        {
            "id": "mem-uuid-1234",
            "score": 0.8,
            "content": "Outdated memory",
            "metadata": {
                "wing": "personal",
                "room": None,
                "valence": -0.5,
                "emotional_weight": 0.9,
                "importance_score": 0.8,
                "recall_count": 1,
                "last_recalled_at": 1000.0,
                "created_at": 1000.0,
            },
        }
    ]

    # DB has decayed/updated properties for the same memory ID
    db_rows = [
        {
            "id": "mem-uuid-1234",
            "valence": -0.5,
            "emotional_weight": 0.45,  # Decayed from 0.9
            "importance_score": 0.65,  # Decayed from 0.8
            "recall_count": 5,  # Incremented
            "last_recalled_at": datetime.now(timezone.utc),
        }
    ]

    conn.fetch.return_value = db_rows

    # Mock embedding return
    with patch.object(store, "get_embedding", return_value=[0.1] * 768):
        # Let's mock search_vector_memories in the SemanticRecallStore
        store.qdrant_store.search_vector_memories = MagicMock(return_value=candidates)

        # Run memory search
        results = await store.search_memories("outdated", threshold=-10.0, limit=1)

        # Verify database query was made with candidate ID
        fetch_args = conn.fetch.call_args
        assert fetch_args is not None

        # Check that 'mem-uuid-1234' is present in the arguments passed to fetch
        args_flat = []
        for arg in fetch_args[0]:
            if isinstance(arg, list):
                args_flat.extend(arg)
            else:
                args_flat.append(arg)
        assert any("mem-uuid-1234" in str(x) for x in args_flat)

        # Verify results contained the merged DB properties instead of static Qdrant metadata
        assert len(results) == 1
        assert results[0]["recall_count"] == 5
        assert results[0]["valence"] == -0.5


# ----------------- Identity Trait Capping Tests -----------------


@pytest.fixture
def base_personality():
    return {
        "name": "friend",
        "core_personality": {
            "adaptive_traits": ["Trait1", "Trait2", "Trait3", "Trait4", "Trait5"]
        },
    }


def test_adaptive_traits_init_cap():
    # Personality starts with 7 traits
    p = {
        "name": "friend",
        "core_personality": {
            "adaptive_traits": ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
        },
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(p))):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake")
            # Should be capped to the last 5 traits
            assert len(manager.personality["core_personality"]["adaptive_traits"]) == 5
            assert manager.personality["core_personality"]["adaptive_traits"] == [
                "T3",
                "T4",
                "T5",
                "T6",
                "T7",
            ]


@pytest.mark.asyncio
async def test_adaptive_traits_evolve_cap(base_personality):
    with patch("builtins.open", mock_open(read_data=json.dumps(base_personality))):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake")
            manager.personality = base_personality

            # Evolve with 2 new traits (total 7)
            await manager.evolve_persona({"new_traits": ["Trait6", "Trait7"]})

            # Verify traits are capped at 5 and keeps the latest
            traits = manager.personality["core_personality"]["adaptive_traits"]
            assert len(traits) == 5
            assert traits == ["Trait3", "Trait4", "Trait5", "Trait6", "Trait7"]


@pytest.mark.asyncio
async def test_adaptive_traits_hydration_cap():
    p = {
        "name": "friend",
        "core_personality": {"adaptive_traits": ["T1", "T2", "T3", "T4", "T5"]},
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(p))):
        with patch("os.path.exists", return_value=True):
            manager = IdentityManager(base_path="/fake")

            # Mock Config Store that returns 7 traits
            config_store = AsyncMock()
            config_store.get_agent_config.return_value = {
                "personality": json.dumps(
                    {
                        "name": "friend",
                        "core_personality": {
                            "adaptive_traits": [
                                "A1",
                                "A2",
                                "A3",
                                "A4",
                                "A5",
                                "A6",
                                "A7",
                            ]
                        },
                    }
                ),
                "history": "{}",
            }

            await manager.hydrate_from_config_store(config_store)

            # Verify hydrated traits are capped
            traits = manager.personality["core_personality"]["adaptive_traits"]
            assert len(traits) == 5
            assert traits == ["A3", "A4", "A5", "A6", "A7"]
