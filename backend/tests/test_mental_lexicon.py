"""Tests for the learned MentalLexicon that replaced the static SYNONYM_MAP.

The lexicon boots with a small generic innate seed and then acquires words +
co-occurrence associations from stored memories. These tests exercise seeding,
distributional learning, weight-ranked expansion, graceful cold start, the
pair-fan-out cap, the guard that keeps learning failures from breaking a memory
write, and the dialect-neutral SQL shape on the Postgres path.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.state.conversation_store import ConversationHistoryStore
from app.state.lexicon_store import MentalLexicon
from app.state.memory_store import MemoryStore


@pytest.fixture
async def sqlite_lexicon():
    store = ConversationHistoryStore()
    store.dsn = "sqlite:///:memory:"  # isolated per test; no shared app.db state
    await store.initialize()
    lex = MentalLexicon(store.pool)
    yield lex
    await store.close()


class TestInnateSeed:
    @pytest.mark.asyncio
    async def test_seed_present_and_expands_after_refresh(self, sqlite_lexicon):
        await sqlite_lexicon.refresh()
        async with sqlite_lexicon.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM vocabulary WHERE source = 'innate'"
            )
        assert int(count) > 0
        # "happy" is an innate cluster head; its cluster-mates must surface.
        associates = sqlite_lexicon.expand("happy")
        assert "glad" in associates or "joy" in associates

    @pytest.mark.asyncio
    async def test_seed_runs_only_once(self, sqlite_lexicon):
        await sqlite_lexicon.refresh()
        async with sqlite_lexicon.pool.acquire() as conn:
            first = await conn.fetchval("SELECT COUNT(*) FROM vocabulary")
        # A second ensure/refresh must not double-insert the seed.
        await sqlite_lexicon._seed_innate()
        async with sqlite_lexicon.pool.acquire() as conn:
            second = await conn.fetchval("SELECT COUNT(*) FROM vocabulary")
        assert int(first) == int(second)


class TestLearning:
    @pytest.mark.asyncio
    async def test_learn_upserts_vocab_and_increments_times_seen(self, sqlite_lexicon):
        await sqlite_lexicon.learn_from_text("rocket engine ignited")
        await sqlite_lexicon.learn_from_text("rocket engine ignited")
        async with sqlite_lexicon.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT times_seen, source FROM vocabulary WHERE term = 'rocket'"
            )
        assert row is not None
        assert int(row["times_seen"]) == 2
        assert row["source"] == "acquired"

    @pytest.mark.asyncio
    async def test_cooccurrence_is_reinforced_and_symmetric(self, sqlite_lexicon):
        await sqlite_lexicon.learn_from_text("quantum physics fascinating")
        await sqlite_lexicon.learn_from_text("quantum physics again")
        # Checked before any refresh(): refresh() now also decays (P2-5), so
        # this raw weight must be read before that side effect touches it.
        async with sqlite_lexicon.pool.acquire() as conn:
            weight = await conn.fetchval(
                "SELECT weight FROM lexical_associations "
                "WHERE term_a = 'physic' AND term_b = 'quantum'"
            )
        assert float(weight) == pytest.approx(2.0)

        # Fresh instance forces the association to come from the DB, not the
        # incrementally-updated in-memory cache.
        fresh = MentalLexicon(sqlite_lexicon.pool)
        await fresh.refresh()
        assert "physic" in fresh.expand("quantum")
        assert "quantum" in fresh.expand("physic")  # symmetric

    @pytest.mark.asyncio
    async def test_expand_ranks_by_weight(self, sqlite_lexicon):
        await sqlite_lexicon.learn_from_text("alpha beta")
        await sqlite_lexicon.learn_from_text("alpha beta")  # beta: weight 2
        await sqlite_lexicon.learn_from_text("alpha gamma")  # gamma: weight 1
        ranked = sqlite_lexicon.expand("alpha")
        assert ranked[0] == "beta"
        assert "gamma" in ranked

    @pytest.mark.asyncio
    async def test_unknown_cue_returns_empty(self, sqlite_lexicon):
        await sqlite_lexicon.refresh()
        assert sqlite_lexicon.expand("zzzznonexistentword") == []

    @pytest.mark.asyncio
    async def test_empty_cue_returns_empty(self, sqlite_lexicon):
        assert sqlite_lexicon.expand("") == []
        assert sqlite_lexicon.expand(None) == []

    def test_tokenize_caps_pair_fanout(self, sqlite_lexicon):
        # 20 distinct content words -> capped to _max_words_per_text so the
        # O(n^2) association fan-out per memory stays bounded.
        text = " ".join(f"word{i:02d}alpha" for i in range(20))
        tokens = sqlite_lexicon._tokenize(text)
        assert len(tokens) == sqlite_lexicon._max_words_per_text


class TestGuards:
    @pytest.mark.asyncio
    async def test_learn_never_raises_on_broken_pool(self):
        broken = MagicMock()
        broken.acquire.side_effect = RuntimeError("db down")
        lex = MentalLexicon(broken)
        # Must swallow and return None rather than propagate.
        assert await lex.learn_from_text("anything at all") is None


class TestPostgresDialect:
    @pytest.mark.asyncio
    async def test_learn_emits_placeholder_upserts(self):
        # No real Postgres: assert the dialect-neutral SQL shape (the same string
        # asyncpg would run, and the SQLite pool translates). On this path
        # (pool_is_sqlite -> False for a bare MagicMock) learn_from_text
        # batches through executemany (P2-5), not per-pair execute calls.
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        conn.fetchval.return_value = 5  # vocabulary already seeded -> skip seed

        lex = MentalLexicon(pool)
        await lex.learn_from_text("rocket engine")

        calls = [c.args[0] for c in conn.executemany.await_args_list]
        vocab_upserts = [s for s in calls if "INSERT INTO vocabulary" in s]
        assoc_upserts = [s for s in calls if "INSERT INTO lexical_associations" in s]
        assert vocab_upserts and all(
            "$1" in s and "ON CONFLICT" in s for s in vocab_upserts
        )
        assert assoc_upserts and all(
            "$1" in s and "$2" in s and "DO UPDATE" in s for s in assoc_upserts
        )


class TestAssociationLifecycle:
    """P2-5: lexical_associations had no decay and no cap -- every
    co-occurrence ever learned was retained and reinforced forever."""

    @pytest.mark.asyncio
    async def test_refresh_decays_every_associations_weight(self, sqlite_lexicon):
        await sqlite_lexicon.learn_from_text("alpha beta")
        async with sqlite_lexicon.pool.acquire() as conn:
            before = await conn.fetchval(
                "SELECT weight FROM lexical_associations "
                "WHERE term_a = 'alpha' AND term_b = 'beta'"
            )

        await sqlite_lexicon.refresh()

        async with sqlite_lexicon.pool.acquire() as conn:
            after = await conn.fetchval(
                "SELECT weight FROM lexical_associations "
                "WHERE term_a = 'alpha' AND term_b = 'beta'"
            )
        assert float(after) == pytest.approx(
            float(before) * sqlite_lexicon._assoc_decay_factor
        )

    @pytest.mark.asyncio
    async def test_decay_prunes_weights_that_fall_below_the_floor(self, sqlite_lexicon):
        await sqlite_lexicon._ensure_ready()
        async with sqlite_lexicon.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO lexical_associations (term_a, term_b, weight) "
                "VALUES ($1, $2, $3)",
                "zeta",
                "omega",
                0.05,
            )

        await sqlite_lexicon._decay_associations()

        async with sqlite_lexicon.pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT weight FROM lexical_associations "
                "WHERE term_a = 'zeta' AND term_b = 'omega'"
            )
        assert row is None, (
            "a weight already below the prune floor must be forgotten, not "
            "merely decayed further and left in the table forever"
        )


class TestBumpCacheGrowthCap:
    """P3-7: _load_cache() bounds the cache at load time, but _bump_cache
    could add brand-new pairs between reloads with no limit at all."""

    def test_new_pairs_are_capped_between_loads(self):
        lex = MentalLexicon(pool=MagicMock())
        lex._max_new_pairs_between_loads = 2

        lex._bump_cache("a", "b", 1.0)
        lex._bump_cache("a", "c", 1.0)
        lex._bump_cache("a", "d", 1.0)  # cap already reached -- must be dropped

        assert lex._new_pairs_since_load == 2
        assert "d" not in lex._assoc_cache.get("a", {})
        assert "b" in lex._assoc_cache.get("a", {})
        assert "c" in lex._assoc_cache.get("a", {})

    def test_reinforcing_an_already_cached_pair_is_never_capped(self):
        lex = MentalLexicon(pool=MagicMock())
        lex._max_new_pairs_between_loads = 1

        lex._bump_cache("a", "b", 1.0)  # uses up the one new-pair slot
        lex._bump_cache("a", "b", 1.0)  # not new -- must still apply

        assert lex._assoc_cache["a"]["b"] == pytest.approx(2.0)
        assert lex._new_pairs_since_load == 1


class TestMemoryStoreIntegration:
    @pytest.mark.asyncio
    async def test_add_memory_teaches_the_lexicon(self):
        store = ConversationHistoryStore()
        store.dsn = "sqlite:///:memory:"  # isolated per test
        await store.initialize()
        mock_graph = MagicMock()
        mock_graph.execute_query = AsyncMock(return_value=[])
        mem = MemoryStore(pool=store.pool, graph_db=mock_graph)
        mem.qdrant_store.client = None
        mem.get_embedding = AsyncMock(return_value=[0.1] * 768)
        try:
            # Two memories share "telescope"; the association must be learned.
            await mem.add_memory("bought a telescope yesterday", importance=0.5)
            await mem.add_memory("telescope shows distant galaxies", importance=0.5)
            # add_memory learns incrementally, so expand reflects it immediately.
            assert "galaxy" in mem.lexicon.expand("telescope") or "distant" in (
                mem.lexicon.expand("telescope")
            )
        finally:
            await store.close()
            await mem.close()
