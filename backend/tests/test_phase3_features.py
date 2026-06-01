"""
Comprehensive Unit & Integration Tests for CVS-1.0 stability, ACT-R consolidation,
neuromodulatory gating, dimensional trust, and dynamic LLM temperature features.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.state.conversation_store import ConversationHistoryStore
from app.state.memory_store import MemoryStore
from app.state.agent_state import StateService, AgentState
from app.cognitive.appraisal import AppraisalVector
from app.cognitive.action import ActionService, ActionPlan
from app.agents.subconscious_agent import SubconsciousAgent
from app.cognitive.learning import ReflectionService
from app.config import Config


@pytest.mark.asyncio
async def test_neuromodulatory_gating_and_actr_pruning():
    """Verify that neuromodulatory gating (arousal, cortisol) and ACT-R base activation decay work correctly."""
    store = ConversationHistoryStore()
    await store.initialize()

    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph)
    mem_store.qdrant_store.client = None

    # 1. Mock embeddings to be close to query
    query_vector = [1.0, 0.0] + [0.0] * 766
    aligned_vector = [0.95, 0.05] + [0.0] * 766
    orthogonal_vector = [0.0, 1.0] + [0.0] * 766

    async def mock_get_embedding(text):
        if "query" in text:
            return query_vector
        if "aligned" in text:
            return aligned_vector
        return orthogonal_vector

    mem_store.get_embedding = mock_get_embedding

    # 2. Add sqlite schema manually
    async with store.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT,
                raw_content TEXT,
                wing TEXT,
                room TEXT,
                embedding TEXT,
                importance_score REAL,
                emotional_weight REAL,
                valence REAL,
                certainty REAL,
                source TEXT,
                metadata TEXT,
                recall_count INTEGER,
                last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lifespan_stage TEXT,
                crisis TEXT,
                virtue TEXT,
                relations TEXT,
                relation_circles TEXT,
                modality TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS archived_memories (
                id TEXT PRIMARY KEY,
                content TEXT,
                raw_content TEXT,
                wing TEXT,
                room TEXT,
                embedding TEXT,
                importance_score REAL,
                emotional_weight REAL,
                valence REAL,
                certainty REAL,
                source TEXT,
                metadata TEXT,
                recall_count INTEGER,
                last_recalled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lifespan_stage TEXT,
                crisis TEXT,
                virtue TEXT,
                relations TEXT,
                relation_circles TEXT,
                modality TEXT
            )
        """)

    # 3. Add personal memories with different emotional weights
    res1 = await mem_store.add_memory(
        "aligned emotional memory",
        wing="personal",
        importance=0.6,
        valence=0.5,
        emotion=0.8,
    )
    res2 = await mem_store.add_memory(
        "orthogonal emotional memory",
        wing="personal",
        importance=0.4,
        valence=-0.5,
        emotion=0.1,
    )

    assert res1 is True
    assert res2 is True

    # 4. Query with high arousal/cortisol matching row 1 (valence=0.5, emotion=0.8)
    results = await mem_store.search_memories(
        "query text",
        wing="personal",
        threshold=-10.0,
        limit=2,
        current_valence=0.5,
        current_arousal=0.8,
        current_cortisol=0.9,
    )

    assert len(results) == 2
    assert results[0]["content"] == "aligned emotional memory"

    # 5. Test ACT-R Pruning (< -2.0)
    # Mock some existing memory that was created long ago and has recall_count = 1
    # decay_rate = 0.8
    import uuid

    old_time = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    async with store.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO memories (id, content, importance_score, recall_count, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            str(uuid.uuid4()),
            "ancient forgotten memory",
            0.4,
            1,
            old_time,
            '{"decay_rate": 0.8}',
        )

    # Apply ACT-R decay pruning
    await mem_store.apply_actr_decay(
        ["ancient forgotten memory", "aligned emotional memory"]
    )

    # Verify that the ancient memory (activation = ln(1) - 0.8 * ln(240+1) = -4.38 < -3.5) was pruned/deleted
    async with store.pool.acquire() as conn:
        row_ancient = await conn.fetchrow(
            "SELECT * FROM memories WHERE content = 'ancient forgotten memory'"
        )
        row_recent = await conn.fetchrow(
            "SELECT * FROM memories WHERE content = 'aligned emotional memory'"
        )

        assert row_ancient is None
        assert row_recent is not None
        # Recent memory survived and was decayed by 0.8 (from 0.6 to 0.48)
        assert abs(row_recent["importance_score"] - 0.48) < 1e-5

    await store.close()
    await mem_store.close()


@pytest.mark.asyncio
async def test_dimensional_trust_matrix():
    """Verify deconstruction of AgentState trust field and dimensional updating."""
    # 1. Verify property alias and initialization
    state = AgentState(trust_benevolence=0.8, trust_competence=0.6, trust_integrity=0.4)
    # trust getter should return mathematical average
    assert abs(state.trust - 0.6) < 1e-5

    # trust setter: scalar writes propagate to all per-dimension fields
    state.trust = 0.7
    assert state.trust_benevolence == 0.7
    assert state.trust_competence == 0.7
    assert state.trust_integrity == 0.7

    # trust setter with sequence
    state.trust = (0.9, 0.7, 0.5)
    assert state.trust_benevolence == 0.9
    assert state.trust_competence == 0.7
    assert state.trust_integrity == 0.5

    # trust setter with dict
    state.trust = {"trust_benevolence": 0.3}
    assert state.trust_benevolence == 0.3
    assert state.trust_competence == 0.7
    assert state.trust_integrity == 0.5

    # 2. Verify independent update_from_appraisal logic
    # Mock StateService with local MockPGPool
    store = ConversationHistoryStore()
    await store.initialize()

    state_service = StateService()
    # Mock Neo4j persist
    state_service.persist_state = AsyncMock()

    appraisal = AppraisalVector(
        goal_congruence=0.8,  # affects Competence
        relationship_impact=0.6,  # affects Benevolence
        novelty=0.1,
        relevance=0.4,  # affects Competence
        agency=0.5,
        norm_alignment=-0.5,  # affects Integrity (downward impact)
    )

    # Initialize agent state to 0.5 across all dimensions
    state_service.current_state.trust_benevolence = 0.5
    state_service.current_state.trust_competence = 0.5
    state_service.current_state.trust_integrity = 0.5

    await state_service.update_from_appraisal(appraisal)

    # Tb should go up by delta (0.1) * RI (0.6) = +0.06 -> 0.56
    # Tc should go up by delta (0.1) * (0.6*G + 0.4*R) = 0.1 * (0.48 + 0.16) = +0.064 -> 0.564
    # Ti should go down/up by delta (0.1) * NA (-0.5) = -0.05 -> 0.45
    assert abs(state_service.current_state.trust_benevolence - 0.56) < 1e-5
    assert abs(state_service.current_state.trust_competence - 0.564) < 1e-5
    assert abs(state_service.current_state.trust_integrity - 0.45) < 1e-5

    await store.close()


@pytest.mark.asyncio
async def test_subconscious_agent_silence_check_and_24h_window():
    """Verify subconscious consolidation checks user silence and retrieves only within 24-hour window."""
    store = ConversationHistoryStore()
    await store.initialize()

    mock_graph = MagicMock()
    mock_graph.execute_query = AsyncMock(return_value=[])
    mem_store = MemoryStore(pool=store.pool, graph_db=mock_graph)
    mem_store.get_embedding = AsyncMock(return_value=[0.1] * 768)

    # 1. Log two messages: one very recent, one > 24 hours old
    recent_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    old_time = (datetime.utcnow() - timedelta(hours=36)).strftime("%Y-%m-%d %H:%M:%S")

    async with store.pool.acquire() as conn:
        # Create messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                consolidated INTEGER DEFAULT 0
            )
        """)
        await conn.execute(
            "INSERT INTO messages (id, role, content, timestamp, consolidated) VALUES ('msg1', 'user', 'Recent message', ?, 0)",
            recent_time,
        )
        await conn.execute(
            "INSERT INTO messages (id, role, content, timestamp, consolidated) VALUES ('msg2', 'user', 'Ancient message', ?, 0)",
            old_time,
        )

    # Verify that only 1 message (recent) is retrieved inside get_recent_unconsolidated_episodes
    episodes = await mem_store.get_recent_unconsolidated_episodes(limit=10)
    assert len(episodes) == 1
    assert episodes[0]["content"] == "Recent message"

    # 2. Test SubconsciousAgent 5-minute silence check
    state_service = StateService()
    ref_service = ReflectionService(
        llm_service=AsyncMock(), graph_store=MagicMock(), pg_vector=mem_store
    )

    agent = SubconsciousAgent(
        memory_store=mem_store,
        reflection_service=ref_service,
        graph_db=MagicMock(),
        state_service=state_service,
    )

    # Set user activity to very recent (0 seconds ago) and configure bypass=False
    state_service.current_state.last_user_interaction = time.time()
    orig_bypass = getattr(Config, "TESTING_CONSOLIDATION_BYPASS_SILENCE", True)
    try:
        Config.TESTING_CONSOLIDATION_BYPASS_SILENCE = False

        # Mock reflection trigger
        ref_service.trigger_reflection = AsyncMock()

        # Run system tick (should bypass consolidation because user was active recently)
        await agent._on_system_tick({"uptime": 1})
        ref_service.trigger_reflection.assert_not_called()

        # Now enable bypass
        Config.TESTING_CONSOLIDATION_BYPASS_SILENCE = True
        await agent._on_system_tick({"uptime": 2})
        ref_service.trigger_reflection.assert_called_once()
    finally:
        Config.TESTING_CONSOLIDATION_BYPASS_SILENCE = orig_bypass

    await store.close()
    await mem_store.close()


@pytest.mark.asyncio
async def test_dynamic_endocrine_temperature_modulation():
    """Verify ActionService modulates temperature and top_p independently based on cortisol and dopamine."""
    action_service = ActionService(llm_service=AsyncMock(), memory_store=AsyncMock())

    # 1. High Cortisol, Low Dopamine -> expect low temperature (rigid/defensive), standard top_p
    plan_stressed = ActionPlan(
        action_type="RESPOND_CHAT",
        payload={
            "message": "I feel extremely anxious.",
            "cortisol": 1.0,
            "dopamine": 0.0,
            "fatigue": 0.0,
        },
        goal="Help user",
    )

    # Mock LLM stream generator
    async def mock_generate_stream(*args, **kwargs):
        # Capture options override passed to LLM
        options = kwargs.get("options_override") or {}
        assert abs(options["temperature"] - 0.3) < 1e-5
        assert abs(options["top_p"] - 0.7) < 1e-5
        assert options["num_predict"] == 40
        yield "Stressed response"

    action_service.llm.generate_stream = mock_generate_stream

    async for _ in action_service.execute(plan_stressed):
        pass

    # 2. Low Cortisol, High Dopamine -> expect high temperature (relaxed/creative), high top_p
    plan_excited = ActionPlan(
        action_type="RESPOND_CHAT",
        payload={
            "message": "Let us brainstorm ideas!",
            "cortisol": 0.0,
            "dopamine": 1.0,
            "fatigue": 1.0,
        },
        goal="Brainstorm",
    )

    async def mock_generate_stream_excited(*args, **kwargs):
        options = kwargs.get("options_override") or {}
        assert abs(options["temperature"] - 0.9) < 1e-5
        assert abs(options["top_p"] - 0.95) < 1e-5
        assert options["num_predict"] == 15  # exhausted reply length
        yield "Excited reply"

    action_service.llm.generate_stream = mock_generate_stream_excited

    async for _ in action_service.execute(plan_excited):
        pass
